#!/usr/bin/env python3
"""
ELTA Corrected Network Configuration
Using ports that are actually listening:
- 23004 (original port - LISTENING)
- 30080 (installation guide port - LISTENING) 
- 6072, 9966 (discovered ports - LISTENING)
"""

import socket
import struct
import threading
import time
from datetime import datetime
from elta_message_decoder import EltaMessageDecoder

class EltaCorrectedNetworkConfig:
    def __init__(self):
        # Network configuration
        self.elta_simulator_ip = '132.4.6.202'  # ELTA simulator IP
        self.customer_ip = '132.4.6.205'        # Your machine IP
        
        # Use ports that are actually listening
        self.tcp_ports = [23004, 30080, 6072, 9966]  # Actually listening ports
        self.udp_port = 32004
        
        self.running = False
        self.decoder = EltaMessageDecoder()
        
        # Sockets
        self.tcp_sockets = {}
        self.udp_socket = None
        
        # Statistics
        self.stats = {
            'status_received': 0,
            'keep_alive_sent': 0,
            'target_messages': 0,
            'connections_established': 0,
            'total_messages': 0
        }
    
    def start_udp_handler(self):
        """Handle UDP communication"""
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp_socket.bind(('', self.udp_port))  # Bind to all interfaces
            self.udp_socket.settimeout(1.0)
            
            print(f"[{datetime.now()}] 📡 UDP Handler active on port {self.udp_port}")
            
            while self.running:
                try:
                    data, addr = self.udp_socket.recvfrom(4096)
                    self.process_message(data, f"UDP from {addr}")
                    
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
    
    def start_tcp_client(self, port):
        """Connect as TCP client to simulator"""
        port_name = f"TCP:{port}"
        
        while self.running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                
                print(f"[{datetime.now()}] 🔌 {port_name} connecting to {self.elta_simulator_ip}:{port}")
                
                # Connect to ELTA simulator
                sock.connect((self.elta_simulator_ip, port))
                
                print(f"[{datetime.now()}] ✅ {port_name} CONNECTED to {self.elta_simulator_ip}:{port}")
                self.stats['connections_established'] += 1
                
                self.tcp_sockets[port] = sock
                
                # Send System Control after connection
                time.sleep(1)
                self.send_system_control(port)
                
                # Listen for messages
                buffer = b''
                while self.running:
                    try:
                        data = sock.recv(4096)
                        if not data:
                            print(f"[{datetime.now()}] {port_name} connection closed by simulator")
                            break
                            
                        buffer += data
                        buffer = self.process_tcp_buffer(buffer, port_name)
                        
                    except socket.timeout:
                        continue
                    except socket.error as e:
                        print(f"[{datetime.now()}] {port_name} error: {e}")
                        break
                        
            except Exception as e:
                if self.running:
                    print(f"[{datetime.now()}] {port_name} connection error: {e}")
                    time.sleep(5)
            finally:
                if port in self.tcp_sockets:
                    try:
                        self.tcp_sockets[port].close()
                    except:
                        pass
                    del self.tcp_sockets[port]
    
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
        """Process received message"""
        self.stats['total_messages'] += 1
        
        print(f"\n[{datetime.now()}] 🎯 MESSAGE from {source}")
        print(f"Length: {len(data)} bytes")
        print(f"Hex: {data.hex().upper()}")
        
        try:
            if len(data) >= 20:
                source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', data[:20])
                
                # Check for important message types
                if msg_id == 0xCEF00403:  # System Status
                    self.stats['status_received'] += 1
                    print(f"🚨 SYSTEM STATUS MESSAGE #{self.stats['status_received']}")
                elif msg_id in [0xCEF00404, 0xCEF00406, 0xCEF0041A]:  # Target data
                    self.stats['target_messages'] += 1
                    print(f"🎯 TARGET DATA MESSAGE! (Total: {self.stats['target_messages']})")
                    
                    if msg_id == 0xCEF00404:
                        print("📊 TARGET REPORT - Multiple targets")
                    elif msg_id == 0xCEF00406:
                        print("🎯 SINGLE TARGET REPORT")
                    elif msg_id == 0xCEF0041A:
                        print("📍 SENSOR POSITION")
                
                # Decode message
                decoded = self.decoder.decode_message(data)
                print(decoded)
                
        except Exception as e:
            print(f"Error processing message: {e}")
        
        print("-" * 80)
    
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
            
            # Send to ELTA simulator (try multiple ports)
            for port in [self.udp_port, 23004, 30080]:
                try:
                    self.udp_socket.sendto(message, (self.elta_simulator_ip, port))
                except:
                    pass
            
            self.stats['keep_alive_sent'] += 1
            
            if self.stats['keep_alive_sent'] % 10 == 0:
                print(f"[{datetime.now()}] 💓 Keep Alive #{self.stats['keep_alive_sent']} sent")
                
        except Exception as e:
            print(f"[{datetime.now()}] Keep Alive error: {e}")
    
    def send_system_control(self, port):
        """Send System Control command via TCP"""
        if port not in self.tcp_sockets:
            return
            
        try:
            print(f"[{datetime.now()}] 📤 Sending SYSTEM CONTROL (OPERATE) via TCP:{port}")
            
            source_id = 0x2135
            msg_id = 0xCEF00401      # System Control
            msg_length = 60          # As per ICD
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = 1
            
            # System Control payload (OPERATE state)
            rdr_state = 4            # OPERATE
            mission_category = 0     # Default mission
            controls = b'\x00' * 8   # HFL/Radar controls
            freq_index = 1           # Frequency index
            spare = b'\x00' * 20     # Spare bytes
            
            payload = struct.pack('<II', rdr_state, mission_category) + controls + struct.pack('<I', freq_index) + spare
            message = struct.pack('<IIIII', source_id, msg_id, msg_length, time_tag, seq_num) + payload
            
            self.tcp_sockets[port].send(message)
            print(f"[{datetime.now()}] ✅ SYSTEM CONTROL sent via TCP:{port}")
            
        except Exception as e:
            print(f"[{datetime.now()}] System Control error on TCP:{port}: {e}")
    
    def print_statistics(self):
        """Print statistics"""
        print(f"\n📊 COMMUNICATION STATISTICS:")
        print("=" * 50)
        print(f"Connections Established: {self.stats['connections_established']}")
        print(f"Total Messages:          {self.stats['total_messages']}")
        print(f"System Status Messages:  {self.stats['status_received']}")
        print(f"Target Data Messages:    {self.stats['target_messages']}")
        print(f"Keep Alive Sent:         {self.stats['keep_alive_sent']}")
        print(f"Active TCP Connections:  {len(self.tcp_sockets)}")
        print("=" * 50)
    
    def start(self):
        """Start the corrected network configuration"""
        self.running = True
        
        print("🚀 ELTA Corrected Network Configuration")
        print("=" * 60)
        print(f"ELTA Simulator IP:    {self.elta_simulator_ip}")
        print(f"Customer IP:          {self.customer_ip}")
        print(f"TCP Ports (listening): {self.tcp_ports}")
        print(f"UDP Port:             {self.udp_port}")
        print("Looking for: SENSOR_POSITION, SINGLE_TARGET_REPORT, TARGET_REPORT")
        print("=" * 60)
        
        # Start UDP handler
        udp_thread = threading.Thread(target=self.start_udp_handler)
        udp_thread.daemon = True
        udp_thread.start()
        
        # Start TCP clients for each listening port
        for port in self.tcp_ports:
            tcp_thread = threading.Thread(target=self.start_tcp_client, args=(port,))
            tcp_thread.daemon = True
            tcp_thread.start()
            time.sleep(0.5)  # Stagger connections
        
        try:
            while self.running:
                time.sleep(10)
                self.print_statistics()
        except KeyboardInterrupt:
            print(f"\n[{datetime.now()}] 🛑 Stopping...")
            self.running = False
            
        self.print_statistics()
        print(f"[{datetime.now()}] ✅ Stopped")

if __name__ == "__main__":
    config = EltaCorrectedNetworkConfig()
    config.start()