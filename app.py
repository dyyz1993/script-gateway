import os
import sys

# 获取当前文件（app.py）所在目录的绝对路径（即 /app）
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 将项目根目录加入Python搜索路径
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from fastapi import FastAPI, UploadFile, File, Form, Query, Request, Response
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional, Dict, Any
import json
import shutil
import time

from src.core.config import Config, ensure_dirs
from src.core.path_init import initialize_paths
from src.core.database import init_db, list_scripts, get_script_by_id, update_alias, get_setting, set_setting
from src.services.executor import run_script, terminate_script, get_running_scripts
from src.services.scanner import start_scanner
from src.utils.logger import get_gateway_logger, read_script_logs, read_gateway_logs, list_script_log_files, cleanup_expired_logs, read_script_log_file
from src.services.cleanup import start_cleanup_scheduler
from src.api.temp_file_service import temp_file_service
from src.core.error_handler import ScriptError, ErrorType
from src.utils.deps import script_deps_manager
from src.utils.script_env_manager import script_env_manager

app = FastAPI(title="ScriptGateway")

# mount static
ensure_dirs()
app.mount("/static", StaticFiles(directory=Config.STATIC_DIR), name="static")


@app.on_event("startup")
def on_startup():
    # 初始化路径设置，确保所有模块可以正确导入
    initialize_paths()
    
    init_db()
    start_scanner()
    start_cleanup_scheduler()
    temp_file_service.start_cleanup_service()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger = get_gateway_logger()
    start = time.time()
    response = await call_next(request)
    duration = int((time.time() - start) * 1000)
    logger.info(f"{request.method} {request.url.path} {response.status_code} {duration}ms")
    return response


