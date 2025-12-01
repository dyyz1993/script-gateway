import argparse
import json
import sys

ARGS_MAP = {
    "operation": {"flag": "--operation", "type": "str", "required": True, "help": "操作类型 (add/subtract/multiply/divide)"},
    "a": {"flag": "--a", "type": "float", "required": True, "help": "数字A"},
    "b": {"flag": "--b", "type": "float", "required": True, "help": "数字B"}
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
    operation = getattr(args, 'operation', 'add')
    a = getattr(args, 'a', 0)
    b = getattr(args, 'b', 0)
    
    # 调试输出
    print(f"DEBUG: operation={operation}, a={a}, b={b}, type(a)={type(a)}, type(b)={type(b)}", file=sys.stderr)
    
    try:
        if operation == 'add':
            result = a + b
        elif operation == 'subtract':
            result = a - b
        elif operation == 'multiply':
            result = a * b
        elif operation == 'divide':
            if b == 0:
                result = "Error: Division by zero"
            else:
                result = a / b
        else:
            result = f"Error: Unknown operation {operation}"
    except Exception as e:
        result = f"Error: {str(e)}"
    
    output = {
        "operation": operation,
        "a": a,
        "b": b,
        "result": result,
        "timestamp": str(__import__('datetime').datetime.now())
    }
    print(json.dumps(output, ensure_ascii=False))

if __name__ == "__main__":
    main()
