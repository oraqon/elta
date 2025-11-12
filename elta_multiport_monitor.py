#!/usr/bin/env python3
"""
ELTA Multi-Port Monitor
Monitors all ports used by tdp.exe process to find where data is sent
"""

import socket
import threading
import time
import struct
from datetime import datetime

class EltaMultiPortMonitor:
    def __init__(self):
        self.running = True
        self.message_count = {}
        
        # All ports discovered from netstat for tdp.exe (PID 7120)
        self.tcp_ports = [23004, 6072, 9966, 30080]
        self.udp_ports = [20071, 22230, 23014, 32004]  # Added our standard 32004
        
    def tcp_monitor(self, port):
        """Monitor specific TCP port"""
        port_name = f"TCP:{port}"
        self.message_count[port_name] = 0
        
        print(f"[{datetime.now()}] 🚀 {port_name} Monitor starting...")
        
        while self.running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2.0)
                sock.connect(('localhost', port))
                
                print(f"[{datetime.now()}] ✅ {port_name} Connected!")
                
                buffer = b''
                while self.running:
                    try:
                        data = sock.recv(4096)
                        if not data:
                            print(f"[{datetime.now()}] {port_name} connection closed")
                            break
                        
                        buffer += data
                        self.message_count[port_name] += 1
                        self.process_data(data, port_name, buffer)
                        
                    except socket.timeout:
                        continue
                    except socket.error as e:
                        print(f"[{datetime.now()}] {port_name} error: {e}")
                        break
                        
            except socket.error as e:
                if "Connection refused" not in str(e):
                    print(f"[{datetime.now()}] {port_name} connection failed: {e}")
                time.sleep(5)
            finally:
                try:
                    sock.close()
                except:
                    pass
    
    def udp_monitor(self, port):
        """Monitor specific UDP port"""
        port_name = f"UDP:{port}"
        self.message_count[port_name] = 0
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Try to bind to the port
            try:
                sock.bind(('', port))
                print(f"[{datetime.now()}] 📡 {port_name} Listener active (bound)")
            except:
                # Port might be in use, try to receive on all interfaces
                sock.bind(('', 0))  # Bind to any available port
                print(f"[{datetime.now()}] 📡 {port_name} Listener active (monitor only)")
            
            sock.settimeout(2.0)
            
            while self.running:
                try:
                    data, addr = sock.recvfrom(4096)
                    self.message_count[port_name] += 1
                    self.process_data(data, f"{port_name} from {addr}")
                    
                except socket.timeout:
                    continue
                except socket.error as e:
                    if self.running:
                        print(f"[{datetime.now()}] {port_name} error: {e}")
                    break
                    
        except Exception as e:
            print(f"[{datetime.now()}] {port_name} setup failed: {e}")
        finally:
            try:
                sock.close()
            except:
                pass
    
    def process_data(self, data, source, buffer=None):
        """Process received data"""
        print(f"\n[{datetime.now()}] 🎯 DATA FROM {source}!")
        print(f"Length: {len(data)} bytes")
        print(f"Hex: {data.hex().upper()}")
        
        # Check for ELTA message format
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
                
                if msg_id in msg_types:
                    msg_name = msg_types[msg_id]
                    print(f"🚨 ELTA MESSAGE DETECTED: {msg_name}")
                    print(f"   Source ID: 0x{source_id:08X}")
                    print(f"   Message ID: 0x{msg_id:08X}")
                    print(f"   Length: {msg_length}")
                    print(f"   Time Tag: {time_tag}")
                    print(f"   Sequence: {seq_num}")
                    
                    if msg_id in [0xCEF00404, 0xCEF00406, 0xCEF0041A]:
                        print(f"   🎯 TARGET/SENSOR DATA MESSAGE!")
                        
                        # Try to decode payload
                        if len(data) > 20:
                            payload = data[20:]
                            print(f"   Payload: {payload.hex().upper()}")
                else:
                    print(f"Unknown message ID: 0x{msg_id:08X}")
                    
            except struct.error:
                print("Not ELTA message format")
        
        # Check for other patterns
        if data.startswith(b'HTTP'):
            print("🌐 HTTP traffic detected")
        elif data.startswith(b'GET') or data.startswith(b'POST'):
            print("🌐 HTTP request detected")
        elif len(data) == 4:
            # Could be a simple integer
            try:
                val = struct.unpack('<I', data)[0]
                print(f"🔢 32-bit integer: {val} (0x{val:08X})")
            except:
                pass
        
        print("-" * 70)
    
    def statistics_reporter(self):
        """Report statistics periodically"""
        while self.running:
            time.sleep(30)
            total = sum(self.message_count.values())
            if total > 0:
                print(f"\n📊 MESSAGE STATISTICS (Total: {total}):")
                for port, count in sorted(self.message_count.items()):
                    if count > 0:
                        print(f"   {port}: {count} messages")
            else:
                print(f"\n⏳ No messages yet... Monitoring {len(self.tcp_ports)} TCP + {len(self.udp_ports)} UDP ports")
    
    def start(self):
        """Start monitoring all ports"""
        print("🚀 ELTA Multi-Port Monitor")
        print("=" * 60)
        print(f"Monitoring tdp.exe (PID 7120) ports:")
        print(f"TCP Ports: {self.tcp_ports}")
        print(f"UDP Ports: {self.udp_ports}")
        print("Looking for: Any data from ELTA simulator system")
        print("Press Ctrl+C to stop...")
        print("=" * 60)
        
        # Start TCP monitors
        for port in self.tcp_ports:
            thread = threading.Thread(target=self.tcp_monitor, args=(port,))
            thread.daemon = True
            thread.start()
        
        # Start UDP monitors  
        for port in self.udp_ports:
            thread = threading.Thread(target=self.udp_monitor, args=(port,))
            thread.daemon = True
            thread.start()
        
        # Start statistics reporter
        stats_thread = threading.Thread(target=self.statistics_reporter)
        stats_thread.daemon = True
        stats_thread.start()
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n[{datetime.now()}] 🛑 Stopping multi-port monitor...")
            self.running = False
            
        print(f"\n[{datetime.now()}] 📊 Final Statistics:")
        total = sum(self.message_count.values())
        print(f"Total Messages: {total}")
        for port, count in sorted(self.message_count.items()):
            if count > 0:
                print(f"   {port}: {count}")
        print(f"[{datetime.now()}] ✅ Monitor stopped")

if __name__ == "__main__":
    monitor = EltaMultiPortMonitor()
    monitor.start()