#!/usr/bin/env python3
"""
ELTA Keep-Alive Connection Client
================================
New strategy: Maintain a persistent TCP connection with minimal keep-alive messages
to keep the data channel open, while listening on UDP ports for actual data.

This approach:
1. Establishes TCP connection to 127.0.0.1:23004
2. Sends System Control OPERATE once
3. Maintains connection with periodic keep-alive messages
4. Listens on UDP ports for target data

The key insight: The simulator might need an active TCP connection to send UDP data.
"""

import socket
import struct
import threading
import time
from datetime import datetime
from elta_message_decoder import EltaMessageDecoder

class EltaKeepAliveClient:
    def __init__(self):
        # Network configuration
        self.tcp_server = {
            'host': '127.0.0.1',
            'port': 23004,
            'description': 'Main GDU Control Channel'
        }
        
        self.udp_listeners = {
            'main_target_data': {
                'host': '127.0.0.1',
                'port': 32004,
                'description': 'Main Target Data Reception'
            },
            'extapp_data': {
                'host': '132.4.6.205',
                'port': 22230,
                'description': 'External App Data Reception'
            }
        }
        
        self.tcp_socket = None
        self.udp_sockets = {}
        self.running = False
        self.decoder = EltaMessageDecoder()
        
        # State tracking
        self.system_control_sent = False
        self.keep_alive_count = 0
        self.last_keep_alive = time.time()
        
        # Statistics
        self.stats = {
            'system_control_sent': 0,
            'keep_alive_sent': 0,
            'tcp_messages_received': 0,
            'udp_messages_received': 0,
            'target_messages': 0,
            'connection_duration': 0
        }
    
    def maintain_tcp_connection(self):
        """Maintain persistent TCP connection with keep-alive messages"""
        connection_start = time.time()
        
        while self.running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                
                print(f"[{datetime.now()}] 🔌 Establishing persistent TCP connection...")
                sock.connect((self.tcp_server['host'], self.tcp_server['port']))
                
                self.tcp_socket = sock
                print(f"[{datetime.now()}] ✅ Persistent TCP connection established!")
                
                # Send initial System Control OPERATE
                if not self.system_control_sent:
                    time.sleep(1)
                    self.send_system_control_operate(sock)
                    self.system_control_sent = True
                
                # Maintain connection with periodic keep-alives and message listening
                buffer = b''
                last_keep_alive = time.time()
                
                while self.running:
                    try:
                        # Check if we need to send keep-alive
                        current_time = time.time()
                        if current_time - last_keep_alive > 10:  # Every 10 seconds
                            self.send_keep_alive(sock)
                            last_keep_alive = current_time
                        
                        # Listen for incoming messages
                        sock.settimeout(1.0)
                        data = sock.recv(4096)
                        
                        if not data:
                            print(f"[{datetime.now()}] TCP connection closed by server")
                            break
                        
                        buffer += data
                        buffer = self.process_tcp_buffer(buffer)
                        
                    except socket.timeout:
                        # Timeout is normal for keep-alive timing
                        continue
                    except socket.error as e:
                        print(f"[{datetime.now()}] TCP connection error: {e}")
                        break
                
                self.stats['connection_duration'] = time.time() - connection_start
                
            except Exception as e:
                if self.running:
                    print(f"[{datetime.now()}] TCP connection failed: {e}")
                    print(f"[{datetime.now()}] ⏳ Retrying in 5 seconds...")
                    time.sleep(5)
            finally:
                if self.tcp_socket:
                    try:
                        self.tcp_socket.close()
                    except:
                        pass
                    self.tcp_socket = None
    
    def send_system_control_operate(self, sock):
        """Send System Control OPERATE message"""
        try:
            print(f"[{datetime.now()}] 📤 Sending System Control OPERATE...")
            
            source_id = 0x0001        # Safe minimal ID
            msg_id = 0xCEF00401       # System Control
            msg_length = 60
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = 1
            
            # OPERATE state payload
            rdr_state = 4             # OPERATE
            mission_category = 0
            controls = b'\x00' * 8
            freq_index = 1
            spare = b'\x00' * 20
            
            payload = struct.pack('<II', rdr_state, mission_category) + controls + struct.pack('<I', freq_index) + spare
            message = struct.pack('<IIIII', source_id, msg_id, msg_length, time_tag, seq_num) + payload
            
            sock.send(message)
            self.stats['system_control_sent'] += 1
            print(f"[{datetime.now()}] ✅ System Control OPERATE sent!")
            
        except Exception as e:
            print(f"[{datetime.now()}] ❌ System Control error: {e}")
    
    def send_keep_alive(self, sock):
        """Send Keep Alive message to maintain connection"""
        try:
            source_id = 0x0001
            msg_id = 0xCEF00400       # Keep Alive
            msg_length = 20
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = self.keep_alive_count + 1
            
            message = struct.pack('<IIIII', source_id, msg_id, msg_length, time_tag, seq_num)
            
            sock.send(message)
            self.keep_alive_count += 1
            self.stats['keep_alive_sent'] += 1
            
            if self.keep_alive_count % 5 == 0:  # Log every 5th keep-alive
                print(f"[{datetime.now()}] 💓 Keep Alive #{self.keep_alive_count} sent")
            
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Keep Alive error: {e}")
    
    def process_tcp_buffer(self, buffer):
        """Process TCP message buffer"""
        while len(buffer) >= 20:
            try:
                source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', buffer[:20])
                
                if len(buffer) >= msg_length:
                    message = buffer[:msg_length]
                    buffer = buffer[msg_length:]
                    
                    print(f"\n[{datetime.now()}] 📨 TCP MESSAGE received")
                    print(f"Header: SRC=0x{source_id:08X} MSG=0x{msg_id:08X} LEN={msg_length}")
                    
                    self.stats['tcp_messages_received'] += 1
                    
                    # Decode message
                    decoded = self.decoder.decode_message(message)
                    print(decoded)
                    print("-" * 60)
                else:
                    break
                    
            except struct.error:
                buffer = buffer[1:]
                continue
                
        return buffer
    
    def start_udp_listener(self, name, config):
        """Start UDP listener for data reception"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((config['host'], config['port']))
            sock.settimeout(10.0)
            
            self.udp_sockets[name] = sock
            
            print(f"[{datetime.now()}] ✅ UDP {name} active on {config['host']}:{config['port']}")
            print(f"   📋 {config['description']}")
            
            while self.running:
                try:
                    data, addr = sock.recvfrom(4096)
                    
                    print(f"\n[{datetime.now()}] 🎉 UDP DATA RECEIVED on {name}!")
                    print(f"📨 From: {addr}")
                    print(f"📏 Length: {len(data)} bytes")
                    
                    self.stats['udp_messages_received'] += 1
                    self.process_udp_message(data, addr, name)
                    
                except socket.timeout:
                    continue
                except socket.error as e:
                    if self.running:
                        print(f"[{datetime.now()}] ❌ UDP {name} error: {e}")
                    break
                    
        except Exception as e:
            print(f"[{datetime.now()}] ❌ UDP {name} setup error: {e}")
        finally:
            if name in self.udp_sockets:
                try:
                    self.udp_sockets[name].close()
                except:
                    pass
                del self.udp_sockets[name]
    
    def process_udp_message(self, data, addr, listener_name):
        """Process received UDP message"""
        try:
            if len(data) >= 20:
                source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', data[:20])
                
                print(f"📋 ELTA HEADER:")
                print(f"   Source ID:   0x{source_id:08X}")
                print(f"   Message ID:  0x{msg_id:08X}")
                print(f"   Length:      {msg_length}")
                print(f"   Sequence:    {seq_num}")
                
                # Check for target data
                if msg_id in [0xCEF00404, 0xCEF00406, 0xCEF0041A]:
                    self.stats['target_messages'] += 1
                    print(f"🎯🎯🎯 TARGET DATA MESSAGE! (Total: {self.stats['target_messages']}) 🎯🎯🎯")
                
                # Decode message
                decoded = self.decoder.decode_message(data)
                print(decoded)
                
        except Exception as e:
            print(f"❌ Error processing UDP message: {e}")
        
        print("=" * 80)
    
    def print_statistics(self):
        """Print current statistics"""
        print(f"\n📊 KEEP-ALIVE CLIENT STATISTICS:")
        print("=" * 60)
        print(f"System Control Sent:     {self.stats['system_control_sent']}")
        print(f"Keep Alive Messages:     {self.stats['keep_alive_sent']}")
        print(f"TCP Messages Received:   {self.stats['tcp_messages_received']}")
        print(f"UDP Messages Received:   {self.stats['udp_messages_received']}")
        print(f"🎯 Target Data Messages: {self.stats['target_messages']} 🎯")
        print(f"Connection Active:       {'✅ Yes' if self.tcp_socket else '❌ No'}")
        print(f"Connection Duration:     {self.stats['connection_duration']:.1f}s")
        print("=" * 60)
    
    def start(self):
        """Start keep-alive client"""
        self.running = True
        
        print("🚀 ELTA KEEP-ALIVE CONNECTION CLIENT")
        print("=" * 70)
        print("🔗 Strategy: Persistent TCP connection + Keep-alive messages")
        print("📡 UDP listeners for target data reception")
        print("💓 Maintain connection to keep data channel open")
        print("=" * 70)
        
        # Start UDP listeners
        for name, config in self.udp_listeners.items():
            thread = threading.Thread(target=self.start_udp_listener, args=(name, config))
            thread.daemon = True
            thread.start()
            time.sleep(1)
        
        # Start TCP connection maintenance
        tcp_thread = threading.Thread(target=self.maintain_tcp_connection)
        tcp_thread.daemon = True
        tcp_thread.start()
        
        print(f"\n[{datetime.now()}] 🚀 All connections started!")
        
        try:
            while self.running:
                time.sleep(20)  # Print stats every 20 seconds
                self.print_statistics()
                
        except KeyboardInterrupt:
            print(f"\n[{datetime.now()}] 🛑 Stopping...")
            self.running = False
        
        self.print_statistics()
        print(f"[{datetime.now()}] ✅ Stopped")

if __name__ == "__main__":
    client = EltaKeepAliveClient()
    client.start()