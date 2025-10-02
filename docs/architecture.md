# SES 110kV Thermal Measurement Application Architecture

## Overview

The SES 110kV Thermal Measurement Application is a Python-based system designed to monitor thermal cameras in electrical substations. It collects temperature data from multiple thermal camera nodes, publishes the data via MQTT, and provides a web-based user interface for monitoring and control.

## System Architecture

### High-Level Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Thermal       │    │   Thermal       │    │   Thermal       │
│   Camera 1      │    │   Camera 2      │    │   Camera N      │
│   (192.168.1.171)│    │   (IP...)       │    │   (IP...)       │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          │ HTTP API Calls       │                      │
          │ (PTZ Control +       │                      │
          │  Temperature Read)   │                      │
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────▼─────────────┐
                    │     Main Application      │
                    │   (Python + NiceGUI)      │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │    Worker Threads         │
                    │  ┌─────────────────────┐  │
                    │  │  Thermal Pollers    │  │
                    │  │  (per camera)       │  │
                    │  └─────────────────────┘  │
                    │  ┌─────────────────────┐  │
                    │  │  MQTT Publisher     │  │
                    │  └─────────────────────┘  │
                    │  ┌─────────────────────┐  │
                    │  │  MQTT Subscriber    │  │
                    │  └─────────────────────┘  │
                    │  ┌─────────────────────┐  │
                    │  │  RTSP Fetchers      │  │
                    │  └─────────────────────┘  │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │      MQTT Broker         │
                    │    (192.168.1.86:1883)   │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │   Web UI (NiceGUI)       │
                    │   (Port 8080)            │
                    └───────────────────────────┘
```

## Core Components

### 1. Main Application (`main.py`)

**Purpose**: Application entry point and orchestration layer

**Key Responsibilities**:
- Initialize and manage worker threads
- Handle application lifecycle (startup/shutdown)
- Coordinate between different components
- Serve the web UI

**Key Functions**:
- `start_workers()`: Spawns all worker threads
- `stop_workers()`: Gracefully shuts down all workers
- `main()`: Application entry point

### 2. Configuration Management (`config_loader.py`)

**Purpose**: Load and normalize application configuration

**Key Features**:
- Loads configuration from `config.json`
- Normalizes camera configurations
- Provides default values for missing settings
- Supports both legacy and new configuration formats

**Configuration Structure**:
```json
{
  "cameras": [
    {
      "name": "camera_name",
      "node_thermals": [
        {
          "name": "node1",
          "url_presetID": "http://.../ptz.cgi?...",
          "url_areaTemperature": "http://.../param.cgi?..."
        }
      ],
      "username": "admin",
      "password": "password",
      "interval_seconds": 30,
      "url_get_rtsp_url": "http://.../video.cgi?..."
    }
  ],
  "mqtt": {
    "enabled": true,
    "host": "192.168.1.86",
    "port": 1883,
    "topic": "camera",
    "username": "mqtt-user",
    "password": "mqtt-pass"
  }
}
```

### 3. Worker Threads

#### 3.1 Thermal Poller (`read_thermal_poller.py`)

**Purpose**: Poll thermal cameras for temperature data

**Key Features**:
- Two-step process: PTZ preset invocation → temperature reading
- Configurable polling intervals
- Support for multiple thermal nodes per camera
- Error handling and retry logic
- Authentication support

**Workflow**:
1. Invoke PTZ preset (if configured)
2. Wait for camera to settle
3. Read temperature data from specified area
4. Parse temperature value from response
5. Queue data for MQTT publishing

#### 3.2 MQTT Publisher (`mqtt_publisher.py`)

**Purpose**: Publish collected data to MQTT broker

**Key Features**:
- Publishes temperature data to MQTT topics
- Publishes RTSP URLs when requested
- Graceful fallback to stdout if MQTT unavailable
- Configurable topic structure
- JSON payload formatting

**MQTT Topics**:
- `camera/temperature`: Temperature data
- `camera/{camera_id}/url`: RTSP stream URLs

#### 3.3 MQTT Subscriber (`mqtt_subscriber.py`)

**Purpose**: Listen for commands via MQTT

**Key Features**:
- Subscribes to command topics
- Processes camera control commands
- Handles RTSP URL requests
- Queues commands for processing

**Subscribed Topics**:
- `camera/cmd`: General commands
- `camera/get_url`: RTSP URL requests

#### 3.4 RTSP Fetcher (`rtsp_fetcher.py`)

**Purpose**: Fetch RTSP stream URLs from cameras

**Key Features**:
- Responds to MQTT requests for RTSP URLs
- Injects authentication credentials into URLs
- Handles camera-specific RTSP URL formats
- Command-driven operation

### 4. Web User Interface (`ui_app.py`)

**Purpose**: Provide web-based monitoring and control interface

**Key Features**:
- Login authentication system
- Real-time temperature data display
- Tabbed interface (Home, Setup, About)
- Auto-refresh of temperature data
- Logout functionality

**UI Components**:
- Login screen with credential validation
- Main dashboard with temperature monitoring
- Settings panel (placeholder)
- About information panel

### 5. Utility Modules

#### 5.1 HTTP Client (`utils/http.py`)

**Purpose**: HTTP communication with thermal cameras

**Key Features**:
- Basic authentication support
- Configurable timeouts
- Error handling for network issues
- UTF-8 text response handling

#### 5.2 Logging (`utils/logging.py`)

**Purpose**: Centralized logging configuration

**Key Features**:
- Structured logging format
- Thread-aware logging
- Configurable log levels
- Consistent log formatting across components

#### 5.3 Type Definitions (`utils/types.py`)

**Purpose**: Type hints and data structures

**Key Types**:
- `CameraConfig`: Camera configuration structure
- `PollerConfig`: Poller configuration structure
- `MQTTConfig`: MQTT configuration structure
- `QueueItem`: Data structure for inter-thread communication

## Data Flow

### Temperature Data Flow

```
Thermal Camera → HTTP API → Thermal Poller → Queue → MQTT Publisher → MQTT Broker
                                                      ↓
