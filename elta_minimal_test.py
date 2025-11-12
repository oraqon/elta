#!/usr/bin/env python3
"""
ELTA Minimal Test - Very Conservative Approach
Test minimal connection without causing TDP crashes
"""

import socket
import struct
import time
from datetime import datetime

class EltaMinimalTest:
    def __init__(self):
        self.elta_ip = '132.4.6.202'  # TDP simulator IP
        
    def test_single_connection(self):
        """Test single TCP connection to see if we can connect without crashes"""
        print(f"[{datetime.now()}] 🧪 MINIMAL TEST - Single Connection")
        print("=" * 60)
        
        # Try just the critical port 30073
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10.0)
            
            print(f"[{datetime.now()}] 🔌 Connecting to {self.elta_ip}:30073...")
            sock.connect((self.elta_ip, 30073))
            print(f"[{datetime.now()}] ✅ CONNECTED to port 30073!")
            
            # Just listen for 10 seconds without sending anything
            print(f"[{datetime.now()}] 👂 Listening for 10 seconds (no messages sent)...")
            sock.settimeout(1.0)
            
            for i in range(10):
                try:
                    data = sock.recv(4096)
                    if data:
                        print(f"[{datetime.now()}] 📨 Received {len(data)} bytes: {data.hex().upper()}")
                except socket.timeout:
                    print(f"[{datetime.now()}] ⏰ Timeout {i+1}/10")
                    continue
                except Exception as e:
                    print(f"[{datetime.now()}] ❌ Error: {e}")
                    break
            
            print(f"[{datetime.now()}] 🔚 Closing connection...")
            sock.close()
            print(f"[{datetime.now()}] ✅ Test completed")
            
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Connection failed: {e}")
    
    def test_message_format(self):
        """Test if our message format is causing issues"""
        print(f"\n[{datetime.now()}] 🧪 MESSAGE FORMAT TEST")
        print("=" * 60)
        
        # Test different source_id values to see which ones work
        test_source_ids = [
            0x2135,        # Working localhost version
            0x1000,        # Simple value
            0x0001,        # Minimal value  
            0x2136,        # Slight variation
            0xAAAA,        # Pattern test
        ]
        
        for source_id in test_source_ids:
            try:
                print(f"\n[{datetime.now()}] Testing source_id: 0x{source_id:04X}")
                
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                
                sock.connect((self.elta_ip, 30073))
                print(f"[{datetime.now()}] ✅ Connected for source_id 0x{source_id:04X}")
                
                # Create a simple Keep Alive message
                msg_id = 0xCEF00400      # Keep Alive
                msg_length = 20
                time_tag = int((time.time() % 86400) * 1000)
                seq_num = 1
                
                message = struct.pack('<IIIII', source_id, msg_id, msg_length, time_tag, seq_num)
                
                print(f"[{datetime.now()}] 📤 Sending Keep Alive with source_id 0x{source_id:04X}...")
                print(f"Message: {message.hex().upper()}")
                
                sock.send(message)
                print(f"[{datetime.now()}] ✅ Message sent successfully")
                
                # Listen for response for 3 seconds
                sock.settimeout(3.0)
                try:
                    response = sock.recv(4096)
                    if response:
                        print(f"[{datetime.now()}] 📨 Response received: {response.hex().upper()}")
                except socket.timeout:
                    print(f"[{datetime.now()}] ⏰ No response within 3 seconds")
                
                sock.close()
                print(f"[{datetime.now()}] ✅ Test completed for 0x{source_id:04X}")
                
                # Wait 2 seconds between tests
                time.sleep(2)
                
            except Exception as e:
                print(f"[{datetime.now()}] ❌ Error with source_id 0x{source_id:04X}: {e}")
                time.sleep(1)
    
    def run_tests(self):
        """Run all minimal tests"""
        print("🧪 ELTA MINIMAL TESTING SUITE")
        print("Testing connection stability and message formats")
        print("=" * 80)
        
        # Test 1: Simple connection without sending messages
        self.test_single_connection()
        
        # Wait before next test
        time.sleep(5)
        
        # Test 2: Test different message formats
        self.test_message_format()
        
        print(f"\n[{datetime.now()}] 🏁 All tests completed")

if __name__ == "__main__":
    tester = EltaMinimalTest()
    tester.run_tests()