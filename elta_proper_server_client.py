#!/usr/bin/env python3
"""
ELTA Proper Server/Client Configuration
Based on TDP log analysis - some ports need servers, others need clients
Port 30073 is critical and was missing
"""

import socket
import struct
import threading
import time
from datetime import datetime
from elta_message_decoder import EltaMessageDecoder

class EltaProperServerClient:
    def __init__(self):
        # Network configuration based on TDP log analysis
        self.elta_simulator_ip = 'localhost'
        
        # Ports where we should be TCP SERVERS (simulator connects to us)
        self.tcp_server_ports = [30073, 6070, 6071]  # Critical: 30073 was missing!
        
        # Ports where we should be TCP CLIENTS (we connect to simulator)  
        self.tcp_client_ports = [23004, 30080, 6072, 9966]
        
        self.udp_port = 32004
        
        self.running = False
        self.decoder = EltaMessageDecoder()
        
        # Sockets
        self.tcp_servers = {}
        self.tcp_clients = {}
        self.server_sockets = {}
        self.udp_socket = None
        
        # State management
        self.status_message_count = 0
        self.operate_requested = False
        self.connected_clients = {}
        
        # Statistics
        self.stats = {
            'status_received': 0,
            'acknowledge_sent': 0,
            'keep_alive_sent': 0,
            'target_messages': 0,
            'server_connections': 0,
            'client_connections': 0,
            'total_messages': 0
        }
        
    def start_tcp_server(self, port):
        """Start TCP server on specified port"""
        try:
            server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind(('localhost', port))
            server_sock.listen(5)
            server_sock.settimeout(1.0)
            
            self.tcp_servers[port] = server_sock
            
            print(f"[{datetime.now()}] 🏭 TCP SERVER listening on port {port}")
            
            while self.running:
                try:
                    client_sock, addr = server_sock.accept()
                    print(f"[{datetime.now()}] ✅ TCP SERVER:{port} client connected from {addr}")
                    
                    self.stats['server_connections'] += 1
                    self.connected_clients[f"server_{port}_{addr[1]}"] = client_sock
                    
                    # Handle client in separate thread
                    client_thread = threading.Thread(
                        target=self.handle_server_client, 
                        args=(client_sock, port, addr)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except socket.timeout:
                    continue
                except socket.error as e:
                    if self.running:
                        print(f"[{datetime.now()}] TCP SERVER:{port} accept error: {e}")
                    break
                    
        except Exception as e:
            print(f"[{datetime.now()}] TCP SERVER:{port} setup error: {e}")
        finally:
            if port in self.tcp_servers:
                try:
                    self.tcp_servers[port].close()
                except:
                    pass
                del self.tcp_servers[port]
    
    def handle_server_client(self, client_sock, server_port, addr):
        """Handle messages from a client connected to our server"""
        client_name = f"SERVER:{server_port}<-{addr[1]}"
        
        try:
            client_sock.settimeout(5.0)
            buffer = b''
            
            while self.running:
                try:
                    data = client_sock.recv(4096)
                    if not data:
                        print(f"[{datetime.now()}] {client_name} disconnected")
                        break
                        
                    buffer += data
                    buffer = self.process_tcp_buffer(buffer, client_name)
                    
                except socket.timeout:
                    continue
                except socket.error as e:
                    print(f"[{datetime.now()}] {client_name} error: {e}")
                    break
                    
        except Exception as e:
            print(f"[{datetime.now()}] {client_name} handler error: {e}")
        finally:
            try:
                client_sock.close()
            except:
                pass
    
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
                
                # Send System Control after connection
                time.sleep(1)
                self.send_system_control(port)
                
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
                    time.sleep(5)
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
                            time.sleep(0.5)  # Small delay before sending control
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
        """Send System Control command via TCP client (initial standby)"""
        if port not in self.tcp_clients:
            return
            
        try:
            print(f"[{datetime.now()}] 📤 Sending SYSTEM CONTROL (STANDBY) via CLIENT:{port}")
            
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
            print(f"[{datetime.now()}] ✅ SYSTEM CONTROL (STANDBY) sent via CLIENT:{port}")
            
        except Exception as e:
            print(f"[{datetime.now()}] System Control error on CLIENT:{port}: {e}")
    
    def send_system_control_operate(self):
        """Send System Control to transition to OPERATE state"""
        # Send via first available TCP client connection
        for port, sock in self.tcp_clients.items():
            try:
                print(f"[{datetime.now()}] 📤 Sending SYSTEM CONTROL (OPERATE) via CLIENT:{port}")
                
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
                
                sock.send(message)
                print(f"[{datetime.now()}] ✅ SYSTEM CONTROL (OPERATE) sent via CLIENT:{port}")
                break  # Only send via one connection
                
            except Exception as e:
                print(f"[{datetime.now()}] System Control OPERATE error on CLIENT:{port}: {e}")
                continue
    
    def send_acknowledge(self, original_seq_num):
        """Send Acknowledge message via TCP clients"""
        # Try to send acknowledge via any available TCP client connection
        for port, sock in self.tcp_clients.items():
            try:
                print(f"[{datetime.now()}] 📤 Sending ACKNOWLEDGE for status seq #{original_seq_num} via CLIENT:{port}")
                
                source_id = 0x2135
                msg_id = 0xCEF00405      # Acknowledge message
                msg_length = 24          # Header + 4 bytes for original seq num
                time_tag = int((time.time() % 86400) * 1000)
                seq_num = int(time.time()) % 65536
                
                message = struct.pack('<IIIIII', source_id, msg_id, msg_length, time_tag, seq_num, original_seq_num)
                
                sock.send(message)
                self.stats['acknowledge_sent'] += 1
                print(f"[{datetime.now()}] ✅ ACKNOWLEDGE sent via CLIENT:{port}")
                break  # Only send via one connection
                
            except Exception as e:
                print(f"[{datetime.now()}] Acknowledge error on CLIENT:{port}: {e}")
                continue
    
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
            
            # Send to ELTA simulator on localhost (try multiple ports)
            for port in [23004, 20071, 22230, 23014]:
                try:
                    self.udp_socket.sendto(message, ('localhost', port))
                except:
                    pass
            
            self.stats['keep_alive_sent'] += 1
            
            if self.stats['keep_alive_sent'] % 5 == 0:
                print(f"[{datetime.now()}] 💓 Keep Alive #{self.stats['keep_alive_sent']} sent")
                
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
            self.udp_socket.sendto(message, ('localhost', 23004))
            print(f"[{datetime.now()}] 💓 Keep Alive RESPONSE sent")
            
        except Exception as e:
            print(f"[{datetime.now()}] Keep Alive response error: {e}")
    
    def print_statistics(self):
        """Print statistics"""
        print(f"\n📊 COMMUNICATION STATISTICS:")
        print("=" * 60)
        print(f"TCP Server Connections:  {self.stats['server_connections']}")
        print(f"TCP Client Connections:  {self.stats['client_connections']}")
        print(f"Total Messages:          {self.stats['total_messages']}")
        print(f"System Status Messages:  {self.stats['status_received']}")
        print(f"🎯 TARGET DATA MESSAGES: {self.stats['target_messages']} 🎯")
        print(f"Acknowledgments Sent:    {self.stats['acknowledge_sent']}")
        print(f"Keep Alive Sent:         {self.stats['keep_alive_sent']}")
        print(f"Active TCP Servers:      {len(self.tcp_servers)}")
        print(f"Active TCP Clients:      {len(self.tcp_clients)}")
        print(f"Connected Server Clients: {len(self.connected_clients)}")
        print(f"Status Message Count:    {self.status_message_count}")
        print(f"OPERATE State Requested: {self.operate_requested}")
        print("=" * 60)
    
    def start(self):
        """Start the proper server/client configuration"""
        self.running = True
        
        print("🚀 ELTA Proper Server/Client Configuration")
        print("=" * 70)
        print(f"ELTA Simulator:       {self.elta_simulator_ip} (localhost)")
        print(f"TCP Server Ports:     {self.tcp_server_ports} (simulator connects to us)")
        print(f"TCP Client Ports:     {self.tcp_client_ports} (we connect to simulator)")
        print(f"UDP Port:             {self.udp_port}")
        print("🎯 Looking for: SENSOR_POSITION, SINGLE_TARGET_REPORT, TARGET_REPORT")
        print("=" * 70)
        
        # Start UDP handler
        udp_thread = threading.Thread(target=self.start_udp_handler)
        udp_thread.daemon = True
        udp_thread.start()
        
        # Start TCP servers (simulator will connect to these)
        for port in self.tcp_server_ports:
            server_thread = threading.Thread(target=self.start_tcp_server, args=(port,))
            server_thread.daemon = True
            server_thread.start()
            time.sleep(0.2)
        
        # Start TCP clients (connect to simulator)
        for port in self.tcp_client_ports:
            client_thread = threading.Thread(target=self.start_tcp_client, args=(port,))
            client_thread.daemon = True
            client_thread.start()
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
    config = EltaProperServerClient()
    config.start()