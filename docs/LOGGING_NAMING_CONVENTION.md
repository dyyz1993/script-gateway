# 脚本日志命名规范

## 概述

本文档定义了 ScriptGateway 项目中脚本日志的统一命名规范，确保所有脚本的日志记录一致、可读且易于管理，特别是对于位于二级目录中的脚本。

## 问题背景

在项目中发现，位于二级目录中的脚本（如 `SenseVoiceSmall/transcribe_tool.py`）的日志无法通过 API 正确查看，原因是：

1. 脚本日志文件名使用的是基本文件名（如 `transcribe_tool_2025-12-01.log`）
2. 但 API 查询时使用的是完整路径（如 `SenseVoiceSmall/transcribe_tool`）
3. 导致日志文件名和查询参数不匹配

## 解决方案

### 1. 日志文件命名规范

所有脚本日志文件统一使用以下命名格式：

```
{脚本基本名称}_{日期}.log
```

其中：
- **脚本基本名称**：仅使用文件名，不包含路径和扩展名
- **日期**：使用 YYYY-MM-DD 格式

示例：
- `scripts_repo/python/SenseVoiceSmall/transcribe_tool.py` → `transcribe_tool_2025-12-01.log`
- `scripts_repo/python/whisper_transcriber.py` → `whisper_transcriber_2025-12-01.log`

### 2. 日志记录器获取规范

所有脚本在获取日志记录器时，应使用以下代码：

```python
from src.utils.logger import get_script_logger
import os

# 获取脚本基本名称（去除路径和扩展名）
script_name = os.path.splitext(os.path.basename(__file__))[0]
logger = get_script_logger(script_name)
```

### 3. 日志读取函数规范

日志读取函数（`read_script_logs` 和 `list_script_log_files`）已更新，支持带路径的脚本名称，但内部会自动提取基本名称进行匹配。

## 代码修改

### 1. src/utils/logger.py 修改

已修改以下函数以支持二级目录：

1. `read_script_logs(script_name: str, lines: int = 100)`
   - 添加了 `os.path.basename()` 提取脚本基本名称
   - 添加了详细的函数文档

2. `list_script_log_files(script_name: str)`
   - 添加了 `os.path.basename()` 提取脚本基本名称
   - 添加了详细的函数文档

### 2. app.py 修改

已修改 `api_script_logs` 函数：

```python
@app.get("/api/scripts/{script_id}/logs")
def api_script_logs(script_id: int, lines: int = 100):
    script = get_script_by_id(script_id)
    if not script:
        return JSONResponse(status_code=404, content={"error": "not found"})
    # 提取脚本基本名称（去除路径和扩展名）
    name, _ = os.path.splitext(os.path.basename(script['filename']))
    logs = read_script_logs(name, lines)
    files = list_script_log_files(name)
    return {"logs": logs, "files": files}
```

## 最佳实践

### 1. 脚本开发

所有新开发的脚本应遵循以下模式：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
from typing import Dict, Any

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.utils.logger import get_script_logger

# 获取日志记录器 - 使用基本文件名
script_name = os.path.splitext(os.path.basename(__file__))[0]
logger = get_script_logger(script_name)

def main():
    """主函数"""
    # 记录脚本启动
    logger.info(f"{script_name} 脚本启动")
    
    # 业务逻辑...
    
    # 记录脚本完成
    logger.info(f"{script_name} 脚本完成")

if __name__ == "__main__":
    main()
```

### 2. 脚本模板

已更新 `templates/python_template.py` 文件，确保新创建的脚本遵循正确的日志命名规范。

### 3. 现有脚本检查

对于现有脚本，特别是位于二级目录中的脚本，应检查并确保：

1. 使用 `os.path.basename(__file__)` 获取基本文件名
2. 传递给 `get_script_logger()` 的是基本文件名，不是完整路径

## 测试验证

### 1. 测试用例

```python
# 测试脚本路径解析
script_path = "SenseVoiceSmall/transcribe_tool.py"
expected_name = "transcribe_tool"

# 使用 os.path.splitext(os.path.basename(script_path))[0]
actual_name = os.path.splitext(os.path.basename(script_path))[0]

assert actual_name == expected_name
```

### 2. API 测试

```bash
# 测试获取脚本日志
curl -s "http://0.0.0.0:8001/api/scripts/10/logs?lines=10" | jq .

# 应该返回日志内容，而不是空结果
```

## 维护指南

### 1. 新增脚本

当新增脚本时，特别是位于二级目录中的脚本，确保：

1. 使用正确的日志记录器获取方式
2. 测试日志记录和查看功能

### 2. 代码审查

在代码审查时，特别关注：

1. 日志记录器的获取方式
2. 是否使用了 `os.path.basename()`
3. 日志文件命名是否符合规范

### 3. 问题排查

如果发现日志无法查看的问题，检查：

1. 脚本日志文件名是否符合规范
2. API 查询参数是否正确提取了基本名称
3. 日志文件是否存在于正确的目录

## 总结

通过统一日志命名规范和修改相关代码，我们解决了二级目录脚本日志无法查看的问题。所有脚本，无论位于哪个目录层级，都应使用基本文件名作为日志文件名的前缀，确保日志系统的一致性和可维护性。