#!/usr/bin/env python3
"""
Test Data Generator for ELTA ELM-2135 Radar Protocol
Generates test messages according to ICD_2135M-004 specification
"""

import socket
import struct
import time
import threading
from datetime import datetime

class EltaTestDataGenerator:
    def __init__(self, tcp_port=23004, udp_port=32004, host='localhost'):
        self.tcp_port = tcp_port
        self.udp_port = udp_port
        self.host = host
        self.running = False
        self.seq_counter = 0
        
        # Message codes from specification
        self.MSG_SYSTEM_STATUS = 0xCEF00403
        self.MSG_TARGET_REPORT = 0xCEF00404
        self.MSG_KEEP_ALIVE = 0xCEF00400
        self.MSG_SINGLE_TARGET_REPORT = 0xCEF00406
        self.MSG_SENSOR_POSITION = 0xCEF0041A
        
    def create_message_header(self, msg_id, body_size=0):
        """Create standard 20-byte message header"""
        source_id = 0x2135  # ELTA radar source
        msg_length = 20 + body_size  # Header + body
        time_tag = int((datetime.now().timestamp() * 1000) % (24 * 60 * 60 * 1000))
        seq_num = self.seq_counter
        self.seq_counter += 1
        
        return struct.pack('<IIIII', source_id, msg_id, msg_length, time_tag, seq_num)
    
    def create_system_status_message(self):
        """Create a system status message"""
        header = self.create_message_header(self.MSG_SYSTEM_STATUS, 12)
        
        # Example status data (12 bytes)
        radar_state = 2  # OPERATE state
        system_health = 1  # OK
        target_count = 5
        
        body = struct.pack('<III', radar_state, system_health, target_count)
        return header + body
    
    def create_target_report_message(self):
        """Create target report message with multiple targets"""
        # Number of targets (4 bytes)
        num_targets = 3
        
        # Create payload starting with target count
        payload = struct.pack('<I', num_targets)
        
        # Add target data (32 bytes per target)
        targets = [
            # Target 1: Aircraft
            (1001, int(12.5 * 1000), int(45.0 * 1000), int(5.0 * 1000), 
             int(220.0 * 100), int(-8.5 * 100), 1, 92),
            # Target 2: Helicopter  
            (1002, int(8.2 * 1000), int(135.0 * 1000), int(2.5 * 1000),
             int(85.0 * 100), int(-15.2 * 100), 2, 88),
            # Target 3: Bird
            (1003, int(3.1 * 1000), int(270.0 * 1000), int(1.2 * 1000),
             int(15.0 * 100), int(-25.0 * 100), 3, 65)
        ]
        
        for target_id, range_m, azimuth, elevation, velocity, rcs, target_class, confidence in targets:
            target_data = struct.pack('<IIIIiiii', 
                target_id, range_m, azimuth, elevation, 
                velocity, rcs, target_class, confidence
            )
            payload += target_data
        
        header = self.create_message_header(self.MSG_TARGET_REPORT, len(payload))
        return header + payload
    
    def create_single_target_report_message(self):
        """Create single target report message"""
        # Target fields according to ICD specification (32 bytes per target)
        target_id = 12345
        range_m = int(15.750 * 1000)      # Range in meters * 1000
        azimuth = int(127.5 * 1000)       # Azimuth in degrees * 1000
        elevation = int(5.2 * 1000)       # Elevation in degrees * 1000
        velocity = int(85.3 * 100)        # Velocity in m/s * 100
        rcs = int(-12.5 * 100)            # RCS in dBsm * 100
        target_class = 1                  # Aircraft
        confidence = 85                   # Confidence percentage
        
        # Pack single target data (32 bytes)
        target_data = struct.pack('<IIIIiiii', 
            target_id, range_m, azimuth, elevation, 
            velocity, rcs, target_class, confidence
        )
        
        header = self.create_message_header(self.MSG_SINGLE_TARGET_REPORT, len(target_data))
        return header + target_data
    
    def create_sensor_position_message(self):
        """Create sensor position message"""
        # Sensor position fields (24 bytes)
        latitude = int(32.0851 * 10000000)    # Latitude in degrees * 10^7
        longitude = int(34.7818 * 10000000)   # Longitude in degrees * 10^7 
        altitude = int(120.5 * 1000)          # Altitude in meters * 1000
        heading = int(45.0 * 1000)            # Heading in degrees * 1000
        pitch = int(2.1 * 1000)               # Pitch in degrees * 1000
        roll = int(-1.3 * 1000)               # Roll in degrees * 1000
        
        # Pack sensor position data (24 bytes)
        position_data = struct.pack('<iiiiii', 
            latitude, longitude, altitude, heading, pitch, roll
        )
        
        header = self.create_message_header(self.MSG_SENSOR_POSITION, len(position_data))
        return header + position_data
    
    def start_tcp_server(self):
        """Start TCP server to send target data"""
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('', self.tcp_port))
            server_socket.listen(1)
            server_socket.settimeout(1.0)
            
            print(f"[{datetime.now()}] TCP Test server listening on port {self.tcp_port}")
            
            while self.running:
                try:
                    client_socket, addr = server_socket.accept()
                    print(f"[{datetime.now()}] TCP Client connected: {addr}")
                    
                    # Send critical radar data periodically
                    message_cycle = 0
                    while self.running:
                        try:
                            # Cycle through critical message types over TCP
                            if message_cycle % 4 == 0:
                                # Send target report (multiple targets)
                                msg = self.create_target_report_message()
                                msg_type = "Target Report"
                            elif message_cycle % 4 == 1:
                                # Send single target report
                                msg = self.create_single_target_report_message()
                                msg_type = "Single Target Report"
                            elif message_cycle % 4 == 2:
                                # Send sensor position
                                msg = self.create_sensor_position_message()
                                msg_type = "Sensor Position"
                            else:
                                # Send another single target with different data
                                msg = self.create_single_target_report_message()
                                msg_type = "Single Target Report"
                            
                            client_socket.send(msg)
                            print(f"[{datetime.now()}] Sent TCP {msg_type} ({len(msg)} bytes)")
                            message_cycle += 1
                            time.sleep(2)  # Send critical data every 2 seconds
                            
                        except socket.error:
                            print(f"[{datetime.now()}] TCP Client disconnected")
                            break
                            
                    client_socket.close()
                    
                except socket.timeout:
                    continue
                except socket.error as e:
                    if self.running:
                        print(f"[{datetime.now()}] TCP Server error: {e}")
                    break
                    
            server_socket.close()
            
        except Exception as e:
            print(f"[{datetime.now()}] Failed to start TCP server: {e}")
    
    def start_udp_sender(self):
        """Start UDP sender for status and keep-alive messages only"""
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        message_cycle = 0
        
        try:
            while self.running:
                # Send only status and keep-alive messages over UDP
                if message_cycle % 2 == 0:
                    # Send system status
                    msg = self.create_system_status_message()
                    msg_type = "System Status"
                else:
                    # Send keep-alive (simplified - just header)
                    msg = self.create_message_header(self.MSG_KEEP_ALIVE)
                    msg_type = "Keep Alive"
                
                udp_socket.sendto(msg, (self.host, self.udp_port))
                print(f"[{datetime.now()}] Sent UDP {msg_type} message ({len(msg)} bytes)")
                message_cycle += 1
                time.sleep(1)  # Send status messages every 1 second
                
        except Exception as e:
            print(f"[{datetime.now()}] UDP sender error: {e}")
        finally:
            udp_socket.close()
    
    def start(self):
        """Start the test data generator"""
        self.running = True
        
        print("ELTA ELM-2135 Test Data Generator")
        print("=" * 40)
        print(f"TCP Server port: {self.tcp_port}")
        print(f"UDP Target host:port: {self.host}:{self.udp_port}")
        print("Press Ctrl+C to stop...")
        print("=" * 40)
        
        # Start TCP server thread
        tcp_thread = threading.Thread(target=self.start_tcp_server)
        tcp_thread.daemon = True
        tcp_thread.start()
        
        # Start UDP sender thread
        udp_thread = threading.Thread(target=self.start_udp_sender)
        udp_thread.daemon = True
        udp_thread.start()
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n[{datetime.now()}] Shutting down test generator...")
            self.stop()
    
    def stop(self):
        """Stop the test data generator"""
        self.running = False
        print(f"[{datetime.now()}] Test data generator stopped")

def main():
    generator = EltaTestDataGenerator()
    generator.start()

if __name__ == "__main__":
    main()