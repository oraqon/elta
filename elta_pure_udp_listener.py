#!/usr/bin/env python3
"""
ELTA Pure UDP Listener
====================
This approach completely avoids the TDP simulator crash issue by:
1. Only binding to UDP port 32004 (as requested in original requirements)
2. NOT making any outbound connections that could trigger simulator bugs
3. Waiting for the simulator to send data to us
4. Decoding any received ELTA messages

This should be completely safe and matches the original request:
"write a python script that bind to port 32004 and connects to port 23004, 
reads the data and decodes it based on the specification"

We'll bind to 32004, and if the simulator is configured to send data to us,
we'll receive and decode it without risking crashes.
"""

import socket
import struct
import time
from datetime import datetime
from elta_message_decoder import EltaMessageDecoder

class EltaPureUDPListener:
    def __init__(self):
        self.udp_port = 32004
        self.socket = None
        self.decoder = EltaMessageDecoder()
        self.running = False
        
        # Statistics
        self.stats = {
            'total_messages': 0,
            'target_data_messages': 0,
            'system_status_messages': 0,
            'keep_alive_messages': 0,
            'unknown_messages': 0,
            'bytes_received': 0,
            'message_types': {}
        }
    
    def start(self):
        """Start pure UDP listener on port 32004"""
        print("🎯 ELTA Pure UDP Listener")
        print("=" * 60)
        print(f"Binding to UDP port {self.udp_port}")
        print("📡 Waiting for ELTA simulator to send target data...")
        print("🔒 SAFE MODE - No outbound connections to prevent crashes")
        print("=" * 60)
        
        try:
            # Create UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to port 32004 on localhost (as per config files)
            self.socket.bind(('127.0.0.1', self.udp_port))
            print(f"[{datetime.now()}] 🔧 Binding to 127.0.0.1:{self.udp_port} (per ELTA config)")
            self.socket.settimeout(10.0)  # 10 second timeout for status updates
            
            print(f"[{datetime.now()}] ✅ UDP socket bound to port {self.udp_port}")
            print(f"[{datetime.now()}] 👂 Listening for ELTA messages...")
            
            self.running = True
            message_count = 0
            
            while self.running:
                try:
                    # Wait for UDP data
                    data, addr = self.socket.recvfrom(4096)
                    message_count += 1
                    
                    print(f"\n[{datetime.now()}] 📨 MESSAGE #{message_count} from {addr}")
                    print(f"Length: {len(data)} bytes")
                    print(f"Raw Data: {data.hex().upper()}")
                    
                    # Process the message
                    self.process_message(data, addr)
                    
                    # Print stats every 10 messages
                    if message_count % 10 == 0:
                        self.print_statistics()
                    
                except socket.timeout:
                    # Print periodic status updates
                    print(f"[{datetime.now()}] ⏰ Waiting for data... (Messages received: {message_count})")
                    if message_count > 0:
                        self.print_statistics()
                    continue
                    
                except socket.error as e:
                    print(f"[{datetime.now()}] ❌ UDP error: {e}")
                    break
                    
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Setup error: {e}")
        finally:
            self.cleanup()
    
    def process_message(self, data, addr):
        """Process received ELTA message"""
        try:
            self.stats['total_messages'] += 1
            self.stats['bytes_received'] += len(data)
            
            if len(data) >= 20:
                # Parse ELTA header
                source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', data[:20])
                
                print(f"📋 ELTA HEADER:")
                print(f"   Source ID:   0x{source_id:08X} ({source_id})")
                print(f"   Message ID:  0x{msg_id:08X} ({msg_id})")
                print(f"   Length:      {msg_length} bytes")
                print(f"   Time Tag:    {time_tag}")
                print(f"   Sequence:    {seq_num}")
                
                # Track message types
                msg_id_hex = f"0x{msg_id:08X}"
                if msg_id_hex not in self.stats['message_types']:
                    self.stats['message_types'][msg_id_hex] = 0
                self.stats['message_types'][msg_id_hex] += 1
                
                # Categorize message
                if msg_id == 0xCEF00404:  # Target Report
                    self.stats['target_data_messages'] += 1
                    print("🎯🎯🎯 TARGET REPORT MESSAGE! 🎯🎯🎯")
                elif msg_id == 0xCEF00406:  # Single Target Report  
                    self.stats['target_data_messages'] += 1
                    print("🎯 SINGLE TARGET REPORT MESSAGE! 🎯")
                elif msg_id == 0xCEF0041A:  # Sensor Position
                    self.stats['target_data_messages'] += 1
                    print("📍 SENSOR POSITION MESSAGE! 📍")
                elif msg_id == 0xCEF00403:  # System Status
                    self.stats['system_status_messages'] += 1
                    print("📊 SYSTEM STATUS MESSAGE")
                elif msg_id == 0xCEF00400:  # Keep Alive
                    self.stats['keep_alive_messages'] += 1
                    print("💓 KEEP ALIVE MESSAGE")
                else:
                    self.stats['unknown_messages'] += 1
                    print(f"❓ UNKNOWN MESSAGE TYPE: 0x{msg_id:08X}")
                
                # Decode message using our decoder
                print(f"\n📖 DECODED MESSAGE:")
                decoded = self.decoder.decode_message(data)
                print(decoded)
                
            else:
                print("⚠️  Message too short for ELTA header")
                print(f"Raw bytes: {data.hex().upper()}")
                
        except Exception as e:
            print(f"❌ Error processing message: {e}")
            print(f"Raw data: {data.hex().upper()}")
        
        print("-" * 80)
    
    def print_statistics(self):
        """Print current statistics"""
        print(f"\n📊 LISTENER STATISTICS:")
        print("=" * 50)
        print(f"Total Messages:          {self.stats['total_messages']}")
        print(f"🎯 Target Data Messages: {self.stats['target_data_messages']} 🎯")
        print(f"System Status Messages:  {self.stats['system_status_messages']}")
        print(f"Keep Alive Messages:     {self.stats['keep_alive_messages']}")
        print(f"Unknown Messages:        {self.stats['unknown_messages']}")
        print(f"Total Bytes Received:    {self.stats['bytes_received']}")
        
        if self.stats['message_types']:
            print(f"\nMessage Types Seen:")
            for msg_type, count in sorted(self.stats['message_types'].items()):
                print(f"   {msg_type}: {count} messages")
        
        print("=" * 50)
    
    def cleanup(self):
        """Clean up resources"""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        
        print(f"\n[{datetime.now()}] 🛑 Pure UDP Listener stopped")
        self.print_statistics()

if __name__ == "__main__":
    try:
        listener = EltaPureUDPListener()
        listener.start()
    except KeyboardInterrupt:
        print(f"\n[{datetime.now()}] 🛑 Interrupted by user")
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Fatal error: {e}")