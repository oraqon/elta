#!/usr/bin/env python3
"""
ELTA Pure Config-Based Listeners
================================
Based on ELTA configuration files, this creates ONLY UDP listeners
on the ports where the simulator sends data:

1. 127.0.0.1:32004 - Target data from gdu_chl.xml
2. 132.4.6.205:22230 - External app data from extapp_chl.xml

NO TCP connections = NO simulator crashes!
"""

import socket
import struct
import threading
import time
from datetime import datetime
from elta_message_decoder import EltaMessageDecoder

class EltaPureConfigListeners:
    def __init__(self):
        # Listening ports based on ELTA config files
        self.listeners = {
            'target_data': {
                'host': '127.0.0.1',     # gdu_chl.xml DefaultDestIp
                'port': 32004,           # gdu_chl.xml DefaultDestPort
                'description': 'Main Target Data (gdu_chl.xml)',
                'expected_data': 'TARGET_REPORT, SINGLE_TARGET, SENSOR_POSITION'
            },
            'extapp_data': {
                'host': '132.4.6.205',   # extapp_chl.xml DefaultDestIp  
                'port': 22230,           # extapp_chl.xml DefaultDestPort
                'description': 'External App Data (extapp_chl.xml)',
                'expected_data': 'External application messages'
            }
        }
        
        self.sockets = {}
        self.running = False
        self.decoder = EltaMessageDecoder()
        
        # Statistics per listener
        self.stats = {
            'target_data': {'messages': 0, 'bytes': 0, 'target_messages': 0},
            'extapp_data': {'messages': 0, 'bytes': 0, 'target_messages': 0},
            'total_messages': 0,
            'total_target_messages': 0
        }
    
    def start_listener(self, name, config):
        """Start UDP listener for specific port"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            print(f"[{datetime.now()}] 🔧 Binding {name} to {config['host']}:{config['port']}")
            sock.bind((config['host'], config['port']))
            sock.settimeout(10.0)
            
            self.sockets[name] = sock
            
            print(f"[{datetime.now()}] ✅ {name.upper()} LISTENER ACTIVE")
            print(f"   📍 Address: {config['host']}:{config['port']}")
            print(f"   📋 Purpose: {config['description']}")
            print(f"   🎯 Expected: {config['expected_data']}")
            print("-" * 60)
            
            message_count = 0
            
            while self.running:
                try:
                    data, addr = sock.recvfrom(4096)
                    message_count += 1
                    
                    print(f"\n[{datetime.now()}] 🎉 DATA RECEIVED on {name.upper()}!")
                    print(f"📨 Message #{message_count} from {addr}")
                    print(f"📏 Length: {len(data)} bytes")
                    print(f"🔢 Raw: {data.hex().upper()}")
                    
                    # Update statistics
                    self.stats[name]['messages'] += 1
                    self.stats[name]['bytes'] += len(data)
                    self.stats['total_messages'] += 1
                    
                    # Process the message
                    self.process_message(data, addr, name)
                    
                except socket.timeout:
                    # Periodic status update
                    if message_count == 0:
                        print(f"[{datetime.now()}] ⏰ {name.upper()} waiting... (No messages yet)")
                    else:
                        print(f"[{datetime.now()}] ⏰ {name.upper()} waiting... ({message_count} messages received)")
                    continue
                    
                except socket.error as e:
                    if self.running:
                        print(f"[{datetime.now()}] ❌ {name.upper()} error: {e}")
                    break
                    
        except Exception as e:
            print(f"[{datetime.now()}] ❌ {name.upper()} setup error: {e}")
        finally:
            if name in self.sockets:
                try:
                    self.sockets[name].close()
                except:
                    pass
                del self.sockets[name]
            print(f"[{datetime.now()}] 🔚 {name.upper()} listener stopped")
    
    def process_message(self, data, addr, listener_name):
        """Process received ELTA message"""
        try:
            if len(data) >= 20:
                # Parse ELTA header
                source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', data[:20])
                
                print(f"📋 ELTA HEADER ANALYSIS:")
                print(f"   Source ID:   0x{source_id:08X} ({source_id})")
                print(f"   Message ID:  0x{msg_id:08X} ({msg_id})")
                print(f"   Length:      {msg_length} bytes")
                print(f"   Time Tag:    {time_tag}")
                print(f"   Sequence:    {seq_num}")
                
                # Identify message type
                is_target_data = False
                if msg_id == 0xCEF00404:  # Target Report
                    print("🎯🎯🎯 TARGET REPORT MESSAGE! 🎯🎯🎯")
                    is_target_data = True
                elif msg_id == 0xCEF00406:  # Single Target Report
                    print("🎯 SINGLE TARGET REPORT MESSAGE! 🎯") 
                    is_target_data = True
                elif msg_id == 0xCEF0041A:  # Sensor Position
                    print("📍 SENSOR POSITION MESSAGE! 📍")
                    is_target_data = True
                elif msg_id == 0xCEF00403:  # System Status
                    print("📊 SYSTEM STATUS MESSAGE")
                elif msg_id == 0xCEF00400:  # Keep Alive
                    print("💓 KEEP ALIVE MESSAGE")
                else:
                    print(f"❓ UNKNOWN MESSAGE TYPE: 0x{msg_id:08X}")
                
                if is_target_data:
                    self.stats[listener_name]['target_messages'] += 1
                    self.stats['total_target_messages'] += 1
                    print(f"🎊 TARGET DATA COUNT: {self.stats['total_target_messages']} TOTAL!")
                
                # Decode message using our decoder
                print(f"\n📖 DETAILED DECODING:")
                decoded = self.decoder.decode_message(data)
                print(decoded)
                
            else:
                print("⚠️  Message too short for ELTA header")
                
        except Exception as e:
            print(f"❌ Error processing message: {e}")
        
        print("=" * 80)
    
    def print_statistics(self):
        """Print comprehensive statistics"""
        print(f"\n📊 PURE LISTENERS STATISTICS:")
        print("=" * 60)
        print(f"Total Messages Received:     {self.stats['total_messages']}")
        print(f"🎯 Total Target Data:        {self.stats['total_target_messages']} 🎯")
        print()
        
        for name, config in self.listeners.items():
            stats = self.stats[name]
            print(f"{name.upper()} ({config['host']}:{config['port']}):")
            print(f"   Messages: {stats['messages']}")
            print(f"   Target Data: {stats['target_messages']}")  
            print(f"   Bytes: {stats['bytes']}")
            print()
        
        print(f"Active Listeners: {len(self.sockets)}")
        print("=" * 60)
    
    def start(self):
        """Start all pure UDP listeners"""
        self.running = True
        
        print("🎯 ELTA PURE CONFIG-BASED LISTENERS")
        print("=" * 70)
        print("🔒 SAFE MODE: Only UDP listeners - No TCP connections")
        print("📋 Based on actual ELTA configuration files:")
        print("   • gdu_chl.xml: Target data → 127.0.0.1:32004")
        print("   • extapp_chl.xml: External data → 132.4.6.205:22230")
        print("=" * 70)
        
        # Start all listeners in separate threads
        threads = []
        for name, config in self.listeners.items():
            thread = threading.Thread(target=self.start_listener, args=(name, config))
            thread.daemon = True
            thread.start()
            threads.append(thread)
            time.sleep(1)  # Stagger starts
        
        print(f"\n[{datetime.now()}] 🚀 All listeners started - Waiting for ELTA data...")
        
        try:
            while self.running:
                time.sleep(30)  # Print stats every 30 seconds
                self.print_statistics()
        except KeyboardInterrupt:
            print(f"\n[{datetime.now()}] 🛑 Stopping all listeners...")
            self.running = False
        
        # Wait for threads to finish
        for thread in threads:
            thread.join(timeout=2)
        
        self.print_statistics()
        print(f"[{datetime.now()}] ✅ All listeners stopped")

if __name__ == "__main__":
    try:
        listeners = EltaPureConfigListeners()
        listeners.start()
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Fatal error: {e}")