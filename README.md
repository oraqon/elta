# ELTA ELM-2135 Radar Data Client

A Python client for receiving and decoding ELTA ELM-2135 radar data from TDP simulator.

## Overview

This project provides a complete solution for connecting to ELTA radar simulators and decoding real-time radar data streams according to ELTA engineer specifications.

## Files

- **`elta_engineer_specs.py`** - Main client application (working implementation)
- **`elta_message_decoder.py`** - Message decoder for ELTA radar data
- **`ICD_2135M-004.pdf`** - ELTA Interface Control Document (reference)
- **`ICD_2135M-004.txt`** - Text version of ICD (reference)

## Usage

### Running the Client

```bash
python elta_engineer_specs.py
```

### Connection Specifications

Based on ELTA engineer specifications:
- **TCP Connection**: `132.4.6.205:30087` (radar data stream)
- **UDP Listener**: Port `22230` (expecting data from simulator port `30080`)

### Supported Messages

- **Message ID `0x00000210`**: Radar Data Stream (live target data from TDP simulator)
- Standard ICD messages: Keep Alive, System Status, Target Reports, etc.

## Features

- ✅ Real-time radar data reception
- ✅ Message decoding and analysis
- ✅ Connection statistics and monitoring
- ✅ Comprehensive error handling
- ✅ Hex dump analysis for debugging

## Network Architecture

The client connects according to ELTA specifications:
1. Establishes TCP connection to radar simulator
2. Listens for UDP data streams
3. Decodes and displays all received radar messages
4. Provides real-time statistics and monitoring

## Requirements

- Python 3.x
- Network access to ELTA simulator (132.4.6.205)
- TDP simulator running and playing data

## Example Output

```
🚀 ELTA ENGINEER SPECIFICATION CLIENT
============================================================
📋 Based on ELTA Engineer Communication:
   🔌 TCP: Connect to 132.4.6.205:30087
   📡 UDP: Listen on port 22230 for data from simulator port 30080
============================================================

✅ TCP CONNECTED to 132.4.6.205:30087!
✅ UDP listening on 0.0.0.0:22230

📨 TCP received 528 bytes from 132.4.6.205:30087
🎯 TCP DECODED:
============================================================
MESSAGE HEADER
============================================================
Source ID:         0xCEF00414
Message ID:        0x00000210
Message Name:      Radar Data Stream
Message Length:    477954 bytes
Time Tag:          657 ms (from midnight)
Sequence Number:   100
============================================================
MESSAGE TYPE: Radar Data Stream
============================================================
```

## Development Notes

This implementation was developed through extensive testing with live ELTA TDP simulator data and represents the final working solution based on direct ELTA engineer specifications.