import argparse
import json
import sys
import pandas as pd  # 需要第三方库
from io import StringIO

ARGS_MAP = {
    "data": {"flag": "--data", "type": "str", "required": True, "help": "CSV数据或文件路径"},
    "operation": {"flag": "--operation", "type": "str", "required": False, "help": "操作类型(sum/mean/count)", "default": "sum"}
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
    data_input = args.data
    operation = getattr(args, 'operation', 'sum')
    
    try:
        # 尝试读取CSV数据
        if '\n' in data_input or ',' in data_input:
            # 直接是CSV字符串
            df = pd.read_csv(StringIO(data_input))
        else:
            # 可能是文件路径
            df = pd.read_csv(data_input)
        
        # 执行数据分析操作
        result = {
            "rows": len(df),
            "columns": list(df.columns),
            "operation": operation,
            "code": 200
        }
        
        if operation == "sum":
            numeric_cols = df.select_dtypes(include=['number']).columns
            result["summary"] = {col: float(df[col].sum()) for col in numeric_cols}
        elif operation == "mean":
            numeric_cols = df.select_dtypes(include=['number']).columns
            result["summary"] = {col: float(df[col].mean()) for col in numeric_cols}
        elif operation == "count":
            result["summary"] = {col: int(df[col].count()) for col in df.columns}
        
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        error_result = {"error": str(e), "code": 500}
        print(json.dumps(error_result, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()
