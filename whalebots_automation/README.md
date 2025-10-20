# WhaleBots Automation Platform

A comprehensive Python interface for managing the WhaleBots gaming automation platform with proper error handling, logging, security validation, and performance optimizations.

## Overview

This refactored version provides a robust, production-ready automation system for managing WhaleBots instances, including:

- **State Management**: Read and manage emulator states from WhaleBots configuration
- **Process Monitoring**: Detect and monitor running emulator processes
- **UI Automation**: Control WhaleBots interface through window automation
- **Configuration Management**: Flexible configuration system with validation
- **Security**: Input validation, file path sanitization, and backup mechanisms
- **Performance**: File I/O caching, optimized operations, and proper resource management
- **Logging**: Comprehensive logging with structured output and performance tracking

## Architecture

The refactored code follows SOLID principles with clear separation of concerns:

```
whalebots_automation/
├── __init__.py                 # Package initialization and public API
├── config.py                   # Configuration management system
├── exceptions.py               # Custom exception hierarchy
├── logger.py                   # Enhanced logging utilities
├── utils.py                    # File I/O, caching, and backup utilities
├── whalesbot.py               # Main WhaleBots class
├── tests.py                   # Comprehensive test suite
├── example_usage.py           # Usage examples
├── core/                      # Core functionality
│   ├── __init__.py
│   ├── emulator_action.py     # Window automation (SOLID design)
│   └── state.py               # State management (refactored)
└── README.md                  # This file
```

## Key Improvements

### 🔒 Security
- **Input Validation**: All inputs are validated before processing
- **File Path Sanitization**: Prevents path traversal attacks
- **Backup System**: Automatic backup creation for important files
- **Secure File Operations**: Atomic writes with temporary files

### 🏗️ Architecture
- **SOLID Principles**: Single responsibility, open/closed, dependency inversion
- **Interface Segregation**: Clean interfaces for different functionalities
- **Dependency Injection**: Configurable dependencies for better testability
- **Separation of Concerns**: Clear boundaries between different modules

### ⚡ Performance
- **File I/O Caching**: Intelligent caching with TTL and LRU eviction
- **Lazy Initialization**: Components initialized only when needed
- **Optimized Operations**: Reduced redundant file reads and computations
- **Resource Management**: Proper cleanup and resource management

### 🛠️ Error Handling
- **Custom Exception Hierarchy**: Specific exceptions for different error types
- **Comprehensive Logging**: Detailed error context and operation tracking
- **Graceful Degradation**: Fallback mechanisms for missing dependencies
- **Context Management**: Proper resource cleanup

### 📊 Observability
- **Structured Logging**: Consistent log format with context information
- **Performance Metrics**: Operation timing and resource usage tracking
- **Debug Support**: Detailed debugging information and error tracing
- **Configuration Validation**: Early detection of configuration issues

## Installation

### Requirements
- Python 3.7+
- Windows OS (for UI automation)
- Optional: `psutil` for enhanced process monitoring
- Optional: `pywin32` for window automation

### Basic Installation
```bash
# Clone or extract to your project directory
cd whalebots_automation

# Install optional dependencies
pip install psutil pywin32
```

## Quick Start

### Basic Usage
```python
from whalebots_automation import create_whalesbot

# Method 1: Convenience function (uses current directory)
whalesbot = create_whalesbot()

# Method 2: With specific path
whalesbot = create_whalesbot("C:/path/to/whalebots")

# Get emulator states
states = whalesbot.get_emulator_states()
print(f"Found {len(states)} configured emulators")

# Get active/inactive emulators
active = whalesbot.get_active_emulators()
inactive = whalesbot.get_inactive_emulators()
print(f"Active: {len(active)}, Inactive: {len(inactive)}")

# Get comprehensive summary
summary = whalesbot.get_state_summary()
print(f"Summary: {summary}")
```

