#!/usr/bin/env python3
"""
ELTA ELM-2135 Radar Data Reader
Based on ICD_2135M-004 specification
Binds to port 32004 (UDP server) and connects to port 23004 (TCP client)
Reads and prints data in hex format AND decoded readable format
"""

import socket
import struct
import threading
import time
import sys
from datetime import datetime
from elta_message_decoder import EltaMessageDecoder

class EltaDataReader:
    def __init__(self, bind_port=32004, connect_port=23004, host='localhost'):
        self.bind_port = bind_port
        self.connect_port = connect_port
        self.host = host
        self.running = False
        
        # UDP Server socket (for status messages)
        self.udp_socket = None
        
        # TCP Client socket (for target data)
        self.tcp_socket = None
        
        # Initialize message decoder
        self.decoder = EltaMessageDecoder()
        
        # Message codes from specification
        self.MESSAGE_CODES = {
            0xCEF00400: "Keep Alive",
            0xCEF00401: "System Control", 
            0xCEF00402: "System Motion",
            0xCEF00403: "System Status",
            0xCEF00404: "Target Report",
            0xCEF00405: "Acknowledge",
            0xCEF00406: "Single Target Report",
            0xCEF00407: "Maintenance Data",
            0xCEF00408: "Single Target Extended Data",
            0xCEF00409: "Bit Status Data",
            0xCEF0040A: "BIT Request",
            0xCEF0040B: "Resource Request",
            0xCEF0040C: "Maintenance Request",
            0xCEF00418: "Set Sensor Position",
            0xCEF00419: "Get Sensor Position",
            0xCEF0041A: "Sensor Position"
        }
        
    def start_udp_server(self):
        """Start UDP server that binds to specified port for status messages"""
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp_socket.bind(('', self.bind_port))
            self.udp_socket.settimeout(1.0)  # Set timeout for checking running flag
            
            print(f"[{datetime.now()}] UDP Server listening on port {self.bind_port}")
            
            while self.running:
                try:
                    data, addr = self.udp_socket.recvfrom(4096)
                    print(f"\n[{datetime.now()}] UDP Data received from {addr}")
                    print(f"Length: {len(data)} bytes")
                    self.print_hex_data(data, "UDP")
                    self.decode_message_header(data, "UDP")
                    
                    # Decode message with full decoder
                    print("\n" + "="*60)
                    print("DECODED MESSAGE (UDP)")
                    print("="*60)
                    decoded_msg = self.decoder.decode_message(data)
                    print(decoded_msg)
                    
                except socket.timeout:
                    continue  # Check running flag
                except socket.error as e:
                    if self.running:
                        print(f"[{datetime.now()}] UDP error: {e}")
                    break
                    
        except Exception as e:
            print(f"[{datetime.now()}] Failed to start UDP server: {e}")
            
    def start_tcp_client(self):
        """Connect to TCP server on specified port for target data"""
        while self.running:
            try:
                self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.tcp_socket.settimeout(5.0)
                self.tcp_socket.connect((self.host, self.connect_port))
                print(f"[{datetime.now()}] TCP connected to {self.host}:{self.connect_port}")
                
                # Remove timeout for data reception
                self.tcp_socket.settimeout(None)
                
                while self.running:
                    data = self.tcp_socket.recv(4096)
                    if not data:
                        print(f"[{datetime.now()}] TCP connection closed by remote host")
                        break
                        
                    print(f"\n[{datetime.now()}] TCP Data received")
                    print(f"Length: {len(data)} bytes")
                    self.print_hex_data(data, "TCP")
                    self.decode_message_header(data, "TCP")
                    
                    # Decode message with full decoder
                    print("\n" + "="*60)
                    print("DECODED MESSAGE (TCP)")
                    print("="*60)
                    decoded_msg = self.decoder.decode_message(data)
                    print(decoded_msg)
                    
            except ConnectionRefusedError:
                print(f"[{datetime.now()}] TCP Connection refused to {self.host}:{self.connect_port}")
                time.sleep(5)  # Wait before retrying
            except socket.timeout:
                print(f"[{datetime.now()}] TCP Connection timeout to {self.host}:{self.connect_port}")
                time.sleep(5)
            except Exception as e:
                if self.running:
                    print(f"[{datetime.now()}] TCP Connection error: {e}")
                    time.sleep(5)
            finally:
                if self.tcp_socket:
                    self.tcp_socket.close()
                    self.tcp_socket = None
                    
    def print_hex_data(self, data, protocol):
        """Print data in hex format"""
        print(f"=== {protocol} HEX DATA ===")
        
        # Print hex dump with address and ASCII
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            hex_part = ' '.join(f'{b:02X}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            print(f"{i:04X}: {hex_part:<48} |{ascii_part}|")
            
        # Print continuous hex
        print(f"\nContinuous hex: {data.hex().upper()}")
        print("=" * 50)
        
    def decode_message_header(self, data, protocol):
        """Decode message header according to ICD specification"""
        if len(data) < 20:
            print(f"[{datetime.now()}] Data too short for header (need 20 bytes, got {len(data)})")
            return
            
        try:
            # Message Header structure (20 bytes, little-endian):
            # - Message source_id (4 bytes)
            # - Message ID - code (4 bytes) 
            # - Message Length include header + body in bytes (4 bytes)
            # - Message time Tag (MS from midnight) (4 bytes)
            # - Message Sequence Number (4 bytes)
            
            source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', data[:20])
            
            print(f"\n=== {protocol} MESSAGE HEADER ===")
            print(f"Source ID:        0x{source_id:08X}")
            print(f"Message ID:       0x{msg_id:08X}")
            
            # Look up message name
            msg_name = self.MESSAGE_CODES.get(msg_id, "Unknown Message")
            print(f"Message Name:     {msg_name}")
            
            print(f"Message Length:   {msg_length} bytes")
            print(f"Time Tag:         {time_tag} ms (from midnight)")
            print(f"Sequence Number:  {seq_num}")
            
            # Convert time tag to readable format
            hours = (time_tag // (1000 * 60 * 60)) % 24
            minutes = (time_tag // (1000 * 60)) % 60
            seconds = (time_tag // 1000) % 60
            milliseconds = time_tag % 1000
            print(f"Time (HH:MM:SS.mmm): {hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}")
            
            # Show payload if exists
            if len(data) > 20:
                payload_size = len(data) - 20
                print(f"\nPayload size: {payload_size} bytes")
                if msg_length != len(data):
                    print(f"WARNING: Header length ({msg_length}) != actual length ({len(data)})")
                    
            print("=" * 40)
            
        except struct.error as e:
            print(f"[{datetime.now()}] Header decode error: {e}")
            
    def send_keepalive(self):
        """Send keep alive message every second via UDP"""
        keepalive_count = 0
        
        while self.running:
            try:
                # Create keep alive message (Message ID: 0xCEF00400)
                # Header only message (20 bytes)
                source_id = 0x12345678  # Example source ID
                msg_id = 0xCEF00400     # Keep Alive message code
                msg_length = 20         # Header only
                time_tag = int((datetime.now().timestamp() * 1000) % (24 * 60 * 60 * 1000)) # MS from midnight
                seq_num = keepalive_count
                
                keepalive_msg = struct.pack('<IIIII', source_id, msg_id, msg_length, time_tag, seq_num)
                
                # Send to radar (assuming it's listening on connect_port for UDP)
                keepalive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                try:
                    keepalive_socket.sendto(keepalive_msg, (self.host, self.connect_port))
                    print(f"[{datetime.now()}] Sent keep alive #{keepalive_count}")
                except Exception as e:
                    print(f"[{datetime.now()}] Keep alive send error: {e}")
                finally:
                    keepalive_socket.close()
                    
                keepalive_count += 1
                time.sleep(1)  # Send every second
                
            except Exception as e:
                print(f"[{datetime.now()}] Keep alive error: {e}")
                time.sleep(1)
                
    def start(self):
        """Start the data reader service"""
        self.running = True
        
        print("ELTA ELM-2135 Radar Data Reader")
        print("=" * 40)
        print(f"UDP Server port: {self.bind_port}")
        print(f"TCP Client connecting to: {self.host}:{self.connect_port}")
        print("Protocol: Little-endian")
        print("Press Ctrl+C to stop...")
        print("=" * 40)
        
        # Start UDP server thread
        udp_thread = threading.Thread(target=self.start_udp_server)
        udp_thread.daemon = True
        udp_thread.start()
        
        # Start TCP client thread
        tcp_thread = threading.Thread(target=self.start_tcp_client)
        tcp_thread.daemon = True
        tcp_thread.start()
        
        # Start keep alive thread
        keepalive_thread = threading.Thread(target=self.send_keepalive)
        keepalive_thread.daemon = True
        keepalive_thread.start()
        
        try:
            # Keep main thread alive
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n[{datetime.now()}] Shutting down...")
            self.stop()
            
    def stop(self):
        """Stop the data reader service"""
        self.running = False
        
        if self.udp_socket:
            self.udp_socket.close()
            
        if self.tcp_socket:
            self.tcp_socket.close()
            
        print(f"[{datetime.now()}] ELTA Data Reader stopped")

def main():
    """Main function"""
    # Command line arguments
    bind_port = 32004
    connect_port = 23004
    host = 'localhost'
    
    if len(sys.argv) > 1:
        try:
            bind_port = int(sys.argv[1])
        except ValueError:
            print("Invalid bind port. Using default 32004")
            
    if len(sys.argv) > 2:
        try:
            connect_port = int(sys.argv[2])
        except ValueError:
            print("Invalid connect port. Using default 23004")
            
    if len(sys.argv) > 3:
        host = sys.argv[3]
        
    # Create and start data reader
    reader = EltaDataReader(bind_port, connect_port, host)
    reader.start()

if __name__ == "__main__":
    main()