Web UI ← Real-time Updates ← Queue ← MQTT Subscriber ← MQTT Broker
```

### RTSP URL Flow

```
MQTT Command → MQTT Subscriber → Command Queue → RTSP Fetcher → Camera API → RTSP URL
                                                                              ↓
MQTT Publisher ← Queue ← RTSP Fetcher ← RTSP URL Response ← Camera API
```

## Threading Model

The application uses a multi-threaded architecture with the following thread types:

1. **Main Thread**: UI and application orchestration
2. **Thermal Poller Threads**: One per camera (configurable polling)
3. **MQTT Publisher Thread**: Single thread for all MQTT publishing
4. **MQTT Subscriber Thread**: Single thread for command processing
5. **RTSP Fetcher Threads**: One per camera (on-demand operation)

### Thread Communication

The application uses a sophisticated queue-based communication system with two main queues and event-based coordination:

#### Queue Architecture

**1. Output Queue (`out_queue`)**
- **Type**: `queue.Queue[dict]` with `maxsize=100`
- **Purpose**: Collects all data from thermal pollers and RTSP fetchers for MQTT publishing
- **Producers**: 
  - Thermal Poller threads (temperature data)
  - RTSP Fetcher threads (RTSP URLs)
- **Consumer**: MQTT Publisher thread
- **Data Flow**: Many-to-One (multiple producers → single consumer)

**2. Command Queue (`cmd_queue`)**
- **Type**: `queue.Queue[str]` with `maxsize=50`
- **Purpose**: Routes MQTT commands to appropriate workers
- **Producers**: MQTT Subscriber thread
- **Consumers**: RTSP Fetcher threads
- **Data Flow**: One-to-Many (single producer → multiple consumers)

#### Queue Communication Patterns

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Thermal Poller  │    │ Thermal Poller  │    │ Thermal Poller  │
│ Thread 1        │    │ Thread 2        │    │ Thread N        │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          │ Temperature Data     │                      │
          │ (dict)               │                      │
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────▼─────────────┐
                    │      out_queue            │
                    │   (maxsize=100)           │
                    │   queue.Queue[dict]       │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │   MQTT Publisher Thread   │
                    │   (Single Consumer)       │
                    └───────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ RTSP Fetcher    │    │ RTSP Fetcher    │    │ RTSP Fetcher    │
│ Thread 1        │    │ Thread 2        │    │ Thread N        │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          │ RTSP URLs            │                      │
          │ (dict)               │                      │
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────▼─────────────┐
                    │      out_queue            │
                    │   (maxsize=100)           │
                    │   queue.Queue[dict]       │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │   MQTT Publisher Thread   │
                    │   (Single Consumer)       │
                    └───────────────────────────┘

┌─────────────────┐
│ MQTT Subscriber │
│ Thread          │
└─────────┬───────┘
          │
          │ Commands (JSON strings)
          │
          ▼
┌─────────────────┐
│   cmd_queue     │
│  (maxsize=50)   │
│ queue.Queue[str]│
└─────────┬───────┘
          │
    ┌─────┼─────┐
    │     │     │
    ▼     ▼     ▼
┌─────┐ ┌─────┐ ┌─────┐
│RTSP │ │RTSP │ │RTSP │
│Fet.1│ │Fet.2│ │Fet.N│
└─────┘ └─────┘ └─────┘
```

