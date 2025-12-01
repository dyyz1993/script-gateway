import argparse
import json
import sys
import requests  # 这个需要不同版本

ARGS_MAP = {
    "url": {"flag": "--url", "type": "str", "required": True, "help": "要测试的URL"},
    "method": {"flag": "--method", "type": "str", "required": False, "help": "HTTP方法", "default": "GET"}
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
    url = getattr(args, 'url', '')
    method = getattr(args, 'method', 'GET')
    
    try:
        response = requests.request(method, url, timeout=10)
        output = {
            "url": url,
            "method": method,
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "requests_version": requests.__version__
        }
    except Exception as e:
        output = {
            "url": url,
            "method": method,
            "error": str(e),
            "requests_version": requests.__version__
        }
    
    print(json.dumps(output, ensure_ascii=False))

if __name__ == "__main__":
    main()
