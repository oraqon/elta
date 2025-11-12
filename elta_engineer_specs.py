#!/usr/bin/env python3
"""
ELTA Client - Engineer Specifications
====================================
Based on direct communication with ELTA engineer:
- UDP: Connect to port 22230, receive data from simulator on port 30080
- TCP: Connect to 132.4.6.205 on port 30087
"""

import socket
import threading
import time
import struct
from datetime import datetime
from elta_message_decoder import EltaMessageDecoder

class EltaEngineerSpecClient:
    def __init__(self):
        self.decoder = EltaMessageDecoder()
        self.running = True
        self.stats = {
            'tcp_connections': 0,
            'tcp_messages': 0,
            'udp_messages': 0,
            'target_messages': 0
        }
        
    def log(self, message):
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S.%f]")
        print(f"{timestamp} {message}")
        
    def start_tcp_client(self):
        """Connect to 132.4.6.205:30087 as specified by engineer"""
        def tcp_handler():
            while self.running:
                try:
                    self.log("🔌 TCP connecting to 132.4.6.205:30087")
                    self.log("   📋 ELTA Engineer Specification")
                    
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(15.0)
                    sock.connect(('132.4.6.205', 30087))
                    
                    self.log("✅ TCP CONNECTED to 132.4.6.205:30087!")
                    self.stats['tcp_connections'] += 1
                    
                    # Keep connection alive and listen for data
                    sock.settimeout(1.0)
                    while self.running:
                        try:
                            data = sock.recv(4096)
                            if not data:
                                self.log("TCP connection closed by server")
                                break
                                
                            self.log(f"📨 TCP received {len(data)} bytes from 132.4.6.205:30087")
                            self.log(f"   Raw: {data.hex()}")
                            
                            # Try to decode the message
                            try:
                                decoded = self.decoder.decode_message(data)
                                if decoded:
                                    self.log(f"🎯 TCP DECODED: {decoded}")
                                    self.stats['tcp_messages'] += 1
                                    if 'TARGET' in str(decoded):
                                        self.stats['target_messages'] += 1
                            except Exception as e:
                                self.log(f"   ⚠️ Decode error: {e}")
                                
                        except socket.timeout:
                            continue
                        except Exception as e:
                            self.log(f"TCP receive error: {e}")
                            break
                            
                    sock.close()
                    
                except Exception as e:
                    self.log(f"TCP connection error: {e}")
                    
                if self.running:
                    self.log("   ⏳ Retrying TCP in 10 seconds...")
                    time.sleep(10)
                    
        thread = threading.Thread(target=tcp_handler, daemon=True)
        thread.start()
        return thread
        
    def start_udp_client(self):
        """Connect to port 22230 and receive data from simulator on port 30080"""
        def udp_handler():
            try:
                # Create UDP socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(1.0)
                
                # Bind to port 22230 as specified by engineer
                sock.bind(('0.0.0.0', 22230))
                self.log("✅ UDP listening on 0.0.0.0:22230")
                self.log("   📋 ELTA Engineer Specification")
                self.log("   🎯 Expecting data from simulator on port 30080")
                
                while self.running:
                    try:
                        data, addr = sock.recvfrom(4096)
                        self.log(f"📨 UDP received {len(data)} bytes from {addr}")
                        self.log(f"   Raw: {data.hex()}")
                        
                        # Check if data is from expected simulator port 30080
                        if addr[1] == 30080:
                            self.log("   ✅ Data from expected simulator port 30080!")
                        else:
                            self.log(f"   ⚠️ Data from unexpected port {addr[1]} (expected 30080)")
                            
                        # Try to decode the message
                        try:
                            decoded = self.decoder.decode_message(data)
                            if decoded:
                                self.log(f"🎯 UDP DECODED: {decoded}")
                                self.stats['udp_messages'] += 1
                                if 'TARGET' in str(decoded):
                                    self.stats['target_messages'] += 1
                        except Exception as e:
                            self.log(f"   ⚠️ Decode error: {e}")
                            
                    except socket.timeout:
                        continue
                    except Exception as e:
                        self.log(f"UDP receive error: {e}")
                        break
                        
            except Exception as e:
                self.log(f"UDP setup error: {e}")
                
        thread = threading.Thread(target=udp_handler, daemon=True)
        thread.start()
        return thread
        
    def print_stats(self):
        """Print connection statistics"""
        print("\n📊 ELTA ENGINEER SPEC CLIENT STATISTICS:")
        print("=" * 60)
        print(f"TCP Connections:         {self.stats['tcp_connections']}")
        print(f"TCP Messages Received:   {self.stats['tcp_messages']}")
        print(f"UDP Messages Received:   {self.stats['udp_messages']}")
        print(f"🎯 Target Data Messages: {self.stats['target_messages']} 🎯")
        print("=" * 60)
        
    def run(self):
        """Main execution loop"""
        print("🚀 ELTA ENGINEER SPECIFICATION CLIENT")
        print("=" * 60)
        print("📋 Based on ELTA Engineer Communication:")
        print("   🔌 TCP: Connect to 132.4.6.205:30087")
        print("   📡 UDP: Listen on port 22230 for data from simulator port 30080")
        print("=" * 60)
        
        # Start both clients
        tcp_thread = self.start_tcp_client()
        udp_thread = self.start_udp_client()
        
        try:
            # Main loop with periodic stats
            while True:
                time.sleep(10)
                self.print_stats()
                
        except KeyboardInterrupt:
            self.log("🛑 Stopping...")
            self.running = False
            
            # Wait for threads to finish
            tcp_thread.join(timeout=2)
            udp_thread.join(timeout=2)
            
            self.print_stats()
            self.log("✅ Stopped")

if __name__ == "__main__":
    client = EltaEngineerSpecClient()
    client.run()