### Advanced Usage
```python
from whalebots_automation import WhaleBots, create_default_config

# Create custom configuration
config = create_default_config()
config.debug_mode = True
config.ui.step_size = 25
config.files.max_backup_files = 15

# Use with custom configuration
with WhaleBots("C:/path/to/whalebots", config=config) as whalesbot:
    # Start/stop emulators
    whalesbot.start("Emulator_1")
    whalesbot.stop(0)  # By index

    # Monitor processes
    running = whalesbot.detect_running_emulators()
    for proc in running:
        pid = proc['process_info']['pid']
        info = whalesbot.get_process_info(pid)
        print(f"Process {pid}: {info['name']}")
```

## Configuration

### Configuration System
The platform uses a comprehensive configuration system:

```python
from whalebots_automation import load_config, WhaleBotsConfiguration

# Load from file
config = WhaleBotsConfiguration.from_file("config.json")

# Create programmatically
config = create_default_config()
config.ui.base_x_coordinate = 20
config.ui.step_size = 25
config.files.enable_backups = True
config.logging.default_level = "DEBUG"
```

### Configuration Options

#### UI Configuration
```python
ui_config = UIConfiguration(
    window_title_pattern=r".*Rise of Kingdoms Bot.*",
    base_x_coordinate=16,
    base_y_coordinate=14,
    step_size=20,
    max_visible_items=6,
    click_delay=0.05,
    operation_timeout=30.0
)
```

#### File Configuration
```python
file_config = FileConfiguration(
    enable_backups=True,
    max_backup_files=10,
    enable_file_cache=True,
    cache_ttl_seconds=30,
    max_file_size_mb=100
)
```

#### Security Configuration
```python
security_config = SecurityConfiguration(
    validate_file_encoding=True,
    sanitize_file_paths=True,
    validate_coordinates=True,
    max_coordinate_value=10000
)
```

## Error Handling

The refactored code provides comprehensive error handling:

```python
from whalebots_automation import WhaleBots
from whalebots_automation.exceptions import (
    WhaleBotsError, EmulatorNotFoundError, EmulatorStateError
)

try:
    whalesbot = WhaleBots("C:/path/to/whalebots")

    # Try to start non-existent emulator
    whalesbot.start("NonExistentEmulator")

except EmulatorNotFoundError as e:
    print(f"Emulator not found: {e.emulator_identifier}")

except EmulatorStateError as e:
    print(f"State error: {e}")

except WhaleBotsError as e:
    print(f"WhaleBots error: {e}")

except Exception as e:
    print(f"Unexpected error: {e}")
```

## Logging

### Basic Logging
```python
from whalebots_automation import get_logger

logger = get_logger("my_module")
logger.info("Application started")
logger.warning("Something to note")
logger.error("An error occurred")
```

### Performance Logging
```python
from whalebots_automation import log_performance

@log_performance()
def my_function():
    # Function execution will be timed
    pass
```

### Operation Tracking
```python
operation_id = logger.log_operation_start("data_processing")
# ... do work ...
logger.log_operation_end(operation_id, success=True)
```

## Testing

### Run Tests
```bash
cd whalebots_automation
python tests.py
```

### Test Coverage
- Configuration management
- File I/O operations and caching
- State management and validation
- Error handling
- Logging functionality
- Security validation

## Examples

### Basic State Management
```python
from whalebots_automation import create_whalesbot

with create_whalesbot() as whalesbot:
    # Check if emulator exists
    if whalesbot.check_status("MyEmulator"):
        print("Emulator configured")

    # Check if active
    if whalesbot.is_active("MyEmulator"):
        whalesbot.stop("MyEmulator")
    else:
        whalesbot.start("MyEmulator")
```

### Process Monitoring
```python
running = whalesbot.detect_running_emulators()
for emulator in running:
    pid = emulator['process_info']['pid']
    process_info = whalesbot.get_process_info(pid)

    print(f"PID: {pid}")
    print(f"Memory: {process_info['memory_info']['rss'] / 1024 / 1024:.1f} MB")
    print(f"CPU: {process_info['cpu_percent']:.1f}%")
```

