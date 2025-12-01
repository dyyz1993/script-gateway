const ARGS_MAP = {
  message: { flag: "--message", type: "str", required: true, help: "测试消息" }
};

function getSchema() { 
  return JSON.stringify(ARGS_MAP); 
}

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    const t = argv[i];
    for (const [k, m] of Object.entries(ARGS_MAP)) {
      if (t === m.flag && i + 1 < argv.length) {
        args[k] = argv[i + 1];
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
  const message = args.message || "Hello";
  
  // 故意的语法错误 - 缺少结束引号
  console.log(`{"message": "${message}, "status": "ok"}`);
}

if (require.main === module) { 
  main(); 
}
