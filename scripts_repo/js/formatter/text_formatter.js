const ARGS_MAP = {
  text: { flag: "--text", type: "str", required: true, help: "要格式化的文本" },
  format: { flag: "--format", type: "str", required: false, help: "格式类型 (json/yaml/csv)", "default": "json" },
  indent: { flag: "--indent", type: "str", required: false, help: "缩进字符", "default": "  " }
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

function formatAsJson(text, indent) {
  try {
    const obj = { text: text, formatted_at: new Date().toISOString() };
    return JSON.stringify(obj, null, indent);
  } catch (error) {
    return JSON.stringify({ error: error.message });
  }
}

function formatAsYaml(text, indent) {
  return `text: "${text}"\nformatted_at: "${new Date().toISOString()}"\n`;
}

function formatAsCsv(text, indent) {
  return `text,formatted_at\n"${text}","${new Date().toISOString()}"\n`;
}

function main() {
  const argv = process.argv.slice(2);
  if (argv[0] === "--_sys_get_schema") {
    console.log(getSchema());
    return;
  }
  
  const args = parseArgs(argv);
  const text = args.text || "Hello";
  const format = args.format || "json";
  const indentStr = args.indent || "  ";
  
  let result = "";
  try {
    switch (format) {
      case "json":
        result = formatAsJson(text, indentStr);
        break;
      case "yaml":
        result = formatAsYaml(text, indentStr);
        break;
      case "csv":
        result = formatAsCsv(text, indentStr);
        break;
      default:
        result = JSON.stringify({ error: `Unknown format: ${format}` });
    }
  } catch (error) {
    result = JSON.stringify({ error: error.message });
  }
  
  console.log(result);
}

if (require.main === module) { 
  main(); 
}
