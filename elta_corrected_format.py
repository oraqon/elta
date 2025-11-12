#!/usr/bin/env python3
"""
ELTA Corrected Message Format
=============================
Using the correct message format as established in the working localhost version:
source_id, msg_id, msg_length, time_tag, seq_num

Key Fixes:
- Correct header format (source_id first, not sync pattern)
- Proper sequence number management
- Gentle initialization following ICD sequence
"""

import socket
import threading
import time
import struct
from datetime import datetime
from elta_message_decoder import EltaMessageDecoder

class EltaCorrectedClient:
    def __init__(self, simulator_ip='localhost'):
        self.simulator_ip = simulator_ip
        
        # TCP Client ports for data reception
        self.tcp_client_ports = [23004, 30080, 6072, 9966, 30073]
        self.control_port = 30073  # Main control channel
        self.udp_port = 32004
        
        # Connection management
        self.tcp_clients = {}
        self.udp_socket = None
        self.running = False
        self.decoder = EltaMessageDecoder()
        
        # Message sequencing
        self.sequence_number = 1
        
        # State management
        self.current_state = "DISCONNECTED"
        self.operate_requested = False
        self.last_status_response = None
        
        # Statistics
        self.stats = {
            'tcp_connections': 0,
            'total_messages': 0,
            'system_status_messages': 0,
            'target_data_messages': 0,
            'acknowledgments_sent': 0,
            'keep_alive_sent': 0,
            'active_tcp_clients': 0,
            'status_message_count': 0
        }
        
        print("🔧 ELTA Corrected Message Format Client")
        print("=" * 60)
        print(f"ELTA Simulator:       {self.simulator_ip}")
        print(f"TCP Client Ports:     {self.tcp_client_ports}")
        print(f"Control Port:         {self.control_port}")
        print(f"UDP Port:             {self.udp_port}")
        print("✅ USING CORRECT MESSAGE FORMAT")
        print("=" * 60)

    def create_message(self, message_id, data=b''):
        """Create properly formatted ELTA message with correct header format"""
        source_id = 0x00002135        # Source ID (our system)
        msg_length = 20 + len(data)   # Header (20) + payload
        # Use milliseconds since epoch, modulo to fit in 32-bit unsigned int
        time_tag = int(time.time() * 1000) % 0xFFFFFFFF
        seq_num = self.sequence_number
        
        self.sequence_number += 1
        if self.sequence_number > 0xFFFFFFFF:
            self.sequence_number = 1
        
        # Correct format: source_id, msg_id, msg_length, time_tag, seq_num
        header = struct.pack('<IIIII', 
                           source_id,      # Source ID first (not sync pattern!)
                           message_id,     # Message ID
                           msg_length,     # Message length
                           time_tag,       # Time tag
                           seq_num         # Sequence number
                           )
        return header + data

    def send_keep_alive(self, client_socket):
        """Send KEEP_ALIVE message (proper handshake start)"""
        try:
            message = self.create_message(0xCEF00400)  # KEEP_ALIVE
            client_socket.send(message)
            print(f"📤 KEEP_ALIVE sent")
            return True
        except Exception as e:
            print(f"❌ KEEP_ALIVE error: {e}")
            return False

    def send_system_control_standby(self, client_socket):
        """Send SYSTEM_CONTROL for STANDBY state"""
        try:
            # STANDBY control data (proper format from working version)
            rdr_state = 1  # STANDBY
            mission_category = 0
            controls = b'\x00' * 12  # 12 bytes of control data
            freq_index = 0
            spare = b'\x00' * 4  # 4 bytes spare
            
            payload = struct.pack('<II', rdr_state, mission_category) + controls + struct.pack('<I', freq_index) + spare
            message = self.create_message(0xCEF00401, payload)  # SYSTEM_CONTROL
            client_socket.send(message)
            print(f"📤 SYSTEM CONTROL (STANDBY) sent")
            return True
        except Exception as e:
            print(f"❌ SYSTEM CONTROL (STANDBY) error: {e}")
            return False

    def send_system_control_operate(self, client_socket):
        """Send SYSTEM_CONTROL for OPERATE state"""
        try:
            # OPERATE control data (proper format from working version)
            rdr_state = 2  # OPERATE
            mission_category = 0
            controls = b'\x00' * 12  # 12 bytes of control data
            freq_index = 0
            spare = b'\x00' * 4  # 4 bytes spare
            
            payload = struct.pack('<II', rdr_state, mission_category) + controls + struct.pack('<I', freq_index) + spare
            message = self.create_message(0xCEF00401, payload)  # SYSTEM_CONTROL
            client_socket.send(message)
            print(f"📤 SYSTEM CONTROL (OPERATE) sent")
            self.operate_requested = True
            return True
        except Exception as e:
            print(f"❌ SYSTEM CONTROL (OPERATE) error: {e}")
            return False

    def request_system_status(self, client_socket):
        """Request system status"""
        try:
            message = self.create_message(0xCEF00402)  # SYSTEM_STATUS_REQUEST
            client_socket.send(message)
            print(f"📤 Status request sent")
            return True
        except Exception as e:
            print(f"❌ Status request error: {e}")
            return False

    def send_acknowledge(self, client_socket, original_seq_num):
        """Send acknowledgment message"""
        try:
            # Acknowledge payload contains original sequence number
            payload = struct.pack('<I', original_seq_num)
            message = self.create_message(0xCEF00405, payload)  # ACKNOWLEDGE
            client_socket.send(message)
            self.stats['acknowledgments_sent'] += 1
            print(f"📤 ACKNOWLEDGE sent for seq #{original_seq_num}")
            return True
        except Exception as e:
            print(f"❌ ACKNOWLEDGE error: {e}")
            return False

    def handle_tcp_client(self, port):
        """Handle TCP client connection with corrected message format"""
        reconnect_delay = 5
        initialization_done = False
        
        while self.running:
            try:
                print(f"[{datetime.now()}] 🔌 CLIENT:{port} connecting to {self.simulator_ip}:{port}")
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.settimeout(10)
                client_socket.connect((self.simulator_ip, port))
                
                self.tcp_clients[port] = client_socket
                self.stats['tcp_connections'] += 1
                self.stats['active_tcp_clients'] += 1
                
                print(f"[{datetime.now()}] ✅ CLIENT:{port} CONNECTED!")
                
                # Gentle initialization sequence ONLY for control port
                if port == self.control_port and not initialization_done:
                    print(f"🎯 Control port - starting corrected initialization")
                    time.sleep(1)  # Let connection stabilize
                    
                    # Step 1: Send KEEP_ALIVE (proper handshake)
                    print("📝 Step 1: Sending KEEP_ALIVE")
                    if self.send_keep_alive(client_socket):
                        time.sleep(2)  # Wait for response/stabilization
                        
                        # Step 2: Request current status
                        print("📝 Step 2: Requesting system status")
                        if self.request_system_status(client_socket):
                            time.sleep(3)  # Wait for status response
                            
                            # Step 3: Request STANDBY state
                            print("📝 Step 3: Requesting STANDBY state")
                            if self.send_system_control_standby(client_socket):
                                self.current_state = "STANDBY_REQUESTED"
                                time.sleep(5)  # Wait for STANDBY to be established
                                
                                # Step 4: Request status again to confirm STANDBY
                                print("📝 Step 4: Confirming STANDBY state")
                                if self.request_system_status(client_socket):
                                    time.sleep(3)  # Wait for confirmation
                                    
                                    # Step 5: Request OPERATE state (gently)
                                    print("📝 Step 5: Requesting OPERATE state")
                                    if self.send_system_control_operate(client_socket):
                                        self.current_state = "OPERATE_REQUESTED"
                                        print("🎯 OPERATE STATE REQUESTED WITH CORRECT FORMAT!")
                                        initialization_done = True
                
                elif port != self.control_port:
                    print(f"📡 Data channel - listening for messages")
                
                # Listen for messages
                while self.running:
                    try:
                        data = client_socket.recv(4096)
                        if not data:
                            print(f"CLIENT:{port} connection closed by simulator")
                            break
                            
                        if len(data) >= 20:  # Valid ELTA message
                            self.stats['total_messages'] += 1
                            decoded = self.decoder.decode_message(data)
                            
                            if decoded:
                                msg_type = decoded.get('message_type', 'UNKNOWN')
                                seq_num = decoded.get('sequence_number', 0)
                                
                                if 'SYSTEM_STATUS' in msg_type:
                                    self.stats['system_status_messages'] += 1
                                    self.last_status_response = decoded
                                    system_state = decoded.get('system_state', 'UNKNOWN')
                                    print(f"📊 System State: {system_state}")
                                    
                                    # Send acknowledgment for system status
                                    if port == self.control_port:
                                        self.send_acknowledge(client_socket, seq_num)
                                    
                                    # If we're in OPERATE state, celebrate!
                                    if 'OPERATE' in str(system_state) or 'OPERATIONAL' in str(system_state):
                                        print("🎉 OPERATE STATE ACHIEVED! Listening for target data...")
                                        self.current_state = "OPERATE"
                                
                                elif any(target_type in msg_type for target_type in ['TARGET_REPORT', 'SINGLE_TARGET']):
                                    self.stats['target_data_messages'] += 1
                                    print(f"🎯 TARGET DATA RECEIVED: {msg_type}")
                                    print(f"   Data: {decoded}")
                                
                                print(f"[{port}] 📨 {msg_type}")
                            
                    except socket.timeout:
                        continue
                    except Exception as e:
                        print(f"CLIENT:{port} error: {e}")
                        break
                        
            except Exception as e:
                print(f"CLIENT:{port} connection error: {e}")
                
            finally:
                if port in self.tcp_clients:
                    try:
                        self.tcp_clients[port].close()
                    except:
                        pass
                    del self.tcp_clients[port]
                    self.stats['active_tcp_clients'] -= 1
                    
            if self.running:
                print(f"🔄 CLIENT:{port} reconnecting in {reconnect_delay} seconds...")
                time.sleep(reconnect_delay)

    def handle_udp(self):
        """Handle UDP communication"""
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.bind(('', self.udp_port))
            self.udp_socket.settimeout(1)
            print(f"[{datetime.now()}] 📡 UDP Handler active on port {self.udp_port}")
            
            while self.running:
                try:
                    data, addr = self.udp_socket.recvfrom(4096)
                    if len(data) >= 20:
                        self.stats['total_messages'] += 1
                        decoded = self.decoder.decode_message(data)
                        if decoded:
                            msg_type = decoded.get('message_type', 'UNKNOWN')
                            print(f"[UDP] 📨 {msg_type} from {addr}")
                            
                            if any(target_type in msg_type for target_type in ['TARGET_REPORT', 'SINGLE_TARGET']):
                                self.stats['target_data_messages'] += 1
                                print(f"🎯 UDP TARGET DATA: {msg_type}")
                                
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"UDP error: {e}")
                    
        except Exception as e:
            print(f"❌ UDP Handler error: {e}")

    def status_monitor(self):
        """Gentle status monitoring"""
        while self.running:
            time.sleep(20)  # Check every 20 seconds (very gentle)
            
            if self.control_port in self.tcp_clients and self.current_state in ["STANDBY_REQUESTED", "OPERATE_REQUESTED"]:
                try:
                    self.request_system_status(self.tcp_clients[self.control_port])
                except:
                    pass

    def print_stats(self):
        """Print communication statistics"""
        while self.running:
            time.sleep(10)  # Print stats every 10 seconds
            print("\n📊 COMMUNICATION STATISTICS:")
            print("=" * 70)
            print(f"TCP Client Connections:  {self.stats['tcp_connections']}")
            print(f"Total Messages:          {self.stats['total_messages']}")
            print(f"System Status Messages:  {self.stats['system_status_messages']}")
            print(f"🎯 TARGET DATA MESSAGES: {self.stats['target_data_messages']} 🎯")
            print(f"Acknowledgments Sent:    {self.stats['acknowledgments_sent']}")
            print(f"Keep Alive Sent:         {self.stats['keep_alive_sent']}")
            print(f"Active TCP Clients:      {self.stats['active_tcp_clients']}")
            print(f"Control Port:            {self.control_port} ({'CONNECTED' if self.control_port in self.tcp_clients else 'DISCONNECTED'})")
            print(f"🎯 Current State: {self.current_state} 🎯")
            print(f"🎯 OPERATE Requested: {self.operate_requested} 🎯")
            print(f"Status Message Count:    {self.stats['status_message_count']}")
            print("=" * 70)

    def start(self):
        """Start the corrected ELTA client"""
        self.running = True
        
        # Start UDP handler
        udp_thread = threading.Thread(target=self.handle_udp)
        udp_thread.daemon = True
        udp_thread.start()
        
        # Start TCP clients with staggered connection times
        tcp_threads = []
        for i, port in enumerate(self.tcp_client_ports):
            thread = threading.Thread(target=self.handle_tcp_client, args=(port,))
            thread.daemon = True
            tcp_threads.append(thread)
            thread.start()
            time.sleep(0.5)  # Stagger connections gently
        
        # Start monitoring threads
        status_thread = threading.Thread(target=self.status_monitor)
        status_thread.daemon = True
        status_thread.start()
        
        stats_thread = threading.Thread(target=self.print_stats)
        stats_thread.daemon = True
        stats_thread.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping...")
            self.running = False
            
            # Clean shutdown
            if self.udp_socket:
                self.udp_socket.close()
                
            for client in list(self.tcp_clients.values()):
                try:
                    client.close()
                except:
                    pass
            
            self.print_stats()
            print("✅ Stopped")

if __name__ == "__main__":
    client = EltaCorrectedClient()
    client.start()