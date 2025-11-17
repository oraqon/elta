#!/usr/bin/env python3
"""
ELTA ELM-2135 Message Decoder
Based on ICD_2135M-004 specification
Decodes radar messages and presents them in readable format
"""

import struct
import time
import json
import logging
from datetime import datetime, timedelta
from enum import Enum
import math

class MessageType(Enum):
    # Standard ICD message types - CORRECTED per ICD_2135M-004 specification
    
    # C2 to RC Messages
    KEEP_ALIVE = 0xCEF00400
    SYSTEM_CONTROL = 0xCEF00401
    SYSTEM_MOTION = 0xCEF00412
    BIT_REQUEST = 0xCEF0040A
    MAINTENANCE_REQUEST = 0xCEF0040C
    RESOURCE_REQUEST = 0xCEF0040D
    SET_SENSOR_POSITION = 0xCEF00418
    GET_SENSOR_POSITION = 0xCEF00419
    
    # RC to C2 Messages  
    SYSTEM_STATUS = 0xCEF00402
    TARGET_REPORT = 0xCEF00403
    SINGLE_TARGET_REPORT = 0xCEF00404
    ACKNOWLEDGE = 0xCEF00405
    BIT_STATUS_DATA = 0xCEF00406
    MAINTENANCE_DATA = 0xCEF00407
    SINGLE_TARGET_EXTENDED = 0xCEF00414
    SENSOR_POSITION = 0xCEF0041A
    
    # Actual simulator message types (discovered from live data)
    RADAR_DATA_STREAM = 0x00000210  # Live radar/target data stream from TDP simulator

class SystemState(Enum):
    IDLE = 0
    STARTUP = 1
    OPERATIONAL = 2
    STANDBY = 3
    ERROR = 4
    MAINTENANCE = 5

class TargetClass(Enum):
    UNKNOWN = 0
    AIRCRAFT = 1
    HELICOPTER = 2
    BIRD = 3
    CLUTTER = 4
    WEATHER = 5

