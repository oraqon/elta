#!/usr/bin/env python3
"""
ELTA Command Tester
Tests different command sequences to activate the simulator
"""

import socket
import struct
import time
from datetime import datetime

class EltaCommandTester:
    def __init__(self, host='localhost', port=23004):
        self.host = host
        self.port = port
        
    def send_command_sequence(self, commands, description):
        """Send a sequence of commands and listen for response"""
        print(f"\n[{datetime.now()}] 🧪 Testing: {description}")
        print("=" * 60)
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect((self.host, self.port))
            
            print(f"[{datetime.now()}] ✅ Connected to {self.host}:{self.port}")
            
            # Send each command in sequence
            for i, (cmd_type, param, delay, desc) in enumerate(commands):
                print(f"[{datetime.now()}] 📤 Sending {desc}...")
                
                # Create message
                source_id = 0x2135
                msg_id = 0xCEF00401  # SYSTEM_CONTROL
                msg_length = 28
                time_tag = int((time.time() % 86400) * 1000)
                seq_num = i + 1
                
                message = struct.pack('<IIIIIII', 
                                    source_id, msg_id, msg_length, time_tag, seq_num,
                                    cmd_type, param)
                
                sock.send(message)
                print(f"[{datetime.now()}] ✅ Sent {desc}")
                
                # Wait for specified delay
                if delay > 0:
                    time.sleep(delay)
            
            # Listen for response
            print(f"[{datetime.now()}] 👂 Listening for response...")
            total_data = b''
            start_time = time.time()
            
            while time.time() - start_time < 10:  # Listen for 10 seconds
                try:
                    data = sock.recv(4096)
                    if not data:
                        print(f"[{datetime.now()}] Connection closed by simulator")
                        break
                    
                    total_data += data
                    print(f"[{datetime.now()}] 📡 Received {len(data)} bytes!")
                    print(f"Hex: {data.hex().upper()}")
                    
                    # Try to decode header
                    if len(data) >= 20:
                        try:
                            source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', data[:20])
                            msg_types = {
                                0xCEF00400: "KEEP_ALIVE",
                                0xCEF00403: "SYSTEM_STATUS",
                                0xCEF00404: "TARGET_REPORT", 
                                0xCEF00405: "ACKNOWLEDGE",
                                0xCEF00406: "SINGLE_TARGET_REPORT",
                                0xCEF0041A: "SENSOR_POSITION"
                            }
                            msg_name = msg_types.get(msg_id, f"UNKNOWN_0x{msg_id:08X}")
                            print(f"🎯 Message: {msg_name} (Length: {msg_length}, Seq: {seq_num})")
                        except:
                            print("Could not decode header")
                    
                except socket.timeout:
                    elapsed = time.time() - start_time
                    print(f"[{datetime.now()}] No response yet ({elapsed:.1f}s)")
                    continue
                except socket.error as e:
                    print(f"[{datetime.now()}] Socket error: {e}")
                    break
            
            if not total_data:
                print(f"[{datetime.now()}] ❌ No data received")
            else:
                print(f"[{datetime.now()}] ✅ Total received: {len(total_data)} bytes")
                
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Error: {e}")
        finally:
            try:
                sock.close()
            except:
                pass
        
        print("=" * 60)

def main():
    tester = EltaCommandTester()
    
    print("🚀 ELTA Command Sequence Tester")
    print("Testing different command combinations to activate simulator")
    
    # Test different command sequences
    test_sequences = [
        # Sequence 1: Basic startup
        ([
            (1, 2, 0.1, "Start System (Operational)"),
            (4, 3, 0.1, "Start Search (Search & Track)")
        ], "Basic Startup Sequence"),
        
        # Sequence 2: Full startup with mode setting
        ([
            (1, 0, 0.1, "Start System"),
            (6, 2, 0.1, "Set Mode (Operational)"),
            (4, 1, 0.1, "Start Search (Search Only)")
        ], "Full Startup with Mode Setting"),
        
        # Sequence 3: Reset then start
        ([
            (3, 0, 0.2, "Reset System"),
            (1, 2, 0.1, "Start System (Operational)"),
            (4, 3, 0.1, "Start Search (Search & Track)")
        ], "Reset then Start Sequence"),
        
        # Sequence 4: Just start search
        ([
            (4, 3, 0.1, "Start Search (Search & Track)")
        ], "Search Only"),
        
        # Sequence 5: Calibrate then operate
        ([
            (7, 0, 0.2, "Calibrate"),
            (1, 2, 0.1, "Start System (Operational)"),
            (4, 3, 0.1, "Start Search (Search & Track)")
        ], "Calibrate then Operate"),
        
        # Sequence 6: Self test then operate
        ([
            (8, 0, 0.2, "Self Test"),
            (1, 2, 0.1, "Start System (Operational)"),
            (4, 3, 0.1, "Start Search (Search & Track)")
        ], "Self Test then Operate")
    ]
    
    for commands, description in test_sequences:
        tester.send_command_sequence(commands, description)
        time.sleep(2)  # Wait between tests
    
    print("\n🎯 Command testing complete!")
    print("If any sequence received data, that's the one to use!")

if __name__ == "__main__":
    main()