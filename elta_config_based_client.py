#!/usr/bin/env python3
"""
ELTA Config-Based Client
========================
Based on the actual ELTA configuration files:

1. gdu_chl.xml: TcpServer 127.0.0.1:23004 -> sends to 127.0.0.1:32004
2. extapp_chl.xml: TcpServer 132.4.6.202:30080 -> sends to 132.4.6.205:22230

This client follows the exact network architecture specified in the configs.
"""

import socket
import struct
import threading
import time
from datetime import datetime
from elta_message_decoder import EltaMessageDecoder

class EltaConfigBasedClient:
    def __init__(self):
        # Network configuration from ELTA config files
        self.connections = {
            'main_tcp': {
                'type': 'tcp_client',
                'host': '127.0.0.1',      # gdu_chl.xml TcpServer
                'port': 23004,
                'description': 'Main GDU Control Channel'
            },
            'extapp_tcp': {
                'type': 'tcp_client', 
                'host': '132.4.6.202',    # extapp_chl.xml TcpServer
                'port': 30080,
                'description': 'External App Channel'
            },
            'target_data_udp': {
                'type': 'udp_server',
                'host': '127.0.0.1',      # gdu_chl.xml DefaultDestIp
                'port': 32004,
                'description': 'Target Data Reception'
            },
            'extapp_udp': {
                'type': 'udp_server',
                'host': '132.4.6.205',    # extapp_chl.xml DefaultDestIp
                'port': 22230,
                'description': 'External App Data Reception'
            }
        }
        
        self.sockets = {}
        self.running = False
        self.decoder = EltaMessageDecoder()
        
        # State management
        self.message_sequence = 1
        self.system_initialized = False
        
        # Statistics
        self.stats = {
            'tcp_connections': 0,
            'udp_listeners': 0,
            'messages_received': 0,
            'target_data_messages': 0,
            'system_control_sent': 0
        }
    
    def start_udp_listener(self, name, config):
        """Start UDP listener for data reception"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((config['host'], config['port']))
            sock.settimeout(5.0)
            
            self.sockets[name] = sock
            self.stats['udp_listeners'] += 1
            
            print(f"[{datetime.now()}] ✅ UDP {name} listening on {config['host']}:{config['port']}")
            print(f"   📋 {config['description']}")
            
            while self.running:
                try:
                    data, addr = sock.recvfrom(4096)
                    self.process_message(data, f"{name} from {addr}")
                    
                except socket.timeout:
                    continue
                except socket.error as e:
                    if self.running:
                        print(f"[{datetime.now()}] ❌ UDP {name} error: {e}")
                    break
                    
        except Exception as e:
            print(f"[{datetime.now()}] ❌ UDP {name} setup error: {e}")
        finally:
            if name in self.sockets:
                try:
                    self.sockets[name].close()
                except:
                    pass
                del self.sockets[name]
    
    def start_tcp_client(self, name, config):
        """Start TCP client connection"""
        while self.running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(10.0)
                
                print(f"[{datetime.now()}] 🔌 TCP {name} connecting to {config['host']}:{config['port']}")
                print(f"   📋 {config['description']}")
                
                sock.connect((config['host'], config['port']))
                
                self.sockets[name] = sock
                self.stats['tcp_connections'] += 1
                
                print(f"[{datetime.now()}] ✅ TCP {name} CONNECTED!")
                
                # Send initial system control after connection
                if name == 'main_tcp':
                    time.sleep(1)
                    self.send_system_control_standby(sock)
                
                # Listen for messages
                buffer = b''
                while self.running:
                    try:
                        data = sock.recv(4096)
                        if not data:
                            print(f"[{datetime.now()}] TCP {name} closed by server")
                            break
                        
                        buffer += data
                        buffer = self.process_tcp_buffer(buffer, f"TCP {name}")
                        
                    except socket.timeout:
                        continue
                    except socket.error as e:
                        print(f"[{datetime.now()}] TCP {name} error: {e}")
                        break
                        
            except Exception as e:
                if self.running:
                    print(f"[{datetime.now()}] TCP {name} connection error: {e}")
                    time.sleep(5)  # Wait before retry
            finally:
                if name in self.sockets:
                    try:
                        self.sockets[name].close()
                    except:
                        pass
                    del self.sockets[name]
    
    def process_tcp_buffer(self, buffer, source):
        """Process TCP message buffer"""
        while len(buffer) >= 20:
            try:
                source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', buffer[:20])
                
                if len(buffer) >= msg_length:
                    message = buffer[:msg_length]
                    buffer = buffer[msg_length:]
                    
                    self.process_message(message, source)
                else:
                    break
                    
            except struct.error:
                buffer = buffer[1:]
                continue
                
        return buffer
    
    def process_message(self, data, source):
        """Process received message"""
        self.stats['messages_received'] += 1
        
        print(f"\n[{datetime.now()}] 📨 MESSAGE from {source}")
        print(f"Length: {len(data)} bytes")
        print(f"Raw: {data.hex().upper()}")
        
        try:
            if len(data) >= 20:
                source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', data[:20])
                
                print(f"Header: SRC=0x{source_id:08X} MSG=0x{msg_id:08X} LEN={msg_length} SEQ={seq_num}")
                
                # Handle specific message types
                if msg_id == 0xCEF00403:  # System Status
                    print("📊 SYSTEM STATUS - Consider sending acknowledge")
                    
                elif msg_id in [0xCEF00404, 0xCEF00406, 0xCEF0041A]:  # Target data
                    self.stats['target_data_messages'] += 1
                    print(f"🎯🎯🎯 TARGET DATA MESSAGE! (Total: {self.stats['target_data_messages']}) 🎯🎯🎯")
                    
                elif msg_id == 0xCEF00400:  # Keep Alive
                    print("💓 KEEP ALIVE - No response needed in config-based mode")
                
                # Decode message
                decoded = self.decoder.decode_message(data)
                print(decoded)
                
        except Exception as e:
            print(f"Error processing: {e}")
        
        print("-" * 80)
    
    def send_system_control_standby(self, sock):
        """Send System Control STANDBY command"""
        try:
            print(f"[{datetime.now()}] 📤 Sending SYSTEM CONTROL (STANDBY)")
            
            # Use a safe source_id that won't conflict
            source_id = 0x1000        # Simple, non-conflicting ID
            msg_id = 0xCEF00401       # System Control
            msg_length = 60           # ICD specified length
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = self.message_sequence
            self.message_sequence += 1
            
            # System Control payload - STANDBY first
            rdr_state = 2             # STANDBY state
            mission_category = 0      # Default
            controls = b'\x00' * 8    # Control bytes
            freq_index = 1            # Frequency
            spare = b'\x00' * 20      # Spare
            
            payload = struct.pack('<II', rdr_state, mission_category) + controls + struct.pack('<I', freq_index) + spare
            message = struct.pack('<IIIII', source_id, msg_id, msg_length, time_tag, seq_num) + payload
            
            print(f"Message: {message.hex().upper()}")
            sock.send(message)
            
            self.stats['system_control_sent'] += 1
            print(f"[{datetime.now()}] ✅ SYSTEM CONTROL (STANDBY) sent")
            
        except Exception as e:
            print(f"[{datetime.now()}] ❌ System Control error: {e}")
    
    def print_statistics(self):
        """Print current statistics"""
        print(f"\n📊 CONFIG-BASED CLIENT STATISTICS:")
        print("=" * 50)
        print(f"TCP Connections:         {self.stats['tcp_connections']}")
        print(f"UDP Listeners:           {self.stats['udp_listeners']}")
        print(f"Messages Received:       {self.stats['messages_received']}")
        print(f"🎯 Target Data Messages: {self.stats['target_data_messages']} 🎯")
        print(f"System Control Sent:     {self.stats['system_control_sent']}")
        print(f"Active Connections:      {len(self.sockets)}")
        print("=" * 50)
    
    def start(self):
        """Start the config-based client"""
        self.running = True
        
        print("🚀 ELTA Config-Based Client")
        print("=" * 60)
        print("Based on actual ELTA configuration files:")
        print("📋 gdu_chl.xml: 127.0.0.1:23004 -> 127.0.0.1:32004")
        print("📋 extapp_chl.xml: 132.4.6.202:30080 -> 132.4.6.205:22230")
        print("=" * 60)
        
        threads = []
        
        # Start connections based on config
        for name, config in self.connections.items():
            if config['type'] == 'udp_server':
                thread = threading.Thread(target=self.start_udp_listener, args=(name, config))
            elif config['type'] == 'tcp_client':
                thread = threading.Thread(target=self.start_tcp_client, args=(name, config))
            
            thread.daemon = True
            thread.start()
            threads.append(thread)
            time.sleep(1)  # Stagger starts
        
        try:
            while self.running:
                time.sleep(10)
                self.print_statistics()
        except KeyboardInterrupt:
            print(f"\n[{datetime.now()}] 🛑 Stopping...")
            self.running = False
        
        self.print_statistics()
        print(f"[{datetime.now()}] ✅ Stopped")

if __name__ == "__main__":
    client = EltaConfigBasedClient()
    client.start()