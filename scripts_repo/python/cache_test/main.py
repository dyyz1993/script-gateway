import argparse
import json
import sys
import requests

ARGS_MAP = {
    "url": {"flag": "--url", "type": "str", "required": True, "help": "测试URL"}
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
    
    try:
        response = requests.get(url, timeout=5)
        output = {
            "url": url,
            "status_code": response.status_code,
            "requests_version": requests.__version__,
            "cache_test": "success"
        }
    except Exception as e:
        output = {
            "url": url,
            "error": str(e),
            "cache_test": "error"
        }
    
    print(json.dumps(output, ensure_ascii=False))

if __name__ == "__main__":
    main()
