#!/usr/bin/env python3
"""
ELTA Network Discovery Tool
==========================
Since the simulator is in OPERATE state but we're not receiving data,
let's scan the network to see if there's any ELTA traffic flowing elsewhere.

This tool will:
1. Monitor multiple potential UDP ports for ELTA messages
2. Listen for broadcasts on the network
3. Check if data is being sent to other destinations
"""

import socket
import struct
import threading
import time
from datetime import datetime

class EltaNetworkDiscovery:
    def __init__(self):
        # Potential ELTA ports based on configs and common patterns
        self.potential_udp_ports = [
            32004,   # gdu_chl.xml DefaultDestPort
            22230,   # extapp_chl.xml DefaultDestPort
            32014,   # gdu_udp_chl.xml DefaultDestPort
            30080,   # extapp_chl.xml Port
            23004,   # gdu_chl.xml Port
            23014,   # gdu_udp_chl.xml Port
            20071,   # Common ELTA port
            22230,   # From config
            32000,   # Common base
            32001, 32002, 32003, 32005, 32006, 32007, 32008,  # Range around 32004
        ]
        
        self.broadcast_addresses = [
            '255.255.255.255',  # Global broadcast
            '132.4.6.255',      # Network broadcast
            '127.0.0.1',        # Localhost
        ]
        
        self.sockets = []
        self.running = False
        self.message_count = 0
        
    def is_elta_message(self, data):
        """Check if data looks like an ELTA message"""
        if len(data) < 20:
            return False
        
        try:
            source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', data[:20])
            
            # Check for known ELTA message IDs
            known_elta_ids = [
                0xCEF00400,  # Keep Alive
                0xCEF00401,  # System Control
                0xCEF00403,  # System Status
                0xCEF00404,  # Target Report
                0xCEF00405,  # Acknowledge
                0xCEF00406,  # Single Target Report
                0xCEF0041A,  # Sensor Position
            ]
            
            # Check if message ID matches ELTA pattern or known IDs
            if msg_id in known_elta_ids:
                return True
                
            # Check if message ID has ELTA pattern (0xCEF00xxx)
            if (msg_id & 0xFFFFF000) == 0xCEF00000:
                return True
                
            # Check if length is reasonable
            if msg_length > len(data) or msg_length < 20 or msg_length > 10000:
                return False
                
            return True
            
        except:
            return False
    
    def start_port_listener(self, port):
        """Listen on a specific UDP port for ELTA traffic"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Try to bind to all interfaces
            try:
                sock.bind(('', port))
                bind_addr = f"0.0.0.0:{port}"
            except:
                # If that fails, try localhost
                try:
                    sock.bind(('127.0.0.1', port))
                    bind_addr = f"127.0.0.1:{port}"
                except:
                    # Port might be in use
                    return
            
            sock.settimeout(2.0)
            self.sockets.append(sock)
            
            print(f"[{datetime.now()}] 👂 Listening on UDP {bind_addr}")
            
            while self.running:
                try:
                    data, addr = sock.recvfrom(4096)
                    
                    if self.is_elta_message(data):
                        self.message_count += 1
                        
                        print(f"\n[{datetime.now()}] 🎉 ELTA TRAFFIC DETECTED!")
                        print(f"📍 Port: {port}")
                        print(f"📨 From: {addr}")
                        print(f"📏 Length: {len(data)} bytes")
                        print(f"🔢 Raw: {data[:40].hex().upper()}{'...' if len(data) > 40 else ''}")
                        
                        # Parse header
                        if len(data) >= 20:
                            source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', data[:20])
                            print(f"📋 Header: SRC=0x{source_id:08X} MSG=0x{msg_id:08X} LEN={msg_length}")
                            
                            # Identify message type
                            if msg_id == 0xCEF00404:
                                print("🎯 TARGET REPORT MESSAGE!")
                            elif msg_id == 0xCEF00406:
                                print("🎯 SINGLE TARGET REPORT!")
                            elif msg_id == 0xCEF0041A:
                                print("📍 SENSOR POSITION MESSAGE!")
                            elif msg_id == 0xCEF00403:
                                print("📊 SYSTEM STATUS MESSAGE")
                            elif msg_id == 0xCEF00400:
                                print("💓 KEEP ALIVE MESSAGE")
                            else:
                                print(f"❓ UNKNOWN ELTA MESSAGE: 0x{msg_id:08X}")
                        
                        print("=" * 60)
                        
                except socket.timeout:
                    continue
                except socket.error:
                    break
                    
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Port {port} error: {e}")
        finally:
            try:
                sock.close()
            except:
                pass
    
    def start_broadcast_listener(self, address):
        """Listen for broadcast ELTA traffic"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            # Listen on all broadcast ports
            for port in [32004, 23004, 22230]:
                try:
                    sock.bind((address, port))
                    self.sockets.append(sock)
                    
                    print(f"[{datetime.now()}] 📡 Broadcast listener on {address}:{port}")
                    
                    sock.settimeout(3.0)
                    
                    while self.running:
                        try:
                            data, addr = sock.recvfrom(4096)
                            
                            if self.is_elta_message(data):
                                print(f"\n[{datetime.now()}] 📡 BROADCAST ELTA TRAFFIC!")
                                print(f"📍 Address: {address}:{port}")
                                print(f"📨 From: {addr}")
                                print(f"🔢 Data: {data[:40].hex().upper()}")
                                print("=" * 60)
                                
                        except socket.timeout:
                            continue
                        except socket.error:
                            break
                    break
                    
                except:
                    continue
                    
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Broadcast {address} error: {e}")
        finally:
            try:
                sock.close()
            except:
                pass
    
    def check_active_connections(self):
        """Check what ports are actively sending/receiving data"""
        print(f"\n[{datetime.now()}] 🔍 CHECKING ACTIVE NETWORK CONNECTIONS...")
        
        import subprocess
        try:
            # Check UDP connections
            result = subprocess.run(['netstat', '-an', '-p', 'udp'], 
                                  capture_output=True, text=True, shell=True)
            
            lines = result.stdout.split('\n')
            print("📊 ACTIVE UDP CONNECTIONS:")
            for line in lines:
                if '32004' in line or '23004' in line or '22230' in line or '30080' in line:
                    print(f"   {line.strip()}")
                    
        except Exception as e:
            print(f"Network check error: {e}")
    
    def start_discovery(self):
        """Start comprehensive ELTA network discovery"""
        self.running = True
        
        print("🔍 ELTA NETWORK DISCOVERY TOOL")
        print("=" * 60)
        print("🎯 Scanning for ELTA traffic on multiple ports...")
        print("📡 Listening for broadcasts...")
        print("🔍 Looking for TARGET_REPORT, SENSOR_POSITION, etc.")
        print("=" * 60)
        
        # Check current network state
        self.check_active_connections()
        
        # Start listeners for potential ports
        threads = []
        
        for port in self.potential_udp_ports:
            thread = threading.Thread(target=self.start_port_listener, args=(port,))
            thread.daemon = True
            thread.start()
            threads.append(thread)
            time.sleep(0.1)  # Small delay between starts
        
        print(f"\n[{datetime.now()}] 🚀 {len(self.potential_udp_ports)} port listeners started")
        print(f"[{datetime.now()}] 👂 Waiting for ELTA traffic...")
        
        try:
            # Run for a while to see if we detect anything
            for i in range(60):  # Run for 60 seconds
                time.sleep(1)
                if i % 10 == 0:
                    print(f"[{datetime.now()}] ⏰ Discovery running... ({self.message_count} ELTA messages found)")
                    
                if self.message_count > 0:
                    print(f"\n🎉 FOUND {self.message_count} ELTA MESSAGES!")
                    break
                    
        except KeyboardInterrupt:
            print(f"\n[{datetime.now()}] 🛑 Discovery stopped by user")
        
        self.running = False
        
        # Close all sockets
        for sock in self.sockets:
            try:
                sock.close()
            except:
                pass
        
        print(f"\n📊 DISCOVERY RESULTS:")
        print(f"Total ELTA messages found: {self.message_count}")
        if self.message_count == 0:
            print("❌ No ELTA traffic detected on any monitored ports")
            print("💡 This suggests:")
            print("   • Simulator might need additional configuration")
            print("   • Data might be sent to different destinations")
            print("   • Additional handshake might be required")
        else:
            print("✅ ELTA traffic detected! Check output above for details.")

if __name__ == "__main__":
    discovery = EltaNetworkDiscovery()
    discovery.start_discovery()