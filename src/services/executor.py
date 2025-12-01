import os
import io
import json
import time
import uuid
import subprocess
import sys
from typing import Dict, Any, Tuple

from ..core.config import Config
from ..core.path_init import get_project_root
from ..core.database import insert_run, update_last_run
from .notifier import send_notify
from ..utils.logger import get_script_logger
from ..api.media_middleware import media_middleware
from ..utils.script_env_manager import script_env_manager

# 维护运行中的进程映射
running_processes = {}  # {script_id: (process, script_name)}


def build_cli_args(args_schema: Dict[str, Any], http_params: Dict[str, Any]) -> Tuple[list, Dict[str, Any]]:
    cli = []
    effective = {}
    for name, meta in args_schema.items():
        flag = meta.get('flag')
        typ = meta.get('type', 'str')
        required = meta.get('required', False)
        val = http_params.get(name)
        if val is None:
            if required:
                raise ValueError(f"missing required param: {name}")
            else:
                continue
        if typ == 'int':
            val = int(val)
        elif typ == 'float':
            val = float(val)
        elif typ == 'bool':
            # accept true/false, 1/0
            if isinstance(val, str):
                val = val.lower() in ['true', '1', 'yes']
            val = 1 if val else 0
        # file/json handled by caller
        cli.extend([flag, str(val)])
        effective[name] = val
    return cli, effective


def save_binary_output(script_name: str, data: bytes) -> Dict[str, Any]:
    ts = int(time.time())
    out_dir_tmpl = Config.OUTPUT_PATH_TEMPLATE.format(script_name=script_name, timestamp=ts)
    out_dir = os.path.join(Config.BASE_DIR, out_dir_tmpl)
    os.makedirs(out_dir, exist_ok=True)
    fname = f"{uuid.uuid4().hex}"
    path = os.path.join(out_dir, fname)
    with open(path, 'wb') as f:
        f.write(data)
    # build url
    rel = os.path.relpath(path, Config.BASE_DIR)
    url = "/" + rel.replace(os.sep, "/")
    
    # 如果配置了base_url，则生成完整URL
    from ..core.database import get_setting
    base_url = get_setting('base_url')
    if base_url:
        base_url = base_url.rstrip('/')
        url = base_url + url
    
    return {"url": url, "filename": fname, "size": len(data)}


def run_script(script: Dict[str, Any], args_schema: Dict[str, Any], http_params: Dict[str, Any]) -> Dict[str, Any]:
    # 使用音视频处理中间件包装脚本执行
    return media_middleware.wrap_script_execution(
        script, args_schema, http_params, _execute_script
    )


