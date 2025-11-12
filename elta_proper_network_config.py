#!/usr/bin/env python3
"""
ELTA Proper Network Configuration
Based on installation guide network settings:
- ELTA Simulator: 132.4.6.202
- Customer Computer: 132.4.6.205 (your machine)
- TCP Client Bind Ports: 22230 and 30080
"""

import socket
import struct
import threading
import time
from datetime import datetime
from elta_message_decoder import EltaMessageDecoder

class EltaProperNetworkConfig:
    def __init__(self):
        # Network configuration from installation guide
        self.elta_simulator_ip = '132.4.6.202'  # ELTA simulator IP
        self.customer_ip = '132.4.6.205'        # Your machine IP
        self.tcp_client_ports = [22230, 30080]   # TCP client bind ports
        self.udp_port = 32004                    # Standard UDP port
        
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
            'total_messages': 0
        }
    
    def check_network_config(self):
        """Check current network configuration"""
        print("🔍 NETWORK CONFIGURATION CHECK")
        print("=" * 50)
        
        try:
            # Get local IP addresses
            hostname = socket.gethostname()
            local_ips = socket.gethostbyname_ex(hostname)[2]
            
            print(f"Hostname: {hostname}")
            print(f"Local IPs: {local_ips}")
            
            # Check if customer IP is configured
            customer_ip_found = self.customer_ip in local_ips
            print(f"Customer IP ({self.customer_ip}) configured: {'✅' if customer_ip_found else '❌'}")
            
            if not customer_ip_found:
                print(f"⚠️  WARNING: Your machine should be configured with IP {self.customer_ip}")
                print("   Please set your network adapter to this static IP address")
                
            # Test connectivity to ELTA simulator
            print(f"\nTesting connectivity to ELTA simulator ({self.elta_simulator_ip})...")
            
            import subprocess
            try:
                result = subprocess.run(['ping', '-n', '1', self.elta_simulator_ip], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    print(f"✅ Can ping ELTA simulator at {self.elta_simulator_ip}")
                else:
                    print(f"❌ Cannot ping ELTA simulator at {self.elta_simulator_ip}")
            except:
                print(f"❌ Ping test failed")
            
        except Exception as e:
            print(f"❌ Network check error: {e}")
        
        print("=" * 50)
    
    def start_udp_handler(self):
        """Handle UDP communication"""
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to customer IP and UDP port
            self.udp_socket.bind((self.customer_ip, self.udp_port))
            self.udp_socket.settimeout(1.0)
            
            print(f"[{datetime.now()}] 📡 UDP Handler bound to {self.customer_ip}:{self.udp_port}")
            
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
            print("💡 Make sure your machine IP is set to 132.4.6.205")
        finally:
            if self.udp_socket:
                self.udp_socket.close()
    
    def start_tcp_handler(self, port):
        """Handle TCP communication on specific port"""
        port_name = f"TCP:{port}"
        
        while self.running:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                
                # Bind to customer IP and specific port
                sock.bind((self.customer_ip, port))
                sock.settimeout(5.0)
                
                print(f"[{datetime.now()}] 🔌 {port_name} bound to {self.customer_ip}:{port}")
                
                # Connect to ELTA simulator
                sock.connect((self.elta_simulator_ip, port))
                
                print(f"[{datetime.now()}] ✅ {port_name} connected to {self.elta_simulator_ip}:{port}")
                
                self.tcp_sockets[port] = sock
                
                # Listen for messages
                buffer = b''
                while self.running:
                    try:
                        data = sock.recv(4096)
                        if not data:
                            print(f"[{datetime.now()}] {port_name} connection closed")
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
        
        print(f"\n[{datetime.now()}] 📡 Message from {source}")
        print(f"Length: {len(data)} bytes")
        print(f"Hex: {data.hex().upper()}")
        
        try:
            if len(data) >= 20:
                source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', data[:20])
                
                # Check for important message types
                if msg_id == 0xCEF00403:  # System Status
                    self.stats['status_received'] += 1
                    print(f"🎯 SYSTEM STATUS MESSAGE #{self.stats['status_received']}")
                elif msg_id in [0xCEF00404, 0xCEF00406, 0xCEF0041A]:  # Target data
                    self.stats['target_messages'] += 1
                    print(f"🚨 TARGET DATA MESSAGE! (Total: {self.stats['target_messages']})")
                
                # Decode message
                decoded = self.decoder.decode_message(data)
                print(decoded)
                
        except Exception as e:
            print(f"Error processing message: {e}")
        
        print("-" * 70)
    
    def send_keep_alive(self):
        """Send Keep Alive message"""
        if not self.udp_socket:
            return
            
        try:
            source_id = 0x2135
            msg_id = 0xCEF00400
            msg_length = 20
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = self.stats['keep_alive_sent'] + 1
            
            message = struct.pack('<IIIII', source_id, msg_id, msg_length, time_tag, seq_num)
            
            # Send to ELTA simulator
            self.udp_socket.sendto(message, (self.elta_simulator_ip, self.udp_port))
            
            self.stats['keep_alive_sent'] += 1
            
            if self.stats['keep_alive_sent'] % 10 == 0:
                print(f"[{datetime.now()}] 💓 Keep Alive #{self.stats['keep_alive_sent']} sent to {self.elta_simulator_ip}")
                
        except Exception as e:
            print(f"[{datetime.now()}] Keep Alive error: {e}")
    
    def send_system_control(self, port):
        """Send System Control command"""
        if port not in self.tcp_sockets:
            return
            
        try:
            print(f"[{datetime.now()}] 📤 Sending SYSTEM CONTROL via TCP:{port}")
            
            source_id = 0x2135
            msg_id = 0xCEF00401
            msg_length = 60
            time_tag = int((time.time() % 86400) * 1000)
            seq_num = 1
            
            # System Control payload (OPERATE state)
            rdr_state = 4  # OPERATE
            mission_category = 0
            controls = b'\x00' * 8  # HFL/Radar controls
            freq_index = 1
            spare = b'\x00' * 20
            
            payload = struct.pack('<II', rdr_state, mission_category) + controls + struct.pack('<I', freq_index) + spare
            message = struct.pack('<IIIII', source_id, msg_id, msg_length, time_tag, seq_num) + payload
            
            self.tcp_sockets[port].send(message)
            print(f"[{datetime.now()}] ✅ SYSTEM CONTROL sent via TCP:{port}")
            
        except Exception as e:
            print(f"[{datetime.now()}] System Control error on TCP:{port}: {e}")
    
    def print_statistics(self):
        """Print statistics"""
        print(f"\n📊 STATISTICS:")
        print("=" * 40)
        print(f"Total Messages:     {self.stats['total_messages']}")
        print(f"Status Messages:    {self.stats['status_received']}")
        print(f"Target Messages:    {self.stats['target_messages']}")
        print(f"Keep Alive Sent:    {self.stats['keep_alive_sent']}")
        print("=" * 40)
    
    def start(self):
        """Start the proper network configuration"""
        self.running = True
        
        print("🚀 ELTA Proper Network Configuration")
        print("=" * 60)
        print(f"ELTA Simulator IP:    {self.elta_simulator_ip}")
        print(f"Customer IP:          {self.customer_ip}")
        print(f"TCP Client Ports:     {self.tcp_client_ports}")
        print(f"UDP Port:             {self.udp_port}")
        print("=" * 60)
        
        # Check network configuration
        self.check_network_config()
        
        print("\nStarting communication handlers...")
        
        # Start UDP handler
        udp_thread = threading.Thread(target=self.start_udp_handler)
        udp_thread.daemon = True
        udp_thread.start()
        
        # Start TCP handlers for each port
        for port in self.tcp_client_ports:
            tcp_thread = threading.Thread(target=self.start_tcp_handler, args=(port,))
            tcp_thread.daemon = True
            tcp_thread.start()
        
        # Wait a bit then send system control commands
        time.sleep(3)
        for port in self.tcp_client_ports:
            if port in self.tcp_sockets:
                self.send_system_control(port)
        
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
    config = EltaProperNetworkConfig()
    config.start()