### Configuration Management
```python
from whalebots_automation import create_default_config

# Create and save configuration
config = create_default_config()
config.debug_mode = True
config.save_to_file("my_config.json")

# Load configuration
from whalebots_automation import WhaleBotsConfiguration
config = WhaleBotsConfiguration.from_file("my_config.json")
```

## Migration from Original

### Key Changes
1. **Import Path**: `from core.emulater_action` → `from core.emulator_action`
2. **Exception Handling**: All methods now raise specific exception types
3. **Configuration**: Magic numbers extracted to configuration system
4. **Logging**: Replaced print statements with proper logging
5. **Type Safety**: Added comprehensive type annotations
6. **Security**: Added input validation and file path sanitization

### Breaking Changes
- Constructor parameters changed (path is now required)
- Some method signatures updated for better type safety
- Exception types changed (more specific hierarchy)
- Configuration system introduced

### Compatibility
The refactored version maintains functional compatibility while adding new features and improvements. See the example_usage.py file for comprehensive usage examples.

## Performance Considerations

### Caching
- File I/O operations are cached with configurable TTL
- State information cached to reduce file reads
- LRU eviction prevents memory bloat

### Resource Management
- Lazy initialization of UI components
- Proper cleanup with context managers
- Automatic resource management

### Optimizations
- Reduced redundant file operations
- Efficient state management
- Optimized coordinate calculations

## Security Features

### Input Validation
- All coordinates validated against configurable limits
- File paths sanitized to prevent traversal attacks
- State values validated for type and range

### File Operations
- Atomic writes using temporary files
- Automatic backup creation
- File size limits to prevent resource exhaustion

### Access Control
- Proper error messages without sensitive data exposure
- Logging with security filtering
- Safe process monitoring

## Troubleshooting

### Common Issues

1. **"psutil not available" warnings**
   ```bash
   pip install psutil
   ```

2. **Window automation failures**
   ```bash
   pip install pywin32
   ```

3. **Configuration validation fails**
   - Check file paths exist
   - Verify file permissions
   - Ensure proper directory structure

4. **Import errors**
   - Check Python version (3.7+)
   - Verify module structure
   - Check for missing __init__.py files

### Debug Mode
```python
config = create_default_config()
config.debug_mode = True
config.logging.default_level = "DEBUG"

whalesbot = WhaleBots("path", config=config)
```

## Contributing

### Development Setup
1. Ensure Python 3.7+
2. Install dependencies: `pip install psutil pywin32`
3. Run tests: `python tests.py`
4. Follow SOLID principles and maintain test coverage

### Code Style
- Use type hints for all functions
- Follow PEP 8 guidelines
- Add comprehensive docstrings
- Include error handling for all operations

## License

This code is provided as-is for educational and development purposes. Please refer to the original WhaleBots license terms for usage restrictions.

## Support

For issues and questions:
1. Check the example_usage.py file for usage patterns
2. Run tests to verify functionality
3. Enable debug logging for detailed error information
4. Review configuration validation output

---

## File Structure Summary

### Core Files
- **`whalesbot.py`**: Main WhaleBots class with comprehensive functionality
- **`config.py`**: Configuration management system
- **`exceptions.py`**: Custom exception hierarchy
- **`logger.py`**: Enhanced logging utilities
- **`utils.py`**: File I/O, caching, and backup utilities

### Core Module
- **`core/state.py`**: Refactored state management with validation
- **`core/emulator_action.py`**: SOLID-designed window automation

### Support Files
- **`tests.py`**: Comprehensive test suite
- **`example_usage.py`**: Usage examples and best practices
- **`README.md`**: This documentation

This refactored version provides a robust, maintainable, and secure foundation for WhaleBots automation with extensive testing and documentation.