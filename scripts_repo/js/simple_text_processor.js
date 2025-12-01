const ARGS_MAP = {
  text: { flag: "--text", type: "str", required: true, help: "要处理的文本" },
  action: { flag: "--action", type: "str", required: false, help: "操作类型(upper/lower/reverse/count)", "default": "upper" }
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
  const text = args.text || "Hello";
  const action = args.action || "upper";
  
  let result = "";
  try {
    switch (action) {
      case "upper":
        result = text.toUpperCase();
        break;
      case "lower":
        result = text.toLowerCase();
        break;
      case "reverse":
        result = text.split("").reverse().join("");
        break;
      case "count":
        result = text.length.toString();
        break;
      default:
        result = `Error: Unknown action ${action}`;
    }
  } catch (error) {
    result = `Error: ${error.message}`;
  }
  
  const output = {
    original_text: text,
    action: action,
    result: result,
    timestamp: new Date().toISOString()
  };
  
  console.log(JSON.stringify(output));
}

if (require.main === module) { 
  main(); 
}