#### Queue Operations and Data Structures

**Output Queue Operations:**

1. **Thermal Poller → Output Queue**:
   ```python
   out_queue.put({
       "camera": name,
       "type": "temperature", 
       "node_thermal": node_thermal_name,
       "url": url_areaTemperature,
       "timestamp": timestamp,
       "data_t": temperature_value
   }, block=False)
   ```

2. **RTSP Fetcher → Output Queue**:
   ```python
   out_queue.put({
       "sid": camera_name,
       "type": "rtsp_url",
       "timestamp": timestamp,
       "rtsp_url": rtsp_url,
       "status": "ok"
   }, block=False)
   ```

3. **MQTT Publisher ← Output Queue**:
   ```python
   item = in_queue.get(timeout=0.5)  # Non-blocking with timeout
   ```

**Command Queue Operations:**

1. **MQTT Subscriber → Command Queue**:
   ```python
   cmd_queue.put_nowait(json.dumps({
       "camera": camera_name,
       "topic": topic,
       "payload": payload_text.strip(),
       "type": "get_url_rtsp"  # or "command"
   }))
   ```

2. **RTSP Fetcher ← Command Queue**:
   ```python
   cmd = cmd_queue.get_nowait()  # Non-blocking
   cmd_data = json.loads(cmd)
   ```

#### Queue Management Features

**1. Bounded Queues with Overflow Protection**:
- `out_queue`: maxsize=100 (prevents memory overflow from temperature data)
- `cmd_queue`: maxsize=50 (prevents command queue overflow)

**2. Non-blocking Operations**:
- `put(block=False)`: Prevents thread blocking on full queues
- `get_nowait()`: Immediate return, no waiting
- `get(timeout=0.5)`: Short timeout to allow graceful shutdown

**3. Sentinel Values for Shutdown**:
```python
# Shutdown signal to MQTT Publisher
out_queue.put_nowait(None)  # Sentinel value
```

**4. Error Handling**:
- `queue.Full` exceptions handled gracefully
- `queue.Empty` exceptions handled with continue logic
- Overflow protection with logging

#### Queue Data Types

**Temperature Data Structure**:
```python
{
    "camera": str,           # Camera identifier
    "type": "temperature",   # Message type
    "node_thermal": str,     # Thermal node name
    "url": str,              # Source URL
    "timestamp": str,        # ISO timestamp
    "data_t": str            # Temperature value
}
```

**RTSP URL Data Structure**:
```python
{
    "sid": str,              # Camera/session ID
    "type": "rtsp_url",      # Message type
    "timestamp": str,        # ISO timestamp
    "rtsp_url": str,         # RTSP stream URL
    "status": str            # Status ("ok", "error")
}
```

**Command Data Structure**:
```python
{
    "camera": str,           # Target camera
    "topic": str,            # MQTT topic
    "payload": str,          # Command payload
    "type": str              # Command type ("get_url_rtsp", "command")
}
```

#### Performance Characteristics

**Queue Throughput**:
- Output queue: ~100 temperature readings + RTSP URLs
- Command queue: ~50 pending commands
- Non-blocking operations prevent thread starvation

**Memory Management**:
- Bounded queues prevent unbounded memory growth
- Automatic cleanup on application shutdown
- Sentinel values ensure clean thread termination

**Thread Safety**:
- All queue operations are thread-safe
- No additional locking required
- Atomic put/get operations

#### UI Queue Communication

**Web UI Data Access**:
The web interface accesses the output queue for real-time temperature display:

