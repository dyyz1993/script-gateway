import argparse
import json
import sys

ARGS_MAP = {
    "message": {"flag": "--message", "type": "str", "required": True, "help": "测试消息"}
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
    message = getattr(args, 'message', '')
    
    # 修复语法
    print(f"Message: {message}")

if __name__ == "__main__":
    main()
