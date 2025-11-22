import argparse
import json
import sys
import requests  # 需要第三方库

ARGS_MAP = {
    "city": {"flag": "--city", "type": "str", "required": True, "help": "城市名称"},
    "units": {"flag": "--units", "type": "str", "required": False, "help": "单位(metric/imperial)", "default": "metric"}
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
    city = args.city
    units = getattr(args, 'units', 'metric')
    
    # 使用免费的天气API（示例，需要替换实际API KEY）
    # 这里使用模拟数据
    try:
        # 实际使用时需要: api_key = "YOUR_API_KEY"
        # url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&units={units}&appid={api_key}"
        # response = requests.get(url, timeout=10)
        # data = response.json()
        
        # 模拟返回
        result = {
            "city": city,
            "temperature": 25 if units == "metric" else 77,
            "unit": "°C" if units == "metric" else "°F",
            "weather": "晴朗",
            "humidity": 65,
            "message": "这是模拟数据，实际使用需配置API KEY",
            "code": 200
        }
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        error_result = {"error": str(e), "code": 500}
        print(json.dumps(error_result, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()
