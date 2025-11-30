#!/usr/bin/env node

/**
 * JavaScript 脚本模板 - 支持参数验证、错误处理和多种响应格式
 * 使用说明:
 * 1. 定义 ARGS_MAP 对象来描述命令行参数
 * 2. 实现 processRequest 函数处理业务逻辑
 * 3. 使用错误处理函数处理异常情况
 * 4. 支持 --_sys_get_schema 参数输出 JSON 格式的参数定义
 */

const fs = require('fs');
const path = require('path');
const url = require('url');

// =============================================================================
// 参数定义区域
// =============================================================================

/**
 * 参数定义映射表
 * 支持的参数类型: str, int, float, bool, file, url, json
 * 
 * 示例参数类型:
 * 1. 基本类型: str, int, float, bool
 *    name: { flag: "--name", type: "str", required: true, help: "姓名" }
 *    age: { flag: "--age", type: "int", required: false, help: "年龄", default: 18 }
 *    height: { flag: "--height", type: "float", required: false, help: "身高", default: 170.5 }
 *    enabled: { flag: "--enabled", type: "bool", required: false, help: "是否启用", default: false }
 *
 * 2. 文件路径: file
 *    image: { flag: "--image", type: "file", required: true, help: "图片文件路径" }
 *    config: { flag: "--config", type: "file", required: false, help: "配置文件路径", default: "config.json" }
 *
 * 3. URL: url
 *    apiUrl: { flag: "--api-url", type: "url", required: true, help: "API接口地址" }
 *
 * 4. JSON: json
 *    data: { flag: "--data", type: "json", required: false, help: "JSON格式数据", default: {} }
 *
 * 5. 选择项: choice (需要指定 choices 数组)
 *    format: { flag: "--format", type: "choice", required: false, help: "输出格式", 
 *              choices: ["json", "xml", "csv"], default: "json" }
 */
const ARGS_MAP = {
    // 基本参数示例
    name: { flag: "--name", type: "str", required: true, help: "姓名，不能为空" },
    age: { flag: "--age", type: "int", required: false, help: "年龄，必须大于0", default: 18 },
    email: { flag: "--email", type: "str", required: false, help: "电子邮箱地址" },
    
    // 文件参数示例
    inputFile: { flag: "--input-file", type: "file", required: false, help: "输入文件路径" },
    outputDir: { flag: "--output-dir", type: "str", required: false, help: "输出目录", default: "./output" },
    
    // URL 参数示例
    apiUrl: { flag: "--api-url", type: "url", required: false, help: "API接口地址" },
    
    // JSON 参数示例
    metadata: { flag: "--metadata", type: "json", required: false, help: "元数据(JSON格式)", default: {} },
    
    // 布尔参数示例
    verbose: { flag: "--verbose", type: "bool", required: false, help: "详细输出模式", default: false },
    debug: { flag: "--debug", type: "bool", required: false, help: "调试模式", default: false },
    
    // 选择项示例
    format: { flag: "--format", type: "choice", required: false, help: "输出格式", 
              choices: ["json", "xml", "csv"], default: "json" }
};

// =============================================================================
// 辅助函数区域
// =============================================================================

/**
 * 返回参数定义的JSON格式字符串
 * 用于系统自动获取参数定义
 * @returns {string} JSON格式的参数定义
 */
function getSchema() {
    return JSON.stringify(ARGS_MAP);
}

/**
 * 解析命令行参数
 * @param {Array<string>} argv - 命令行参数数组
 * @returns {Object} 解析后的参数对象
 */
function parseArgs(argv) {
    const args = {};
    
    for (let i = 0; i < argv.length; i++) {
        const token = argv[i];
        
        for (const [key, meta] of Object.entries(ARGS_MAP)) {
            if (token === meta.flag) {
                // 处理布尔参数
                if (meta.type === "bool") {
                    args[key] = true;
                } else if (i + 1 < argv.length) {
                    // 其他类型参数，获取下一个值
                    const value = argv[i + 1];
                    
                    // 类型转换
                    if (meta.type === "int") {
                        const intValue = parseInt(value, 10);
                        args[key] = isNaN(intValue) ? null : intValue;
                    } else if (meta.type === "float") {
                        const floatValue = parseFloat(value);
                        args[key] = isNaN(floatValue) ? null : floatValue;
                    } else if (meta.type === "json") {
                        try {
                            args[key] = JSON.parse(value);
                        } catch (e) {
                            args[key] = value; // 如果解析失败，保留原始字符串
                        }
                    } else {
                        args[key] = value;
                    }
                }
                break;
            }
        }
    }
    
    // 应用默认值
    for (const [key, meta] of Object.entries(ARGS_MAP)) {
        if (args[key] === undefined && meta.default !== undefined) {
            args[key] = meta.default;
        }
    }
    
    return args;
}

/**
 * 创建成功响应
 * @param {Object} data - 响应数据
 * @param {string} message - 响应消息
 * @returns {Object} 成功响应对象
 */
