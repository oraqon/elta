#!/usr/bin/env python3
"""
ELTA Passive Monitor
Monitors both TCP and UDP for any data from the ELTA simulator
No commands sent - just pure listening
"""

import socket
import threading
import time
import struct
from datetime import datetime

class EltaPassiveMonitor:
    def __init__(self):
        self.running = True
        self.total_tcp_messages = 0
        self.total_udp_messages = 0
        
    def tcp_monitor(self, host='localhost', port=23004):
        """Monitor TCP connections - reconnect when closed"""
        print(f"[{datetime.now()}] 🚀 TCP Monitor starting for {host}:{port}")
        
        while self.running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2.0)
                sock.connect((host, port))
                
                print(f"[{datetime.now()}] ✅ TCP Connected! Passive listening...")
                
                # Passive listening - no commands sent
                while self.running:
                    try:
                        data = sock.recv(4096)
                        if not data:
                            print(f"[{datetime.now()}] TCP connection closed by simulator")
                            break
                        
                        self.total_tcp_messages += 1
                        self.process_tcp_data(data)
                        
                    except socket.timeout:
                        continue  # Keep listening
                    except socket.error as e:
                        print(f"[{datetime.now()}] TCP error: {e}")
                        break
                        
            except socket.error as e:
                if self.running:
                    print(f"[{datetime.now()}] TCP connection failed: {e}")
                    time.sleep(5)  # Wait before retry
            finally:
                try:
                    sock.close()
                except:
                    pass
    
    def udp_monitor(self, port=32004):
        """Monitor UDP on multiple ports"""
        ports_to_try = [32004, 23004, 23005, 32005, 4001, 4002]
        
        for udp_port in ports_to_try:
            thread = threading.Thread(target=self.udp_listener, args=(udp_port,))
            thread.daemon = True
            thread.start()
    
    def udp_listener(self, port):
        """Listen on specific UDP port"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('', port))
            sock.settimeout(2.0)
            
            print(f"[{datetime.now()}] 📡 UDP Listener active on port {port}")
            
            while self.running:
                try:
                    data, addr = sock.recvfrom(4096)
                    self.total_udp_messages += 1
                    self.process_udp_data(data, addr, port)
                    
                except socket.timeout:
                    continue
                except socket.error as e:
                    if self.running:
                        print(f"[{datetime.now()}] UDP port {port} error: {e}")
                    break
                    
        except Exception as e:
            print(f"[{datetime.now()}] UDP port {port} setup failed: {e}")
        finally:
            try:
                sock.close()
            except:
                pass
    
    def process_tcp_data(self, data):
        """Process received TCP data"""
        print(f"\n[{datetime.now()}] 📡 TCP DATA RECEIVED!")
        print(f"Length: {len(data)} bytes")
        print(f"Hex: {data.hex().upper()}")
        
        # Try to decode as ELTA message
        self.decode_elta_message(data, "TCP")
        print("-" * 60)
    
    def process_udp_data(self, data, addr, port):
        """Process received UDP data"""
        print(f"\n[{datetime.now()}] 📡 UDP DATA RECEIVED!")
        print(f"From: {addr} on port {port}")
        print(f"Length: {len(data)} bytes")
        print(f"Hex: {data.hex().upper()}")
        
        # Try to decode as ELTA message
        self.decode_elta_message(data, f"UDP:{port}")
        print("-" * 60)
    
    def decode_elta_message(self, data, source):
        """Try to decode data as ELTA message"""
        if len(data) >= 20:
            try:
                source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', data[:20])
                
                msg_types = {
                    0xCEF00400: "KEEP_ALIVE",
                    0xCEF00401: "SYSTEM_CONTROL",
                    0xCEF00403: "SYSTEM_STATUS",
                    0xCEF00404: "TARGET_REPORT",
                    0xCEF00405: "ACKNOWLEDGE", 
                    0xCEF00406: "SINGLE_TARGET_REPORT",
                    0xCEF0041A: "SENSOR_POSITION"
                }
                
                msg_name = msg_types.get(msg_id, f"UNKNOWN_0x{msg_id:08X}")
                
                print(f"🎯 DECODED ELTA MESSAGE ({source}):")
                print(f"   Source ID: 0x{source_id:08X}")
                print(f"   Message: {msg_name} (0x{msg_id:08X})")
                print(f"   Length: {msg_length} bytes")
                print(f"   Time Tag: {time_tag}")
                print(f"   Sequence: {seq_num}")
                
                if msg_id in [0xCEF00404, 0xCEF00406, 0xCEF0041A]:
                    print(f"   🚨 TARGET/SENSOR DATA DETECTED!")
                
            except struct.error:
                print(f"Could not decode as ELTA message format")
        else:
            print(f"Data too short for ELTA header ({len(data)} bytes)")
    
    def statistics_reporter(self):
        """Report statistics periodically"""
        while self.running:
            time.sleep(30)  # Report every 30 seconds
            if self.total_tcp_messages > 0 or self.total_udp_messages > 0:
                print(f"\n📊 STATISTICS: TCP: {self.total_tcp_messages}, UDP: {self.total_udp_messages}")
            else:
                print(f"\n⏳ Still monitoring... (TCP: {self.total_tcp_messages}, UDP: {self.total_udp_messages})")
    
    def start(self):
        """Start passive monitoring"""
        print("🚀 ELTA Passive Monitor")
        print("=" * 50)
        print("Monitoring strategy: Pure passive listening")
        print("- TCP: localhost:23004 (no commands sent)")
        print("- UDP: Multiple ports (32004, 23004, 23005, etc.)")
        print("- Looking for: Any data from ELTA simulator")
        print("Press Ctrl+C to stop...")
        print("=" * 50)
        
        # Start TCP monitor
        tcp_thread = threading.Thread(target=self.tcp_monitor)
        tcp_thread.daemon = True
        tcp_thread.start()
        
        # Start UDP monitors
        self.udp_monitor()
        
        # Start statistics reporter
        stats_thread = threading.Thread(target=self.statistics_reporter)
        stats_thread.daemon = True
        stats_thread.start()
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n[{datetime.now()}] 🛑 Stopping monitor...")
            self.running = False
            
        print(f"[{datetime.now()}] 📊 Final Statistics:")
        print(f"   TCP Messages: {self.total_tcp_messages}")
        print(f"   UDP Messages: {self.total_udp_messages}")
        print(f"[{datetime.now()}] ✅ Monitor stopped")

if __name__ == "__main__":
    monitor = EltaPassiveMonitor()
    monitor.start()