@app.exception_handler(ScriptError)
async def script_error_handler(request: Request, exc: ScriptError):
    """处理脚本执行错误"""
    logger = get_gateway_logger()
    logger.error(f"脚本错误: {exc.message}, 类型: {exc.error_type.value}")
    
    return JSONResponse(
        status_code=400,
        content=exc.to_dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """处理未捕获的异常"""
    logger = get_gateway_logger()
    logger.error(f"未处理的异常: {str(exc)}", exc_info=True)
    
    error_response = ScriptError(
        message=f"系统内部错误: {str(exc)}",
        error_type=ErrorType.SYSTEM
    ).to_dict()
    
    return JSONResponse(
        status_code=500,
        content=error_response
    )


@app.get("/", response_class=HTMLResponse)
def index():
    index_path = os.path.join(Config.STATIC_DIR, "index.html")
    if os.path.isfile(index_path):
        with open(index_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>ScriptGateway</h1><p>管理页面未找到</p>"


@app.get("/deps.html", response_class=HTMLResponse)
def deps_page():
    deps_path = os.path.join(Config.STATIC_DIR, "deps.html")
    if os.path.isfile(deps_path):
        with open(deps_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>依赖管理</h1><p>页面未找到</p>"


@app.get("/settings.html", response_class=HTMLResponse)
def settings_page():
    settings_path = os.path.join(Config.STATIC_DIR, "settings.html")
    if os.path.isfile(settings_path):
        with open(settings_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>系统设置</h1><p>页面未找到</p>"


@app.get("/scripts-swagger.html", response_class=HTMLResponse)
def scripts_swagger_page():
    swagger_path = os.path.join(Config.STATIC_DIR, "scripts-swagger.html")
    if os.path.isfile(swagger_path):
        with open(swagger_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Scripts API</h1><p>页面未找到</p>"


@app.get("/templates.html", response_class=HTMLResponse)
def templates_page():
    templates_path = os.path.join(Config.STATIC_DIR, "templates.html")
    if os.path.isfile(templates_path):
        with open(templates_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>模板管理</h1><p>页面未找到</p>"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/scripts")
def api_list_scripts(
    type: Optional[str] = Query(default=None, regex="^(python|js)$"),
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    items, total = list_scripts(type, search, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@app.patch("/api/scripts/{script_id}/alias")
def api_update_alias(script_id: int, alias: str = Form(...)):
    update_alias(script_id, alias)
    return {"status": "success"}


@app.get("/api/scripts/running")
def api_running_scripts():
    """获取运行中的脚本列表"""
    from src.services.executor import get_running_scripts
    return {"running": list(get_running_scripts())}


@app.get("/api/scripts/swagger-all")
def api_all_scripts_swagger():
    """生成所有脚本的统一Swagger文档"""
    from src.core.database import get_conn
    conn = get_conn()
    scripts = conn.execute("SELECT * FROM scripts WHERE status_load = 1 ORDER BY script_type, filename").fetchall()
    
    paths = {}
    tags = []
    
    for script in scripts:
        script_dict = dict(script)
        script_id = script_dict['id']
        script_name = script_dict['filename']
        script_type = script_dict['script_type']
        
        # 加载参数schema
        args_schema = _load_args_schema(script_dict)
        if not args_schema:
            continue
        
        tag_name = f"{script_type.upper()} Scripts"
        if tag_name not in tags:
            tags.append(tag_name)
        
        has_file = any(meta.get('type') == 'file' for meta in args_schema.values())
        path_key = f"/api/scripts/{script_id}/run"
        
        # 构建GET操作
        get_op = None
        if not has_file:
            params = [
                {
                    "name": k,
                    "in": "query",
                    "required": meta.get('required', False),
                    "schema": {"type": "string"},
                    "description": meta.get('help', '')
                }
                for k, meta in args_schema.items()
            ]
            get_op = {
                "summary": f"Run {script_name}",
                "description": f"执行脚本: {script_name}",
                "tags": [tag_name],
                "parameters": params,
                "responses": {
                    "200": {"description": "Success"},
                    "404": {"description": "Not found"}
                }
            }
        
        # 构建POST操作
        json_props = {k: {"type": "string"} for k, m in args_schema.items() if m.get('type') != 'file'}
        post_op = {
            "summary": f"Run {script_name} (POST)",
            "description": f"执行脚本: {script_name}",
            "tags": [tag_name],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": json_props
                        }
                    }
                }
            },
            "responses": {
                "200": {"description": "Success"},
                "404": {"description": "Not found"}
            }
        }
        
        # 如果有文件参数，添加multipart
        if has_file:
            file_props = {}
            for k, m in args_schema.items():
                if m.get('type') == 'file':
                    file_props[k] = {"type": "string", "format": "binary"}
                else:
                    file_props[k] = {"type": "string"}
            
            post_op["requestBody"]["content"]["multipart/form-data"] = {
                "schema": {
                    "type": "object",
                    "properties": file_props
                }
            }
        
        paths[path_key] = {}
        if get_op:
            paths[path_key]["get"] = get_op
        paths[path_key]["post"] = post_op
    
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "ScriptGateway - Scripts API",
            "version": "1.0.0",
            "description": "所有已加载脚本的API文档"
        },
        "tags": [{"name": tag} for tag in tags],
        "paths": paths
    }


@app.get("/api/scripts/{script_id}")
def api_get_script(script_id: int):
    """获取单个脚本的详细信息"""
    script = get_script_by_id(script_id)
    if not script:
        return JSONResponse(status_code=404, content={"error": "not found"})
    return dict(script)


@app.patch("/api/scripts/{script_id}")
def api_update_script(script_id: int, payload: Dict[str, Any]):
    """更新脚本信息（如notify_enabled等）"""
    from src.core.database import get_conn
    script = get_script_by_id(script_id)
    if not script:
        return JSONResponse(status_code=404, content={"error": "not found"})
    
    conn = get_conn()
    updates = []
    values = []
    
    if 'notify_enabled' in payload:
        updates.append('notify_enabled=?')
        values.append(1 if payload['notify_enabled'] else 0)
    if 'alias' in payload:
        updates.append('alias_name=?')  # 修正为 alias_name
        values.append(payload['alias'])
    
    if updates:
        updates.append("updated_at=datetime('now')")
        values.append(script_id)
        sql = f"UPDATE scripts SET {', '.join(updates)} WHERE id=?"
        conn.execute(sql, values)
        conn.commit()
    
    return {"status": "success"}


@app.get("/api/scripts/{script_id}/schema")
def api_get_schema(script_id: int):
    script = get_script_by_id(script_id)
    if not script:
        return JSONResponse(status_code=404, content={"error": "not found"})
    # prefer sidecar
    name, _ = os.path.splitext(script['filename'])
    sidecar = os.path.join(
        Config.SCRIPTS_PY_DIR if script['script_type'] == 'python' else Config.SCRIPTS_JS_DIR,
        f"{name}._map.json",
    )
    if os.path.isfile(sidecar):
        with open(sidecar, 'r', encoding='utf-8') as f:
            return json.load(f)
    if script.get('args_schema'):
        return json.loads(script['args_schema'])
    return {}


@app.get("/api/scripts/{script_id}/content")
def api_get_script_content(script_id: int):
    """获取脚本文件内容"""
    script = get_script_by_id(script_id)
    if not script:
        return JSONResponse(status_code=404, content={"error": "script not found"})
    
    file_path = os.path.join(
        Config.SCRIPTS_PY_DIR if script['script_type'] == 'python' else Config.SCRIPTS_JS_DIR,
        script['filename']
    )
    
    if not os.path.isfile(file_path):
        return JSONResponse(status_code=404, content={"error": "file not found"})
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {
            "status": "success",
            "filename": script['filename'],
            "alias": script.get('alias_name'),  # 修正为 alias_name
            "content": content
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.put("/api/scripts/{script_id}/content")
def api_update_script_content(script_id: int, payload: Dict[str, Any]):
    """更新脚本文件内容"""
    from src.services.scanner import parse_and_register
    
    script = get_script_by_id(script_id)
    if not script:
        return JSONResponse(status_code=404, content={"error": "script not found"})
    
    content = payload.get('content', '')
    alias = payload.get('alias')
    
    if not content:
        return JSONResponse(status_code=400, content={"error": "content is required"})
    
    file_path = os.path.join(
        Config.SCRIPTS_PY_DIR if script['script_type'] == 'python' else Config.SCRIPTS_JS_DIR,
        script['filename']
    )
    
    if not os.path.isfile(file_path):
        return JSONResponse(status_code=404, content={"error": "file not found"})
    
    try:
        # 保存文件内容
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 更新备注
        if alias is not None:
            from src.core.database import get_conn
            conn = get_conn()
            conn.execute(
                "UPDATE scripts SET alias_name=?, updated_at=datetime('now') WHERE id=?",  # 修正为 alias_name
                (alias, script_id)
            )
            conn.commit()
        
        # 重新加载脚本
        try:
            parse_and_register(file_path)
        except Exception:
            pass
        
        return {"status": "success"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/scripts/{script_id}/run")
async def api_run_script(
    script_id: int,
    request: Request,
):
    script = get_script_by_id(script_id)
    if not script:
        return JSONResponse(status_code=404, content={"error": "not found"})
    # load schema
    name, _ = os.path.splitext(script['filename'])
    sidecar = os.path.join(
        Config.SCRIPTS_PY_DIR if script['script_type'] == 'python' else Config.SCRIPTS_JS_DIR,
        f"{name}._map.json",
    )
    args_schema: Dict[str, Any]
    if os.path.isfile(sidecar):
        with open(sidecar, 'r', encoding='utf-8') as f:
            args_schema = json.load(f)
    elif script.get('args_schema'):
        args_schema = json.loads(script['args_schema'])
    else:
        return JSONResponse(status_code=400, content={"error": "schema missing"})

    http_params: Dict[str, Any] = {}
    content_type = request.headers.get('content-type', '')
    if content_type.startswith('application/json'):
        try:
            http_params = await request.json()
            if not isinstance(http_params, dict):
                return JSONResponse(status_code=400, content={"error": "invalid json payload"})
        except Exception:
            return JSONResponse(status_code=400, content={"error": "invalid json payload"})
    else:
        form = await request.form()
        payload = form.get('payload')
        if payload:
            try:
                http_params = json.loads(payload)
            except Exception:
                return JSONResponse(status_code=400, content={"error": "invalid json payload"})
        # handle file uploads with dynamic field names
        import uuid
        tmp_dir = os.path.join(Config.BASE_DIR, 'tmp', 'upload')
        os.makedirs(tmp_dir, exist_ok=True)
        for key, val in form.multi_items():
            if hasattr(val, 'filename'):
                # UploadFile
                data = await val.read()
                save_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}_{val.filename}")
                with open(save_path, 'wb') as f:
                    f.write(data)
                http_params[key] = save_path
            else:
                # non-file field
                if key != 'payload':
                    http_params[key] = str(val)

    result = run_script(script, args_schema, http_params)
    return result


# helpers

def _load_args_schema(script: Dict[str, Any]) -> Dict[str, Any]:
    name, _ = os.path.splitext(script['filename'])
    sidecar = os.path.join(
        Config.SCRIPTS_PY_DIR if script['script_type'] == 'python' else Config.SCRIPTS_JS_DIR,
        f"{name}._map.json",
    )
    if os.path.isfile(sidecar):
        with open(sidecar, 'r', encoding='utf-8') as f:
            return json.load(f)
    if script.get('args_schema'):
        return json.loads(script['args_schema'])
    return {}


@app.get("/api/scripts/{script_id}/run")
async def api_run_script_get(script_id: int, request: Request):
    script = get_script_by_id(script_id)
    if not script:
        return JSONResponse(status_code=404, content={"error": "not found"})
    args_schema = _load_args_schema(script)
    # reject GET if file param exists
    if any(meta.get('type') == 'file' for meta in args_schema.values()):
        return JSONResponse(status_code=405, content={"error": "file param requires POST"})
    http_params = dict(request.query_params)
    return run_script(script, args_schema, http_params)


@app.post("/api/scripts/create")
async def api_create_script(payload: Dict[str, Any]):
    import os
    from src.services.scanner import parse_and_register
    runtime = payload.get('runtime', 'python')
    filename = payload.get('filename', '')
    alias = payload.get('alias', '')
    content = payload.get('content', '')
    if not content:
        return JSONResponse(status_code=400, content={"error": "content is required"})
    # 选择目标目录与扩展名
    if runtime not in ('python', 'js'):
        return JSONResponse(status_code=400, content={"error": "invalid runtime"})
    dest_root = Config.SCRIPTS_PY_DIR if runtime == 'python' else Config.SCRIPTS_JS_DIR
    # 自动补全扩展名
    if not filename:
        filename = f"new_{int(time.time())}.{ 'py' if runtime=='python' else 'js'}"
    else:
        base, ext = os.path.splitext(filename)
        if not ext:
            filename = f"{filename}.{ 'py' if runtime=='python' else 'js'}"
    # 避免重名：添加 _vN 后缀
    base, ext = os.path.splitext(os.path.basename(filename))
    dest_dir = dest_root
    dest_path = os.path.join(dest_dir, base + ext)
    n = 1
    while os.path.exists(dest_path):
        dest_path = os.path.join(dest_dir, f"{base}_v{n}{ext}")
        n += 1
    os.makedirs(dest_dir, exist_ok=True)
    with open(dest_path, 'w', encoding='utf-8') as f:
        f.write(content)
    # 立即注册解析
    try:
        parse_and_register(dest_path)
    except Exception:
        pass
    return {"status": "success", "path": dest_path, "filename": os.path.basename(dest_path)}


@app.post("/api/scripts/upload")
async def api_upload_scripts(request: Request):
    import os, json
    from src.services.scanner import parse_and_register
    form = await request.form()
    runtime = form.get('runtime')  # 可选
    # 收集文件（支持多文件与目录上传）
    files = []
    rel_paths = []
    if 'rel_paths' in form:
        try:
            rel_paths = json.loads(form.get('rel_paths') or '[]')
        except Exception:
            rel_paths = []
    idx = 0
    for key, val in form.multi_items():
        if hasattr(val, 'filename'):
            files.append(val)
    if not files:
        return JSONResponse(status_code=400, content={"error": "no files"})
    created = []
    for i, up in enumerate(files):
        name = up.filename
        # 依据扩展或指定runtime选择目录
        _, ext = os.path.splitext(name)
        rt = runtime
        if not rt:
            if ext == '.py':
                rt = 'python'
            elif ext == '.js':
                rt = 'js'
            else:
                rt = 'python'
        dest_root = Config.SCRIPTS_PY_DIR if rt == 'python' else Config.SCRIPTS_JS_DIR
        # 处理相对路径（目录上传）
        rel = rel_paths[i] if i < len(rel_paths) else ''
        rel_dir = os.path.dirname(rel) if rel else ''
        target_dir = os.path.join(dest_root, rel_dir) if rel_dir else dest_root
        os.makedirs(target_dir, exist_ok=True)
        base, extn = os.path.splitext(os.path.basename(name))
        dest_path = os.path.join(target_dir, base + extn)
        n = 1
        while os.path.exists(dest_path):
            dest_path = os.path.join(target_dir, f"{base}_v{n}{extn}")
            n += 1
        data = await up.read()
        with open(dest_path, 'wb') as f:
            f.write(data)
        try:
            parse_and_register(dest_path)
        except Exception:
            pass
        created.append({"path": dest_path, "filename": os.path.basename(dest_path)})
    return {"status": "success", "created": created}


@app.get("/api/scripts/{script_id}/curl")
def api_curl(script_id: int):
    script = get_script_by_id(script_id)
    if not script:
        return JSONResponse(status_code=404, content={"error": "not found"})
    args = _load_args_schema(script)
    base = f"http://localhost:8001/api/scripts/{script_id}/run"
    has_file = any(meta.get('type') == 'file' for meta in args.values())
    # GET example
    get_cmd = None
    if not has_file:
        qs = "&".join([f"{k}={str(meta.get('default', 'value'))}" for k, meta in args.items()])
        get_cmd = f"curl \"{base}?{qs}\""
    # POST examples
    json_payload = {k: meta.get('default', 'value') for k, meta in args.items() if meta.get('type') != 'file'}
    post_json = f"curl -X POST \"{base}\" -H 'Content-Type: application/json' -d '{json.dumps(json_payload)}'"
    multipart_parts = [f"-F 'payload={json.dumps(json_payload)}'"] + [f"-F '{k}=@/path/to/file'" for k, meta in args.items() if meta.get('type') == 'file']
    post_multipart = f"curl -X POST \"{base}\" {' '.join(multipart_parts)}" if has_file else None
    return {"get": get_cmd, "post_json": post_json, "post_multipart": post_multipart}


@app.get("/api/scripts/{script_id}/schema/download")
def api_schema_download(script_id: int):
    script = get_script_by_id(script_id)
    if not script:
        return JSONResponse(status_code=404, content={"error": "not found"})
    name, _ = os.path.splitext(script['filename'])
    sidecar = os.path.join(
        Config.SCRIPTS_PY_DIR if script['script_type'] == 'python' else Config.SCRIPTS_JS_DIR,
        f"{name}._map.json",
    )
    if os.path.isfile(sidecar):
        return FileResponse(sidecar, filename=f"{name}._map.json")
    return JSONResponse(status_code=404, content={"error": "sidecar missing"})


@app.delete("/api/scripts/{script_id}")
def api_delete_script(script_id: int, delete_file: bool = False):
    from src.core.database import get_conn
    conn = get_conn()
    script = get_script_by_id(script_id)
    if not script:
        return JSONResponse(status_code=404, content={"error": "not found"})
    # delete db record
    conn.execute("DELETE FROM scripts WHERE id=?", (script_id,))
    conn.commit()
    # delete sidecar and static resources
    name, _ = os.path.splitext(script['filename'])
    sidecar = os.path.join(
        Config.SCRIPTS_PY_DIR if script['script_type'] == 'python' else Config.SCRIPTS_JS_DIR,
        f"{name}._map.json",
    )
    if os.path.isfile(sidecar):
        os.remove(sidecar)
    # static outputs
    out_dir = os.path.join(Config.BASE_DIR, Config.OUTPUT_PATH_TEMPLATE.format(script_name=name, timestamp=""))
    # remove all resembling dirs
    static_root = os.path.join(Config.BASE_DIR, "static", name)
    if os.path.isdir(static_root):
        shutil.rmtree(static_root, ignore_errors=True)
    # physical script
    if delete_file:
        path = os.path.join(Config.SCRIPTS_PY_DIR if script['script_type'] == 'python' else Config.SCRIPTS_JS_DIR, script['filename'])
        if os.path.isfile(path):
            os.remove(path)
    return {"status": "success"}


@app.post("/api/scripts/batch_delete")
def api_batch_delete(payload: Dict[str, Any]):
    ids = payload.get('ids') or []
    delete_file = bool(payload.get('delete_file', False))
    ok = 0
    for i in ids:
        try:
            api_delete_script(int(i), delete_file)
            ok += 1
        except Exception:
            pass
    return {"deleted": ok, "requested": len(ids)}


@app.patch("/api/scripts/{script_id}/notify")
def api_toggle_notify(script_id: int, enabled: int = Form(...)):
    from src.core.database import get_conn
    conn = get_conn()
    conn.execute("UPDATE scripts SET notify_enabled=?, updated_at=datetime('now') WHERE id=?", (1 if enabled else 0, script_id))
    conn.commit()
    return {"status": "success", "enabled": 1 if enabled else 0}


@app.get("/api/settings")
def api_get_settings():
    from src.core.database import get_setting
    keys = ["scan_interval", "timeout_min", "notify_url", "script_log_retention_days", "gateway_log_retention_days", "scan_ignore_patterns", "base_url", 
            "temp_file_cleanup_interval_hours", "temp_file_max_age_hours_default", "local_file_access_patterns"]
    vals = {k: get_setting(k) for k in keys}
    vals["scripts_py_dir"] = Config.SCRIPTS_PY_DIR
    vals["scripts_js_dir"] = Config.SCRIPTS_JS_DIR
    vals["static_dir"] = Config.STATIC_DIR
    return vals


@app.put("/api/settings")
def api_put_settings(payload: Dict[str, Any]):
    from src.core.database import set_setting
    for k in ["scan_interval", "timeout_min", "notify_url", "script_log_retention_days", "gateway_log_retention_days", "scan_ignore_patterns", "base_url", 
              "temp_file_cleanup_interval_hours", "temp_file_max_age_hours_default", "local_file_access_patterns"]:
        if k in payload:
            set_setting(k, str(payload[k]))
            
            # 如果更新的是文件访问模式，同时更新全局media_middleware中的FileAccessChecker
            if k == "local_file_access_patterns":
                from src.api.media_middleware import media_middleware
                # 处理逗号分隔或换行分隔的模式
                patterns_str = str(payload[k])
                if ',' in patterns_str:
                    pattern_list = [p.strip() for p in patterns_str.split(',') if p.strip()]
                else:
                    pattern_list = [p.strip() for p in patterns_str.split('\n') if p.strip()]
                
                media_middleware.media_processor.file_access_checker.update_patterns(pattern_list)
                
    return {"status": "success"}


@app.get("/api/deps")
def api_list_deps(runtime: str = Query('python', regex="^(python|js|javascript)$")):
    if runtime == 'python':
        from src.utils.deps import list_python_deps
        return {"runtime": "python", "installed": list_python_deps()}
    elif runtime == 'js' or runtime == 'javascript':
        from src.utils.deps import list_node_deps
        return {"runtime": runtime, "installed": list_node_deps()}
    return JSONResponse(status_code=400, content={"error": "invalid runtime"})


@app.post("/api/deps/parse")
def api_parse_deps(payload: Dict[str, Any]):
    runtime = payload.get('runtime', 'python')
    content = payload.get('content', '')
    
    if runtime == 'python':
        from src.utils.deps import parse_requirements_text, list_python_deps
        requested = parse_requirements_text(content)
        installed = list_python_deps()
    elif runtime == 'js' or runtime == 'javascript':
        from src.utils.deps import parse_package_json, list_node_deps
        requested = parse_package_json(content)
        installed = list_node_deps()
    else:
        return JSONResponse(status_code=400, content={"error": "unsupported runtime"})
    
    # 简单冲突检测（仅Python）
    conflicts = []
    if runtime == 'python':
        inst_map = {d['name'].lower(): d['version'] for d in installed}
        for r in requested:
            name = r['name'].lower()
            target = r['version']
            cur = inst_map.get(name)
            if cur and target and ('==' in target):
                target_ver = target.replace('==', '').strip()
                if cur != target_ver:
                    conflicts.append({
                        'name': r['name'],
                        'current_version': cur,
                        'requested_version': target_ver
                    })
    
    return {"runtime": runtime, "requested": requested, "conflicts": conflicts}


@app.post("/api/deps/install")
def api_install_deps(payload: Dict[str, Any]):
    runtime = payload.get('runtime', 'python')
    deps = payload.get('deps', [])
    
    if runtime == 'python':
        from src.utils.deps import list_python_deps, detect_conflicts, install_python_deps
        conflicts = detect_conflicts(list_python_deps(), deps)
        log, status = install_python_deps(deps)
        return {"status": "success" if status == 1 else "error", "conflicts": conflicts, "log": log}
    elif runtime == 'js' or runtime == 'javascript':
        from src.utils.deps import install_node_deps
        log, status = install_node_deps(deps)
        return {"status": "success" if status == 1 else "error", "log": log}
    
    return JSONResponse(status_code=400, content={"error": "unsupported runtime"})


@app.get("/api/deps/config-file")
def api_get_config_file_deps(runtime: str = Query('python', regex="^(python|js|javascript)$")):
    """读取配置文件中的依赖列表"""
    if runtime == 'python':
        req_file = os.path.join(Config.BASE_DIR, 'requirements.txt')
        if not os.path.exists(req_file):
            return {"runtime": "python", "deps": []}
        
        from src.utils.deps import parse_requirements_text
        with open(req_file, 'r', encoding='utf-8') as f:
            content = f.read()
        deps = parse_requirements_text(content)
        return {"runtime": "python", "deps": deps}
    
    elif runtime == 'js' or runtime == 'javascript':
        pkg_file = os.path.join(Config.BASE_DIR, 'package.json')
        if not os.path.exists(pkg_file):
            return {"runtime": runtime, "deps": []}
        
        from src.utils.deps import parse_package_json
        with open(pkg_file, 'r', encoding='utf-8') as f:
            content = f.read()
        deps = parse_package_json(content)
        return {"runtime": runtime, "deps": deps}
    
    return JSONResponse(status_code=400, content={"error": "invalid runtime"})


@app.get("/swagger")
def swagger_redirect():
    """主Swagger入口重定向到脚本 API文档"""
    return RedirectResponse(url="/scripts-swagger.html")


def _template_path(runtime: str) -> str:
    ext = 'py' if runtime == 'python' else 'js'
    return os.path.join(Config.TEMPLATES_DIR, f"{runtime}_template.{ext}")

PY_DEFAULT = """import argparse
import json
import sys

ARGS_MAP = {
    "name": {"flag": "--name", "type": "str", "required": True, "help": "姓名"},
    "photo": {"flag": "--photo", "type": "file", "required": False, "help": "图片路径"}
}

def get_schema():
    return json.dumps(ARGS_MAP, ensure_ascii=False)

def main():
    parser = argparse.ArgumentParser()
    for key, cfg in ARGS_MAP.items():
        parser.add_argument(cfg["flag"], required=cfg.get("required", False), help=cfg.get("help", ""))
    if len(sys.argv) > 1 and sys.argv[1] == "--_sys_get_schema":
        print(get_schema())
        sys.exit(0)
    args = parser.parse_args()
    name = getattr(args, 'name', 'World')
    result = {"msg": f"Hello {name}", "code": 200}
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
"""

JS_DEFAULT = """const ARGS_MAP = {
  name: { flag: "--name", type: "str", required: true, help: "姓名" },
  file: { flag: "--file", type: "file", required: false, help: "文件路径" },
};

function getSchema() { return JSON.stringify(ARGS_MAP); }
function parseArgs(argv) {
  const args = {}; for (let i=0;i<argv.length;i++){ const t = argv[i]; for (const [k,m] of Object.entries(ARGS_MAP)){ if(t===m.flag && i+1<argv.length){ args[k]=argv[i+1]; } } }
  return args;
}
function main(){ const argv = process.argv.slice(2); if(argv[0] === "--_sys_get_schema"){ console.log(getSchema()); return; } const args = parseArgs(argv); const name = args.name || "World"; console.log(JSON.stringify({ msg: `Hello ${name}`, code: 200 })); }
if (require.main === module) { main(); }
"""

@app.get("/api/templates/{runtime}")
def api_get_template(runtime: str):
    if runtime not in ("python", "js"):
        return JSONResponse(status_code=400, content={"error": "unsupported runtime"})
    path = _template_path(runtime)
    if not os.path.isfile(path):
        # initialize with defaults
        os.makedirs(Config.TEMPLATES_DIR, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(PY_DEFAULT if runtime == 'python' else JS_DEFAULT)
    with open(path, 'r', encoding='utf-8') as f:
        return {"runtime": runtime, "content": f.read()}


@app.put("/api/templates/{runtime}")
def api_put_template(runtime: str, payload: Dict[str, Any]):
    if runtime not in ("python", "js"):
        return JSONResponse(status_code=400, content={"error": "unsupported runtime"})
    content = payload.get('content', '')
    path = _template_path(runtime)
    os.makedirs(Config.TEMPLATES_DIR, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return {"status": "success"}


@app.get("/api/templates/{runtime}/download")
def api_template_download(runtime: str):
    if runtime not in ("python", "js"):
        return JSONResponse(status_code=400, content={"error": "unsupported runtime"})
    path = _template_path(runtime)
    if not os.path.isfile(path):
        return JSONResponse(status_code=404, content={"error": "not found"})
    return FileResponse(path, filename=os.path.basename(path))


@app.post("/api/templates/{runtime}/reset")
def api_template_reset(runtime: str):
    if runtime not in ("python", "js"):
        return JSONResponse(status_code=400, content={"error": "unsupported runtime"})
    path = _template_path(runtime)
    os.makedirs(Config.TEMPLATES_DIR, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(PY_DEFAULT if runtime == 'python' else JS_DEFAULT)
    return {"status": "success"}


@app.get("/api/scripts/{script_id}/swagger")
def api_script_swagger(script_id: int):
    script = get_script_by_id(script_id)
    if not script:
        return JSONResponse(status_code=404, content={"error": "not found"})
    args = _load_args_schema(script)
    has_file = any(meta.get('type') == 'file' for meta in args.values())
    path_key = f"/api/scripts/{script_id}/run"
    # build minimal openapi fragment
    get_op = None
    if not has_file:
        params = [{"name": k, "in": "query", "required": meta.get('required', False), "schema": {"type": "string"}, "description": meta.get('help', '')} for k, meta in args.items()]
        get_op = {"summary": f"Run {script['filename']} (GET)", "parameters": params}
    post_op = {"summary": f"Run {script['filename']} (POST)", "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "properties": {k: {"type": "string"} for k, m in args.items() if m.get('type') != 'file'}}}}}}
    if has_file:
        # add multipart
        post_op["requestBody"]["content"]["multipart/form-data"] = {"schema": {"type": "object", "properties": {k: {"type": "string", "format": "binary"} if m.get('type') == 'file' else {"type": "string"} for k, m in args.items()}}}
    paths = {path_key: {}}
    if get_op:
        paths[path_key]["get"] = get_op
    paths[path_key]["post"] = post_op
    return {"openapi": "3.0.0", "info": {"title": script['filename'], "version": "1.0.0"}, "paths": paths}


@app.get("/api/scripts/{script_id}/logs")
def api_script_logs(script_id: int, lines: int = 100):
    script = get_script_by_id(script_id)
    if not script:
        return JSONResponse(status_code=404, content={"error": "not found"})
    name, _ = os.path.splitext(script['filename'])
    logs = read_script_logs(name, lines)
    files = list_script_log_files(name)
    return {"logs": logs, "files": files}


@app.get("/api/scripts/logs/file/{filename}")
def api_read_log_file(filename: str, lines: int = 1000):
    """读取指定的日志文件内容"""
    # 安全检查：只允许读取.log文件
    if not filename.endswith('.log'):
        return JSONResponse(status_code=400, content={"error": "invalid file"})
    
    content = read_script_log_file(filename, lines)
    if content:
        return {"logs": content, "filename": filename}
    else:
        return JSONResponse(status_code=404, content={"error": "file not found"})


@app.get("/api/logs/gateway")
def api_gateway_logs(date: Optional[str] = None, lines: int = 100):
    logs = read_gateway_logs(date, lines)
    return {"logs": logs, "date": date or time.strftime('%Y-%m-%d')}


@app.post("/api/logs/cleanup")
def api_cleanup_logs():
    """手动清理过期日志"""
    try:
        script_days = int(get_setting('script_log_retention_days') or '7')
        gateway_days = int(get_setting('gateway_log_retention_days') or '7')
        result = cleanup_expired_logs(script_days, gateway_days)
        return {"status": "success", "cleaned": result}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/scripts/{script_id}/terminate")
def api_terminate_script(script_id: int):
    """中止运行中的脚本"""
    result = terminate_script(script_id)
    if result['status'] == 'error':
        return JSONResponse(status_code=400, content=result)
    return result


# 临时文件管理 API

@app.get("/api/temp-files/status")
def api_temp_files_status():
    """获取临时文件清理状态"""
    return temp_file_service.get_cleanup_status()


@app.post("/api/temp-files/cleanup")
def api_temp_files_cleanup():
    """执行一次临时文件清理"""
    try:
        deleted_count = temp_file_service.cleanup_once()
        return {
            "status": "success",
            "deleted_count": deleted_count,
            "message": f"已清理 {deleted_count} 个临时文件"
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"清理失败: {str(e)}"
            }
        )


@app.post("/api/temp-files/interval")
def api_temp_files_set_interval(interval_hours: float = Form(...)):
    """设置临时文件清理间隔（小时）"""
    try:
        if interval_hours <= 0:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "清理间隔必须大于0"
                }
            )
        
        temp_file_service.update_cleanup_interval(interval_hours)
        
        # 保存到数据库设置
        set_setting("temp_file_cleanup_interval", str(interval_hours))
        
        return {
            "status": "success",
            "interval_hours": interval_hours,
            "message": f"清理间隔已设置为 {interval_hours} 小时"
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"设置失败: {str(e)}"
            }
        )


# 文件访问限制 API

@app.get("/api/file-access/patterns")
def api_file_access_patterns():
    """获取文件访问限制模式"""
    from src.utils.file_access_checker import FileAccessChecker
    checker = FileAccessChecker()
    return {
        "patterns": checker.get_allowed_patterns()
    }


@app.post("/api/file-access/patterns")
def api_file_access_set_patterns(patterns: str = Form(...)):
    """设置文件访问限制模式（每行一个模式）"""
    try:
        from src.utils.file_access_checker import FileAccessChecker
        from src.api.media_middleware import media_middleware
        checker = FileAccessChecker()
        
        # 按行分割模式
        pattern_list = [p.strip() for p in patterns.split('\n') if p.strip()]
        
        # 更新模式
        checker.update_patterns(pattern_list)
        
        # 更新全局media_middleware中的FileAccessChecker
        media_middleware.media_processor.file_access_checker.update_patterns(pattern_list)
        
        # 保存到数据库设置
        set_setting("local_file_access_patterns", '\n'.join(pattern_list))
        
        return {
            "status": "success",
            "patterns": pattern_list,
            "message": f"已更新 {len(pattern_list)} 个访问模式"
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"设置失败: {str(e)}"
            }
        )



# ========== 脚本依赖管理 API ==========

@app.get("/api/scripts/{script_id}/dependencies")
def api_get_script_dependencies(script_id: int):
    """获取脚本的依赖信息"""
    script = get_script_by_id(script_id)
    if not script:
        return JSONResponse(status_code=404, content={"error": "script not found"})
    
    script_path = os.path.join(
        Config.SCRIPTS_PY_DIR if script['script_type'] == 'python' else Config.SCRIPTS_JS_DIR,
        script['filename']
    )
    
    if not os.path.exists(script_path):
        return JSONResponse(status_code=404, content={"error": "script file not found"})
    
    try:
        deps_info = script_deps_manager.scan_script_dependencies(script_path)
        env_info = script_deps_manager.get_execution_environment(script_path)
        validation = script_env_manager.validate_dependencies(script_path)
        
        return {
            "script_id": script_id,
            "script_path": script_path,
            "dependencies": deps_info,
            "environment": env_info,
            "validation": validation
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"获取依赖信息失败: {str(e)}"}
        )


