#!/usr/bin/env python3
"""
ELTA Selective Control Configuration
Based on TDP log analysis - send control messages only to main radar channel (port 30073)
Other ports are for data channels
"""

import socket
import struct
import threading
import time
from datetime import datetime
from elta_message_decoder import EltaMessageDecoder

class EltaSelectiveControlConfig:
    def __init__(self):
        # Network configuration based on TDP log analysis
        self.elta_simulator_ip = 'localhost'
        
        # All ports as TCP CLIENTS
        self.tcp_client_ports = [23004, 30080, 6072, 9966, 30073]
        
        # Port 30073 is the main radar control channel (radar1_chl.xml)
        self.control_port = 30073
        
        self.udp_port = 32004
        
        self.running = False
        self.decoder = EltaMessageDecoder()
        
        # Sockets
        self.tcp_clients = {}
        self.udp_socket = None
        
        # State management
        self.status_message_count = 0
        self.operate_requested = False
        
        # Statistics
        self.stats = {
            'status_received': 0,
            'acknowledge_sent': 0,
            'keep_alive_sent': 0,
            'target_messages': 0,
            'client_connections': 0,
            'total_messages': 0
        }
        
    def start_tcp_client(self, port):
        """Connect as TCP client to simulator"""
        client_name = f"CLIENT:{port}"
        
        while self.running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                
                print(f"[{datetime.now()}] 🔌 {client_name} connecting to {self.elta_simulator_ip}:{port}")
                
                # Connect to ELTA simulator
                sock.connect((self.elta_simulator_ip, port))
                
                print(f"[{datetime.now()}] ✅ {client_name} CONNECTED!")
                self.stats['client_connections'] += 1
                
                self.tcp_clients[port] = sock
                
                # Send System Control ONLY to the main radar control port (30073)
                if port == self.control_port:
                    time.sleep(1)
                    print(f"[{datetime.now()}] 🎯 Main radar control port connected - sending system control")
                    self.send_system_control(port)
                else:
                    print(f"[{datetime.now()}] 📡 Data channel port {port} connected - listening for messages")
                
                # Listen for messages
                buffer = b''
                while self.running:
                    try:
                        data = sock.recv(4096)
                        if not data:
                            print(f"[{datetime.now()}] {client_name} connection closed by simulator")
                            break
                            
                        buffer += data
                        buffer = self.process_tcp_buffer(buffer, client_name)
                        
                    except socket.timeout:
                        continue
                    except socket.error as e:
                        print(f"[{datetime.now()}] {client_name} error: {e}")
                        break
                        
            except Exception as e:
                if self.running:
                    print(f"[{datetime.now()}] {client_name} connection error: {e}")
                    time.sleep(5)  # Longer retry for failed connections
            finally:
                if port in self.tcp_clients:
                    try:
                        self.tcp_clients[port].close()
                    except:
                        pass
                    del self.tcp_clients[port]
    
    def start_udp_handler(self):
        """Handle UDP communication"""
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp_socket.bind(('', self.udp_port))
            self.udp_socket.settimeout(2.0)  # Longer timeout to reduce spam
            
            print(f"[{datetime.now()}] 📡 UDP Handler active on port {self.udp_port}")
            
            while self.running:
                try:
                    data, addr = self.udp_socket.recvfrom(4096)
                    self.process_message(data, f"UDP from {addr}")
                    
                except socket.timeout:
                    # Send Keep Alive every 2 seconds
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
    
    def process_tcp_buffer(self, buffer, source):
        """Process TCP message buffer"""
        while len(buffer) >= 20:
            try:
                source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', buffer[:20])
                
                if len(buffer) >= msg_length:
                    message = buffer[:msg_length]
                    buffer = buffer[msg_length:]
                    
                    self.process_message(message, source)
                else:
                    break
                    
            except struct.error:
                buffer = buffer[1:]
                continue
                
        return buffer
    
    def process_message(self, data, source):
        """Process received message with proper state management"""
        self.stats['total_messages'] += 1
        
        print(f"\n[{datetime.now()}] 🎯 MESSAGE from {source}")
        print(f"Length: {len(data)} bytes")
        print(f"Hex: {data.hex().upper()}")
        
        try:
            if len(data) >= 20:
                source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', data[:20])
                
                # Handle System Status messages (crucial for state transitions)
                if msg_id == 0xCEF00403:  # System Status
                    self.stats['status_received'] += 1
                    self.status_message_count += 1
                    print(f"🚨 SYSTEM STATUS MESSAGE #{self.stats['status_received']} (count: {self.status_message_count})")
                    
                    # Send acknowledge every 3rd status message as per ICD
                    if self.status_message_count % 3 == 0:
                        print(f"[{datetime.now()}] 📤 Time to acknowledge (every 3rd status)")
                        self.send_acknowledge(seq_num)
                        
                        # After acknowledging, request OPERATE state if not done yet
                        if not self.operate_requested:
                            print(f"[{datetime.now()}] 🎯 Requesting transition to OPERATE state")
                            time.sleep(0.5)
                            self.send_system_control_operate()
                            self.operate_requested = True
                
                # Handle target data messages
                elif msg_id in [0xCEF00404, 0xCEF00406, 0xCEF0041A]:  # Target data
                    self.stats['target_messages'] += 1
                    print(f"🎯🎯🎯 TARGET DATA MESSAGE! (Total: {self.stats['target_messages']}) 🎯🎯🎯")
                    
                    if msg_id == 0xCEF00404:
                        print("📊 TARGET REPORT - Multiple targets detected!")
                    elif msg_id == 0xCEF00406:
                        print("🎯 SINGLE TARGET REPORT - Individual target!")
                    elif msg_id == 0xCEF0041A:
                        print("📍 SENSOR POSITION - Radar position data!")
                
                # Handle Keep Alive requests
                elif msg_id == 0xCEF00400:  # Keep Alive
                    print(f"💓 Keep Alive received - responding immediately")
                    self.send_keep_alive_response()
                
                # Decode message for detailed view
                decoded = self.decoder.decode_message(data)
                print(decoded)
                
        except Exception as e:
            print(f"Error processing message: {e}")
        
        print("-" * 80)
    
    def send_system_control(self, port):
        """Send System Control command via main radar control port only"""
        if port not in self.tcp_clients or port != self.control_port:
            return
            
        try:
            print(f"[{datetime.now()}] 📤 Sending SYSTEM CONTROL (STANDBY) via MAIN CONTROL PORT:{port}")
            
            source_id = 0x2135
            msg_id = 0xCEF00401      # System Control
            msg_length = 60          # As per ICD
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = 1
            
            # System Control payload (STANDBY state first)
            rdr_state = 2            # STANDBY (transition first)
            mission_category = 0     # Default mission
            controls = b'\x00' * 8   # HFL/Radar controls
            freq_index = 1           # Frequency index
            spare = b'\x00' * 20     # Spare bytes
            
            payload = struct.pack('<II', rdr_state, mission_category) + controls + struct.pack('<I', freq_index) + spare
            message = struct.pack('<IIIII', source_id, msg_id, msg_length, time_tag, seq_num) + payload
            
            self.tcp_clients[port].send(message)
            print(f"[{datetime.now()}] ✅ SYSTEM CONTROL (STANDBY) sent via MAIN CONTROL PORT:{port}")
            
        except Exception as e:
            print(f"[{datetime.now()}] System Control error on MAIN CONTROL PORT:{port}: {e}")
    
    def send_system_control_operate(self):
        """Send System Control to transition to OPERATE state via main control port"""
        if self.control_port not in self.tcp_clients:
            print(f"[{datetime.now()}] ⚠️ Main control port {self.control_port} not connected - cannot send OPERATE command")
            return
            
        try:
            print(f"[{datetime.now()}] 📤 Sending SYSTEM CONTROL (OPERATE) via MAIN CONTROL PORT:{self.control_port}")
            
            source_id = 0x2135
            msg_id = 0xCEF00401      # System Control
            msg_length = 60          # As per ICD
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = int(time.time()) % 65536
            
            # System Control payload (OPERATE state)
            rdr_state = 4            # OPERATE
            mission_category = 0     # Default mission
            controls = b'\x00' * 8   # HFL/Radar controls
            freq_index = 1           # Frequency index
            spare = b'\x00' * 20     # Spare bytes
            
            payload = struct.pack('<II', rdr_state, mission_category) + controls + struct.pack('<I', freq_index) + spare
            message = struct.pack('<IIIII', source_id, msg_id, msg_length, time_tag, seq_num) + payload
            
            self.tcp_clients[self.control_port].send(message)
            print(f"[{datetime.now()}] ✅ SYSTEM CONTROL (OPERATE) sent via MAIN CONTROL PORT:{self.control_port}")
            
        except Exception as e:
            print(f"[{datetime.now()}] System Control OPERATE error on MAIN CONTROL PORT:{self.control_port}: {e}")
    
    def send_acknowledge(self, original_seq_num):
        """Send Acknowledge message via main control port"""
        if self.control_port not in self.tcp_clients:
            print(f"[{datetime.now()}] ⚠️ Main control port {self.control_port} not connected - cannot send ACKNOWLEDGE")
            return
            
        try:
            print(f"[{datetime.now()}] 📤 Sending ACKNOWLEDGE for status seq #{original_seq_num} via MAIN CONTROL PORT:{self.control_port}")
            
            source_id = 0x2135
            msg_id = 0xCEF00405      # Acknowledge message
            msg_length = 24          # Header + 4 bytes for original seq num
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = int(time.time()) % 65536
            
            message = struct.pack('<IIIIII', source_id, msg_id, msg_length, time_tag, seq_num, original_seq_num)
            
            self.tcp_clients[self.control_port].send(message)
            self.stats['acknowledge_sent'] += 1
            print(f"[{datetime.now()}] ✅ ACKNOWLEDGE sent via MAIN CONTROL PORT:{self.control_port}")
            
        except Exception as e:
            print(f"[{datetime.now()}] Acknowledge error on MAIN CONTROL PORT:{self.control_port}: {e}")
    
    def send_keep_alive(self):
        """Send Keep Alive message via UDP"""
        if not self.udp_socket:
            return
            
        try:
            source_id = 0x2135
            msg_id = 0xCEF00400
            msg_length = 20
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = self.stats['keep_alive_sent'] + 1
            
            message = struct.pack('<IIIII', source_id, msg_id, msg_length, time_tag, seq_num)
            
            # Send to simulator UDP port (from TDP log: port 20071)
            try:
                self.udp_socket.sendto(message, ('localhost', 20071))
            except:
                pass
            
            self.stats['keep_alive_sent'] += 1
            
            if self.stats['keep_alive_sent'] % 10 == 0:
                print(f"[{datetime.now()}] 💓 Keep Alive #{self.stats['keep_alive_sent']} sent to UDP:20071")
                
        except Exception as e:
            print(f"[{datetime.now()}] Keep Alive error: {e}")
    
    def send_keep_alive_response(self):
        """Send Keep Alive response immediately"""
        if not self.udp_socket:
            return
            
        try:
            source_id = 0x2135
            msg_id = 0xCEF00400
            msg_length = 20
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = int(time.time()) % 65536
            
            message = struct.pack('<IIIII', source_id, msg_id, msg_length, time_tag, seq_num)
            
            # Send response to simulator
            self.udp_socket.sendto(message, ('localhost', 20071))
            print(f"[{datetime.now()}] 💓 Keep Alive RESPONSE sent to UDP:20071")
            
        except Exception as e:
            print(f"[{datetime.now()}] Keep Alive response error: {e}")
    
    def print_statistics(self):
        """Print statistics"""
        print(f"\n📊 COMMUNICATION STATISTICS:")
        print("=" * 70)
        print(f"TCP Client Connections:  {self.stats['client_connections']}")
        print(f"Total Messages:          {self.stats['total_messages']}")
        print(f"System Status Messages:  {self.stats['status_received']}")
        print(f"🎯 TARGET DATA MESSAGES: {self.stats['target_messages']} 🎯")
        print(f"Acknowledgments Sent:    {self.stats['acknowledge_sent']}")
        print(f"Keep Alive Sent:         {self.stats['keep_alive_sent']}")
        print(f"Active TCP Clients:      {len(self.tcp_clients)}")
        print(f"Main Control Port:       {self.control_port} ({'CONNECTED' if self.control_port in self.tcp_clients else 'DISCONNECTED'})")
        print(f"Status Message Count:    {self.status_message_count}")
        print(f"OPERATE State Requested: {self.operate_requested}")
        print("=" * 70)
    
    def start(self):
        """Start the selective control configuration"""
        self.running = True
        
        print("🚀 ELTA Selective Control Configuration")
        print("=" * 80)
        print(f"ELTA Simulator:       {self.elta_simulator_ip} (localhost)")
        print(f"TCP Client Ports:     {self.tcp_client_ports}")
        print(f"Main Control Port:    {self.control_port} (radar1_chl.xml)")
        print(f"UDP Port:             {self.udp_port}")
        print("🎯 Looking for: SENSOR_POSITION, SINGLE_TARGET_REPORT, TARGET_REPORT")
        print("=" * 80)
        
        # Start UDP handler
        udp_thread = threading.Thread(target=self.start_udp_handler)
        udp_thread.daemon = True
        udp_thread.start()
        
        # Start TCP clients - prioritize main control port first
        ports = [self.control_port] + [p for p in self.tcp_client_ports if p != self.control_port]
        
        for port in ports:
            client_thread = threading.Thread(target=self.start_tcp_client, args=(port,))
            client_thread.daemon = True
            client_thread.start()
            time.sleep(0.5)  # Stagger connections
        
        try:
            while self.running:
                time.sleep(15)  # Less frequent statistics
                self.print_statistics()
        except KeyboardInterrupt:
            print(f"\n[{datetime.now()}] 🛑 Stopping...")
            self.running = False
            
        self.print_statistics()
        print(f"[{datetime.now()}] ✅ Stopped")

if __name__ == "__main__":
    config = EltaSelectiveControlConfig()
    config.start()