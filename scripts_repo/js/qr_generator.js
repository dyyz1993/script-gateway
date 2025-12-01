const ARGS_MAP = {
  text: { flag: "--text", type: "str", required: true, help: "要生成二维码的文本" },
  size: { flag: "--size", type: "str", required: false, help: "二维码尺寸", "default": "200" },
  filename: { flag: "--filename", type: "str", required: false, help: "输出文件名", "default": "qrcode.png" }
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
  const text = args.text || "Hello World";
  const size = parseInt(args.size) || 200;
  const filename = args.filename || "qrcode.png";
  
  try {
    // 使用 qrcode 库生成二维码
    const QRCode = require('qrcode');
    
    QRCode.toFile(filename, text, {
      width: size,
      margin: 2,
      color: {
        dark: '#000000',
        light: '#FFFFFF'
      }
    }, function(err) {
      if (err) {
        console.log(JSON.stringify({ 
          success: false, 
          error: err.message,
          code: 500
        }));
      } else {
        console.log(JSON.stringify({ 
          success: true, 
          text: text,
          size: size,
          filename: filename,
          message: `二维码已生成: ${filename}`
        }));
      }
    });
    
  } catch (error) {
    console.log(JSON.stringify({ 
      success: false, 
      error: error.message,
      code: 500
    }));
  }
}

if (require.main === module) { 
  main(); 
}
