import argparse
import json
import sys
import qrcode  # 需要第三方库: pip install qrcode[pil]
from io import BytesIO
import base64

ARGS_MAP = {
    "text": {"flag": "--text", "type": "str", "required": True, "help": "要转换为二维码的文本"},
    "size": {"flag": "--size", "type": "str", "required": False, "help": "二维码大小(small/medium/large)", "default": "medium"}
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
    text = args.text
    size = getattr(args, 'size', 'medium')
    
    try:
        # 设置二维码大小
        box_size = 5
        if size == 'small':
            box_size = 3
        elif size == 'large':
            box_size = 10
        
        # 生成二维码
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=box_size,
            border=4,
        )
        qr.add_data(text)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # 输出为PNG二进制
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        sys.stdout.buffer.write(buffer.getvalue())
        
    except Exception as e:
        error_result = {"error": str(e), "code": 500, "message": "请确保已安装 qrcode[pil]"}
        print(json.dumps(error_result, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()
