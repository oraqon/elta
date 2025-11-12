#!/usr/bin/env python3
"""
ELTA ELM-2135 Real Data Reader
Connects to actual ELTA simulator on port 23004
Receives and decodes real SENSOR_POSITION/SINGLE_TARGET_REPORT/TARGET_REPORT messages
"""

import socket
import struct
import threading
import time
import sys
from datetime import datetime
from elta_message_decoder import EltaMessageDecoder

class EltaRealDataReader:
    def __init__(self, tcp_host='localhost', tcp_port=23004, udp_port=32004):
        self.tcp_host = tcp_host
        self.tcp_port = tcp_port
        self.udp_port = udp_port
        self.running = False
        
        # TCP Client socket (to connect to ELTA simulator)
        self.tcp_socket = None
        
        # UDP Server socket (for any status broadcasts)
        self.udp_socket = None
        
        # Initialize message decoder
        self.decoder = EltaMessageDecoder()
        
        # Track received message types
        self.message_stats = {
            'SENSOR_POSITION': 0,
            'SINGLE_TARGET_REPORT': 0, 
            'TARGET_REPORT': 0,
            'SYSTEM_STATUS': 0,
            'KEEP_ALIVE': 0,
            'OTHER': 0
        }
        
    def connect_to_elta_simulator(self):
        """Connect to the real ELTA simulator and receive messages"""
        while self.running:
            try:
                print(f"[{datetime.now()}] Connecting to ELTA simulator at {self.tcp_host}:{self.tcp_port}")
                self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.tcp_socket.settimeout(5.0)  # 5 second timeout
                self.tcp_socket.connect((self.tcp_host, self.tcp_port))
                
                print(f"[{datetime.now()}] ✅ Connected to ELTA simulator!")
                
                # Send system control command to start operation
                self.send_start_operation_command()
                
                print(f"[{datetime.now()}] Waiting for messages...")
                
                # Receive data continuously
                buffer = b''
                while self.running:
                    try:
                        # Receive data
                        data = self.tcp_socket.recv(4096)
                        if not data:
                            print(f"[{datetime.now()}] Connection closed by ELTA simulator")
                            break
                            
                        buffer += data
                        
                        # Process complete messages from buffer
                        while len(buffer) >= 20:  # Minimum header size
                            # Try to parse header to get message length
                            try:
                                source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', buffer[:20])
                                
                                # Check if we have the complete message
                                if len(buffer) >= msg_length:
                                    # Extract complete message
                                    message = buffer[:msg_length]
                                    buffer = buffer[msg_length:]  # Remove processed message
                                    
                                    # Process the message
                                    self.process_message(message)
                                else:
                                    # Wait for more data
                                    break
                            except struct.error:
                                # Invalid header, skip one byte and try again
                                buffer = buffer[1:]
                                continue
                        
                    except socket.timeout:
                        continue  # Check running flag
                    except socket.error as e:
                        print(f"[{datetime.now()}] TCP receive error: {e}")
                        break
                        
            except ConnectionRefusedError:
                print(f"[{datetime.now()}] ❌ Connection refused - Is ELTA simulator running on port {self.tcp_port}?")
                time.sleep(5)  # Wait before retrying
            except socket.timeout:
                print(f"[{datetime.now()}] ❌ Connection timeout - ELTA simulator not responding")
                time.sleep(5)
            except Exception as e:
                print(f"[{datetime.now()}] ❌ Connection error: {e}")
                time.sleep(5)
            finally:
                if self.tcp_socket:
                    self.tcp_socket.close()
                    self.tcp_socket = None
    
    def send_start_operation_command(self):
        """Send system control command to start operation"""
        try:
            print(f"[{datetime.now()}] 📤 Sending START OPERATION command to ELTA simulator...")
            
            # Create SYSTEM_CONTROL message (0xCEF00401)
            source_id = 0x2135      # Our source ID
            msg_id = 0xCEF00401     # SYSTEM_CONTROL message
            msg_length = 28         # Header (20) + Payload (8)
            time_tag = int((time.time() % 86400) * 1000)  # ms from midnight
            seq_num = 1             # Sequence number
            
            # Control command payload
            command = 1             # Start System command
            parameter = 2           # Set to Operational mode
            
            # Pack the complete message
            message = struct.pack('<IIIIIII', 
                                source_id, msg_id, msg_length, time_tag, seq_num,
                                command, parameter)
            
            # Send the command
            self.tcp_socket.send(message)
            print(f"[{datetime.now()}] ✅ START OPERATION command sent")
            
            # Also try sending a "Start Search" command
            time.sleep(0.1)  # Small delay
            seq_num = 2
            command = 4      # Start Search command
            parameter = 3    # Search & Track mode
            
            message2 = struct.pack('<IIIIIII', 
                                 source_id, msg_id, msg_length, time_tag + 100, seq_num,
                                 command, parameter)
            
            self.tcp_socket.send(message2)
            print(f"[{datetime.now()}] ✅ START SEARCH command sent")
            
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Failed to send operation command: {e}")
                    
    def process_message(self, data):
        """Process received message from ELTA simulator"""
        try:
            # Decode header to identify message type
            if len(data) >= 20:
                source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', data[:20])
                
                # Identify message type
                msg_type = "OTHER"
                if msg_id == 0xCEF0041A:
                    msg_type = "SENSOR_POSITION"
                elif msg_id == 0xCEF00406:
                    msg_type = "SINGLE_TARGET_REPORT"
                elif msg_id == 0xCEF00404:
                    msg_type = "TARGET_REPORT"
                elif msg_id == 0xCEF00403:
                    msg_type = "SYSTEM_STATUS"
                elif msg_id == 0xCEF00400:
                    msg_type = "KEEP_ALIVE"
                
                # Update statistics
                self.message_stats[msg_type] += 1
                
                print(f"\n[{datetime.now()}] 📡 Received {msg_type} from ELTA simulator")
                print(f"Length: {len(data)} bytes")
                
                # Display hex data
                self.print_hex_data(data)
                
                # Decode message with full decoder
                print("\n" + "="*80)
                print("🔍 DECODED ELTA MESSAGE")
                print("="*80)
                decoded_msg = self.decoder.decode_message(data)
                print(decoded_msg)
                
                # Print statistics periodically
                if sum(self.message_stats.values()) % 10 == 0:
                    self.print_statistics()
                    
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Error processing message: {e}")
            print(f"Raw data: {data.hex().upper()}")
    
    def print_hex_data(self, data):
        """Print data in hex format"""
        print("=== HEX DATA ===")
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            hex_part = ' '.join(f'{b:02X}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            print(f"{i:04X}: {hex_part:<48} |{ascii_part}|")
        
        print(f"\nContinuous hex: {data.hex().upper()}")
        print("=" * 50)
    
    def print_statistics(self):
        """Print message reception statistics"""
        total = sum(self.message_stats.values())
        print(f"\n📊 MESSAGE STATISTICS (Total: {total})")
        print("=" * 50)
        for msg_type, count in self.message_stats.items():
            percentage = (count / total * 100) if total > 0 else 0
            print(f"{msg_type:20}: {count:4d} ({percentage:5.1f}%)")
        print("=" * 50)
    
    def start_udp_listener(self):
        """Optional UDP listener for status messages"""
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp_socket.bind(('', self.udp_port))
            self.udp_socket.settimeout(1.0)
            
            print(f"[{datetime.now()}] UDP listener started on port {self.udp_port}")
            
            while self.running:
                try:
                    data, addr = self.udp_socket.recvfrom(4096)
                    print(f"\n[{datetime.now()}] 📡 Received UDP message from {addr}")
                    print(f"Length: {len(data)} bytes")
                    self.print_hex_data(data)
                    
                    # Decode UDP message too
                    decoded_msg = self.decoder.decode_message(data)
                    print(f"\n🔍 DECODED UDP MESSAGE:\n{decoded_msg}")
                    
                except socket.timeout:
                    continue
                except socket.error as e:
                    if self.running:
                        print(f"[{datetime.now()}] UDP error: {e}")
                    break
                    
        except Exception as e:
            print(f"[{datetime.now()}] Failed to start UDP listener: {e}")
    
    def start(self):
        """Start the real data reader"""
        self.running = True
        
        print("🚀 ELTA ELM-2135 Real Data Reader")
        print("=" * 50)
        print(f"Connecting to ELTA simulator: {self.tcp_host}:{self.tcp_port}")
        print(f"UDP listener port: {self.udp_port}")
        print("Looking for: SENSOR_POSITION, SINGLE_TARGET_REPORT, TARGET_REPORT")
        print("Press Ctrl+C to stop...")
        print("=" * 50)
        
        # Start TCP connection thread
        tcp_thread = threading.Thread(target=self.connect_to_elta_simulator)
        tcp_thread.daemon = True
        tcp_thread.start()
        
        # Start UDP listener thread (optional)
        udp_thread = threading.Thread(target=self.start_udp_listener)
        udp_thread.daemon = True
        udp_thread.start()
        
        try:
            # Keep main thread alive
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n[{datetime.now()}] 🛑 Stopping...")
            self.stop()
    
    def stop(self):
        """Stop the data reader"""
        self.running = False
        
        if self.tcp_socket:
            self.tcp_socket.close()
            
        if self.udp_socket:
            self.udp_socket.close()
            
        self.print_statistics()
        print(f"[{datetime.now()}] ✅ ELTA Real Data Reader stopped")
    
    def send_custom_command(self, command_type, parameter=0):
        """Send custom system control command"""
        if not self.tcp_socket:
            print("❌ Not connected to simulator")
            return
            
        try:
            source_id = 0x2135
            msg_id = 0xCEF00401     # SYSTEM_CONTROL
            msg_length = 28
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = int(time.time()) % 65536
            
            message = struct.pack('<IIIIIII', 
                                source_id, msg_id, msg_length, time_tag, seq_num,
                                command_type, parameter)
            
            self.tcp_socket.send(message)
            
            command_names = {
                1: "Start System",
                2: "Stop System", 
                3: "Reset System",
                4: "Start Search",
                5: "Stop Search",
                6: "Set Mode",
                7: "Calibrate",
                8: "Self Test"
            }
            
            cmd_name = command_names.get(command_type, f"Command {command_type}")
            print(f"[{datetime.now()}] 📤 Sent {cmd_name} (param: {parameter})")
            
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Failed to send command: {e}")

def main():
    """Main function"""
    # Command line arguments
    tcp_host = 'localhost'
    tcp_port = 23004
    udp_port = 32004
    
    if len(sys.argv) > 1:
        tcp_host = sys.argv[1]
        
    if len(sys.argv) > 2:
        try:
            tcp_port = int(sys.argv[2])
        except ValueError:
            print("Invalid TCP port. Using default 23004")
            
    if len(sys.argv) > 3:
        try:
            udp_port = int(sys.argv[3])
        except ValueError:
            print("Invalid UDP port. Using default 32004")
    
    # Create and start reader
    reader = EltaRealDataReader(tcp_host, tcp_port, udp_port)
    reader.start()

if __name__ == "__main__":
    main()