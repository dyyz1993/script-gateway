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

### Node.js Dependencies (package.json)
- **HTTP client**: `axios@^1.13.2`
- **Browser automation**: `puppeteer-core@^24.31.0`
- **Utilities**: `uuid@^9.0.1`

### Special Tooling
- **Dual runtime container**: `nikolaik/python-nodejs:python3.11-nodejs20` image
- **Mirror sources**: Configured to use Tsinghua PyPI and npmmirror for Chinese users
- **Pre-installed common packages**: qrcode, numpy, pandas, playwright, etc.

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

## Docker Deployment

### Container Architecture
- **Base image**: Multi-runtime container with both Python 3.11 and Node.js 20
- **Volume mappings**: Scripts, dependencies, database, and logs are persisted outside container
- **Health checks**: `/health` endpoint monitored every 30 seconds
- **Port exposure**: 8001 (configurable via docker-compose.yml)

### Production Considerations
- **Timeout handling**: Scripts are killed after `TIMEOUT_MIN` minutes (default: 10)
- **Resource isolation**: Each script runs in isolated subprocess
- **Log rotation**: Automatic cleanup based on retention settings
- **Dependency persistence**: New installs are written back to requirements.txt/package.json
