import argparse
import json
import sys

ARGS_MAP = {
    "name": {"flag": "--name", "type": "str", "required": True, "help": "姓名"}
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
    name = getattr(args, 'name')
    result = {"msg": f"Hello {name}", "code": 200}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
