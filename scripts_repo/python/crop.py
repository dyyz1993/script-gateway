import argparse
import json
import sys
from io import BytesIO
from PIL import Image

ARGS_MAP = {
    "image": {"flag": "--image", "type": "file", "required": True, "help": "图片路径"},
    "size": {"flag": "--size", "type": "str", "required": True, "help": "输出尺寸，如 100x100"}
}


def get_schema():
    return json.dumps(ARGS_MAP, ensure_ascii=False)


def parse_size(s: str):
    if "x" not in s:
        raise ValueError("size 格式错误，应为 WxH")
    w, h = s.lower().split("x")
    return int(w), int(h)


def main():
    parser = argparse.ArgumentParser()
    for key, cfg in ARGS_MAP.items():
        parser.add_argument(cfg["flag"], required=cfg.get("required", False), help=cfg.get("help", ""))

    if len(sys.argv) > 1 and sys.argv[1] == "--_sys_get_schema":
        print(get_schema())
        sys.exit(0)

    args = parser.parse_args()
    img_path = getattr(args, 'image')
    size_str = getattr(args, 'size')
    w, h = parse_size(size_str)

    with Image.open(img_path) as im:
        # 简单缩放到指定尺寸
        im = im.convert("RGBA")
        im = im.resize((w, h))
        buf = BytesIO()
        im.save(buf, format="PNG")
        sys.stdout.buffer.write(buf.getvalue())


if __name__ == "__main__":
    main()
