#!/usr/bin/env python3
"""
ELTA Minimal Handshake Client
============================
Strategy: Send ONE proper System Control message to trigger data flow,
then immediately switch to pure listening mode.

Based on the ELTA config files and successful OPERATE state transition,
this approach will:
1. Connect to the main TCP server (127.0.0.1:23004)
2. Send ONE System Control OPERATE message 
3. Immediately disconnect TCP and switch to pure UDP listening
4. Listen on the correct UDP ports for target data

This minimizes crash risk while potentially triggering data flow.
"""

import socket
import struct
import threading
import time
from datetime import datetime
from elta_message_decoder import EltaMessageDecoder

class EltaMinimalHandshake:
    def __init__(self):
        # Network configuration from ELTA config files
        self.tcp_server = {
            'host': '127.0.0.1',      # gdu_chl.xml TcpServer
            'port': 23004,
            'description': 'Main GDU Control Channel'
        }
        
        self.udp_listeners = {
            'main_target_data': {
                'host': '127.0.0.1',     # gdu_chl.xml DefaultDestIp
                'port': 32004,           # gdu_chl.xml DefaultDestPort
                'description': 'Main Target Data Reception'
            },
            'extapp_data': {
                'host': '132.4.6.205',   # extapp_chl.xml DefaultDestIp
                'port': 22230,           # extapp_chl.xml DefaultDestPort
                'description': 'External App Data Reception'
            }
        }
        
        self.udp_sockets = {}
        self.running = False
        self.decoder = EltaMessageDecoder()
        self.handshake_completed = False
        
        # Statistics
        self.stats = {
            'handshake_sent': 0,
            'udp_messages': 0,
            'target_messages': 0,
            'tcp_messages': 0
        }
    
    def send_single_handshake(self):
        """Send ONE System Control message then disconnect"""
        try:
            print(f"[{datetime.now()}] 🚀 MINIMAL HANDSHAKE ATTEMPT")
            print("=" * 60)
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10.0)
            
            print(f"[{datetime.now()}] 🔌 Connecting to {self.tcp_server['host']}:{self.tcp_server['port']}")
            sock.connect((self.tcp_server['host'], self.tcp_server['port']))
            print(f"[{datetime.now()}] ✅ Connected!")
            
            # Send System Control OPERATE message
            print(f"[{datetime.now()}] 📤 Sending System Control OPERATE...")
            
            # Use a very simple, safe source_id
            source_id = 0x0001        # Minimal safe ID
            msg_id = 0xCEF00401       # System Control
            msg_length = 60           # ICD specified length
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = 1
            
            # System Control payload - Direct to OPERATE
            rdr_state = 4             # OPERATE state directly
            mission_category = 0      # Default
            controls = b'\x00' * 8    # Control bytes
            freq_index = 1            # Frequency
            spare = b'\x00' * 20      # Spare
            
            payload = struct.pack('<II', rdr_state, mission_category) + controls + struct.pack('<I', freq_index) + spare
            message = struct.pack('<IIIII', source_id, msg_id, msg_length, time_tag, seq_num) + payload
            
            print(f"Message (first 40 bytes): {message[:40].hex().upper()}")
            sock.send(message)
            
            self.stats['handshake_sent'] = 1
            print(f"[{datetime.now()}] ✅ System Control OPERATE sent!")
            
            # Listen for any immediate response for 3 seconds
            sock.settimeout(3.0)
            try:
                response = sock.recv(4096)
                if response:
                    print(f"[{datetime.now()}] 📨 Received response: {len(response)} bytes")
                    print(f"Response: {response[:40].hex().upper()}")
                    self.process_tcp_message(response)
            except socket.timeout:
                print(f"[{datetime.now()}] ⏰ No immediate response (normal)")
            
            # Close TCP connection immediately
            sock.close()
            print(f"[{datetime.now()}] 🔚 TCP connection closed - switching to UDP listening")
            
            self.handshake_completed = True
            
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Handshake error: {e}")
            print(f"[{datetime.now()}] 🔄 Continuing with UDP listening anyway...")
            self.handshake_completed = True
    
    def start_udp_listener(self, name, config):
        """Start UDP listener for data reception"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((config['host'], config['port']))
            sock.settimeout(5.0)
            
            self.udp_sockets[name] = sock
            
            print(f"[{datetime.now()}] ✅ UDP {name} active on {config['host']}:{config['port']}")
            print(f"   📋 {config['description']}")
            
            message_count = 0
            
            while self.running:
                try:
                    data, addr = sock.recvfrom(4096)
                    message_count += 1
                    
                    print(f"\n[{datetime.now()}] 🎉 UDP DATA RECEIVED on {name}!")
                    print(f"📨 Message #{message_count} from {addr}")
                    print(f"📏 Length: {len(data)} bytes")
                    print(f"🔢 Raw: {data[:60].hex().upper()}{'...' if len(data) > 60 else ''}")
                    
                    self.stats['udp_messages'] += 1
                    self.process_udp_message(data, addr, name)
                    
                except socket.timeout:
                    if message_count == 0 and self.stats['udp_messages'] == 0:
                        # Only show waiting message if no data received yet
                        if name == 'main_target_data':  # Reduce spam - only show for main listener
                            print(f"[{datetime.now()}] ⏰ Waiting for target data... (Handshake: {'✅' if self.handshake_completed else '❌'})")
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
    
    def process_tcp_message(self, data):
        """Process TCP response message"""
        try:
            if len(data) >= 20:
                source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', data[:20])
                print(f"TCP Response: SRC=0x{source_id:08X} MSG=0x{msg_id:08X} LEN={msg_length}")
                
                self.stats['tcp_messages'] += 1
                
                # Decode the message
                decoded = self.decoder.decode_message(data)
                print(decoded)
                
        except Exception as e:
            print(f"Error processing TCP message: {e}")
    
    def process_udp_message(self, data, addr, listener_name):
        """Process received UDP message"""
        try:
            if len(data) >= 20:
                source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', data[:20])
                
                print(f"📋 ELTA HEADER:")
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
                    self.stats['target_messages'] += 1
                    print(f"🎊 TARGET DATA COUNT: {self.stats['target_messages']} TOTAL!")
                
                # Decode message using our decoder
                print(f"\n📖 DETAILED DECODING:")
                decoded = self.decoder.decode_message(data)
                print(decoded)
                
            else:
                print("⚠️  Message too short for ELTA header")
                
        except Exception as e:
            print(f"❌ Error processing UDP message: {e}")
        
        print("=" * 80)
    
    def print_statistics(self):
        """Print current statistics"""
        print(f"\n📊 MINIMAL HANDSHAKE CLIENT STATISTICS:")
        print("=" * 60)
        print(f"Handshake Messages Sent: {self.stats['handshake_sent']}")
        print(f"TCP Messages Received:   {self.stats['tcp_messages']}")
        print(f"UDP Messages Received:   {self.stats['udp_messages']}")
        print(f"🎯 Target Data Messages: {self.stats['target_messages']} 🎯")
        print(f"Active UDP Listeners:    {len(self.udp_sockets)}")
        print(f"Handshake Status:        {'✅ Complete' if self.handshake_completed else '❌ Pending'}")
        print("=" * 60)
    
    def start(self):
        """Start minimal handshake client"""
        self.running = True
        
        print("🚀 ELTA MINIMAL HANDSHAKE CLIENT")
        print("=" * 70)
        print("🎯 Strategy: Send ONE System Control message → Pure UDP listening")
        print("📋 Config-based ports: 127.0.0.1:32004 & 132.4.6.205:22230")
        print("⚡ Minimal crash risk with maximum data triggering potential")
        print("=" * 70)
        
        # Start UDP listeners first
        for name, config in self.udp_listeners.items():
            thread = threading.Thread(target=self.start_udp_listener, args=(name, config))
            thread.daemon = True
            thread.start()
            time.sleep(1)
        
        print(f"\n[{datetime.now()}] 📡 UDP listeners started - sending handshake...")
        
        # Send the handshake
        self.send_single_handshake()
        
        print(f"\n[{datetime.now()}] 🎯 Now in pure UDP listening mode...")
        print("Looking for TARGET_REPORT, SINGLE_TARGET_REPORT, SENSOR_POSITION...")
        
        try:
            while self.running:
                time.sleep(30)  # Print stats every 30 seconds
                self.print_statistics()
                
                # If we get target data, celebrate!
                if self.stats['target_messages'] > 0:
                    print(f"\n🎉🎉🎉 SUCCESS! Receiving target data! 🎉🎉🎉")
                    
        except KeyboardInterrupt:
            print(f"\n[{datetime.now()}] 🛑 Stopping...")
            self.running = False
        
        self.print_statistics()
        print(f"[{datetime.now()}] ✅ Stopped")

if __name__ == "__main__":
    client = EltaMinimalHandshake()
    client.start()