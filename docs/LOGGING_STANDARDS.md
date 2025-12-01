# 日志规范文档

## 概述

本文档定义了 ScriptGateway 项目中统一的日志记录规范，确保所有脚本和服务的日志记录一致、可读且易于管理。

## 日志工具类

项目提供了专门的日志工具类 `src/utils/logger.py`，包含以下功能：

- `get_script_logger(script_name: str)`: 获取脚本专用的日志记录器
- `get_gateway_logger()`: 获取网关专用的日志记录器
- `read_script_logs(script_name: str, lines: int = 100)`: 读取脚本日志
- `read_gateway_logs(date: str = None, lines: int = 100)`: 读取网关日志
- `list_script_log_files(script_name: str)`: 列出脚本日志文件
- `read_script_log_file(filename: str, lines: int = 1000)`: 读取指定的脚本日志文件
- `cleanup_expired_logs(script_retention_days: int, gateway_retention_days: int)`: 清理过期日志

## 日志级别

使用标准的 Python logging 级别：

- **DEBUG**: 详细的调试信息，仅在开发或调试时使用
- **INFO**: 一般信息，记录程序正常运行的关键步骤
- **WARNING**: 警告信息，表示可能出现问题，但程序仍能继续运行
- **ERROR**: 错误信息，表示出现了错误，但不影响程序继续运行
- **CRITICAL**: 严重错误，表示出现了严重问题，可能导致程序无法继续运行

## 日志格式

### 标准格式

```
%(asctime)s [%(levelname)s] %(message)s
```

示例：
```
2023-12-01 10:30:45,123 [INFO] 开始处理音频文件: audio.mp3
2023-12-01 10:30:50,456 [ERROR] 处理音频文件失败: 文件格式不支持
```

### 日志内容规范

#### 1. 日志消息应该简洁明了
- 使用清晰、描述性的语言
- 避免使用技术术语或缩写，除非是团队共识的术语
- 包含足够的上下文信息，便于理解问题

#### 2. 包含关键信息
- 操作对象（如文件名、用户ID、请求ID等）
- 操作结果（成功/失败/进行中）
- 关键参数或状态

#### 3. 使用一致的动词
- 开始操作：使用"开始"、"启动"、"初始化"等
- 进行中操作：使用"正在"、"处理中"等
- 完成操作：使用"完成"、"结束"、"成功"等
- 错误情况：使用"失败"、"错误"、"异常"等

## 脚本日志使用规范

### 1. 导入日志工具

```python
from src.utils.logger import get_script_logger
```

### 2. 获取日志记录器

```python
# 使用脚本文件名（不含扩展名）作为日志名称
script_name = os.path.splitext(os.path.basename(__file__))[0]
logger = get_script_logger(script_name)
```

### 3. 日志记录示例

```python
# 记录脚本开始
logger.info(f"开始执行脚本，参数: {json.dumps(params, ensure_ascii=False)}")

# 记录关键步骤
logger.info(f"正在处理文件: {file_path}")

# 记录操作结果
logger.info(f"处理完成，生成文件: {output_file}")

# 记录警告
logger.warning(f"文件 {file_path} 已存在，将被覆盖")

# 记录错误
logger.error(f"处理文件失败: {str(e)}")

# 记录调试信息（仅在调试模式下）
if debug:
    logger.debug(f"详细调试信息: {debug_data}")
```

### 4. 日志级别使用指南

- **INFO**: 记录脚本的主要执行步骤和关键状态变化
- **WARNING**: 记录可能的问题或异常情况，但不影响脚本继续执行
- **ERROR**: 记录错误情况，可能导致部分功能失败
- **DEBUG**: 仅在调试模式下记录详细信息，避免在生产环境中输出过多调试信息

## 日志文件管理

### 1. 日志文件位置

- 脚本日志：`{Config.SCRIPT_LOGS_DIR}/{script_name}_{date}.log`
- 网关日志：`{Config.GATEWAY_LOGS_DIR}/gateway_{date}.log`

### 2. 日志文件命名

- 脚本日志：`{脚本名称}_{日期}.log`，例如：`whisper_transcriber_2023-12-01.log`
- 网关日志：`gateway_{日期}.log`，例如：`gateway_2023-12-01.log`

### 3. 日志轮转与清理

- 定期清理过期日志文件
- 脚本日志保留天数：可配置
- 网关日志保留天数：可配置

## 最佳实践

### 1. 性能考虑

- 避免在循环中记录大量日志
- 对于大量数据，只记录摘要信息
- 使用延迟计算（如使用 % 格式化而不是 f-string）

```python
# 好的做法
logger.info("处理了 %d 个文件", len(files))

# 避免的做法
logger.info(f"处理了 {len(files)} 个文件")
```

### 2. 安全考虑

- 避免在日志中记录敏感信息（密码、密钥、令牌等）
- 对于用户数据，只记录必要的信息
- 在记录错误时，避免暴露系统内部结构

### 3. 异常处理

- 记录异常时，包含足够的上下文信息
- 使用 `logger.exception()` 记录异常堆栈（仅在调试模式下）

```python
try:
    # 业务逻辑
    process_data(data)
except Exception as e:
    if debug:
        logger.exception("处理数据时发生异常")
    else:
        logger.error(f"处理数据失败: {str(e)}")
```

### 4. 结构化日志

对于复杂的信息，考虑使用结构化日志（JSON格式）：

```python
import json

logger.info(f"处理完成: {json.dumps({
    'file': file_path,
    'size': file_size,
    'duration': processing_time,
    'result': 'success'
})}")
```

## 示例：完整的脚本日志实现

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import sys
from typing import Dict, Any

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.core.error_handler import handle_script_errors
from src.utils.logger import get_script_logger

# 获取日志记录器
script_name = os.path.splitext(os.path.basename(__file__))[0]
logger = get_script_logger(script_name)

@handle_script_errors
def process_request(params: Dict[str, Any]) -> Dict[str, Any]:
    """处理请求的主函数"""
    # 记录脚本开始
    logger.info(f"开始执行脚本，参数: {json.dumps(params, ensure_ascii=False)}")
    
    try:
        # 获取参数
        input_file = params.get('input_file')
        output_dir = params.get('output_dir', './output')
        debug = params.get('debug', False)
        
        # 验证输入文件
        if not os.path.exists(input_file):
            logger.error(f"输入文件不存在: {input_file}")
            return {"success": False, "error": "输入文件不存在"}
        
        logger.info(f"正在处理文件: {input_file}")
        
        # 处理文件
        # ... 业务逻辑 ...
        
        # 记录处理结果
        output_file = os.path.join(output_dir, 'result.json')
        logger.info(f"处理完成，生成文件: {output_file}")
        
        return {"success": True, "output_file": output_file}
        
    except Exception as e:
        logger.error(f"处理失败: {str(e)}")
        if debug:
            logger.exception("详细异常信息")
        return {"success": False, "error": str(e)}

def main():
    """主函数"""
    # 解析命令行参数
    # ... 参数解析代码 ...
    
    # 处理请求
    result = process_request(params)
    
    # 输出结果
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
```

## 审核与更新

本日志规范文档应由团队定期审核和更新，以确保其与项目的发展和需求保持一致。