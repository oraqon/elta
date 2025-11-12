#!/usr/bin/env python3
"""
ELTA Force OPERATE Configuration
Forces transition to OPERATE state to receive target data
Fixes message structure issues causing TDP error 8501
"""

import socket
import struct
import threading
import time
from datetime import datetime
from elta_message_decoder import EltaMessageDecoder

class EltaForceOperateConfig:
    def __init__(self):
        # Network configuration
        self.elta_simulator_ip = 'localhost'
        self.tcp_client_ports = [23004, 30080, 6072, 9966, 30073]
        self.control_port = 30073  # Main radar control port
        self.udp_port = 32004
        
        self.running = False
        self.decoder = EltaMessageDecoder()
        
        # Sockets
        self.tcp_clients = {}
        self.udp_socket = None
        
        # State management
        self.status_message_count = 0
        self.operate_requested = False
        self.operate_sent = False
        
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
                
                # Handle initial setup based on port
                if port == self.control_port:
                    time.sleep(1)
                    print(f"[{datetime.now()}] 🎯 Main control port - forcing OPERATE state")
                    self.force_operate_state()
                else:
                    print(f"[{datetime.now()}] 📡 Data channel - listening for messages")
                
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
            self.udp_socket.settimeout(3.0)
            
            print(f"[{datetime.now()}] 📡 UDP Handler active on port {self.udp_port}")
            
            while self.running:
                try:
                    data, addr = self.udp_socket.recvfrom(4096)
                    self.process_message(data, f"UDP from {addr}")
                    
                except socket.timeout:
                    # Send Keep Alive and request status
                    self.send_keep_alive()
                    self.request_system_status()
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
        """Process received message"""
        self.stats['total_messages'] += 1
        
        print(f"\n[{datetime.now()}] 🎯 MESSAGE from {source}")
        print(f"Length: {len(data)} bytes")
        print(f"Hex: {data.hex().upper()}")
        
        try:
            if len(data) >= 20:
                source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', data[:20])
                
                # Handle System Status messages
                if msg_id == 0xCEF00403:  # System Status
                    self.stats['status_received'] += 1
                    self.status_message_count += 1
                    print(f"🚨 SYSTEM STATUS MESSAGE #{self.stats['status_received']}")
                    
                    # Always acknowledge status messages
                    self.send_acknowledge(seq_num)
                    
                    # Force OPERATE state if not already done
                    if not self.operate_sent:
                        print(f"[{datetime.now()}] 🎯 Forcing transition to OPERATE state")
                        time.sleep(0.2)
                        self.send_system_control_operate()
                        self.operate_sent = True
                        self.operate_requested = True
                
                # Handle target data messages
                elif msg_id in [0xCEF00404, 0xCEF00406, 0xCEF0041A]:
                    self.stats['target_messages'] += 1
                    print(f"🎯🎯🎯 TARGET DATA MESSAGE! (Total: {self.stats['target_messages']}) 🎯🎯🎯")
                    
                    if msg_id == 0xCEF00404:
                        print("📊 TARGET REPORT - Multiple targets detected!")
                    elif msg_id == 0xCEF00406:
                        print("🎯 SINGLE TARGET REPORT - Individual target!")
                    elif msg_id == 0xCEF0041A:
                        print("📍 SENSOR POSITION - Radar position data!")
                
                # Handle Keep Alive
                elif msg_id == 0xCEF00400:
                    print(f"💓 Keep Alive received - responding")
                    self.send_keep_alive_response()
                
                # Decode message
                decoded = self.decoder.decode_message(data)
                print(decoded)
                
        except Exception as e:
            print(f"Error processing message: {e}")
        
        print("-" * 80)
    
    def force_operate_state(self):
        """Force immediate transition to OPERATE state"""
        if self.control_port not in self.tcp_clients:
            print(f"[{datetime.now()}] ⚠️ Control port not connected - cannot force OPERATE")
            return
            
        print(f"[{datetime.now()}] 🚀 FORCING IMMEDIATE OPERATE STATE")
        
        # Send OPERATE command immediately
        self.send_system_control_operate()
        self.operate_sent = True
        self.operate_requested = True
        
        # Also request status to trigger status messages
        time.sleep(0.5)
        self.request_system_status()
    
    def send_system_control_operate(self):
        """Send System Control OPERATE command"""
        if self.control_port not in self.tcp_clients:
            return
            
        try:
            print(f"[{datetime.now()}] 📤 Sending SYSTEM CONTROL (OPERATE) via PORT:{self.control_port}")
            
            # Fixed message structure to prevent TDP error - use working source_id
            source_id = 0x2135      # Use 2-byte value like working version (not 4-byte)
            msg_id = 0xCEF00401     # System Control
            msg_length = 60         # Total message length
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = int(time.time()) % 65536
            
            # System Control payload (OPERATE state = 4)
            rdr_state = 4           # OPERATE state
            mission_category = 0    # Default mission
            controls = b'\x00' * 8  # HFL/Radar controls
            freq_index = 1          # Frequency index
            spare = b'\x00' * 20    # Spare bytes
            
            # Build message with correct byte order
            header = struct.pack('<IIIII', source_id, msg_id, msg_length, time_tag, seq_num)
            payload = struct.pack('<II', rdr_state, mission_category) + controls + struct.pack('<I', freq_index) + spare
            message = header + payload
            
            self.tcp_clients[self.control_port].send(message)
            print(f"[{datetime.now()}] ✅ SYSTEM CONTROL (OPERATE) sent!")
            print(f"[{datetime.now()}] 🎯 OPERATE STATE NOW REQUESTED: True")
            
        except Exception as e:
            print(f"[{datetime.now()}] System Control OPERATE error: {e}")
    
    def request_system_status(self):
        """Request system status from simulator"""
        if self.control_port not in self.tcp_clients:
            return
            
        try:
            # Send GET_SENSOR_POSITION to trigger status response
            source_id = 0x2135
            msg_id = 0xCEF00419     # GET_SENSOR_POSITION
            msg_length = 20         # Header only
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = int(time.time()) % 65536
            
            message = struct.pack('<IIIII', source_id, msg_id, msg_length, time_tag, seq_num)
            
            self.tcp_clients[self.control_port].send(message)
            print(f"[{datetime.now()}] 📤 Status request sent")
            
        except Exception as e:
            print(f"[{datetime.now()}] Status request error: {e}")
    
    def send_acknowledge(self, original_seq_num):
        """Send Acknowledge message"""
        if self.control_port not in self.tcp_clients:
            return
            
        try:
            print(f"[{datetime.now()}] 📤 Sending ACKNOWLEDGE for seq #{original_seq_num}")
            
            source_id = 0x2135
            msg_id = 0xCEF00405      # Acknowledge
            msg_length = 24          # Header + 4 bytes
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = int(time.time()) % 65536
            
            message = struct.pack('<IIIIII', source_id, msg_id, msg_length, time_tag, seq_num, original_seq_num)
            
            self.tcp_clients[self.control_port].send(message)
            self.stats['acknowledge_sent'] += 1
            print(f"[{datetime.now()}] ✅ ACKNOWLEDGE sent")
            
        except Exception as e:
            print(f"[{datetime.now()}] Acknowledge error: {e}")
    
    def send_keep_alive(self):
        """Send Keep Alive via UDP"""
        if not self.udp_socket:
            return
            
        try:
            source_id = 0x2135
            msg_id = 0xCEF00400
            msg_length = 20
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = self.stats['keep_alive_sent'] + 1
            
            message = struct.pack('<IIIII', source_id, msg_id, msg_length, time_tag, seq_num)
            
            # Send to UDP port from TDP log
            try:
                self.udp_socket.sendto(message, ('localhost', 20071))
            except:
                pass
            
            self.stats['keep_alive_sent'] += 1
            
            if self.stats['keep_alive_sent'] % 10 == 0:
                print(f"[{datetime.now()}] 💓 Keep Alive #{self.stats['keep_alive_sent']} sent")
                
        except Exception as e:
            print(f"[{datetime.now()}] Keep Alive error: {e}")
    
    def send_keep_alive_response(self):
        """Send Keep Alive response"""
        if not self.udp_socket:
            return
            
        try:
            source_id = 0x2135
            msg_id = 0xCEF00400
            msg_length = 20
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = int(time.time()) % 65536
            
            message = struct.pack('<IIIII', source_id, msg_id, msg_length, time_tag, seq_num)
            
            self.udp_socket.sendto(message, ('localhost', 20071))
            print(f"[{datetime.now()}] 💓 Keep Alive RESPONSE sent")
            
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
        print(f"Control Port:            {self.control_port} ({'CONNECTED' if self.control_port in self.tcp_clients else 'DISCONNECTED'})")
        print(f"🎯 OPERATE State Requested: {self.operate_requested} 🎯")
        print(f"Status Message Count:    {self.status_message_count}")
        print("=" * 70)
    
    def start(self):
        """Start the force operate configuration"""
        self.running = True
        
        print("🚀 ELTA Force OPERATE Configuration")
        print("=" * 80)
        print(f"ELTA Simulator:       {self.elta_simulator_ip}")
        print(f"TCP Client Ports:     {self.tcp_client_ports}")
        print(f"Control Port:         {self.control_port}")
        print(f"UDP Port:             {self.udp_port}")
        print("🎯 FORCING OPERATE STATE TO RECEIVE TARGET DATA")
        print("=" * 80)
        
        # Start UDP handler
        udp_thread = threading.Thread(target=self.start_udp_handler)
        udp_thread.daemon = True
        udp_thread.start()
        
        # Start TCP clients - control port first
        ports = [self.control_port] + [p for p in self.tcp_client_ports if p != self.control_port]
        
        for port in ports:
            client_thread = threading.Thread(target=self.start_tcp_client, args=(port,))
            client_thread.daemon = True
            client_thread.start()
            time.sleep(0.5)
        
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
    config = EltaForceOperateConfig()
    config.start()