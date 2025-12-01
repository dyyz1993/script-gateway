# AGENTS.md

This file provides guidance to neovate when working with code in this repository.

## Development Commands

### Running the Application
- **Development server**: `python -m uvicorn app:app --host 0.0.0.0 --port 8001 --reload`
- **Production server**: `python -m uvicorn app:app --host 0.0.0.0 --port 8001`
- **Docker**: `docker-compose up -d` (uses port 8001)
- **Health check**: `curl http://localhost:8001/health`

### Dependency Management
- **Python dependencies**: `pip install -r requirements.txt`
- **Node.js dependencies**: `npm install` (from project root)
- **Install Python deps via API**: POST to `/api/deps/install` with `{"runtime": "python", "deps": [{"name": "package", "version": "1.0.0"}]}`
- **Install Node.js deps via API**: POST to `/api/deps/install` with `{"runtime": "js", "deps": [{"name": "package", "version": "^1.0.0"}]}`

### Database Operations
- **Initialize database**: Handled automatically on startup via `database.init_db()`
- **Database location**: `./gateway.db` (SQLite)
- **Settings management**: Via `/api/settings` endpoints

### Testing Commands
- No dedicated test framework configured - manual testing via web interface or API calls
- **API testing**: Use `/scripts-swagger.html` for interactive API testing
- **Script testing**: Execute scripts via `/api/scripts/{script_id}/run` endpoints

## Code Architecture & Patterns

### Project Structure Philosophy
ScriptGateway is a script-to-API gateway that automatically converts Python and JavaScript scripts into REST endpoints. The architecture follows a modular pattern:

- **FastAPI web framework** (`app.py`): Main application with API routes
- **Script scanner** (`scanner.py`): Auto-discovers and registers scripts
- **Script executor** (`executor.py`): Manages script execution with timeout handling
- **Database layer** (`database.py`): SQLite persistence for scripts, settings, runs
- **Dependency manager** (`deps.py`): Handles Python and Node.js package installation
- **Configuration** (`config.py`): Centralized settings with environment variable support

### Key Architectural Patterns
- **Plugin-based script system**: Scripts are automatically discovered and registered as API endpoints
- **Schema-first approach**: Scripts must expose their parameter schema via `--_sys_get_schema` flag
- **Dual runtime support**: Both Python 3.11 and Node.js 20 runtimes are supported
- **Hot-reload system**: File changes trigger automatic re-registration (configurable via `SCAN_INTERVAL_SEC`)
- **Process isolation**: Each script execution runs in a separate subprocess with timeout controls

### Data Flow Patterns
1. **Script Discovery**: Scanner walks `scripts_repo/python/` and `scripts_repo/js/` directories
2. **Schema Extraction**: Scripts are executed with `--_sys_get_schema` to extract parameter definitions
3. **API Registration**: Successful scripts are exposed via `/api/scripts/{script_id}/run`
4. **Execution Flow**: HTTP request → parameter validation → subprocess execution → response formatting
5. **Logging**: All executions are logged to both database and rotating log files

### Configuration Management
- **Environment variables**: `SCAN_INTERVAL_SEC`, `TIMEOUT_MIN`, `NOTIFY_URL`, `BASE_URL`
- **Database settings**: Stored in `settings` table, accessible via `/api/settings`
- **Path configuration**: Centralized in `config.py` with Docker volume mappings in `docker-compose.yml`

### Key Abstractions
- **ARGS_MAP**: Standardized parameter schema format used across both Python and JavaScript scripts
- **Sidecar files**: `.{script_name}._map.json` files store extracted schemas alongside scripts
- **Script lifecycle**: Discovery → Registration → Execution → Logging → Cleanup
- **Temp file management**: Centralized via `temp_file_service` with automatic cleanup
- **File access control**: Pattern-based restrictions via `FileAccessChecker`
- **Error handling**: Structured error types via `ScriptError` and `ErrorType` enums
- **Dependency isolation**: Per-script dependency management with caching
- **Environment management**: Dynamic execution environment setup per script

## Technology Stack & Dependencies

### Core Framework
- **FastAPI**: Python web framework with automatic OpenAPI/Swagger generation
- **SQLite**: Embedded database for persistence
- **Uvicorn**: ASGI server for production deployment
- **Docker**: Containerized deployment with Python 3.11 + Node.js 20 base image

### Python Dependencies (requirements.txt)
- **FastAPI ecosystem**: `fastapi`, `uvicorn`, `starlette`, `pydantic`
- **File handling**: `python-multipart`, `pillow`
- **HTTP client**: `requests`
- **Scheduling**: `schedule`
- **Async support**: `anyio`, `sniffio`
- **ML/ASR dependencies**: `funasr>=1.0.0`, `modelscope>=1.15.0`, `numpy>=1.21.0`, `onnxruntime>=1.15.0`, `jieba>=0.42.1`

### Node.js Dependencies (package.json)
- **HTTP client**: `axios@^1.13.2`
- **Browser automation**: `puppeteer-core@^24.31.0`
- **QR code generation**: `qrcode@^1.5.4`
- **Utilities**: `uuid@^9.0.1`

### Special Tooling
- **Docker base image**: `python:3.11-slim-bookworm` with ARM64 native compatibility
- **Mirror sources**: Tsinghua PyPI and npmmirror for Chinese users
- **Pre-installed packages**: qrcode[pil], numpy>=1.23.0, pandas>=2.0.0, openpyxl, python-dateutil, pytz, beautifulsoup4, lxml, pyyaml, redis, pymysql, psycopg2-binary, jieba>=0.42.1
- **Torch support**: torch==2.3.1, torchaudio==2.3.1 (CPU-only, ARM64 compatible)