@app.post("/api/scripts/{script_id}/dependencies/install")
def api_install_script_dependencies(script_id: int, force_reinstall: bool = Form(False)):
    """安装脚本的依赖"""
    script = get_script_by_id(script_id)
    if not script:
        return JSONResponse(status_code=404, content={"error": "script not found"})
    
    script_path = os.path.join(
        Config.SCRIPTS_PY_DIR if script['script_type'] == 'python' else Config.SCRIPTS_JS_DIR,
        script['filename']
    )
    
    if not os.path.exists(script_path):
        return JSONResponse(status_code=404, content={"error": "script file not found"})
    
    try:
        result = script_deps_manager.install_script_dependencies(script_path, force_reinstall)
        return {
            "status": "success",
            "script_id": script_id,
            "result": result
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"安装依赖失败: {str(e)}"}
        )


@app.get("/api/scripts/{script_id}/environment")
def api_get_script_environment(script_id: int):
    """获取脚本的执行环境信息"""
    script = get_script_by_id(script_id)
    if not script:
        return JSONResponse(status_code=404, content={"error": "script not found"})
    
    script_path = os.path.join(
        Config.SCRIPTS_PY_DIR if script['script_type'] == 'python' else Config.SCRIPTS_JS_DIR,
        script['filename']
    )
    
    if not os.path.exists(script_path):
        return JSONResponse(status_code=404, content={"error": "script file not found"})
    
    try:
        env_info = script_env_manager.get_script_info(script_path)
        return {
            "status": "success",
            "script_id": script_id,
            "environment": env_info
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"获取环境信息失败: {str(e)}"}
        )


