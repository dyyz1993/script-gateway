import argparse
import json
import sys
import math

ARGS_MAP = {
    "operation": {"flag": "--operation", "type": "str", "required": True, "help": "操作类型 (sqrt/power/log)"},
    "value": {"flag": "--value", "type": "float", "required": True, "help": "数值"},
    "power": {"flag": "--power", "type": "float", "required": False, "help": "幂次（用于power操作）", "default": 2.0}
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
    operation = getattr(args, 'operation', 'sqrt')
    value = getattr(args, 'value', 0)
    power = getattr(args, 'power', 2.0)
    
    try:
        if operation == 'sqrt':
            if value < 0:
                result = "Error: Cannot calculate sqrt of negative number"
            else:
                result = math.sqrt(value)
        elif operation == 'power':
            result = math.pow(value, power)
        elif operation == 'log':
            if value <= 0:
                result = "Error: Cannot calculate log of non-positive number"
            else:
                result = math.log10(value)
        else:
            result = f"Error: Unknown operation {operation}"
    except Exception as e:
        result = f"Error: {str(e)}"
    
    output = {
        "operation": operation,
        "input_value": value,
        "power": power,
        "result": result,
        "timestamp": str(__import__('datetime').datetime.now())
    }
    print(json.dumps(output, ensure_ascii=False))

if __name__ == "__main__":
    main()
