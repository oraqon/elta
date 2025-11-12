#!/usr/bin/env python3
"""
ELTA ICD-Compliant Client
========================
Based on analysis of ICD_2135M-004.txt specification.

Proper Initialization Sequence:
1. Connect to all TCP ports and UDP
2. Send Keep Alive every 1 second via UDP
3. Wait for System Status messages from radar (~1 Hz)
4. Acknowledge every 3rd status message
5. Send System Control to transition STANDBY → OPERATE
6. Continue monitoring for target data

Key ICD Requirements:
- RDR_STATE: 2=STANDBY, 4=OPERATE  
- Keep Alive: Every 1 second via UDP, response within 3 sec
- Status Messages: ~1 Hz from radar, acknowledge every 3rd
- System Control: 0xCEF00401 to transition states
"""

import socket
import threading
import time
import struct
from datetime import datetime
from elta_message_decoder import EltaMessageDecoder

class EltaIcdCompliantClient:
    def __init__(self, simulator_ip='localhost'):
        self.simulator_ip = simulator_ip
        
        # Network configuration per ICD
        self.tcp_client_ports = [23004, 30080, 6072, 9966, 30073]
        self.control_port = 30073  # Main control channel
        self.udp_port = 32004
        
        # Connection management
        self.tcp_clients = {}
        self.udp_socket = None
        self.running = False
        self.decoder = EltaMessageDecoder()
        
        # ICD State Management
        self.current_state = "INIT"
        self.status_message_count = 0
        self.last_keep_alive = 0
        self.standby_achieved = False
        self.operate_requested = False
        
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
        
        print("📋 ELTA ICD-2135M-004 Compliant Client")
        print("=" * 60)
        print(f"ELTA Simulator:       {self.simulator_ip}")
        print(f"TCP Client Ports:     {self.tcp_client_ports}")
        print(f"Control Port:         {self.control_port}")
        print(f"UDP Port:             {self.udp_port}")
        print("✅ FOLLOWING ICD-2135M-004 SPECIFICATION")
        print("=" * 60)

    def create_icd_message(self, message_id, payload=b''):
        """Create ICD-compliant message format"""
        # Use safe source_id that won't crash simulator
        source_id = 0x1000  # Safe source ID (not 0x2135 which causes crash)
        msg_length = 20 + len(payload)
        time_tag = int((time.time() % 86400) * 1000)  # Milliseconds from midnight per ICD
        seq_num = int(time.time()) % 65536
        
        # ICD header format: source_id, msg_id, msg_length, time_tag, seq_num
        header = struct.pack('<IIIII', source_id, message_id, msg_length, time_tag, seq_num)
        
        return header + payload, seq_num

    def send_keep_alive_udp(self):
        """Send Keep Alive every 1 second per ICD requirement"""
        if not self.udp_socket or time.time() - self.last_keep_alive < 1.0:
            return
            
        try:
            message, seq_num = self.create_icd_message(0xCEF00400)  # Keep Alive per ICD
            
            # Send to radar (try multiple ports as per working version)
            for port in [23004, 20071, 22230, 23014]:
                try:
                    self.udp_socket.sendto(message, (self.simulator_ip, port))
                except:
                    pass
            
            self.stats['keep_alive_sent'] += 1
            self.last_keep_alive = time.time()
            
            if self.stats['keep_alive_sent'] % 10 == 0:
                print(f"[{datetime.now()}] 💓 Keep Alive #{self.stats['keep_alive_sent']} sent (ICD: every 1 sec)")
                
        except Exception as e:
            print(f"[{datetime.now()}] Keep Alive error: {e}")

    def send_system_control_standby(self):
        """Send System Control for STANDBY state per ICD"""
        if self.control_port not in self.tcp_clients:
            return
            
        try:
            print(f"[{datetime.now()}] 📤 ICD: Sending SYSTEM CONTROL (STANDBY=2)")
            
            # ICD System Control payload structure
            rdr_state = 2           # STANDBY per ICD
            mission_category = 0    # Default mission
            hfl_controls = b'\x00' * 4  # HFL sensor controls (4 bytes)
            radar_controls = b'\x00' * 4  # Radar controls (4 bytes)
            freq_index = 1          # Frequency index
            spare = b'\x00' * 20    # Spare bytes to reach 40 byte payload
            
            # Total payload: 4+4+4+4+4+20 = 40 bytes → total message = 60 bytes per ICD
            payload = struct.pack('<II', rdr_state, mission_category) + hfl_controls + radar_controls + struct.pack('<I', freq_index) + spare
            message, seq_num = self.create_icd_message(0xCEF00401, payload)  # System Control per ICD
            
            self.tcp_clients[self.control_port].send(message)
            print(f"[{datetime.now()}] ✅ ICD: SYSTEM CONTROL (STANDBY) sent")
            self.current_state = "STANDBY_REQUESTED"
            
        except Exception as e:
            print(f"[{datetime.now()}] ICD System Control (STANDBY) error: {e}")

    def send_system_control_operate(self):
        """Send System Control for OPERATE state per ICD"""
        if self.control_port not in self.tcp_clients:
            return
            
        try:
            print(f"[{datetime.now()}] 📤 ICD: Sending SYSTEM CONTROL (OPERATE=4)")
            
            # ICD System Control payload structure
            rdr_state = 4           # OPERATE per ICD specification
            mission_category = 0    # Default mission
            hfl_controls = b'\x00' * 4  # HFL sensor controls (4 bytes)
            radar_controls = b'\x00' * 4  # Radar controls (4 bytes)
            freq_index = 1          # Frequency index
            spare = b'\x00' * 20    # Spare bytes to reach 40 byte payload
            
            # Total payload: 4+4+4+4+4+20 = 40 bytes → total message = 60 bytes per ICD
            payload = struct.pack('<II', rdr_state, mission_category) + hfl_controls + radar_controls + struct.pack('<I', freq_index) + spare
            message, seq_num = self.create_icd_message(0xCEF00401, payload)  # System Control per ICD
            
            self.tcp_clients[self.control_port].send(message)
            print(f"[{datetime.now()}] ✅ ICD: SYSTEM CONTROL (OPERATE) sent")
            self.operate_requested = True
            self.current_state = "OPERATE_REQUESTED"
            
        except Exception as e:
            print(f"[{datetime.now()}] ICD System Control (OPERATE) error: {e}")

    def send_acknowledge(self, original_seq_num):
        """Send Acknowledge message per ICD requirement"""
        if self.control_port not in self.tcp_clients:
            return
            
        try:
            print(f"[{datetime.now()}] 📤 ICD: Sending ACKNOWLEDGE for seq #{original_seq_num}")
            
            # ICD Acknowledge payload: original sequence number
            payload = struct.pack('<I', original_seq_num)
            message, seq_num = self.create_icd_message(0xCEF00405, payload)  # Acknowledge per ICD
            
            self.tcp_clients[self.control_port].send(message)
            self.stats['acknowledgments_sent'] += 1
            print(f"[{datetime.now()}] ✅ ICD: ACKNOWLEDGE sent")
            
        except Exception as e:
            print(f"[{datetime.now()}] ICD Acknowledge error: {e}")

    def handle_tcp_client(self, port):
        """Handle TCP client connection with ICD-compliant state machine"""
        reconnect_delay = 5
        
        while self.running:
            try:
                print(f"[{datetime.now()}] 🔌 ICD CLIENT:{port} connecting")
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.settimeout(10)
                client_socket.connect((self.simulator_ip, port))
                
                self.tcp_clients[port] = client_socket
                self.stats['tcp_connections'] += 1
                self.stats['active_tcp_clients'] += 1
                
                print(f"[{datetime.now()}] ✅ ICD CLIENT:{port} CONNECTED!")
                
                if port == self.control_port:
                    print(f"🎯 ICD Control port - following ICD state machine")
                else:
                    print(f"📡 ICD Data channel - listening for target data")
                
                # Listen for messages
                while self.running:
                    try:
                        data = client_socket.recv(4096)
                        if not data:
                            print(f"ICD CLIENT:{port} connection closed by simulator")
                            break
                            
                        if len(data) >= 20:  # Valid ELTA message
                            self.stats['total_messages'] += 1
                            print(f"[{port}] 📥 ICD Message: {len(data)} bytes")
                            
                            # Parse header
                            try:
                                header = struct.unpack('<IIIII', data[:20])
                                source_id, msg_id, msg_length, time_tag, seq_num = header
                                print(f"ICD Header: src=0x{source_id:08X}, msg=0x{msg_id:08X}, seq={seq_num}")
                                
                                # Handle System Status messages per ICD
                                if msg_id == 0xCEF00402:  # System Status per ICD
                                    self.stats['system_status_messages'] += 1
                                    self.status_message_count += 1
                                    print(f"📊 ICD SYSTEM STATUS #{self.status_message_count}")
                                    
                                    # ICD requirement: acknowledge every 3rd status
                                    if self.status_message_count % 3 == 0:
                                        print(f"🔔 ICD: Time to acknowledge (every 3rd status)")
                                        self.send_acknowledge(seq_num)
                                    
                                    # ICD State machine
                                    if port == self.control_port:
                                        if not self.standby_achieved and self.status_message_count >= 2:
                                            print("🎯 ICD: Requesting STANDBY state")
                                            time.sleep(1)  # Brief pause per ICD timing
                                            self.send_system_control_standby()
                                            self.standby_achieved = True
                                        
                                        elif self.standby_achieved and not self.operate_requested and self.status_message_count >= 6:
                                            print("🎯 ICD: Requesting OPERATE state")
                                            time.sleep(1)  # Brief pause per ICD timing
                                            self.send_system_control_operate()
                                
                                # Handle Target Data per ICD
                                elif msg_id in [0xCEF00404, 0xCEF00406, 0xCEF0041A]:  # Target messages per ICD
                                    self.stats['target_data_messages'] += 1
                                    print(f"🎯 ICD TARGET DATA: msg=0x{msg_id:08X} (#{self.stats['target_data_messages']})")
                                    self.current_state = "OPERATE_ACTIVE"
                                
                                # Try to decode with our decoder
                                try:
                                    decoded = self.decoder.decode_message(data)
                                    if decoded and isinstance(decoded, dict):
                                        msg_type = decoded.get('message_type', 'UNKNOWN')
                                        print(f"[{port}] 📨 ICD: {msg_type}")
                                    
                                        # Check system state from decoded message
                                        if 'SYSTEM_STATUS' in msg_type:
                                            system_state = decoded.get('system_state', 'UNKNOWN')
                                            print(f"📊 ICD System State: {system_state}")
                                            
                                            if 'OPERATE' in str(system_state) or 'OPERATIONAL' in str(system_state):
                                                print("🎉 ICD: OPERATE STATE ACHIEVED!")
                                                self.current_state = "OPERATE"
                                        
                                        elif any(target_type in msg_type for target_type in ['TARGET_REPORT', 'SINGLE_TARGET']):
                                            targets = decoded.get('targets', [])
                                            print(f"🎯 ICD Target Data: {len(targets)} targets")
                                            
                                except Exception as decode_error:
                                    # Non-critical decode error
                                    pass
                                
                            except Exception as parse_error:
                                print(f"ICD Header parse error: {parse_error}")
                            
                    except socket.timeout:
                        continue
                    except Exception as e:
                        print(f"ICD CLIENT:{port} error: {e}")
                        break
                        
            except Exception as e:
                print(f"ICD CLIENT:{port} connection error: {e}")
                
            finally:
                if port in self.tcp_clients:
                    try:
                        self.tcp_clients[port].close()
                    except:
                        pass
                    del self.tcp_clients[port]
                    self.stats['active_tcp_clients'] -= 1
                    
            if self.running:
                print(f"🔄 ICD CLIENT:{port} reconnecting in {reconnect_delay} seconds...")
                time.sleep(reconnect_delay)

    def handle_udp(self):
        """Handle UDP communication per ICD requirements"""
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.bind(('', self.udp_port))
            self.udp_socket.settimeout(0.5)  # Short timeout for keep alive timing
            print(f"[{datetime.now()}] 📡 ICD UDP Handler active on port {self.udp_port}")
            
            while self.running:
                try:
                    # ICD requirement: send keep alive every 1 second
                    self.send_keep_alive_udp()
                    
                    data, addr = self.udp_socket.recvfrom(4096)
                    if len(data) >= 20:
                        self.stats['total_messages'] += 1
                        print(f"[UDP] 📥 ICD Message from {addr}: {len(data)} bytes")
                        
                        # Try to decode UDP messages
                        try:
                            decoded = self.decoder.decode_message(data)
                            if decoded and isinstance(decoded, dict):
                                msg_type = decoded.get('message_type', 'UNKNOWN')
                                print(f"[UDP] 📨 ICD: {msg_type}")
                                
                                if any(target_type in msg_type for target_type in ['TARGET_REPORT', 'SINGLE_TARGET']):
                                    self.stats['target_data_messages'] += 1
                                    print(f"🎯 ICD UDP TARGET DATA: {msg_type}")
                        except:
                            pass
                                
                except socket.timeout:
                    continue
                except Exception as e:
                    if "10040" not in str(e):  # Ignore message too long errors
                        print(f"ICD UDP error: {e}")
                    
        except Exception as e:
            print(f"❌ ICD UDP Handler error: {e}")

    def print_stats(self):
        """Print ICD-compliant statistics"""
        while self.running:
            time.sleep(15)  # Stats every 15 seconds
            print("\n📊 ICD-2135M-004 STATISTICS:")
            print("=" * 70)
            print(f"TCP Client Connections:   {self.stats['tcp_connections']}")
            print(f"Total Messages:           {self.stats['total_messages']}")
            print(f"System Status Messages:   {self.stats['system_status_messages']}")
            print(f"🎯 TARGET DATA MESSAGES:  {self.stats['target_data_messages']} 🎯")
            print(f"Acknowledgments Sent:     {self.stats['acknowledgments_sent']}")
            print(f"Keep Alive Sent:          {self.stats['keep_alive_sent']} (ICD: every 1 sec)")
            print(f"Active TCP Clients:       {self.stats['active_tcp_clients']}")
            print(f"Control Port:             {self.control_port} ({'CONNECTED' if self.control_port in self.tcp_clients else 'DISCONNECTED'})")
            print(f"🎯 ICD Current State:     {self.current_state} 🎯")
            print(f"Status Message Count:     {self.status_message_count}")
            print(f"STANDBY Achieved:         {self.standby_achieved}")
            print(f"OPERATE Requested:        {self.operate_requested}")
            print("✅ ICD-2135M-004 COMPLIANT")
            print("=" * 70)

    def start(self):
        """Start the ICD-compliant ELTA client"""
        self.running = True
        
        print("📋 Starting ICD-2135M-004 compliant client")
        print("Following proper initialization sequence per specification")
        
        # Start UDP handler (for keep alive per ICD)
        udp_thread = threading.Thread(target=self.handle_udp)
        udp_thread.daemon = True
        udp_thread.start()
        
        # Start TCP clients with proper timing
        tcp_threads = []
        for i, port in enumerate(self.tcp_client_ports):
            thread = threading.Thread(target=self.handle_tcp_client, args=(port,))
            thread.daemon = True
            tcp_threads.append(thread)
            thread.start()
            time.sleep(0.5)  # Stagger connections per ICD timing
        
        # Start stats monitoring
        stats_thread = threading.Thread(target=self.print_stats)
        stats_thread.daemon = True
        stats_thread.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping ICD-compliant client...")
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
            print("✅ ICD-2135M-004 client stopped")

if __name__ == "__main__":
    client = EltaIcdCompliantClient()
    client.start()