```python
# UI Timer-based polling (ui_app.py)
def update_ui():
    try:
        data = out_queue.get_nowait()  # Non-blocking read
        if data.get('type') == 'temperature':
            text = f'{data["node_thermal"]}: {data["data_t"]} °C at {data["timestamp"]}'
            temp_label.text = text
    except Exception:
        pass  # Ignore queue empty exceptions

ui.timer(0.5, update_ui)  # Poll every 500ms
```

**UI Queue Characteristics**:
- **Access Pattern**: Non-blocking reads with `get_nowait()`
- **Polling Frequency**: 500ms intervals
- **Data Filtering**: Only processes temperature data
- **Error Handling**: Graceful handling of empty queue
- **Thread Safety**: UI runs on main thread, safe queue access

#### Queue Flow Summary

**Complete Data Flow Through Queues**:

1. **Temperature Data Path**:
   ```
   Thermal Camera → HTTP API → Thermal Poller → out_queue → MQTT Publisher → MQTT Broker
                                                      ↓
                                               Web UI (non-blocking read)
   ```

2. **RTSP URL Path**:
   ```
   MQTT Command → MQTT Subscriber → cmd_queue → RTSP Fetcher → Camera API → out_queue → MQTT Publisher
   ```

3. **Command Processing Path**:
   ```
   External MQTT → MQTT Subscriber → cmd_queue → RTSP Fetcher → Camera API → Response
   ```

**Queue Load Distribution**:
- **High Load**: `out_queue` (temperature data from multiple cameras every 30s)
- **Medium Load**: `cmd_queue` (on-demand RTSP requests)
- **Low Load**: UI polling (500ms intervals, non-blocking)

## Configuration

### Camera Configuration

Each camera can have multiple thermal measurement nodes:

```json
{
  "name": "0001000100082",
  "node_thermals": [
    {
      "name": "node1",
      "url_presetID": "http://192.168.1.171/cgi-bin/ptz.cgi?cameraID=1&action=presetInvoke&presetID=1",
      "url_areaTemperature": "http://192.168.1.171/cgi-bin/param.cgi?action=get&type=areaTemperature&cameraID=1&areaID=1"
    }
  ],
  "username": "admin",
  "password": "password",
  "interval_seconds": 30,
  "timeout_seconds": 5,
  "settle_seconds": 5,
  "url_get_rtsp_url": "http://192.168.1.171/cgi-bin/video.cgi?type=RTSP&cameraID=1&streamID=1"
}
```

### MQTT Configuration

```json
{
  "enabled": true,
  "host": "192.168.1.86",
  "port": 1883,
  "topic": "camera",
  "topic_temperature": "camera/temperature",
  "topic_req_url": "camera/get_url",
  "topic_url": "camera/url",
  "username": "mqtt-user",
  "password": "mqtt-pass"
}
```

## Error Handling

### Network Error Handling
- HTTP timeouts and connection errors
- MQTT broker connectivity issues
- Graceful degradation when services unavailable

### Application Error Handling
- Thread-safe error logging
- Graceful worker shutdown
- Queue overflow protection
- Configuration validation

## Security Considerations

### Authentication
- Basic HTTP authentication for camera access
- MQTT username/password authentication
- Web UI login system

### Network Security
- Configurable timeouts to prevent hanging connections
- Error handling to prevent information leakage
- Secure credential storage in configuration

## Deployment

### Requirements
- Python 3.8+
- Required packages: `nicegui`, `paho-mqtt`
- Network access to thermal cameras and MQTT broker

### Running the Application
```bash
python src/main.py
```

The application will:
1. Load configuration from `src/config.json`
2. Start all worker threads
3. Launch web UI on port 8080
4. Begin polling thermal cameras
5. Publish data to MQTT broker

### Monitoring
- Application logs provide detailed operation information
- Web UI shows real-time temperature data
- MQTT topics can be monitored for data flow
- Thread status visible in log output

## Future Enhancements

### Potential Improvements
1. **Database Integration**: Store historical temperature data
2. **Alert System**: Temperature threshold monitoring
3. **Advanced UI**: Charts, graphs, and historical data visualization
4. **REST API**: External system integration
5. **Configuration Management**: Dynamic configuration updates
6. **Health Monitoring**: System health checks and metrics
7. **Multi-camera Support**: Enhanced support for multiple camera types
8. **Data Export**: CSV/JSON data export functionality

### Scalability Considerations
- Horizontal scaling via multiple application instances
- Load balancing for high-camera-count deployments
- Database clustering for large-scale data storage
- Message queue clustering for high-throughput scenarios
