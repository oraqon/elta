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
            elif message_id == MessageType.SINGLE_TARGET_EXTENDED.value:
                return self._decode_single_target_extended(header, payload)
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
    
    def _decode_single_target_extended(self, header, payload):
        """Decode Single Target Extended message (0xCEF00414)
        Message size: 528 bytes (20 byte header + 508 byte payload)
        Payload: 332 bytes targetdata + 176 bytes plot data
        """
        result = self._format_header(header)
        result += "\n" + "="*60 + "\n"
        result += "MESSAGE TYPE: SINGLE TARGET EXTENDED\n"
        result += "="*60 + "\n"
        
        if len(payload) < 508:
            result += f"Insufficient payload data ({len(payload)} bytes, expected 508)\n"
            result += f"Raw payload: {payload.hex().upper()}\n"
            return result
        
        # Decode targetdata (332 bytes) per ICD Section 5.2.2
        targetdata = payload[:332]
        result += self._decode_targetdata(targetdata)
        
        # Decode plot data (176 bytes) per ICD Section 5.2.2.3
        plot_data = payload[332:508]
        result += "\n" + "="*60 + "\n"
        result += "PLOT DATA\n"
        result += "="*60 + "\n"
        result += self._decode_plot_data(plot_data)
        
        return result
    
    def _decode_targetdata(self, data):
        """Decode targetdata structure (332 bytes) per ICD Section 5.2.2"""
        if len(data) < 332:
            return f"Insufficient targetdata ({len(data)} bytes, expected 332)\n"
        
        result = ""
        offset = 0
        
        # Field 1-2: targetId (4) + targetTimeTag (8)
        target_id, target_time_tag = struct.unpack('<IQ', data[offset:offset+12])
        offset += 12
        result += f"Target ID:              {target_id}\n"
        result += f"Target Time Tag:        {target_time_tag} ms (from midnight)\n"
        
        # Field 3: targetFirstUpdateTime (8)
        first_update_time, = struct.unpack('<Q', data[offset:offset+8])
        offset += 8
        result += f"First Update Time:      {first_update_time} ms (from midnight)\n"
        
        # Field 4: targetSource (4)
        target_source, = struct.unpack('<I', data[offset:offset+4])
        offset += 4
        result += f"Target Source:          {target_source}\n"
        
        # Field 5-6: fusionTargetSource[4] (16) + sourceTrack id[4] (16)
        offset += 32  # Skip fusion fields (N/A per ICD)
        
        # Field 7: Target status (4)
        target_status, = struct.unpack('<I', data[offset:offset+4])
        offset += 4
        status_map = {1: "New", 2: "Update", 3: "Delete", 4: "Extrapolate"}
        result += f"Target Status:          {status_map.get(target_status, f'Unknown ({target_status})')}\n"
        
        # Field 8: score (4)
        score, = struct.unpack('<f', data[offset:offset+4])
        offset += 4
        result += f"Score:                  {score:.2f}\n"
        
        # Field 9: targetClassification (4)
        target_class, = struct.unpack('<I', data[offset:offset+4])
        offset += 4
        result += f"Target Classification:  {target_class}\n"
        
        # Field 10: ClassificationConfidence (4)
        class_confidence, = struct.unpack('<f', data[offset:offset+4])
        offset += 4
        result += f"Classification Conf:    {class_confidence:.1f}%\n"
        
        # Field 11: seniority (4)
        seniority, = struct.unpack('<I', data[offset:offset+4])
        offset += 4
        result += f"Seniority:              {seniority} updates\n"
        
        # Field 12: rcs (4)
        rcs, = struct.unpack('<f', data[offset:offset+4])
        offset += 4
        result += f"RCS:                    {rcs:.2f} dBsm\n"
        
        # Field 13-15: Polar coordinates (8+8+8=24)
        elevation, azimuth, range_m = struct.unpack('<ddd', data[offset:offset+24])
        offset += 24
        result += f"Elevation:              {math.degrees(elevation):.3f}° ({elevation:.6f} rad)\n"
        result += f"Azimuth:                {math.degrees(azimuth):.3f}° ({azimuth:.6f} rad)\n"
        result += f"Range:                  {range_m:.3f} m ({range_m/1000:.3f} km)\n"
        
        # Field 16-17: Velocity (4+4=8)
        abs_vel, course = struct.unpack('<ff', data[offset:offset+8])
        offset += 8
        result += f"Absolute Velocity:      {abs_vel:.2f} m/s\n"
        result += f"Course:                 {course:.3f} rad ({math.degrees(course):.1f}°)\n"
        
        # Field 18-20: Sigma values (8+8+8=24)
        sigma_elevation, sigma_azimuth, sigma_range = struct.unpack('<ddd', data[offset:offset+24])
        offset += 24
        result += f"Sigma Elevation:        {math.degrees(sigma_elevation):.6f}° ({sigma_elevation:.6f} rad)\n"
        result += f"Sigma Azimuth:          {math.degrees(sigma_azimuth):.6f}° ({sigma_azimuth:.6f} rad)\n"
        result += f"Sigma Range:            {sigma_range:.3f} m\n"
        
        # Field 21-22: Number_of_dimention (4) + Coordinate_system (4)
        num_dim, coord_sys = struct.unpack('<II', data[offset:offset+8])
        offset += 8
        dim_map = {1: "Radar_2D", 2: "Radar_3D", 3: "Optic_2D", 4: "Fusion_3D", 5: "HFL_2D"}
        coord_map = {0: "SYSTEM_AXIS", 1: "WORLD_AXIS"}
        result += f"Dimension:              {dim_map.get(num_dim, f'Unknown ({num_dim})')}\n"
        result += f"Coordinate System:      {coord_map.get(coord_sys, f'Unknown ({coord_sys})')}\n"
        
        # Field 23-30: Availability flags (8 bytes)
        flags = struct.unpack('<8B', data[offset:offset+8])
        offset += 8
        result += f"Cartesian Loc Avail:    {bool(flags[0])}\n"
        result += f"Cartesian Vel Avail:    {bool(flags[1])}\n"
        result += f"Polar Loc Avail:        {bool(flags[2])}\n"
        result += f"Polar Vel Avail:        {bool(flags[3])}\n"
        result += f"Geo Loc Avail:          {bool(flags[4])}\n"
        result += f"Absolute Vel Avail:     {bool(flags[5])}\n"
        result += f"Cartesian Var Avail:    {bool(flags[6])}\n"
        
        # Field 31-33: Geo location (8+8+8=24) - if available
        altitude, latitude, longitude = struct.unpack('<ddd', data[offset:offset+24])
        offset += 24
        if flags[4]:  # geoLocationAvailable
            result += f"Altitude:               {altitude:.3f} m\n"
            result += f"Latitude:               {latitude:.7f}°\n"
            result += f"Longitude:              {longitude:.7f}°\n"
        
        # Field 34-36: Cartesian location (8+8+8=24) - if available
        target_x, target_y, target_z = struct.unpack('<ddd', data[offset:offset+24])
        offset += 24
        if flags[0]:  # cartesianLocationAvailable
            result += f"Target X (NED):         {target_x:.3f} m\n"
            result += f"Target Y (NED):         {target_y:.3f} m\n"
            result += f"Target Z (NED):         {target_z:.3f} m\n"
        
        # Field 37-39: Cartesian velocity (8+8+8=24) - if available
        vel_x, vel_y, vel_z = struct.unpack('<ddd', data[offset:offset+24])
        offset += 24
        if flags[1]:  # cartesianVelocityAvailable
            result += f"Velocity X (NED):       {vel_x:.3f} m/s\n"
            result += f"Velocity Y (NED):       {vel_y:.3f} m/s\n"
            result += f"Velocity Z (NED):       {vel_z:.3f} m/s\n"
        
        # Field 40-42: Cartesian sigma (8+8+8=24)
        sigma_x, sigma_y, sigma_z = struct.unpack('<ddd', data[offset:offset+24])
        offset += 24
        if flags[6]:  # cartesianVarianceAvailable
            result += f"Sigma X:                {sigma_x:.3f} m\n"
            result += f"Sigma Y:                {sigma_y:.3f} m\n"
            result += f"Sigma Z:                {sigma_z:.3f} m\n"
        
        # Field 43-45: Cartesian velocity sigma (8+8+8=24)
        sigma_vel_x, sigma_vel_y, sigma_vel_z = struct.unpack('<ddd', data[offset:offset+24])
        offset += 24
        if flags[6]:  # cartesianVarianceAvailable
            result += f"Sigma Vel X:            {sigma_vel_x:.3f} m/s\n"
            result += f"Sigma Vel Y:            {sigma_vel_y:.3f} m/s\n"
            result += f"Sigma Vel Z:            {sigma_vel_z:.3f} m/s\n"
        
        # Field 46-48: Polar velocity (8+8+8=24)
        vel_elevation, vel_azimuth, vel_range = struct.unpack('<ddd', data[offset:offset+24])
        offset += 24
        if flags[3]:  # polarVelocityAvailable
            result += f"Velocity Elevation:     {math.degrees(vel_elevation):.3f}° ({vel_elevation:.6f} rad/s)\n"
            result += f"Velocity Azimuth:       {math.degrees(vel_azimuth):.3f}° ({vel_azimuth:.6f} rad/s)\n"
            result += f"Velocity Range:         {vel_range:.3f} m/s\n"
        
        # Field 49-51: Polar velocity variance (8+8+4=20)
        var_vel_elev, var_vel_az, var_vel_range = struct.unpack('<ddf', data[offset:offset+20])
        offset += 20
        if flags[3]:  # polarVelocityAvailable
            result += f"Var Vel Elevation:      {math.degrees(var_vel_elev):.6f}° ({var_vel_elev:.6f} rad/s)\n"
            result += f"Var Vel Azimuth:        {math.degrees(var_vel_az):.6f}° ({var_vel_az:.6f} rad/s)\n"
            result += f"Var Vel Range:          {var_vel_range:.3f} m/s\n"
        
        # Field 52: target_snr (4)
        snr, = struct.unpack('<f', data[offset:offset+4])
        offset += 4
        result += f"SNR:                    {snr:.2f} dB\n"
        
        # Field 53: target_hpt (1)
        hpt, = struct.unpack('<B', data[offset:offset+1])
        offset += 1
        hpt_map = {0: "NO", 1: "HPT", 2: "STT"}
        result += f"HPT Status:             {hpt_map.get(hpt, f'Unknown ({hpt})')}\n"
        
        # Fields 54-57: Spare bytes (1+1+1+1+4=8)
        # offset += 8  # Skip spare fields
        
        return result
    
    def _decode_plot_data(self, data):
        """Decode plot data (176 bytes) per ICD Section 5.2.2.3"""
        if len(data) < 176:
            return f"Insufficient plot data ({len(data)} bytes, expected 176)\n"
        
        result = ""
        offset = 0
        
        # Field 3: plot_time (8)
        plot_time, = struct.unpack('<Q', data[offset:offset+8])
        offset += 8
        result += f"Plot Time:              {plot_time} ms (from midnight)\n"
        
        # Field 4: plot_id (4)
        plot_id, = struct.unpack('<I', data[offset:offset+4])
        offset += 4
        result += f"Plot ID:                {plot_id}\n"
        
        # Field 5-6: plot_elevation (8) + plot_azimuth (8)
        plot_elevation, plot_azimuth = struct.unpack('<dd', data[offset:offset+16])
        offset += 16
        result += f"Plot Elevation:         {math.degrees(plot_elevation):.3f}° ({plot_elevation:.6f} rad)\n"
        result += f"Plot Azimuth:           {math.degrees(plot_azimuth):.3f}° ({plot_azimuth:.6f} rad)\n"
        
        # Field 7-9: plot_range (8) + plot_dopler (4) + plot_snr (4)
        plot_range, plot_doppler, plot_snr = struct.unpack('<dff', data[offset:offset+16])
        offset += 16
        result += f"Plot Range:             {plot_range:.3f} m ({plot_range/1000:.3f} km)\n"
        result += f"Plot Doppler:           {plot_doppler:.2f} m/s\n"
        result += f"Plot SNR:               {plot_snr:.2f} dB\n"
        
        # Field 10-12: plot_sigma values (8+8+8=24)
        plot_sigma_elev, plot_sigma_az, plot_sigma_range = struct.unpack('<ddd', data[offset:offset+24])
        offset += 24
        result += f"Plot Sigma Elevation:   {math.degrees(plot_sigma_elev):.6f}° ({plot_sigma_elev:.6f} rad)\n"
        result += f"Plot Sigma Azimuth:     {math.degrees(plot_sigma_az):.6f}° ({plot_sigma_az:.6f} rad)\n"
        result += f"Plot Sigma Range:       {plot_sigma_range:.3f} m\n"
        
        # Field 13: plot_sigma_dop (4)
        plot_sigma_dop, = struct.unpack('<f', data[offset:offset+4])
        offset += 4
        result += f"Plot Sigma Doppler:     {plot_sigma_dop:.3f} m²\n"
        
        # Field 14: spare[16] (64 bytes)
        # offset += 64  # Skip spare fields
        
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
        
        if payload and self.logger.isEnabledFor(logging.DEBUG):
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
        if self.logger.isEnabledFor(logging.DEBUG):
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