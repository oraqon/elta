#!/usr/bin/env python3
"""
Simple TCP listener for ELTA simulator
Just connects and listens without sending any commands
"""

import socket
import time
import threading
from datetime import datetime

def tcp_listener(host='localhost', port=23004):
    """Simple TCP listener that just receives data"""
    print(f"[{datetime.now()}] 🚀 Simple TCP Listener starting...")
    print(f"[{datetime.now()}] Connecting to {host}:{port}")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10.0)  # 10 second timeout
        sock.connect((host, port))
        
        print(f"[{datetime.now()}] ✅ Connected! Listening for data...")
        
        # Just listen for data
        total_bytes = 0
        start_time = time.time()
        
        while True:
            try:
                data = sock.recv(4096)
                if not data:
                    print(f"[{datetime.now()}] Connection closed by server")
                    break
                
                total_bytes += len(data)
                elapsed = time.time() - start_time
                
                print(f"[{datetime.now()}] 📡 Received {len(data)} bytes (Total: {total_bytes} bytes in {elapsed:.1f}s)")
                print(f"Hex: {data.hex().upper()}")
                
                # Try to identify message type from header if >= 20 bytes
                if len(data) >= 20:
                    import struct
                    try:
                        source_id, msg_id, msg_length, time_tag, seq_num = struct.unpack('<IIIII', data[:20])
                        print(f"Message ID: 0x{msg_id:08X}, Length: {msg_length}, Seq: {seq_num}")
                        
                        # Identify known message types
                        msg_types = {
                            0xCEF00400: "KEEP_ALIVE",
                            0xCEF00403: "SYSTEM_STATUS", 
                            0xCEF00404: "TARGET_REPORT",
                            0xCEF00406: "SINGLE_TARGET_REPORT",
                            0xCEF0041A: "SENSOR_POSITION"
                        }
                        
                        msg_name = msg_types.get(msg_id, f"UNKNOWN_{msg_id:08X}")
                        print(f"🎯 Message Type: {msg_name}")
                        
                    except:
                        print("Could not parse header")
                
                print("-" * 60)
                
            except socket.timeout:
                elapsed = time.time() - start_time
                print(f"[{datetime.now()}] No data received in last 10 seconds (waiting {elapsed:.1f}s total)")
                continue
            except socket.error as e:
                print(f"[{datetime.now()}] Socket error: {e}")
                break
                
    except Exception as e:
        print(f"[{datetime.now()}] ❌ Error: {e}")
    finally:
        try:
            sock.close()
        except:
            pass
        print(f"[{datetime.now()}] Connection closed")

def udp_listener(port=32004):
    """Simple UDP listener"""
    print(f"[{datetime.now()}] 🚀 UDP Listener starting on port {port}...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('', port))
        sock.settimeout(5.0)
        
        print(f"[{datetime.now()}] ✅ UDP listener ready on port {port}")
        
        while True:
            try:
                data, addr = sock.recvfrom(4096)
                print(f"[{datetime.now()}] 📡 UDP from {addr}: {len(data)} bytes")
                print(f"Hex: {data.hex().upper()}")
                
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[{datetime.now()}] UDP error: {e}")
                break
                
    except Exception as e:
        print(f"[{datetime.now()}] ❌ UDP setup error: {e}")

if __name__ == "__main__":
    # Start UDP listener in background
    udp_thread = threading.Thread(target=udp_listener)
    udp_thread.daemon = True
    udp_thread.start()
    
    # Run TCP listener in main thread
    tcp_listener()