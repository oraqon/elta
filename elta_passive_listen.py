#!/usr/bin/env python3
"""
ELTA Passive Client - Listen Only
================================
Based on TDP crash analysis, this version:
1. Only establishes connections
2. Listens for messages from simulator
3. Does NOT send any messages initially
4. Only responds when the simulator requests something

This approach should prevent simulator crashes.
"""

import socket
import threading
import time
import struct
from datetime import datetime
from elta_message_decoder import EltaMessageDecoder

class EltaPassiveClient:
    def __init__(self, simulator_ip='132.4.6.202'):
        self.simulator_ip = simulator_ip
        
        # TCP Client ports for data reception
        self.tcp_client_ports = [23004, 30080, 6072, 9966, 30073]
        self.control_port = 30073
        self.udp_port = 32004
        
        # Connection management
        self.tcp_clients = {}
        self.udp_socket = None
        self.running = False
        self.decoder = EltaMessageDecoder()
        
        # State management
        self.current_state = "LISTENING"
        self.messages_received = []
        
        # Statistics
        self.stats = {
            'tcp_connections': 0,
            'total_messages': 0,
            'system_status_messages': 0,
            'target_data_messages': 0,
            'active_tcp_clients': 0,
            'unique_message_types': set()
        }
        
        print("👂 ELTA Passive Client - Listen Only Mode")
        print("=" * 60)
        print(f"ELTA Simulator:       {self.simulator_ip}")
        print(f"TCP Client Ports:     {self.tcp_client_ports}")
        print(f"Control Port:         {self.control_port}")
        print(f"UDP Port:             {self.udp_port}")
        print("🔇 NO MESSAGES SENT - LISTEN ONLY TO PREVENT CRASHES")
        print("=" * 60)

    def handle_tcp_client(self, port):
        """Handle TCP client connection - PASSIVE MODE"""
        reconnect_delay = 10  # Slower reconnection to be gentle
        
        while self.running:
            try:
                print(f"[{datetime.now()}] 🔌 CLIENT:{port} connecting (passive mode)")
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.settimeout(30)  # Longer timeout
                client_socket.connect((self.simulator_ip, port))
                
                self.tcp_clients[port] = client_socket
                self.stats['tcp_connections'] += 1
                self.stats['active_tcp_clients'] += 1
                
                print(f"[{datetime.now()}] ✅ CLIENT:{port} CONNECTED - LISTENING ONLY")
                
                if port == self.control_port:
                    print(f"🎯 Control port connected - PASSIVE MODE (no messages sent)")
                else:
                    print(f"📡 Data channel - PASSIVE LISTENING")
                
                # PASSIVE LISTENING - NO MESSAGES SENT
                while self.running:
                    try:
                        data = client_socket.recv(4096)
                        if not data:
                            print(f"CLIENT:{port} connection closed by simulator")
                            break
                            
                        if len(data) >= 20:  # Valid ELTA message
                            self.stats['total_messages'] += 1
                            
                            # Log raw data for analysis
                            print(f"\n[{port}] 📥 RECEIVED MESSAGE #{self.stats['total_messages']}")
                            print(f"Length: {len(data)} bytes")
                            print(f"Raw hex: {data[:60].hex().upper()}")
                            
                            # Try to parse header manually (safer than decoder)
                            try:
                                if len(data) >= 20:
                                    header = struct.unpack('<IIIII', data[:20])
                                    source_id, msg_id, msg_length, time_tag, seq_num = header
                                    
                                    print(f"Header: src=0x{source_id:08X}, msg=0x{msg_id:08X}, len={msg_length}, seq={seq_num}")
                                    
                                    # Log message types we see
                                    self.stats['unique_message_types'].add(msg_id)
                                    
                                    # Try decoder for detailed analysis (but don't crash if it fails)
                                    try:
                                        decoded = self.decoder.decode_message(data)
                                        if decoded and isinstance(decoded, dict):
                                            msg_type = decoded.get('message_type', 'UNKNOWN')
                                            print(f"Decoded type: {msg_type}")
                                            
                                            if 'SYSTEM_STATUS' in msg_type:
                                                self.stats['system_status_messages'] += 1
                                                system_state = decoded.get('system_state', 'UNKNOWN')
                                                print(f"📊 System State: {system_state}")
                                            
                                            elif any(target_type in msg_type for target_type in ['TARGET_REPORT', 'SINGLE_TARGET']):
                                                self.stats['target_data_messages'] += 1
                                                print(f"🎯 TARGET DATA: {msg_type}")
                                        
                                    except Exception as decode_error:
                                        print(f"Decode error (non-critical): {decode_error}")
                                        
                            except Exception as parse_error:
                                print(f"Header parse error: {parse_error}")
                            
                            print(f"[{port}] 👂 Message logged (passive mode)")
                            print("-" * 50)
                            
                    except socket.timeout:
                        # Timeout is OK in passive mode
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
        """Handle UDP communication - PASSIVE MODE"""
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.bind(('', self.udp_port))
            self.udp_socket.settimeout(5)
            print(f"[{datetime.now()}] 📡 UDP Handler active (passive mode) on port {self.udp_port}")
            
            while self.running:
                try:
                    data, addr = self.udp_socket.recvfrom(4096)
                    if len(data) >= 20:
                        self.stats['total_messages'] += 1
                        print(f"\n[UDP] 📥 RECEIVED MESSAGE from {addr}")
                        print(f"Length: {len(data)} bytes")
                        print(f"Raw hex: {data[:60].hex().upper()}")
                        
                        # Safe header parsing
                        try:
                            header = struct.unpack('<IIIII', data[:20])
                            source_id, msg_id, msg_length, time_tag, seq_num = header
                            print(f"UDP Header: src=0x{source_id:08X}, msg=0x{msg_id:08X}, len={msg_length}")
                            self.stats['unique_message_types'].add(msg_id)
                        except Exception as e:
                            print(f"UDP header parse error: {e}")
                            
                        print(f"[UDP] 👂 Message logged (passive mode)")
                        print("-" * 50)
                                
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"UDP error: {e}")
                    
        except Exception as e:
            print(f"❌ UDP Handler error: {e}")

    def print_stats(self):
        """Print communication statistics"""
        while self.running:
            time.sleep(20)  # Less frequent stats in passive mode
            print("\n📊 PASSIVE MODE STATISTICS:")
            print("=" * 70)
            print(f"TCP Client Connections:  {self.stats['tcp_connections']}")
            print(f"Total Messages Received: {self.stats['total_messages']}")
            print(f"System Status Messages:  {self.stats['system_status_messages']}")
            print(f"🎯 TARGET DATA MESSAGES: {self.stats['target_data_messages']} 🎯")
            print(f"Active TCP Clients:      {self.stats['active_tcp_clients']}")
            print(f"Control Port:            {self.control_port} ({'CONNECTED' if self.control_port in self.tcp_clients else 'DISCONNECTED'})")
            print(f"🎯 Current State: {self.current_state} 🎯")
            print(f"Unique Message Types Seen: {len(self.stats['unique_message_types'])}")
            
            if self.stats['unique_message_types']:
                print("Message Types (hex):")
                for msg_id in sorted(self.stats['unique_message_types']):
                    print(f"  - 0x{msg_id:08X}")
            
            print("👂 PASSIVE LISTENING MODE - NO MESSAGES SENT")
            print("=" * 70)

    def start(self):
        """Start the passive ELTA client"""
        self.running = True
        
        print("👂 Starting PASSIVE mode - connections only, no messages sent")
        print("This should prevent simulator crashes while we analyze traffic")
        
        # Start UDP handler
        udp_thread = threading.Thread(target=self.handle_udp)
        udp_thread.daemon = True
        udp_thread.start()
        
        # Start TCP clients with longer staggered connection times
        tcp_threads = []
        for i, port in enumerate(self.tcp_client_ports):
            thread = threading.Thread(target=self.handle_tcp_client, args=(port,))
            thread.daemon = True
            tcp_threads.append(thread)
            thread.start()
            time.sleep(2)  # Longer stagger for gentle connections
        
        # Start stats monitoring
        stats_thread = threading.Thread(target=self.print_stats)
        stats_thread.daemon = True
        stats_thread.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping passive client...")
            self.running = False
            
            # Clean shutdown
            if self.udp_socket:
                self.udp_socket.close()
                
            for client in list(self.tcp_clients.values()):
                try:
                    client.close()
                except:
                    pass
            
            # Final stats
            self.print_stats()
            print("✅ Stopped - Passive mode complete")

if __name__ == "__main__":
    client = EltaPassiveClient()
    client.start()