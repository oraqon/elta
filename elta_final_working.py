#!/usr/bin/env python3
"""
ELTA Final Working Configuration
===============================
Based on the working localhost version that successfully communicated with the simulator.
Using the exact message format and sequence that worked:

Key Details from Working Version:
- source_id = 0x2135 (not 0x00002135)
- STANDBY state = 2, OPERATE state = 4
- Message length = 60 for control messages (header + 40 payload)
- UDP for keep alive, TCP for control and status
- No status requests, just wait for status and acknowledge
"""

import socket
import threading
import time
import struct
from datetime import datetime
from elta_message_decoder import EltaMessageDecoder

class EltaFinalWorkingClient:
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
        
        # State management based on working version
        self.current_state = "DISCONNECTED"
        self.operate_requested = False
        self.standby_sent = False
        self.status_message_count = 0
        self.last_status_response = None
        
        # Statistics
        self.stats = {
            'tcp_connections': 0,
            'total_messages': 0,
            'system_status_messages': 0,
            'target_data_messages': 0,
            'acknowledgments_sent': 0,
            'keep_alive_sent': 0,
            'active_tcp_clients': 0
        }
        
        print("🎯 ELTA Final Working Configuration")
        print("=" * 60)
        print(f"ELTA Simulator:       {self.simulator_ip}")
        print(f"TCP Client Ports:     {self.tcp_client_ports}")
        print(f"Control Port:         {self.control_port}")
        print(f"UDP Port:             {self.udp_port}")
        print("✅ USING PROVEN WORKING MESSAGE FORMAT")
        print("=" * 60)

    def send_keep_alive_udp(self):
        """Send Keep Alive via UDP (as per working version)"""
        if not self.udp_socket:
            return
            
        try:
            source_id = 0x2135
            msg_id = 0xCEF00400
            msg_length = 20
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = self.stats['keep_alive_sent'] + 1
            
            message = struct.pack('<IIIII', source_id, msg_id, msg_length, time_tag, seq_num)
            
            # Send to multiple ports as per working version
            for port in [23004, 20071, 22230, 23014]:
                try:
                    self.udp_socket.sendto(message, (self.simulator_ip, port))
                except:
                    pass
            
            self.stats['keep_alive_sent'] += 1
            
            if self.stats['keep_alive_sent'] % 5 == 0:
                print(f"[{datetime.now()}] 💓 Keep Alive #{self.stats['keep_alive_sent']} sent via UDP")
                
        except Exception as e:
            print(f"[{datetime.now()}] Keep Alive error: {e}")

    def send_system_control_standby(self):
        """Send System Control for STANDBY state (working version format)"""
        if self.control_port not in self.tcp_clients:
            return
            
        try:
            print(f"[{datetime.now()}] 📤 Sending SYSTEM CONTROL (STANDBY) via TCP:{self.control_port}")
            
            source_id = 0x2135
            msg_id = 0xCEF00401      # System Control
            msg_length = 60          # As per working version
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = 1
            
            # System Control payload (exact format from working version)
            rdr_state = 2            # STANDBY
            mission_category = 0     # Default mission
            controls = b'\x00' * 8   # HFL/Radar controls
            freq_index = 1           # Frequency index
            spare = b'\x00' * 20     # Spare bytes
            
            payload = struct.pack('<II', rdr_state, mission_category) + controls + struct.pack('<I', freq_index) + spare
            message = struct.pack('<IIIII', source_id, msg_id, msg_length, time_tag, seq_num) + payload
            
            self.tcp_clients[self.control_port].send(message)
            print(f"[{datetime.now()}] ✅ SYSTEM CONTROL (STANDBY) sent")
            self.standby_sent = True
            self.current_state = "STANDBY_REQUESTED"
            
        except Exception as e:
            print(f"[{datetime.now()}] System Control (STANDBY) error: {e}")

    def send_system_control_operate(self):
        """Send System Control for OPERATE state (working version format)"""
        if self.control_port not in self.tcp_clients:
            return
            
        try:
            print(f"[{datetime.now()}] 📤 Sending SYSTEM CONTROL (OPERATE) via TCP:{self.control_port}")
            
            source_id = 0x2135
            msg_id = 0xCEF00401      # System Control
            msg_length = 60          # As per working version
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = int(time.time()) % 65536
            
            # System Control payload (exact format from working version)
            rdr_state = 4            # OPERATE (not 2!)
            mission_category = 0     # Default mission
            controls = b'\x00' * 8   # HFL/Radar controls
            freq_index = 1           # Frequency index
            spare = b'\x00' * 20     # Spare bytes
            
            payload = struct.pack('<II', rdr_state, mission_category) + controls + struct.pack('<I', freq_index) + spare
            message = struct.pack('<IIIII', source_id, msg_id, msg_length, time_tag, seq_num) + payload
            
            self.tcp_clients[self.control_port].send(message)
            print(f"[{datetime.now()}] ✅ SYSTEM CONTROL (OPERATE) sent")
            self.operate_requested = True
            self.current_state = "OPERATE_REQUESTED"
            
        except Exception as e:
            print(f"[{datetime.now()}] System Control (OPERATE) error: {e}")

    def send_acknowledge(self, original_seq_num):
        """Send acknowledgment (working version format)"""
        if self.control_port not in self.tcp_clients:
            return
            
        try:
            print(f"[{datetime.now()}] 📤 Sending ACKNOWLEDGE for seq #{original_seq_num}")
            
            source_id = 0x2135
            msg_id = 0xCEF00405      # Acknowledge message
            msg_length = 24          # Header + 4 bytes for original seq num
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = int(time.time()) % 65536
            
            message = struct.pack('<IIIIII', source_id, msg_id, msg_length, time_tag, seq_num, original_seq_num)
            
            self.tcp_clients[self.control_port].send(message)
            self.stats['acknowledgments_sent'] += 1
            print(f"[{datetime.now()}] ✅ ACKNOWLEDGE sent")
            
        except Exception as e:
            print(f"[{datetime.now()}] Acknowledge error: {e}")

    def handle_tcp_client(self, port):
        """Handle TCP client connection"""
        reconnect_delay = 5
        
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
                
                if port == self.control_port:
                    print(f"🎯 Control port connected - will send control messages based on status")
                else:
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
                            print(f"[{port}] 📥 Raw message: {len(data)} bytes - {data[:40].hex().upper()}")
                            decoded = self.decoder.decode_message(data)
                            
                            if decoded and isinstance(decoded, dict):
                                msg_type = decoded.get('message_type', 'UNKNOWN')
                                seq_num = decoded.get('sequence_number', 0)
                                
                                if 'SYSTEM_STATUS' in msg_type:
                                    self.stats['system_status_messages'] += 1
                                    self.status_message_count += 1
                                    self.last_status_response = decoded
                                    
                                    system_state = decoded.get('system_state', 'UNKNOWN')
                                    print(f"📊 System Status #{self.status_message_count}: {system_state}")
                                    
                                    # State machine logic (based on working version)
                                    if port == self.control_port:
                                        # Send acknowledge every 3rd status message
                                        if self.status_message_count % 3 == 0:
                                            self.send_acknowledge(seq_num)
                                        
                                        # State transition logic
                                        if not self.standby_sent and self.status_message_count >= 2:
                                            print("🎯 Transitioning to STANDBY state")
                                            time.sleep(1)
                                            self.send_system_control_standby()
                                        
                                        elif self.standby_sent and not self.operate_requested and self.status_message_count >= 6:
                                            print("🎯 Transitioning to OPERATE state")
                                            time.sleep(1)
                                            self.send_system_control_operate()
                                        
                                        # Check if we achieved OPERATE state
                                        if 'OPERATE' in str(system_state) or 'OPERATIONAL' in str(system_state):
                                            print("🎉 OPERATE STATE ACHIEVED! Listening for target data...")
                                            self.current_state = "OPERATE"
                                
                                elif any(target_type in msg_type for target_type in ['TARGET_REPORT', 'SINGLE_TARGET']):
                                    self.stats['target_data_messages'] += 1
                                    print(f"🎯 TARGET DATA RECEIVED: {msg_type}")
                                    print(f"   Targets: {decoded.get('target_count', 0)}")
                                    
                                    # Print first few targets for verification
                                    targets = decoded.get('targets', [])
                                    for i, target in enumerate(targets[:3]):
                                        print(f"   Target {i+1}: Range={target.get('range', 0):.1f}m, "
                                              f"Azimuth={target.get('azimuth', 0):.1f}°, "
                                              f"Class={target.get('target_class', 'Unknown')}")
                                
                                print(f"[{port}] 📨 {msg_type}")
                            else:
                                print(f"[{port}] ⚠️  Decode failed or returned non-dict: {type(decoded)} - {decoded}")
                            
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
        """Handle UDP communication and keep alive"""
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.bind(('', self.udp_port))
            self.udp_socket.settimeout(1)
            print(f"[{datetime.now()}] 📡 UDP Handler active on port {self.udp_port}")
            
            # Keep alive timer
            last_keep_alive = time.time()
            
            while self.running:
                try:
                    # Send keep alive every 10 seconds
                    if time.time() - last_keep_alive >= 10:
                        self.send_keep_alive_udp()
                        last_keep_alive = time.time()
                    
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
                    if "10040" not in str(e):  # Ignore message too long errors
                        print(f"UDP error: {e}")
                    
        except Exception as e:
            print(f"❌ UDP Handler error: {e}")

    def print_stats(self):
        """Print communication statistics"""
        while self.running:
            time.sleep(15)  # Print stats every 15 seconds
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
            print(f"Status Message Count:    {self.status_message_count}")
            print("=" * 70)

    def start(self):
        """Start the final working ELTA client"""
        self.running = True
        
        # Start UDP handler (for keep alive and data)
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
            time.sleep(0.5)  # Stagger connections
        
        # Start stats monitoring
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
    client = EltaFinalWorkingClient()
    client.start()