def _execute_script(script: Dict[str, Any], args_schema: Dict[str, Any], processed_params: Dict[str, Any]) -> Dict[str, Any]:
    """实际执行脚本的内部函数"""
    script_name = script['filename']
    script_id = script['id']
    stype = script['script_type']
    
    # 获取脚本日志记录器（使用文件名去除路径和扩展名）
    log_name = os.path.splitext(os.path.basename(script_name))[0]
    logger = get_script_logger(log_name)
    logger.info(f"开始执行脚本: {script_name}, 参数: {json.dumps(processed_params, ensure_ascii=False)}")

    # 构建脚本完整路径
    if stype == 'python':
        script_full_path = os.path.join(Config.SCRIPTS_PY_DIR, script_name)
    else:
        script_full_path = os.path.join(Config.SCRIPTS_JS_DIR, script_name)

    # 创建脚本执行环境（包含依赖管理）
    try:
        env_info = script_env_manager.create_execution_environment(script_full_path, script_id)
        logger.info(f"创建执行环境成功，依赖信息: {env_info['deps_info']}")
    except Exception as e:
        logger.error(f"创建执行环境失败: {str(e)}")
        return {
            "status": "error",
            "script_id": script_id,
            "duration_ms": 0,
            "stderr": f"环境创建失败: {str(e)}",
            "code": 500,
            "run_id": None,
        }

    # files provided in processed_params as absolute path (processed by media middleware)
    cli, eff = build_cli_args(args_schema, processed_params)

    # 使用脚本环境管理器执行脚本
    exec_result = script_env_manager.execute_script_with_env(
        env_info, cli, timeout=Config.TIMEOUT_MIN * 60
    )
    
    # 处理执行结果
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    status = 2
    stdout_preview = None
    stderr_text = None
    output_file_url = None
    duration_ms = exec_result.get('duration_ms', 0)
    
    if exec_result['success'] and not exec_result['timeout']:
        # 执行成功
        out = exec_result['stdout']
        try:
            # 尝试解析JSON - 先将字节转换为字符串
            if isinstance(out, bytes):
                out_str = out.decode('utf-8')
            else:
                out_str = out
                
            data = json.loads(out_str)
            status = 1
            stdout_preview = out_str[:1000]
            logger.info(f"执行成功，耗时 {duration_ms}ms")
            result = {
                "status": "success",
                "script_id": script['id'],
                "duration_ms": duration_ms,
                "data": data,
            }
        except Exception:
            # 二进制输出
            output_name = os.path.splitext(os.path.basename(script_name))[0]
            # 确保是字节类型
            if isinstance(out, bytes):
                binary_data = out
            else:
                # 如果是字符串，尝试编码为字节
                try:
                    binary_data = out.encode('latin-1')  # 使用latin-1可以无损地转换0-255的字节值
                except Exception:
                    binary_data = out.encode('utf-8')
            
            meta = save_binary_output(output_name, binary_data)
            status = 1
            logger.info(f"执行成功（二进制输出），耗时 {duration_ms}ms，文件: {meta['url']}")
            result = {
                "status": "success",
                "script_id": script['id'],
                "duration_ms": duration_ms,
                "type": "file",
                **meta,
            }
            output_file_url = meta['url']
        
        update_last_run(script['id'], 1)
        run_id = insert_run(script['id'], started, time.strftime("%Y-%m-%d %H:%M:%S"), duration_ms, status, json.dumps(processed_params), stdout_preview, None, output_file_url)
        result["run_id"] = run_id
        if script.get('notify_enabled') == 1:
            send_notify(f"【成功】{script['filename']}", "执行完毕")
        return result
        
    else:
        # 执行失败
        if exec_result['timeout']:
            stderr_text = "timeout"
            status = 3
            logger.error(f"执行超时，耗时 {duration_ms}ms")
        else:
            stderr_text = exec_result.get('stderr', 'Unknown error')
            status = 2
            logger.error(f"执行失败，耗时 {duration_ms}ms: {stderr_text[:200]}")
        
        update_last_run(script['id'], 2)
        run_id = insert_run(script['id'], started, time.strftime("%Y-%m-%d %H:%M:%S"), duration_ms, status, json.dumps(processed_params), None, stderr_text, None)
        
        error_code = 504 if exec_result['timeout'] else 500
        result = {
            "status": "error",
            "script_id": script['id'],
            "duration_ms": duration_ms,
            "stderr": stderr_text,
            "code": error_code,
            "run_id": run_id,
        }
        
        if script.get('notify_enabled') == 1:
            send_notify(f"【失败】{script['filename']}", stderr_text)
        return result


def terminate_script(script_id: int) -> Dict[str, Any]:
    """中止运行中的脚本"""
    if script_id not in running_processes:
        return {"status": "error", "message": "脚本未在运行中"}
    
    proc, script_name = running_processes[script_id]
    try:
        proc.kill()
        proc.wait(timeout=5)
        del running_processes[script_id]
        # 使用文件名去除路径和扩展名
        log_name = os.path.splitext(os.path.basename(script_name))[0]
        logger = get_script_logger(log_name)
        logger.warning(f"脚本被用户中止")
        return {"status": "success", "message": "脚本已中止"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_running_scripts() -> list:
    """获取运行中的脚本列表"""
    return [script_id for script_id in running_processes.keys()]
