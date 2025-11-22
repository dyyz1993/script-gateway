// 这是可编辑的 JavaScript 模板示例（Node.js）
// 约定：支持 --_sys_get_schema 输出参数定义

const ARGS_MAP = {
  name: { flag: "--name", type: "str", required: true, help: "姓名" },
  file: { flag: "--file", type: "file", required: false, help: "文件路径" },
};

function getSchema() {
  return JSON.stringify(ARGS_MAP);
}

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    const token = argv[i];
    for (const [key, meta] of Object.entries(ARGS_MAP)) {
      if (token === meta.flag && i + 1 < argv.length) {
        args[key] = argv[i + 1];
      }
    }
  }
  return args;
}

function main() {
  const argv = process.argv.slice(2);
  if (argv[0] === "--_sys_get_schema") {
    console.log(getSchema());
    return;
  }
  const args = parseArgs(argv);
  const name = args.name || "World";
  console.log(JSON.stringify({ msg: `Hello ${name}`, code: 200 }));
}

if (require.main === module) {
  main();
}
