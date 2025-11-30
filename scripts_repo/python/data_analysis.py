import argparse
import json
import sys
import os
from io import StringIO

# 添加项目根目录到Python路径，以便导入error_handler模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from error_handler import (
    handle_script_errors, 
    ValidationError, 
    ResourceError, 
    ScriptError, 
    ErrorType,
    validate_parameters,
    create_success_response,
    print_json_response
)

# 尝试导入pandas
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    IMPORT_ERROR = "缺少pandas库，请使用 pip install pandas 安装"

ARGS_MAP = {
    "data": {"flag": "--data", "type": "str", "required": True, "help": "CSV数据或文件路径"},
    "operation": {"flag": "--operation", "type": "str", "required": False, "help": "操作类型(sum/mean/count)", "default": "sum"}
}

def get_schema():
    """返回参数定义的JSON格式"""
    return json.dumps(ARGS_MAP, ensure_ascii=False)


@handle_script_errors
def process_data_analysis(params):
    """处理数据分析请求"""
    # 检查依赖是否可用
    if not PANDAS_AVAILABLE:
        return ScriptError(
            message=f"缺少必要依赖: {IMPORT_ERROR}",
            error_type=ErrorType.RESOURCE,
            code=500
        ).to_dict()
    
    # 验证参数
    is_valid, error_result = validate_parameters(params, ARGS_MAP)
    if not is_valid:
        return error_result
    
    data_input = params.get('data')
    operation = params.get('operation', 'sum')
    
    # 验证操作类型
    valid_operations = ['sum', 'mean', 'count']
    if operation not in valid_operations:
        return ValidationError(
            message=f"不支持的操作类型: {operation}，支持的操作: {', '.join(valid_operations)}",
            parameter="operation",
            value=operation
        ).to_dict()
    
    # 验证数据输入不为空
    if not data_input or not data_input.strip():
        return ValidationError(
            message="数据输入不能为空",
            parameter="data",
            value=data_input
        ).to_dict()
    
    try:
        # 尝试读取CSV数据
        if '\n' in data_input or ',' in data_input:
            # 直接是CSV字符串
            df = pd.read_csv(StringIO(data_input))
            data_type = "string"
        else:
            # 可能是文件路径
            if not os.path.exists(data_input):
                return ResourceError(
                    message=f"数据文件不存在: {data_input}",
                    resource_type="file",
                    resource_path=data_input
                ).to_dict()
            
            df = pd.read_csv(data_input)
            data_type = "file"
        
        # 验证数据不为空
        if df.empty:
            return ValidationError(
                message="CSV数据为空，请提供有效数据",
                parameter="data"
            ).to_dict()
        
        # 执行数据分析操作
        result_data = {
            "rows": len(df),
            "columns": list(df.columns),
            "operation": operation,
            "data_type": data_type
        }
        
        # 根据操作类型计算结果
        if operation == "sum":
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) == 0:
                return ValidationError(
                    message="数据中没有数值列，无法执行求和操作",
                    parameter="operation"
                ).to_dict()
            result_data["summary"] = {col: float(df[col].sum()) for col in numeric_cols}
        elif operation == "mean":
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) == 0:
                return ValidationError(
                    message="数据中没有数值列，无法执行平均值计算",
                    parameter="operation"
                ).to_dict()
            result_data["summary"] = {col: float(df[col].mean()) for col in numeric_cols}
        elif operation == "count":
            result_data["summary"] = {col: int(df[col].count()) for col in df.columns}
        
        # 创建成功响应
        return create_success_response(
            data=result_data,
            metadata={
                "script": "data_analysis",
                "version": "1.0",
                "pandas_version": pd.__version__
            }
        )
        
    except pd.errors.EmptyDataError:
        return ValidationError(
            message="CSV数据为空或格式不正确",
            parameter="data"
        ).to_dict()
    except pd.errors.ParserError as e:
        return ValidationError(
            message=f"CSV数据解析错误: {str(e)}",
            parameter="data"
        ).to_dict()
    except Exception as e:
        return ScriptError(
            message=f"数据处理过程中出错: {str(e)}",
            error_type=ErrorType.EXECUTION
        ).to_dict()


def main():
    """主函数"""
    parser = argparse.ArgumentParser()
    for key, cfg in ARGS_MAP.items():
        parser.add_argument(cfg["flag"], required=cfg.get("required", False), help=cfg.get("help", ""))
    
    if len(sys.argv) > 1 and sys.argv[1] == "--_sys_get_schema":
        print(get_schema())
        sys.exit(0)
    
    args = parser.parse_args()
    
    # 构建参数字典
    params = {}
    for key in ARGS_MAP.keys():
        value = getattr(args, key, None)
        if value is not None:
            params[key] = value
    
    # 处理请求并打印结果
    result = process_data_analysis(params)
    print_json_response(result)


if __name__ == "__main__":
    main()