@app.post("/api/scripts/batch/dependencies/install")
def api_batch_install_dependencies(payload: Dict[str, Any]):
    """批量安装脚本依赖"""
    script_ids = payload.get('script_ids', [])
    force_reinstall = payload.get('force_reinstall', False)
    
    if not script_ids:
        return JSONResponse(status_code=400, content={"error": "script_ids is required"})
    
    script_paths = []
    for script_id in script_ids:
        script = get_script_by_id(script_id)
        if script:
            script_path = os.path.join(
                Config.SCRIPTS_PY_DIR if script['script_type'] == 'python' else Config.SCRIPTS_JS_DIR,
                script['filename']
            )
            if os.path.exists(script_path):
                script_paths.append(script_path)
    
    if not script_paths:
        return JSONResponse(status_code=404, content={"error": "no valid scripts found"})
    
    try:
        result = script_env_manager.batch_install_dependencies(script_paths, force_reinstall)
        return {
            "status": "success",
            "result": result
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"批量安装依赖失败: {str(e)}"}
        )


@app.get("/api/dependencies/cache/status")
def api_get_cache_status():
    """获取依赖缓存状态"""
    try:
        cache_base = script_deps_manager.cache_base
        cache_info = {
            "cache_base": cache_base,
            "python_cache": os.path.join(cache_base, "python"),
            "nodejs_cache": os.path.join(cache_base, "nodejs"),
            "python_cache_count": 0,
            "nodejs_cache_count": 0,
            "total_size_mb": 0
        }
        
        # 计算缓存统计
        for runtime in ['python', 'nodejs']:
            runtime_dir = os.path.join(cache_base, runtime)
            if os.path.exists(runtime_dir):
                for cache_dir in os.listdir(runtime_dir):
                    cache_path = os.path.join(runtime_dir, cache_dir)
                    if os.path.isdir(cache_path):
                        cache_info[f"{runtime}_cache_count"] += 1
                        # 计算目录大小
                        dir_size = sum(
                            os.path.getsize(os.path.join(dirpath, filename))
                            for dirpath, _, filenames in os.walk(cache_path)
                            for filename in filenames
                            if os.path.isfile(os.path.join(dirpath, filename))
                        )
                        cache_info["total_size_mb"] += dir_size / (1024 * 1024)
        
        return {
            "status": "success",
            "cache_info": cache_info
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"获取缓存状态失败: {str(e)}"}
        )


@app.post("/api/dependencies/cache/cleanup")
def api_cleanup_dependencies_cache(max_age_days: int = Form(30)):
    """清理过期的依赖缓存"""
    try:
        cleaned = script_deps_manager.cleanup_cache(max_age_days)
        return {
            "status": "success",
            "cleaned": cleaned,
            "message": f"已清理 {cleaned['python'] + cleaned['nodejs']} 个缓存目录，释放 {cleaned['total_size_mb']:.2f} MB 空间"
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"清理缓存失败: {str(e)}"}
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