class EltaMessageDecoder:
    """
    ELTA ELM-2135 Message Decoder
    Decodes binary radar messages according to ICD_2135M-004 specification
    """
    
    def __init__(self):
        self.message_types = {msg.value: msg.name.replace('_', ' ').title() for msg in MessageType}
        self.system_states = {state.value: state.name.replace('_', ' ').title() for state in SystemState}
        self.target_classes = {tc.value: tc.name.replace('_', ' ').title() for tc in TargetClass}
        
        # Load configuration and setup logging
        self._load_config()
        self._setup_logging()
    
    def _load_config(self):
        """Load configuration from config.json"""
        try:
            with open('config.json', 'r') as f:
                self.config = json.load(f)
        except Exception:
            # Default config if file not found
            self.config = {'log_level': 'DEBUG'}
    
    def _setup_logging(self):
        """Setup logging based on config"""
        log_level = self.config.get('log_level', 'DEBUG')
        self.logger = logging.getLogger(__name__)
        
    def decode_message(self, data):
        """
        Main decoder method - analyzes message type and routes to appropriate decoder
        """
        if len(data) < 20:
            return self._format_error("Message too short", data)
            
        try:
            # Parse standard 20-byte header
            header = self._decode_header(data[:20])
            payload = data[20:] if len(data) > 20 else b''
            
            # Route to specific decoder based on message type
            message_id = header['message_id']
            
            if message_id == MessageType.KEEP_ALIVE.value:
                return self._decode_keep_alive(header, payload)
            elif message_id == MessageType.SYSTEM_STATUS.value:
                return self._decode_system_status(header, payload)
            elif message_id == MessageType.TARGET_REPORT.value:
                return self._decode_target_report(header, payload)
            elif message_id == MessageType.SINGLE_TARGET_REPORT.value:
                return self._decode_single_target(header, payload)
            elif message_id == MessageType.SYSTEM_CONTROL.value:
                return self._decode_system_control(header, payload)
            elif message_id == MessageType.SYSTEM_MOTION.value:
                return self._decode_system_motion(header, payload)
            elif message_id == MessageType.SENSOR_POSITION.value:
                return self._decode_sensor_position(header, payload)
            elif message_id == MessageType.RADAR_DATA_STREAM.value:
                return self._decode_radar_data_stream(header, payload)
            else:
                return self._decode_generic_message(header, payload)
                
        except Exception as e:
            return self._format_error(f"Decoding error: {str(e)}", data)
    
    def _decode_header(self, header_data):
        """Decode standard 20-byte message header"""
        if len(header_data) < 20:
            raise ValueError("Header too short")
            
        # Unpack header fields (little-endian format) - CORRECTED per ICD Section 3.2
        msg_id, msg_length, time_tag, seq_num, source_id = struct.unpack('<IIIII', header_data)
        
        return {
            'source_id': source_id,
            'message_id': msg_id,
            'message_length': msg_length,
            'time_tag': time_tag,
            'sequence_number': seq_num,
            'message_name': self.message_types.get(msg_id, f"Unknown (0x{msg_id:08X})")
        }
    
    def _decode_keep_alive(self, header, payload):
        """Decode Keep Alive message"""
        result = self._format_header(header)
        result += "\n" + "="*60 + "\n"
        result += "MESSAGE TYPE: KEEP ALIVE\n"
        result += "="*60 + "\n"
        result += "Description: Heartbeat message to maintain connection\n"
        result += f"Payload Size: {len(payload)} bytes\n"
        
        if payload:
            result += f"Additional Data: {payload.hex().upper()}\n"
            
        return result
    
    def _decode_system_status(self, header, payload):
        """Decode System Status message"""
        result = self._format_header(header)
        result += "\n" + "="*60 + "\n"
        result += "MESSAGE TYPE: SYSTEM STATUS\n"
        result += "="*60 + "\n"
        
        if len(payload) >= 12:
            # Parse system status fields (3 fields = 12 bytes)
            system_state, operational_mode, error_code = struct.unpack('<III', payload[:12])
            
            result += f"System State:      {self.system_states.get(system_state, f'Unknown ({system_state})')}\n"
            result += f"Operational Mode:  {self._decode_operational_mode(operational_mode)}\n"
            result += f"Error Code:        {self._decode_error_code(error_code)}\n"
            
            # Check if there's temperature data (4th field)
            if len(payload) >= 16:
                temperature, = struct.unpack('<I', payload[12:16])
                result += f"System Temperature: {temperature/10.0:.1f}°C\n"
            
            # Additional status fields if present
            if len(payload) >= 20:
                power_status, = struct.unpack('<I', payload[16:20])
                result += f"Power Status:      {self._decode_power_status(power_status)}\n"
                
            if len(payload) >= 24:
                antenna_position, = struct.unpack('<I', payload[20:24])
                result += f"Antenna Position:  {antenna_position/100.0:.2f}°\n"
                
        else:
            result += f"Insufficient payload data ({len(payload)} bytes)\n"
            result += f"Raw payload: {payload.hex().upper()}\n"
            
        return result
    
    def _decode_target_report(self, header, payload):
        """Decode Target Report message"""
        result = self._format_header(header)
        result += "\n" + "="*60 + "\n"
        result += "MESSAGE TYPE: TARGET REPORT\n"
        result += "="*60 + "\n"
        
        if len(payload) < 4:
            result += f"Insufficient payload data ({len(payload)} bytes)\n"
            return result
            
        # Parse number of targets
        num_targets, = struct.unpack('<I', payload[:4])
        result += f"Number of Targets: {num_targets}\n\n"
        
        offset = 4
        target_size = 32  # Each target record is 32 bytes
        
        for i in range(min(num_targets, (len(payload) - 4) // target_size)):
            if offset + target_size <= len(payload):
                target_data = payload[offset:offset + target_size]
                result += self._decode_single_target_data(target_data, i + 1)
                result += "\n"
                offset += target_size
            else:
                result += f"Target {i+1}: Incomplete data\n"
                break
                
        return result
    
    def _decode_single_target(self, header, payload):
        """Decode Single Target Report message"""
        result = self._format_header(header)
        result += "\n" + "="*60 + "\n"
        result += "MESSAGE TYPE: SINGLE TARGET REPORT\n"
        result += "="*60 + "\n"
        
        if len(payload) >= 32:
            result += self._decode_single_target_data(payload[:32], 1)
        else:
            result += f"Insufficient payload data ({len(payload)} bytes)\n"
            result += f"Raw payload: {payload.hex().upper()}\n"
            
        return result
    
    def _decode_single_target_data(self, target_data, target_num):
        """Decode individual target data (32 bytes)"""
        if len(target_data) < 32:
            return f"Target {target_num}: Incomplete data ({len(target_data)} bytes)\n"
            
        # Unpack target fields
        target_id, range_m, azimuth, elevation, velocity, rcs, target_class, confidence = struct.unpack('<IIIIiiii', target_data)
        
        result = f"--- TARGET {target_num} ---\n"
        result += f"Target ID:         {target_id}\n"
        result += f"Range:             {range_m/1000.0:.3f} km\n"
        result += f"Azimuth:           {azimuth/1000.0:.3f}°\n"
        result += f"Elevation:         {elevation/1000.0:.3f}°\n"
        result += f"Velocity:          {velocity/100.0:.2f} m/s\n"
        result += f"RCS:               {rcs/100.0:.2f} dBsm\n"
        result += f"Target Class:      {self.target_classes.get(target_class, f'Unknown ({target_class})')}\n"
        result += f"Confidence:        {confidence}%\n"
        
        return result
    
    def _decode_system_control(self, header, payload):
        """Decode System Control message"""
        result = self._format_header(header)
        result += "\n" + "="*60 + "\n"
        result += "MESSAGE TYPE: SYSTEM CONTROL\n"
        result += "="*60 + "\n"
        
        if len(payload) >= 8:
            command, parameter = struct.unpack('<II', payload[:8])
            result += f"Control Command:   {self._decode_control_command(command)}\n"
            result += f"Parameter:         {parameter}\n"
        else:
            result += f"Insufficient payload data ({len(payload)} bytes)\n"
            
        return result
    
    def _decode_system_motion(self, header, payload):
        """Decode System Motion message (0xCEF00412)"""
        result = self._format_header(header)
        result += "\n" + "="*60 + "\n"
        result += "MESSAGE TYPE: SYSTEM MOTION\n"
        result += "="*60 + "\n"
        
        if len(payload) >= 172:  # Expected size from ICD: 192 bytes total - 20 byte header = 172 bytes
            try:
                # Parse motion data according to ICD specification
                offset = 0
                
                # timeOfDataGeneration (8 bytes)
                time_gen, = struct.unpack('<Q', payload[offset:offset+8])
                offset += 8
                
                # Position data (3 * 8 bytes = 24 bytes)
                altitude, latitude, longitude = struct.unpack('<ddd', payload[offset:offset+24])
                offset += 24
                
                # Attitude data (4 * 8 bytes = 32 bytes)
                pitch, roll, yaw, heading = struct.unpack('<dddd', payload[offset:offset+32])
                offset += 32
                
                # Spare fields (3 * 8 bytes = 24 bytes)
                offset += 24  # Skip spare fields
                
                # Velocity data (3 * 8 bytes = 24 bytes)
                north_vel, east_vel, down_vel = struct.unpack('<ddd', payload[offset:offset+24])
                offset += 24
                
                # Angular velocity (3 * 8 bytes = 24 bytes)
                ang_vel_x, ang_vel_y, ang_vel_z = struct.unpack('<ddd', payload[offset:offset+24])
                offset += 24
                
                # Acceleration (3 * 8 bytes = 24 bytes)
                accel_x, accel_y, accel_z = struct.unpack('<ddd', payload[offset:offset+24])
                
                result += f"Time of Data Generation: {time_gen} ms\n"
                result += f"\n--- POSITION ---\n"
                result += f"Altitude:          {altitude:.3f} m\n"
                result += f"Latitude:          {latitude:.7f}°\n"
                result += f"Longitude:         {longitude:.7f}°\n"
                result += f"\n--- ATTITUDE ---\n"
                result += f"Pitch:             {pitch:.3f} rad ({math.degrees(pitch):.1f}°)\n"
                result += f"Roll:              {roll:.3f} rad ({math.degrees(roll):.1f}°)\n"
                result += f"Yaw:               {yaw:.3f} rad ({math.degrees(yaw):.1f}°)\n"
                result += f"Platform Heading:  {heading:.3f} rad ({math.degrees(heading):.1f}°)\n"
                result += f"\n--- VELOCITY ---\n"
                result += f"North Velocity:    {north_vel:.3f} m/s\n"
                result += f"East Velocity:     {east_vel:.3f} m/s\n"
                result += f"Down Velocity:     {down_vel:.3f} m/s\n"
                result += f"\n--- ANGULAR VELOCITY ---\n"
                result += f"Angular Vel X:     {ang_vel_x:.6f} rad/s\n"
                result += f"Angular Vel Y:     {ang_vel_y:.6f} rad/s\n"
                result += f"Angular Vel Z:     {ang_vel_z:.6f} rad/s\n"
                result += f"\n--- ACCELERATION ---\n"
                result += f"Acceleration X:    {accel_x:.3f} m/s²\n"
                result += f"Acceleration Y:    {accel_y:.3f} m/s²\n"
                result += f"Acceleration Z:    {accel_z:.3f} m/s²\n"
                
            except Exception as e:
                result += f"Error parsing motion data: {e}\n"
                result += f"Raw payload: {payload.hex().upper()}\n"
        else:
            result += f"Insufficient payload data ({len(payload)} bytes, expected 172+)\n"
            result += f"Raw payload: {payload.hex().upper()}\n"
            
        return result
    
    def _decode_sensor_position(self, header, payload):
        """Decode Sensor Position message"""
        result = self._format_header(header)
        result += "\n" + "="*60 + "\n"
        result += "MESSAGE TYPE: SENSOR POSITION\n"
        result += "="*60 + "\n"
        
        if len(payload) >= 24:
            latitude, longitude, altitude, heading, pitch, roll = struct.unpack('<iiiiii', payload[:24])
            
            result += f"Latitude:          {latitude/10000000.0:.7f}°\n"
            result += f"Longitude:         {longitude/10000000.0:.7f}°\n"
            result += f"Altitude:          {altitude/1000.0:.3f} m\n"
            result += f"Heading:           {heading/1000.0:.3f}°\n"
            result += f"Pitch:             {pitch/1000.0:.3f}°\n"
            result += f"Roll:              {roll/1000.0:.3f}°\n"
        else:
            result += f"Insufficient payload data ({len(payload)} bytes)\n"
            
        return result
    
    def _decode_generic_message(self, header, payload):
        """Decode unknown or generic message"""
        result = self._format_header(header)
        result += "\n" + "="*60 + "\n"
        result += f"MESSAGE TYPE: {header['message_name']}\n"
        result += "="*60 + "\n"
        result += f"Payload Size: {len(payload)} bytes\n"
        
        if payload:
            result += f"Raw Payload (Hex): {payload.hex().upper()}\n"
            result += self._format_hex_dump(payload)
            
        return result
    
    def _format_header(self, header):
        """Format message header information"""
        time_str = self._format_time_tag(header['time_tag'])
        
        result = "\n" + "="*60 + "\n"
        result += "MESSAGE HEADER\n"
        result += "="*60 + "\n"
        result += f"Source ID:         0x{header['source_id']:08X}\n"
        result += f"Message ID:        0x{header['message_id']:08X}\n"
        result += f"Message Name:      {header['message_name']}\n"
        result += f"Message Length:    {header['message_length']} bytes\n"
        result += f"Time Tag:          {header['time_tag']} ms (from midnight)\n"
        result += f"Time (HH:MM:SS.mmm): {time_str}\n"
        result += f"Sequence Number:   {header['sequence_number']}\n"
        
        return result
    
    def _format_time_tag(self, time_tag_ms):
        """Convert time tag (ms from midnight) to HH:MM:SS.mmm format"""
        try:
            total_seconds = time_tag_ms / 1000.0
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            seconds = total_seconds % 60
            return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"
        except:
            return f"Invalid ({time_tag_ms})"
    
    def _decode_operational_mode(self, mode):
        """Decode operational mode"""
        modes = {
            0: "Standby",
            1: "Search",
            2: "Track",
            3: "Search & Track",
            4: "Maintenance",
            5: "Test"
        }
        return modes.get(mode, f"Unknown ({mode})")
    
    def _decode_error_code(self, error_code):
        """Decode error code"""
        if error_code == 0:
            return "No Error"
        elif error_code < 100:
            return f"Warning Code {error_code}"
        elif error_code < 200:
            return f"Error Code {error_code}"
        else:
            return f"Critical Error {error_code}"
    
    def _decode_power_status(self, power_status):
        """Decode power status"""
        status_bits = {
            0x01: "Main Power",
            0x02: "Backup Power",
            0x04: "Transmitter",
            0x08: "Receiver",
            0x10: "Antenna Drive",
            0x20: "Processing Unit"
        }
        
        active_systems = []
        for bit, name in status_bits.items():
            if power_status & bit:
                active_systems.append(name)
                
        return ", ".join(active_systems) if active_systems else "All Systems Off"
    
    def _decode_control_command(self, command):
        """Decode control command"""
        commands = {
            1: "Start System",
            2: "Stop System",
            3: "Reset System",
            4: "Start Search",
            5: "Stop Search",
            6: "Set Mode",
            7: "Calibrate",
            8: "Self Test"
        }
        return commands.get(command, f"Unknown Command ({command})")
    
    def _format_hex_dump(self, data, bytes_per_line=16):
        """Format binary data as hex dump"""
        result = "\nHex Dump:\n"
        for i in range(0, len(data), bytes_per_line):
            chunk = data[i:i+bytes_per_line]
            hex_part = ' '.join(f'{b:02X}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            result += f"{i:04X}: {hex_part:<48} |{ascii_part}|\n"
        return result
    
    def _format_error(self, error_msg, data):
        """Format error message with hex data"""
        result = "\n" + "="*60 + "\n"
        result += "DECODING ERROR\n"
        result += "="*60 + "\n"
        result += f"Error: {error_msg}\n"
        result += f"Data Length: {len(data)} bytes\n"
        result += f"Raw Data (Hex): {data.hex().upper()}\n"
        result += self._format_hex_dump(data)
        return result
    
    def _decode_radar_data_stream(self, header, payload):
        """
        Decode Radar Data Stream (0x00000210)
        Live radar data from TDP simulator containing target tracks and sensor data
        """
        result = self._format_header(header)
        result += "=" * 60 + "\n"
        result += f"MESSAGE TYPE: {header['message_name']}\n"
        result += "=" * 60 + "\n"
        
        if not payload:
            result += "No payload data\n"
            return result
            
        result += f"Payload Size: {len(payload)} bytes\n"
        
        # Analyze the payload structure
        if len(payload) >= 508:  # Standard size we've observed
            result += "\n--- RADAR DATA STREAM ANALYSIS ---\n"
            
            # Try to extract some meaningful data from the structured payload
            try:
                # The payload appears to have a structured format
                # Based on the hex dumps, there are repeated patterns suggesting track data
                
                # Look for potential target count or data structure info
                if len(payload) >= 16:
                    # First few bytes might contain metadata
                    meta_data = struct.unpack('<IIII', payload[0:16])
                    result += f"Stream Metadata: {[hex(x) for x in meta_data]}\n"
                
                # Look for floating point values that might be coordinates/ranges
                float_count = 0
                coordinate_values = []
                for i in range(0, min(len(payload) - 4, 200), 4):  # Check first 200 bytes
                    try:
                        value = struct.unpack('<f', payload[i:i+4])[0]
                        # Look for reasonable coordinate/range values
                        if 0.1 < abs(value) < 10000 and not math.isnan(value) and not math.isinf(value):
                            coordinate_values.append((i, value))
                            float_count += 1
                    except:
                        continue
                
                if coordinate_values:
                    result += f"\nPotential Coordinate/Range Values Found: {min(float_count, 10)}\n"
                    for i, (offset, value) in enumerate(coordinate_values[:5]):  # Show first 5
                        result += f"  Offset {offset:3d}: {value:8.3f}\n"
                        
                # Look for data patterns that might indicate targets
                result += f"\nData Pattern Analysis:\n"
                result += f"  Total payload: {len(payload)} bytes\n"
                result += f"  Non-zero bytes: {sum(1 for b in payload if b != 0)}\n"
                result += f"  Potential floats: {float_count}\n"
                
            except Exception as e:
                result += f"Analysis error: {e}\n"
        
        # Always show raw payload for analysis
        result += f"\nRaw Payload (Hex): {payload.hex().upper()}\n"
        result += "\nHex Dump:\n"
        result += self._format_hex_dump(payload)
        
        return result

# Test function
def test_decoder():
    """Test the decoder with sample data"""
    # Setup logging for test
    logging.basicConfig(
        level=logging.DEBUG,
        format='[%(asctime)s.%(msecs)03d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger(__name__)
    
    decoder = EltaMessageDecoder()
    
    # Sample Keep Alive message - CORRECTED header format per ICD Section 3.2
    keep_alive_data = struct.pack('<IIIII', 0xCEF00400, 20, 123456789, 1, 0x2135)
    logger.debug("=== KEEP ALIVE TEST ===")
    logger.debug(decoder.decode_message(keep_alive_data))
    
    # Sample System Status message - CORRECTED header format per ICD Section 3.2
    header = struct.pack('<IIIII', 0xCEF00402, 32, 123456789, 2, 0x2135)
    payload = struct.pack('<IIII', 2, 1, 0, 250)  # Operational, Search mode, No error, 25.0°C
    status_data = header + payload
    logger.debug("\n=== SYSTEM STATUS TEST ===")
    logger.debug(decoder.decode_message(status_data))
    
    # Sample Target Report message - CORRECTED header format per ICD Section 3.2
    header = struct.pack('<IIIII', 0xCEF00403, 40, 123456789, 3, 0x2135)
    payload = struct.pack('<I', 1)  # 1 target
    target_data = struct.pack('<IIIIiiii', 1001, 5000000, 45000, 10000, 2500, -500, 1, 85)  # Sample target
    target_report_data = header + payload + target_data
    logger.debug("\n=== TARGET REPORT TEST ===")
    logger.debug(decoder.decode_message(target_report_data))

if __name__ == "__main__":
    test_decoder()