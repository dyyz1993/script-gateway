import argparse
import json
import sys
from PIL import Image, ImageFilter
import os

ARGS_MAP = {
    "image": {"flag": "--image", "type": "file", "required": True, "help": "输入图片文件"},
    "operation": {"flag": "--operation", "type": "str", "required": False, "help": "操作类型 (blur/sharpen/grayscale/resize)", "default": "resize"},
    "size": {"flag": "--size", "type": "str", "required": False, "help": "调整大小的尺寸 (width,height)", "default": "300,300"}
}

def get_schema():
    return json.dumps(ARGS_MAP, ensure_ascii=False)

def resize_image(image_path, size_str):
    """调整图片大小"""
    try:
        width, height = map(int, size_str.split(','))
        with Image.open(image_path) as img:
            resized = img.resize((width, height))
            output_path = f"resized_{os.path.basename(image_path)}"
            resized.save(output_path)
            return {"success": True, "output": output_path, "original_size": img.size, "new_size": (width, height)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def blur_image(image_path):
    """模糊图片"""
    try:
        with Image.open(image_path) as img:
            blurred = img.filter(ImageFilter.BLUR)
            output_path = f"blurred_{os.path.basename(image_path)}"
            blurred.save(output_path)
            return {"success": True, "output": output_path}
    except Exception as e:
        return {"success": False, "error": str(e)}

def sharpen_image(image_path):
    """锐化图片"""
    try:
        with Image.open(image_path) as img:
            sharpened = img.filter(ImageFilter.SHARPEN)
            output_path = f"sharpened_{os.path.basename(image_path)}"
            sharpened.save(output_path)
            return {"success": True, "output": output_path}
    except Exception as e:
        return {"success": False, "error": str(e)}

def grayscale_image(image_path):
    """转灰度图片"""
    try:
        with Image.open(image_path) as img:
            grayscale = img.convert('L')
            output_path = f"grayscale_{os.path.basename(image_path)}"
            grayscale.save(output_path)
            return {"success": True, "output": output_path}
    except Exception as e:
        return {"success": False, "error": str(e)}

def main():
    parser = argparse.ArgumentParser()
    for key, cfg in ARGS_MAP.items():
        parser.add_argument(cfg["flag"], required=cfg.get("required", False), help=cfg.get("help", ""))
    
    if len(sys.argv) > 1 and sys.argv[1] == "--_sys_get_schema":
        print(get_schema())
        sys.exit(0)
    
    args = parser.parse_args()
    image_path = getattr(args, 'image', '')
    operation = getattr(args, 'operation', 'resize')
    size = getattr(args, 'size', '300,300')
    
    if not image_path or not os.path.exists(image_path):
        result = {"error": "图片文件不存在", "code": 400}
    else:
        if operation == "resize":
            result = resize_image(image_path, size)
        elif operation == "blur":
            result = blur_image(image_path)
        elif operation == "sharpen":
            result = sharpen_image(image_path)
        elif operation == "grayscale":
            result = grayscale_image(image_path)
        else:
            result = {"error": f"不支持的操作: {operation}", "code": 400}
    
    result["script"] = "image_processor"
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
