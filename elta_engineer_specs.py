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
        
    def _send_system_control_operate(self, sock):
        """Send System Control message to command radar to OPERATE state"""
        try:
            # Build System Control message per ICD specification
            # Message ID: 0xCEF00401 (System Control)
            # Per ICD: RDR_STATE = 4 (OPERATE)
            
            # Header: source_id, message_id, message_length, time_tag, sequence_number
            import time
            current_time_ms = int((time.time() % 86400) * 1000)  # ms from midnight
            
            # CORRECTED: Header field order per ICD Section 3.2
            header = struct.pack('<IIIII', 
                               0xCEF00401,      # message_id (System Control) - FIRST
                               60,              # message_length (20 byte header + 40 byte payload) - SECOND
                               current_time_ms, # time_tag (MS from midnight) - THIRD
                               1,               # sequence_number - FOURTH  
                               0x12345678)      # source_id (C2 system ID) - FIFTH
            
            # Payload: System Control fields per ICD Section 5.1.1
            payload = struct.pack('<I', 4)  # RDR_STATE = 4 (OPERATE)
            payload += struct.pack('<I', 0)  # Mission Category = 0
            
            # HFL Sensor controls (4 bytes, all disabled for now)
            payload += struct.pack('<BBBB', 1, 1, 1, 1)  # HFL_Sensor1-4_control = disabled
            
            # Radar controls (4 bytes, all enabled)
            payload += struct.pack('<BBBB', 0, 0, 0, 0)  # Radar1-4_control = enabled
            
            # Freq Index and spare fields
            payload += struct.pack('<I', 1)  # Freq Index = 1
            payload += struct.pack('<IIIII', 0, 0, 0, 0, 0)  # 5 spare fields
            
            message = header + payload
            
            self.log(f"   📋 System Control Message Details:")
            self.log(f"      Command: OPERATE (state=4)")
            self.log(f"      Message Length: {len(message)} bytes")
            self.log(f"      Raw hex: {message.hex().upper()}")
            
            sock.send(message)
            self.log("   ✅ System Control message sent successfully!")
            
        except Exception as e:
            self.log(f"   ❌ Error sending System Control message: {e}")
    
    def _start_keep_alive_sender(self, udp_sock):
        """Start Keep Alive message sender (required every 1 second per ICD)"""
        def keep_alive_sender():
            sequence = 1
            while self.running:
                try:
                    # Build Keep Alive message per ICD specification
                    # Message ID: 0xCEF00400 (Keep Alive)
                    current_time_ms = int((time.time() % 86400) * 1000)  # ms from midnight
                    
                    # CORRECTED: Header field order per ICD Section 3.2
                    message = struct.pack('<IIIII', 
                                        0xCEF00400,      # message_id (Keep Alive) - FIRST
                                        20,              # message_length (header only) - SECOND
                                        current_time_ms, # time_tag - THIRD
                                        sequence,        # sequence_number - FOURTH
                                        0x12345678)      # source_id (C2 system ID) - FIFTH
                    
                    # Send to radar (assuming same IP, different port or broadcast)
                    # For now, we'll log it - the actual destination depends on configuration
                    self.log(f"💓 Sending Keep Alive #{sequence} (required by ICD)")
                    
                    sequence += 1
                    time.sleep(1.0)  # Send every 1 second as required by ICD
                    
                except Exception as e:
                    self.log(f"Keep Alive sender error: {e}")
                    time.sleep(1.0)
                    
        thread = threading.Thread(target=keep_alive_sender, daemon=True)
        thread.start()
        return thread
    
    def _send_acknowledge(self, sock):
        """Send Acknowledge message in response to System Status"""
        try:
            current_time_ms = int((time.time() % 86400) * 1000)  # ms from midnight
            
            # Build Acknowledge message per ICD specification
            # Message ID: 0xCEF00405 (Acknowledge)
            # CORRECTED: Header field order per ICD Section 3.2
            message = struct.pack('<IIIII', 
                                0xCEF00405,      # message_id (Acknowledge) - FIRST
                                20,              # message_length (header only) - SECOND
                                current_time_ms, # time_tag - THIRD
                                2,               # sequence_number - FOURTH
                                0x12345678)      # source_id (C2 system ID) - FIFTH
            
            sock.send(message)
            self.log("   ✅ Acknowledge message sent!")
            
        except Exception as e:
            self.log(f"   ❌ Error sending Acknowledge: {e}")
        
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
                    
                    # Send System Control message to move radar to OPERATE state (per ICD Section 6.2)
                    self.log("📤 Sending System Control message to command radar to OPERATE state...")
                    self._send_system_control_operate(sock)
                    
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
                                    
                                    # Check if this is a System Status message that needs acknowledgment
                                    if 'SYSTEM STATUS' in str(decoded):
                                        self.log("📤 System Status received - sending Acknowledge per ICD...")
                                        self._send_acknowledge(sock)
                                        
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
                
                # Start keep alive sender (required by ICD - every 1 second)
                self._start_keep_alive_sender(sock)
                
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