function createSuccessResponse(data, message = "处理成功") {
    return {
        success: true,
        message: message,
        data: data,
        timestamp: new Date().toISOString()
    };
}

/**
 * 创建错误响应
 * @param {string} message - 错误消息
 * @param {string} code - 错误代码
 * @param {Object} details - 错误详情
 * @returns {Object} 错误响应对象
 */
function createErrorResponse(message, code = "ERROR", details = {}) {
    return {
        success: false,
        message: message,
        error: {
            code: code,
            details: details
        },
        timestamp: new Date().toISOString()
    };
}

/**
 * 创建文件响应
 * @param {Object} data - 响应数据
 * @param {string} filePath - 文件路径
 * @param {string} message - 响应消息
 * @returns {Object} 文件响应对象
 */
function createFileResponse(data, filePath, message = "处理成功，结果已保存到文件") {
    return {
        success: true,
        message: message,
        data: data,
        file: {
            path: filePath,
            exists: fs.existsSync(filePath),
            size: fs.existsSync(filePath) ? fs.statSync(filePath).size : 0
        },
        timestamp: new Date().toISOString()
    };
}

/**
 * 自定义参数验证函数
 * 在标准验证之后执行，用于业务逻辑相关的验证
 * @param {Object} params - 参数对象
 * @returns {Object} 验证结果 { isValid: boolean, error: Object|null }
 */
function validateCustomParameters(params) {
    // 示例1: 验证姓名不为空且长度合理
    const name = params.name;
    if (!name || !name.trim()) {
        return {
            isValid: false,
            error: createErrorResponse(
                "姓名不能为空",
                "VALIDATION_ERROR",
                { parameter: "name", value: name }
            )
        };
    }
    
    if (name.length > 100) {
        return {
            isValid: false,
            error: createErrorResponse(
                "姓名长度不能超过100个字符",
                "VALIDATION_ERROR",
                { parameter: "name", value: name }
            )
        };
    }
    
    // 示例2: 验证年龄范围
    const age = params.age;
    if (age !== null && (age < 0 || age > 150)) {
        return {
            isValid: false,
            error: createErrorResponse(
                "年龄必须在0-150之间",
                "VALIDATION_ERROR",
                { parameter: "age", value: age }
            )
        };
    }
    
    // 示例3: 验证邮箱格式
    const email = params.email;
    if (email && email.indexOf('@') === -1) {
        return {
            isValid: false,
            error: createErrorResponse(
                "邮箱格式不正确",
                "VALIDATION_ERROR",
                { parameter: "email", value: email }
            )
        };
    }
    
    // 示例4: 验证输入文件是否存在
    const inputFile = params.inputFile;
    if (inputFile && !fs.existsSync(inputFile)) {
        return {
            isValid: false,
            error: createErrorResponse(
                "输入文件不存在",
                "VALIDATION_ERROR",
                { parameter: "inputFile", value: inputFile }
            )
        };
    }
    
    // 示例5: 验证输出目录是否存在，不存在则创建
    const outputDir = params.outputDir;
    if (outputDir) {
        if (!fs.existsSync(outputDir)) {
            try {
                fs.mkdirSync(outputDir, { recursive: true });
            } catch (e) {
                return {
                    isValid: false,
                    error: createErrorResponse(
                        `无法创建输出目录: ${e.message}`,
                        "VALIDATION_ERROR",
                        { parameter: "outputDir", value: outputDir }
                    )
                };
            }
        }
    }
    
    // 示例6: 验证URL格式
    const apiUrl = params.apiUrl;
    if (apiUrl && !apiUrl.startsWith('http://') && !apiUrl.startsWith('https://')) {
        return {
            isValid: false,
            error: createErrorResponse(
                "URL必须以http://或https://开头",
                "VALIDATION_ERROR",
                { parameter: "apiUrl", value: apiUrl }
            )
        };
    }
    
    // 所有验证通过
    return { isValid: true, error: null };
}

/**
 * 处理业务逻辑的核心函数
 * @param {Object} params - 验证后的参数对象
 * @returns {Object} 业务处理结果数据
 */
