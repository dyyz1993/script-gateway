import argparse
import json
import sys
import os

# 添加项目根目录到Python路径，以便导入error_handler模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from error_handler import (
    handle_script_errors, 
    ValidationError, 
    ScriptError, 
    ErrorType,
    validate_parameters,
    create_success_response,
    print_json_response
)

ARGS_MAP = {
    "name": {"flag": "--name", "type": "str", "required": True, "help": "姓名"}
}


def get_schema():
    """返回参数定义的JSON格式"""
    return json.dumps(ARGS_MAP, ensure_ascii=False)


@handle_script_errors
def process_hello_request(params):
    """处理Hello请求"""
    # 验证参数
    is_valid, error_result = validate_parameters(params, ARGS_MAP)
    if not is_valid:
        return error_result
    
    name = params.get('name')
    
    # 验证姓名不为空
    if not name or not name.strip():
        return ValidationError(
            message="姓名不能为空",
            parameter="name",
            value=name
        ).to_dict()
    
    # 验证姓名长度
    if len(name) > 100:
        return ValidationError(
            message="姓名长度不能超过100个字符",
            parameter="name",
            value=name
        ).to_dict()
    
    # 创建成功响应
    return create_success_response(
        data={"msg": f"Hello {name.strip()}"},
        metadata={
            "script": "hello",
            "version": "1.0"
        }
    )


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
    result = process_hello_request(params)
    print_json_response(result)


if __name__ == "__main__":
    main()
