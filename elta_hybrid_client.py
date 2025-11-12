#!/usr/bin/env python3
"""
ELTA Hybrid Approach - Minimal TCP + UDP Listeners
==================================================
Based on the config files and the successful OPERATE state transition:

1. Make minimal TCP connections to trigger data flow (but don't send messages)
2. Keep UDP listeners active to receive the actual data
3. Use safe connection approach to avoid simulator crashes

This should trigger the simulator to start sending data to our UDP listeners.
"""

import socket
import struct
import threading
import time
from datetime import datetime
from elta_message_decoder import EltaMessageDecoder

class EltaHybridClient:
    def __init__(self):
        # Based on ELTA config files
        self.tcp_servers = {
            'gdu_main': {
                'host': '127.0.0.1',      # gdu_chl.xml TcpServer
                'port': 23004,
                'sends_to': '127.0.0.1:32004',
                'description': 'Main GDU TCP Server'
            },
            'extapp': {
                'host': '132.4.6.202',    # extapp_chl.xml TcpServer
                'port': 30080, 
                'sends_to': '132.4.6.205:22230',
                'description': 'External App TCP Server'
            }
        }
        
        self.udp_listeners = {
            'target_data': {
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
        
        self.tcp_sockets = {}
        self.udp_sockets = {}
        self.running = False
        self.decoder = EltaMessageDecoder()
        
        # Statistics
        self.stats = {
            'tcp_connections': 0,
            'udp_messages': 0,
            'target_messages': 0,
            'tcp_messages': 0
        }
    
    def start_udp_listener(self, name, config):
        """Start UDP listener for data reception"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((config['host'], config['port']))
            sock.settimeout(10.0)
            
            self.udp_sockets[name] = sock
            
            print(f"[{datetime.now()}] ✅ UDP {name} listening on {config['host']}:{config['port']}")
            print(f"   📋 {config['description']}")
            
            while self.running:
                try:
                    data, addr = sock.recvfrom(4096)
                    
                    print(f"\n[{datetime.now()}] 🎉 UDP DATA RECEIVED on {name}!")
                    print(f"📨 From: {addr}")
                    print(f"📏 Length: {len(data)} bytes")
                    
                    self.stats['udp_messages'] += 1
                    self.process_message(data, f"UDP {name} from {addr}")
                    
                except socket.timeout:
                    # Reduce spam - only log every 5th timeout for each listener
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
    
    def start_minimal_tcp_client(self, name, config):
        """Start minimal TCP client - connect but don't send messages"""
        while self.running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(15.0)
                
                print(f"[{datetime.now()}] 🔌 TCP {name} connecting to {config['host']}:{config['port']}")
                print(f"   📋 {config['description']}")
                print(f"   🎯 Should trigger data flow to: {config['sends_to']}")
                
                sock.connect((config['host'], config['port']))
                
                self.tcp_sockets[name] = sock
                self.stats['tcp_connections'] += 1
                
                print(f"[{datetime.now()}] ✅ TCP {name} CONNECTED!")
                print(f"   🔇 PASSIVE MODE - Not sending any messages to avoid crashes")
                
                # Just listen for any incoming messages without sending anything
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
                        # Connection is alive, just no data
                        continue
                    except socket.error as e:
                        print(f"[{datetime.now()}] TCP {name} error: {e}")
                        break
                        
            except Exception as e:
                if self.running:
                    print(f"[{datetime.now()}] TCP {name} connection error: {e}")
                    print(f"   ⏳ Retrying in 10 seconds...")
                    time.sleep(10)
                else:
                    break
            finally:
                if name in self.tcp_sockets:
                    try:
                        self.tcp_sockets[name].close()
                    except:
                        pass
                    del self.tcp_sockets[name]
    
    def process_tcp_buffer(self, buffer, source):
        """Process TCP message buffer"""
        while len(buffer) >= 20:
            try:
                source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', buffer[:20])
                
                if len(buffer) >= msg_length:
                    message = buffer[:msg_length]
                    buffer = buffer[msg_length:]
                    
                    self.stats['tcp_messages'] += 1
                    self.process_message(message, source)
                else:
                    break
                    
            except struct.error:
                buffer = buffer[1:]
                continue
                
        return buffer
    
    def process_message(self, data, source):
        """Process received message"""
        print(f"\n[{datetime.now()}] 📨 MESSAGE from {source}")
        print(f"Length: {len(data)} bytes")
        print(f"Raw: {data[:40].hex().upper()}{'...' if len(data) > 40 else ''}")
        
        try:
            if len(data) >= 20:
                source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', data[:20])
                
                print(f"Header: SRC=0x{source_id:08X} MSG=0x{msg_id:08X} LEN={msg_length} SEQ={seq_num}")
                
                # Identify message type
                if msg_id in [0xCEF00404, 0xCEF00406, 0xCEF0041A]:
                    self.stats['target_messages'] += 1
                    print(f"🎯🎯🎯 TARGET DATA MESSAGE! (Total: {self.stats['target_messages']}) 🎯🎯🎯")
                    
                    if msg_id == 0xCEF00404:
                        print("📊 TARGET REPORT - Multiple targets!")
                    elif msg_id == 0xCEF00406:
                        print("🎯 SINGLE TARGET REPORT - Individual target!")
                    elif msg_id == 0xCEF0041A:
                        print("📍 SENSOR POSITION - Radar position!")
                        
                elif msg_id == 0xCEF00403:
                    print("📊 SYSTEM STATUS MESSAGE")
                elif msg_id == 0xCEF00400:
                    print("💓 KEEP ALIVE MESSAGE")
                else:
                    print(f"❓ MESSAGE TYPE: 0x{msg_id:08X}")
                
                # Decode message
                decoded = self.decoder.decode_message(data)
                print(decoded)
                
        except Exception as e:
            print(f"Error processing: {e}")
        
        print("-" * 80)
    
    def print_statistics(self):
        """Print current statistics"""
        print(f"\n📊 HYBRID CLIENT STATISTICS:")
        print("=" * 50)
        print(f"TCP Connections:         {self.stats['tcp_connections']}")
        print(f"TCP Messages Received:   {self.stats['tcp_messages']}")
        print(f"UDP Messages Received:   {self.stats['udp_messages']}")
        print(f"🎯 Target Data Messages: {self.stats['target_messages']} 🎯")
        print(f"Active TCP Sockets:      {len(self.tcp_sockets)}")
        print(f"Active UDP Sockets:      {len(self.udp_sockets)}")
        print("=" * 50)
    
    def start(self):
        """Start hybrid client"""
        self.running = True
        
        print("🚀 ELTA HYBRID CLIENT")
        print("=" * 60)
        print("🔧 Strategy: Minimal TCP connections + UDP listeners")
        print("📋 TCP connections to trigger data flow (passive mode)")
        print("📡 UDP listeners for actual data reception")
        print("🔒 No messages sent to avoid simulator crashes")
        print("=" * 60)
        
        # Start UDP listeners first
        for name, config in self.udp_listeners.items():
            thread = threading.Thread(target=self.start_udp_listener, args=(name, config))
            thread.daemon = True
            thread.start()
            time.sleep(1)
        
        # Start minimal TCP clients
        for name, config in self.tcp_servers.items():
            thread = threading.Thread(target=self.start_minimal_tcp_client, args=(name, config))
            thread.daemon = True
            thread.start()
            time.sleep(2)  # Longer delay between TCP connections
        
        print(f"\n[{datetime.now()}] 🚀 All connections started - Looking for target data...")
        
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
    client = EltaHybridClient()
    client.start()