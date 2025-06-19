# NeuroSync Network Core

## Overview

NeuroSync is a comprehensive real-time monitoring and command routing system built with Python, designed to manage distributed services and market data streams. The system serves as a centralized hub for coordinating multiple subsystems including heartbeat monitoring, audit logging, command routing, and cryptocurrency market data streaming.

The application is built using FastAPI as the web framework with asynchronous operations throughout, emphasizing real-time data processing and system reliability through comprehensive logging and monitoring capabilities.

## System Architecture

### Core Framework
- **Web Framework**: FastAPI with async/await patterns
- **Runtime**: Python 3.11+ with asyncio for concurrent operations
- **Process Management**: Uvicorn ASGI server
- **Configuration Management**: Environment-based configuration with dotenv support

### Microservices Architecture
The system follows a modular architecture where each component operates independently:
- **Main Application**: FastAPI app managing service lifecycle
- **Service Registry**: Centralized services dictionary for inter-component communication
- **Background Tasks**: Long-running asyncio tasks for each service

## Key Components

### 1. Configuration System (`config.py`)
- Environment-based configuration management
- Centralized settings for logging, heartbeat intervals, and service URLs
- Automatic log directory creation and rotation settings
- Health check endpoint configurations for external services

### 2. Heartbeat Monitor (`heartbeat.py`)
- **Purpose**: Monitor system health and external subsystem availability
- **Features**: 
  - Self-status monitoring with memory usage tracking (psutil integration)
  - External service health checks via HTTP endpoints
  - Persistent logging of subsystem status
- **Dependencies**: httpx for async HTTP requests, psutil for system metrics

### 3. Audit Logger (`audit_logger.py`)
- **Purpose**: Comprehensive audit trail and event logging
- **Features**:
  - Structured JSON logging with event categorization
  - Log rotation and retention management
  - Multiple log levels and event types
  - Dual-format logging (JSON and human-readable)

### 4. Command Router (`command_router.py`)
- **Purpose**: Centralized command execution and routing system
- **Features**:
  - Command queuing with status tracking
  - Retry mechanisms and timeout handling
  - Command validation and throttling
  - Asynchronous command processing

### 5. Market Data Streaming
- **AsterDex Client** (`asterdex_client.py`): WebSocket connection to cryptocurrency exchange
- **K-line Streaming** (`klines_stream.py`): Real-time candlestick data processing
- **Resilient Connection**: Automatic reconnection with exponential backoff

### 6. Failsafe Monitor (`failsafe_monitor.py`)
- **Purpose**: System reliability and automated recovery
- **Features**: Multi-level failsafe conditions and automated response actions

### 7. Sync Manager (`sync_manager.py`)
- **Purpose**: Timestamp validation and state consistency
- **Features**: Time synchronization, drift detection, and state verification

## Data Flow

### 1. Application Startup
```
FastAPI Lifespan Manager → Service Initialization → Background Task Creation → Service Registry Population
```

### 2. Heartbeat Flow
```
HeartbeatSystem → External Health Checks → Status Logging → Audit Event Generation
```

### 3. Market Data Flow
```
WebSocket Connection → Real-time Data Streaming → Data Processing → Status Updates
```

### 4. Command Processing Flow
```
Command Receipt → Validation → Queue Management → Execution → Status Tracking → Audit Logging
```

## External Dependencies

### Core Dependencies
- **FastAPI**: Web framework and API management
- **Uvicorn**: ASGI server for production deployment
- **websockets**: Real-time WebSocket communication
- **httpx**: Async HTTP client for service communication
- **requests**: HTTP client for simple requests
- **aiohttp**: Alternative async HTTP client
- **python-dotenv**: Environment variable management

### Optional Dependencies
- **psutil**: System resource monitoring (memory, CPU usage)
- **python-telegram-bot**: Telegram integration capabilities

### External Services
- **AsterDex API**: Cryptocurrency market data provider
- **Telegram Bot API**: For bot-based interactions
- **External Health Endpoints**: Subsystem monitoring at ports 8001, 8002

## Deployment Strategy

### Runtime Configuration
- **Primary Port**: 8000 (configured in .replit)
- **Alternative Port**: 3000 (configured in .env)
- **Host**: 0.0.0.0 for external accessibility

### Environment Setup
- Environment variables managed through .env file
- Secrets management for API keys and authentication tokens
- Configurable service endpoints and timeouts

### Process Management
- Uvicorn server with auto-reload capabilities
- Graceful shutdown handling through FastAPI lifespan events
- Background task coordination and cleanup

### Logging Strategy
- **Log Directory**: `logs/` with automatic creation
- **Audit Logs**: JSON format for machine processing
- **Status Logs**: Human-readable format for monitoring
- **Log Rotation**: Configurable size limits and retention policies

## Changelog
- June 19, 2025. Initial setup

## User Preferences

Preferred communication style: Simple, everyday language.