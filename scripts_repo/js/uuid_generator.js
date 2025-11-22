// JavaScript示例：使用第三方库 - UUID生成器
// 需要安装: npm install uuid

const ARGS_MAP = {
    count: { flag: "--count", type: "str", required: false, help: "生成UUID的数量", default: "1" },
    version: { flag: "--version", type: "str", required: false, help: "UUID版本(v4/v1)", default: "v4" }
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

function main() {
    const argv = process.argv.slice(2);
    
    if (argv[0] === "--_sys_get_schema") {
        console.log(getSchema());
        return;
    }
    
    const args = parseArgs(argv);
    const count = parseInt(args.count || '1');
    const version = args.version || 'v4';
    
    try {
        // 尝试加载uuid库
        const { v4: uuidv4, v1: uuidv1 } = require('uuid');
        
        const uuids = [];
        for (let i = 0; i < count; i++) {
            if (version === 'v4') {
                uuids.push(uuidv4());
            } else if (version === 'v1') {
                uuids.push(uuidv1());
            }
        }
        
        const output = {
            version: version,
            count: count,
            uuids: uuids,
            code: 200
        };
        
        console.log(JSON.stringify(output));
    } catch (error) {
        // 如果uuid库未安装，提供友好提示
        const output = {
            error: "uuid库未安装",
            message: "请运行: npm install uuid",
            detail: error.message,
            code: 500
        };
        console.log(JSON.stringify(output));
        process.exit(1);
    }
}

if (require.main === module) {
    main();
}

module.exports = { main };