function processBusinessLogic(params) {
    // 示例1: 基本数据处理
    const name = (params.name || '').trim();
    const age = params.age || 18;
    const email = params.email || '';
    const verbose = params.verbose || false;
    const debug = params.debug || false;
    const formatType = params.format || 'json';
    
    // 示例2: 文件处理
    const inputFile = params.inputFile;
    let fileInfo = null;
    if (inputFile && fs.existsSync(inputFile)) {
        const stats = fs.statSync(inputFile);
        fileInfo = {
            name: path.basename(inputFile),
            size: stats.size,
            extension: path.extname(inputFile),
            absolutePath: path.resolve(inputFile),
            isFile: stats.isFile(),
            isDirectory: stats.isDirectory(),
            created: stats.birthtime,
            modified: stats.mtime
        };
    }
    
    // 示例3: 元数据处理
    let metadata = params.metadata || {};
    if (typeof metadata === 'string') {
        try {
            metadata = JSON.parse(metadata);
        } catch (e) {
            metadata = {};
        }
    }
    
    // 示例4: 构建响应数据
    const resultData = {
        userInfo: {
            name: name,
            age: age,
            email: email
        },
        processingInfo: {
            format: formatType,
            verbose: verbose,
            debug: debug
        }
    };
    
    // 添加文件信息（如果有）
    if (fileInfo) {
        resultData.fileInfo = fileInfo;
    }
    
    // 添加元数据（如果有）
    if (Object.keys(metadata).length > 0) {
        resultData.metadata = metadata;
    }
    
    // 示例5: 根据不同格式返回不同结果
    if (formatType === "json") {
        return resultData;
    } else if (formatType === "xml") {
        // 这里可以转换为XML格式
        resultData.xmlOutput = `<user><name>${name}</name><age>${age}</age></user>`;
        return resultData;
    } else if (formatType === "csv") {
        // 这里可以转换为CSV格式
        resultData.csvOutput = `name,age,email\n${name},${age},${email}`;
        return resultData;
    }
    
    return resultData;
}

/**
 * 生成输出文件（可选）
 * @param {Object} params - 参数对象
 * @param {Object} resultData - 处理结果数据
 * @returns {string|null} 生成的文件路径，如果没有生成文件则返回null
 */
function generateOutputFile(params, resultData) {
    const outputDir = params.outputDir || './output';
    const formatType = params.format || 'json';
    
    // 示例1: 生成JSON文件
    if (formatType === 'json') {
        const outputFile = path.join(outputDir, 'result.json');
        try {
            fs.writeFileSync(outputFile, JSON.stringify(resultData, null, 2), 'utf8');
            return outputFile;
        } catch (e) {
            if (params.debug) {
                console.error(`生成JSON文件失败: ${e.message}`);
            }
            return null;
        }
    }
    
    // 示例2: 生成CSV文件
    else if (formatType === 'csv') {
        const outputFile = path.join(outputDir, 'result.csv');
        try {
            const userInfo = resultData.userInfo || {};
            const csvContent = `name,age,email\n${userInfo.name || ''},${userInfo.age || ''},${userInfo.email || ''}\n`;
            fs.writeFileSync(outputFile, csvContent, 'utf8');
            return outputFile;
        } catch (e) {
            if (params.debug) {
                console.error(`生成CSV文件失败: ${e.message}`);
            }
            return null;
        }
    }
    
    return null;
}

// =============================================================================
// 主要处理函数
// =============================================================================

/**
 * 处理请求的主函数
 * 包含参数验证、业务逻辑处理和结果生成
 * @param {Object} params - 参数对象
 * @returns {Object} 处理结果，可能是成功响应、错误响应或文件响应
 */
function processRequest(params) {
    try {
        // 1. 自定义参数验证
        const validation = validateCustomParameters(params);
        if (!validation.isValid) {
            return validation.error;
        }
        
        // 2. 处理业务逻辑
        let resultData;
        try {
            resultData = processBusinessLogic(params);
        } catch (e) {
            if (params.debug) {
                console.error(`业务逻辑处理失败: ${e.message}`);
                console.error(e.stack);
            }
            
            return createErrorResponse(
                `处理业务逻辑时发生错误: ${e.message}`,
                "BUSINESS_LOGIC_ERROR",
                { error: e.message, stack: e.stack }
            );
        }
        
        // 3. 生成输出文件（如果需要）
        const outputFile = generateOutputFile(params, resultData);
        
        // 4. 根据不同情况返回不同类型的响应
        if (outputFile) {
            // 如果生成了文件，返回文件响应
            return createFileResponse(
                resultData,
                outputFile,
                "处理成功，结果已保存到文件"
            );
        } else {
            // 否则返回标准成功响应
            return createSuccessResponse(
                resultData,
                "处理成功"
            );
        }
    } catch (e) {
        // 捕获所有未处理的异常
        return createErrorResponse(
            `处理请求时发生未预期的错误: ${e.message}`,
            "UNEXPECTED_ERROR",
            { error: e.message, stack: e.stack }
        );
    }
}

// =============================================================================
// 入口函数
// =============================================================================

/**
 * 主函数 - 处理命令行参数并调用处理函数
 */
function main() {
    // 1. 处理特殊参数 --_sys_get_schema
    const argv = process.argv.slice(2);
    if (argv[0] === "--_sys_get_schema") {
        console.log(getSchema());
        return;
    }
    
    // 2. 解析命令行参数
    const params = parseArgs(argv);
    
    // 3. 处理请求并输出结果
    const result = processRequest(params);
    console.log(JSON.stringify(result, null, 2));
}

// 只有直接运行此脚本时才执行main函数
if (require.main === module) {
    main();
}

// 导出函数以便测试
module.exports = {
    getSchema,
    parseArgs,
    validateCustomParameters,
    processBusinessLogic,
    generateOutputFile,
    processRequest,
    createSuccessResponse,
    createErrorResponse,
    createFileResponse
};