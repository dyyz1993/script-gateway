// JavaScript示例：文本处理工具

const ARGS_MAP = {
    text: { flag: "--text", type: "str", required: true, help: "要处理的文本" },
    action: { flag: "--action", type: "str", required: false, help: "操作类型(upper/lower/reverse/count)", default: "upper" }
};

function getSchema() {
    return JSON.stringify(ARGS_MAP);
}

function parseArgs(argv) {
    const args = {};
    for (let i = 0; i < argv.length; i++) {
        const arg = argv[i];
        for (const [key, meta] of Object.entries(ARGS_MAP)) {
            if (arg === meta.flag && i + 1 < argv.length) {
                args[key] = argv[i + 1];
                i++;
            }
        }
    }
    return args;
}

function processText(text, action) {
    switch (action) {
        case 'upper':
            return text.toUpperCase();
        case 'lower':
            return text.toLowerCase();
        case 'reverse':
            return text.split('').reverse().join('');
        case 'count':
            return text.length;
        default:
            return text;
    }
}

function main() {
    const argv = process.argv.slice(2);
    
    if (argv[0] === "--_sys_get_schema") {
        console.log(getSchema());
        return;
    }
    
    const args = parseArgs(argv);
    
    if (!args.text) {
        console.log(JSON.stringify({ error: "text参数是必需的", code: 400 }));
        process.exit(1);
    }
    
    const action = args.action || 'upper';
    const result = processText(args.text, action);
    
    const output = {
        original: args.text,
        action: action,
        result: result,
        code: 200
    };
    
    console.log(JSON.stringify(output));
}

if (require.main === module) {
    main();
}

module.exports = { main };
