# ScriptGateway 项目结构说明

## 目录结构

```
server-auto-load/
├── src/                          # 所有 Python 源代码
│   ├── api/                      # API 相关模块
│   │   ├── media_middleware.py   # 媒体处理中间件
│   │   ├── media_processor.py    # 媒体处理器
│   │   ├── temp_file_manager.py   # 临时文件管理器
│   │   └── temp_file_service.py  # 临时文件服务
│   ├── core/                     # 核心功能模块
│   │   ├── config.py             # 配置管理
│   │   ├── database.py           # 数据库操作
│   │   └── error_handler.py      # 错误处理
│   ├── services/                 # 服务层模块
│   │   ├── cleanup.py            # 清理服务
│   │   ├── executor.py           # 脚本执行器
│   │   ├── notifier.py           # 通知服务
│   │   └── scanner.py            # 脚本扫描器
│   └── utils/                    # 工具模块
│       ├── deps.py               # 依赖管理
│       ├── file_access_checker.py # 文件访问检查
│       └── logger.py             # 日志工具
├── scripts_repo/                 # 脚本仓库
│   ├── python/                   # Python 脚本
│   └── js/                       # JavaScript 脚本
├── static/                       # 静态文件
├── templates/                     # 模板文件
├── app.py                        # FastAPI 应用程序
```

## 启动方式

使用 `app.py` 启动应用程序：

```bash
python app.py
```

## 模块说明

### src/api
包含所有 API 相关的模块，负责处理 HTTP 请求和响应。

### src/core
包含应用程序的核心功能，如配置管理、数据库操作和错误处理。

### src/services
包含各种服务实现，如脚本执行、扫描、通知和清理服务。

### src/utils
包含各种工具函数和辅助模块，如依赖管理、文件访问检查和日志工具。

## 导入规则

- 使用相对导入引用同一包内的模块
- 使用绝对导入引用其他包的模块
- 示例：
  ```python
  # 同一包内
  from .config import Config
  
  # 其他包
  from ..core.database import get_conn
  ```