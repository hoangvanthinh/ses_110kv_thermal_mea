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

- **Queue-based Communication**: Threads communicate via Python `queue.Queue`
- **Event-based Coordination**: `threading.Event` for graceful shutdown
- **Thread-safe Data Structures**: All shared data uses thread-safe containers

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
