#!/usr/bin/env python3
"""
ELTA Proper Handshake Implementation
Based on ICD_2135M-004 specification
Implements correct TCP/UDP handshake sequence
"""

import socket
import struct
import threading
import time
from datetime import datetime
from elta_message_decoder import EltaMessageDecoder

class EltaProperHandshake:
    def __init__(self, tcp_host='localhost', tcp_port=23004, udp_port=32004):
        self.tcp_host = tcp_host
        self.tcp_port = tcp_port
        self.udp_port = udp_port
        self.running = False
        
        # Sockets
        self.tcp_socket = None
        self.udp_socket = None
        
        # Message decoder
        self.decoder = EltaMessageDecoder()
        
        # Communication state
        self.last_status_time = 0
        self.status_count = 0
        self.need_acknowledge = False
        
        # Statistics
        self.stats = {
            'status_received': 0,
            'keep_alive_sent': 0,
            'ack_sent': 0,
            'target_messages': 0
        }
        
    def start_udp_handler(self):
        """Handle UDP communication (Status messages, Keep Alive)"""
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp_socket.bind(('', self.udp_port))
            self.udp_socket.settimeout(1.0)
            
            print(f"[{datetime.now()}] 📡 UDP Handler started on port {self.udp_port}")
            
            while self.running:
                try:
                    # Receive UDP data (System Status messages)
                    data, addr = self.udp_socket.recvfrom(4096)
                    self.process_udp_message(data, addr)
                    
                except socket.timeout:
                    # Send Keep Alive every second
                    self.send_keep_alive()
                    continue
                except socket.error as e:
                    if self.running:
                        print(f"[{datetime.now()}] UDP error: {e}")
                    break
                    
        except Exception as e:
            print(f"[{datetime.now()}] UDP setup error: {e}")
        finally:
            if self.udp_socket:
                self.udp_socket.close()
    
    def start_tcp_handler(self):
        """Handle TCP communication (Control commands, Target data)"""
        while self.running:
            try:
                self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.tcp_socket.settimeout(5.0)
                self.tcp_socket.connect((self.tcp_host, self.tcp_port))
                
                print(f"[{datetime.now()}] ✅ TCP Connected to {self.tcp_host}:{self.tcp_port}")
                
                # Wait a bit before sending commands to let UDP handshake establish
                time.sleep(2)
                
                # Send System Control command to move to OPERATE state
                self.send_system_control_command()
                
                # Listen for TCP messages (Target data, Acknowledge, etc.)
                buffer = b''
                while self.running:
                    try:
                        data = self.tcp_socket.recv(4096)
                        if not data:
                            print(f"[{datetime.now()}] TCP connection closed by radar")
                            break
                            
                        buffer += data
                        buffer = self.process_tcp_buffer(buffer)
                        
                    except socket.timeout:
                        continue
                    except socket.error as e:
                        print(f"[{datetime.now()}] TCP error: {e}")
                        break
                        
            except Exception as e:
                if self.running:
                    print(f"[{datetime.now()}] TCP connection error: {e}")
                    time.sleep(5)
            finally:
                if self.tcp_socket:
                    self.tcp_socket.close()
                    self.tcp_socket = None
    
    def process_udp_message(self, data, addr):
        """Process received UDP message (System Status)"""
        print(f"\n[{datetime.now()}] 📡 UDP Message from {addr}")
        print(f"Length: {len(data)} bytes")
        print(f"Hex: {data.hex().upper()}")
        
        try:
            # Decode the message
            if len(data) >= 20:
                source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', data[:20])
                
                if msg_id == 0xCEF00403:  # System Status
                    self.stats['status_received'] += 1
                    self.status_count += 1
                    self.last_status_time = time.time()
                    
                    print(f"🎯 SYSTEM STATUS MESSAGE #{self.stats['status_received']}")
                    
                    # Decode and display
                    decoded = self.decoder.decode_message(data)
                    print(decoded)
                    
                    # Check if we need to send acknowledgment (every 3 status messages)
                    if self.status_count >= 3:
                        self.send_acknowledge(seq_num)
                        self.status_count = 0
                        
                else:
                    print(f"Other UDP message: 0x{msg_id:08X}")
                    decoded = self.decoder.decode_message(data)
                    print(decoded)
                    
        except Exception as e:
            print(f"Error processing UDP message: {e}")
        
        print("-" * 70)
    
    def process_tcp_buffer(self, buffer):
        """Process TCP message buffer"""
        while len(buffer) >= 20:
            try:
                # Parse header to get message length
                source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', buffer[:20])
                
                if len(buffer) >= msg_length:
                    # Extract complete message
                    message = buffer[:msg_length]
                    buffer = buffer[msg_length:]
                    
                    print(f"\n[{datetime.now()}] 📡 TCP Message")
                    print(f"Length: {len(message)} bytes")
                    print(f"Hex: {message.hex().upper()}")
                    
                    # Check for target data messages
                    if msg_id in [0xCEF00404, 0xCEF00406, 0xCEF0041A]:  # Target Report, Single Target, Sensor Position
                        self.stats['target_messages'] += 1
                        print(f"🎯 TARGET DATA MESSAGE! (Total: {self.stats['target_messages']})")
                        
                        if msg_id == 0xCEF00404:
                            print("📊 TARGET REPORT")
                        elif msg_id == 0xCEF00406:
                            print("🎯 SINGLE TARGET REPORT")
                        elif msg_id == 0xCEF0041A:
                            print("📍 SENSOR POSITION")
                    
                    # Decode message
                    decoded = self.decoder.decode_message(message)
                    print(decoded)
                    print("-" * 70)
                else:
                    break  # Wait for more data
                    
            except struct.error:
                # Invalid header, skip one byte
                buffer = buffer[1:]
                continue
                
        return buffer
    
    def send_keep_alive(self):
        """Send Keep Alive message via UDP every second"""
        if not self.udp_socket:
            return
            
        try:
            # Create Keep Alive message (0xCEF00400)
            source_id = 0x2135
            msg_id = 0xCEF00400      # Keep Alive
            msg_length = 20          # Header only
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = self.stats['keep_alive_sent'] + 1
            
            message = struct.pack('<IIIII', source_id, msg_id, msg_length, time_tag, seq_num)
            
            # Send to radar's UDP receive port (might be different from our listen port)
            self.udp_socket.sendto(message, (self.tcp_host, 23004))  # Try same port as TCP
            
            self.stats['keep_alive_sent'] += 1
            
            if self.stats['keep_alive_sent'] % 10 == 0:
                print(f"[{datetime.now()}] 💓 Keep Alive sent #{self.stats['keep_alive_sent']}")
                
        except Exception as e:
            print(f"[{datetime.now()}] Error sending Keep Alive: {e}")
    
    def send_acknowledge(self, original_seq_num):
        """Send Acknowledge message via TCP"""
        if not self.tcp_socket:
            return
            
        try:
            print(f"[{datetime.now()}] 📤 Sending ACKNOWLEDGE for sequence {original_seq_num}")
            
            # Create Acknowledge message (0xCEF00405)
            source_id = 0x2135
            msg_id = 0xCEF00405      # Acknowledge
            msg_length = 24          # Header + 4 bytes for original seq num
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = self.stats['ack_sent'] + 1
            
            message = struct.pack('<IIIIII', source_id, msg_id, msg_length, time_tag, seq_num, original_seq_num)
            
            self.tcp_socket.send(message)
            self.stats['ack_sent'] += 1
            
            print(f"[{datetime.now()}] ✅ ACKNOWLEDGE sent")
            
        except Exception as e:
            print(f"[{datetime.now()}] Error sending Acknowledge: {e}")
    
    def send_system_control_command(self):
        """Send System Control command to move radar to OPERATE state"""
        if not self.tcp_socket:
            return
            
        try:
            print(f"[{datetime.now()}] 📤 Sending SYSTEM CONTROL (OPERATE) command")
            
            # Create System Control message (0xCEF00401) 
            source_id = 0x2135
            msg_id = 0xCEF00401      # System Control
            msg_length = 60          # As specified in ICD
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = 1
            
            # System Control payload
            rdr_state = 4            # OPERATE state
            mission_category = 0     # Default mission
            # HFL and Radar controls (8 bytes)
            hfl_radar_controls = struct.pack('BBBBBBBB', 0, 0, 0, 0, 0, 0, 0, 0)  # All enabled
            freq_index = 1           # Frequency index
            spare = b'\x00' * 20     # 5 * 4 bytes spare
            
            payload = struct.pack('<II', rdr_state, mission_category) + hfl_radar_controls + struct.pack('<I', freq_index) + spare
            
            message = struct.pack('<IIIII', source_id, msg_id, msg_length, time_tag, seq_num) + payload
            
            self.tcp_socket.send(message)
            print(f"[{datetime.now()}] ✅ SYSTEM CONTROL command sent (OPERATE state)")
            
        except Exception as e:
            print(f"[{datetime.now()}] Error sending System Control: {e}")
    
    def print_statistics(self):
        """Print communication statistics"""
        print(f"\n📊 COMMUNICATION STATISTICS:")
        print("=" * 50)
        print(f"Status Messages Received: {self.stats['status_received']}")
        print(f"Keep Alive Messages Sent: {self.stats['keep_alive_sent']}")
        print(f"Acknowledgments Sent:     {self.stats['ack_sent']}")
        print(f"Target Data Messages:     {self.stats['target_messages']}")
        print("=" * 50)
    
    def start(self):
        """Start the proper ELTA handshake"""
        self.running = True
        
        print("🚀 ELTA Proper Handshake Implementation")
        print("=" * 60)
        print("Based on ICD_2135M-004 specification:")
        print("1. UDP: Keep Alive every 1 second")
        print("2. UDP: Receive System Status messages")
        print("3. TCP: Send Acknowledge every 3 status messages")
        print("4. TCP: Send System Control (OPERATE)")
        print("5. TCP: Receive Target data")
        print("Press Ctrl+C to stop...")
        print("=" * 60)
        
        # Start UDP handler
        udp_thread = threading.Thread(target=self.start_udp_handler)
        udp_thread.daemon = True
        udp_thread.start()
        
        # Start TCP handler
        tcp_thread = threading.Thread(target=self.start_tcp_handler)
        tcp_thread.daemon = True
        tcp_thread.start()
        
        try:
            while self.running:
                time.sleep(5)
                self.print_statistics()
        except KeyboardInterrupt:
            print(f"\n[{datetime.now()}] 🛑 Stopping...")
            self.running = False
            
        self.print_statistics()
        print(f"[{datetime.now()}] ✅ ELTA Handshake stopped")

if __name__ == "__main__":
    handshake = EltaProperHandshake()
    handshake.start()