### Script-Level Dependency Management
- **Individual dependencies**: Each script can have its own `requirements.txt` or `package.json`
- **Cache system**: `.deps_cache/` directory stores dependency caches by hash
- **Environment isolation**: Python/Node.js paths injected per script execution
- **Automatic installation**: Dependencies installed on script discovery/execution
- **API management**: REST endpoints for dependency installation and cache management
- **Performance**: 75% reduction in build size (2GB → 500MB)

## Script Development Guidelines

### Script Entry Points
- **Python**: Must contain `if __name__ == "__main__":` block
- **JavaScript**: Must use `module.exports` or `export default`

### Required Schema Interface
Both Python and JavaScript scripts must support:
```bash
script_name --_sys_get_schema
```
This should return a JSON string defining ARGS_MAP with parameter metadata.

### Parameter Schema Format
```json
{
  "param_name": {
    "flag": "--command-line-flag",
    "type": "str|int|float|bool|file",
    "required": true|false,
    "help": "Parameter description"
  }
}
```

### File Locations
- **Python scripts**: `scripts_repo/python/`
- **JavaScript scripts**: `scripts_repo/js/`
- **Template files**: `templates/`
- **Static outputs**: `static/{script_name}/resources/{timestamp}/`

## API Design Patterns

### Script Execution Endpoints
- **GET**: `/api/scripts/{script_id}/run` (for non-file parameters)
- **POST**: `/api/scripts/{script_id}/run` (JSON body or multipart for files)
- **Swagger**: Auto-generated at `/scripts-swagger.html`
- **Script management**: CRUD operations via `/api/scripts/*` endpoints
- **Dependency management**: Install/list via `/api/deps/*` endpoints
- **Settings management**: Get/update via `/api/settings` endpoints

### Response Format
```json
{
  "status": "success|error",
  "script_id": 123,
  "duration_ms": 1500,
  "run_id": 456,
  "data": {...} | "type": "file", "url": "...", "filename": "..."
}
```

### Error Handling
- **Structured errors**: `ScriptError` with `ErrorType` enum
- **Custom exception handlers**: Global handlers for script and system errors
- **Validation errors**: Parameter validation before script execution
- **Resource errors**: File access, timeout, and memory limit handling

## Docker Deployment

### Container Architecture
- **Base image**: `python:3.11-slim-bookworm` with ARM64 native compatibility
- **Dual runtime**: Python 3.11 + Node.js 20 (Node.js installed via apt)
- **Volume mappings**: Scripts, dependencies, database, and logs are persisted outside container
- **Health checks**: `/health` endpoint monitored every 30 seconds
- **Port exposure**: 8001 (configurable via docker-compose.yml)

### Build Strategy
- **Multi-stage optimization**: System dependencies → Python packages → Node.js packages
- **ARM64 compatibility**: Torch CPU version without +cpu suffix for ARM64 support
- **Mirror optimization**: Tsinghua PyPI for Python packages, npmmirror for Node.js
- **Cache management**: Separate layers to optimize rebuild times

### Production Considerations
- **Timeout handling**: Scripts are killed after `TIMEOUT_MIN` minutes (default: 10)
- **Resource isolation**: Each script runs in isolated subprocess
- **Log rotation**: Automatic cleanup based on retention settings
- **Dependency persistence**: New installs are written back to requirements.txt/package.json

## Script-Level Dependency Management

### Architecture
- **Scanner integration**: Automatic dependency detection during script registration
- **Cache-based installation**: MD5 hash-based caching to avoid redundant installs
- **Environment isolation**: PYTHONPATH/NODE_PATH injection per script
- **API endpoints**: RESTful management of script dependencies
- **Performance optimization**: Shared caches for identical dependency sets

### Directory Structure
Scripts can declare dependencies in multiple ways:
```
scripts_repo/
├── python/
│   ├── script.py
│   ├── requirements.txt          # Script-level dependencies
│   └── script_group/
│       ├── main.py
│       └── requirements.txt      # Group-level dependencies
├── js/
│   ├── script.js
│   ├── package.json             # Script-level dependencies
│   └── script_group/
│       ├── main.js
│       └── package.json         # Group-level dependencies
```

### Cache Management
- **Location**: `.deps_cache/python/` and `.deps_cache/nodejs/`
- **Hash-based**: Dependencies grouped by MD5 hash of content
- **Shared**: Identical dependency sets share cache
- **Cleanup**: Automatic cleanup of expired caches (configurable)
- **API**: Cache status and cleanup endpoints available

### API Endpoints
- **GET** `/api/scripts/{id}/dependencies` - View script dependencies
- **POST** `/api/scripts/{id}/dependencies/install` - Install script dependencies
- **GET** `/api/scripts/{id}/environment` - View script execution environment
- **POST** `/api/scripts/batch/dependencies/install` - Batch dependency installation
- **GET** `/api/dependencies/cache/status` - Cache status and statistics
- **POST** `/api/dependencies/cache/cleanup` - Clean expired caches

## Additional Services & Modules

### Media & File Management
- **Media middleware**: Handles file uploads with access control
- **Temporary file service**: Automatic cleanup of upload/processing files
- **File access checker**: Pattern-based security for local file access
- **Resource management**: Configurable retention policies and cleanup intervals

### Monitoring & Logging
- **Rotating logs**: Separate script and gateway log files
- **Execution tracking**: Database records for all script runs
- **Health monitoring**: Built-in health checks and metrics
- **Error tracking**: Structured error logging with types and context

### Configuration Management
- **Environment-based**: Priority: database > environment variables > defaults
- **Dynamic updates**: Runtime setting changes via API
- **Security patterns**: File access restrictions and temp file policies
- **Global state**: Centralized configuration through `Config` class
- **File access restrictions**: Configurable via `local_file_access_patterns` setting
- **Temporary file management**: Automatic cleanup with configurable intervals
