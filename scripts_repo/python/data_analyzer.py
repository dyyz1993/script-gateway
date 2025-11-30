#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据分析脚本 - 支持数据分析和可视化
使用说明:
1. 支持从多种数据源读取数据
2. 提供基本的数据分析功能
3. 支持数据可视化图表生成
4. 可以导出分析结果和图表
"""

import argparse
import json
import sys
import os
from typing import Dict, Any, Optional, Union, List
from pathlib import Path
import traceback
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 添加项目根目录到Python路径，以便导入error_handler模块
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.core.error_handler import (
    handle_script_errors, 
    ValidationError, 
    ResourceError, 
    ScriptError, 
    ErrorType,
    validate_parameters,
    create_success_response,
    create_file_response,
    print_json_response
)

# =============================================================================
# 参数定义区域
# =============================================================================

ARGS_MAP = {
    # 数据源参数
    "data_source": {"flag": "--data-source", "type": "choice", "required": True, "help": "数据源类型", 
                   "choices": ["file", "url", "api"], "default": "file"},
    
    # 文件路径（当data_source为file时使用）
    "data_file": {"flag": "--data-file", "type": "file", "required": False, "help": "数据文件路径"},
    
    # URL（当data_source为url时使用）
    "data_url": {"flag": "--data-url", "type": "url", "required": False, "help": "数据URL"},
    
    # API端点（当data_source为api时使用）
    "api_endpoint": {"flag": "--api-endpoint", "type": "url", "required": False, "help": "API端点URL"},
    
    # 分析类型
    "analysis_type": {"flag": "--analysis-type", "type": "choice", "required": False, "help": "分析类型", 
                     "choices": ["descriptive", "correlation", "distribution", "trend", "all"], "default": "descriptive"},
    
    # 可视化类型
    "chart_type": {"flag": "--chart-type", "type": "choice", "required": False, "help": "图表类型", 
                  "choices": ["histogram", "scatter", "line", "bar", "heatmap", "box", "none"], "default": "histogram"},
    
    # 输出目录
    "output_dir": {"flag": "--output-dir", "type": "str", "required": False, "help": "输出目录", "default": "./output"},
    
    # 列选择（可选）
    "columns": {"flag": "--columns", "type": "str", "required": False, "help": "要分析的列，用逗号分隔"},
    
    # 其他选项
    "verbose": {"flag": "--verbose", "type": "bool", "required": False, "help": "详细输出模式", "default": False},
    "debug": {"flag": "--debug", "type": "bool", "required": False, "help": "调试模式", "default": False},
}

# =============================================================================
# 辅助函数区域
# =============================================================================

def get_schema() -> str:
    """返回参数定义的JSON格式字符串"""
    return json.dumps(ARGS_MAP, ensure_ascii=False)


def validate_custom_parameters(params: Dict[str, Any]) -> tuple[bool, Optional[Dict[str, Any]]]:
    """
    自定义参数验证函数
    验证数据分析相关的参数
    """
    data_source = params.get('data_source', 'file')
    
    # 根据数据源验证相应参数
    if data_source == "file":
        data_file = params.get('data_file')
        if not data_file:
            return False, ValidationError(
                message="当数据源为文件时，必须指定数据文件路径",
                parameter="data_file",
                value=data_file
            ).to_dict()
        
        if not os.path.exists(data_file):
            return False, ValidationError(
                message="数据文件不存在",
                parameter="data_file",
                value=data_file
            ).to_dict()
    
    elif data_source == "url":
        data_url = params.get('data_url')
        if not data_url:
            return False, ValidationError(
                message="当数据源为URL时，必须指定数据URL",
                parameter="data_url",
                value=data_url
            ).to_dict()
    
    elif data_source == "api":
        api_endpoint = params.get('api_endpoint')
        if not api_endpoint:
            return False, ValidationError(
                message="当数据源为API时，必须指定API端点",
                parameter="api_endpoint",
                value=api_endpoint
            ).to_dict()
    
    # 验证输出目录，不存在则创建
    output_dir = params.get('output_dir', './output')
    output_path = Path(output_dir)
    if not output_path.exists():
        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return False, ValidationError(
                message=f"无法创建输出目录: {str(e)}",
                parameter="output_dir",
                value=output_dir
            ).to_dict()
    
    return True, None


def load_data_from_file(file_path: str) -> Optional[pd.DataFrame]:
    """从文件加载数据"""
    path = Path(file_path)
    extension = path.suffix.lower()
    
    try:
        if extension == '.csv':
            return pd.read_csv(file_path)
        elif extension in ['.xlsx', '.xls']:
            return pd.read_excel(file_path)
        elif extension == '.json':
            return pd.read_json(file_path)
        elif extension == '.parquet':
            return pd.read_parquet(file_path)
        else:
            # 尝试以CSV格式读取
            return pd.read_csv(file_path)
    except Exception as e:
        return None


def load_data_from_url(url: str) -> Optional[pd.DataFrame]:
    """从URL加载数据"""
    try:
        # 尝试直接读取CSV
        if url.endswith('.csv'):
            return pd.read_csv(url)
        else:
            # 尝试以JSON格式读取
            return pd.read_json(url)
    except Exception as e:
        return None


def load_data_from_api(api_endpoint: str) -> Optional[pd.DataFrame]:
    """从API加载数据"""
    try:
        import requests
        response = requests.get(api_endpoint)
        response.raise_for_status()
        
        # 尝试解析JSON响应
        data = response.json()
        
        # 如果是字典，尝试找到数据列表
        if isinstance(data, dict):
            # 常见的API响应格式
            for key in ['data', 'results', 'items', 'records']:
                if key in data and isinstance(data[key], list):
                    return pd.DataFrame(data[key])
            
            # 如果没有找到列表，将整个字典转换为单行DataFrame
            return pd.DataFrame([data])
        elif isinstance(data, list):
            return pd.DataFrame(data)
        else:
            return None
    except Exception as e:
        return None


def descriptive_analysis(df: pd.DataFrame, columns: Optional[List[str]] = None) -> Dict[str, Any]:
    """描述性统计分析"""
    if columns:
        df = df[columns]
    
    result = {
        "shape": df.shape,
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "missing_values": df.isnull().sum().to_dict(),
        "numeric_summary": {},
        "categorical_summary": {}
    }
    
    # 数值型列的统计信息
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if numeric_cols:
        result["numeric_summary"] = df[numeric_cols].describe().to_dict()
    
    # 分类型列的统计信息
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    for col in categorical_cols:
        result["categorical_summary"][col] = {
            "unique_count": df[col].nunique(),
            "top_values": df[col].value_counts().head(10).to_dict()
        }
    
    return result


def correlation_analysis(df: pd.DataFrame, columns: Optional[List[str]] = None) -> Dict[str, Any]:
    """相关性分析"""
    if columns:
        df = df[columns]
    
    # 只选择数值型列
    numeric_df = df.select_dtypes(include=[np.number])
    
    if numeric_df.empty:
        return {"error": "没有数值型列可用于相关性分析"}
    
    correlation_matrix = numeric_df.corr()
    
    # 找出强相关关系（相关系数绝对值大于0.7）
    strong_correlations = []
    for i in range(len(correlation_matrix.columns)):
        for j in range(i+1, len(correlation_matrix.columns)):
            corr_value = correlation_matrix.iloc[i, j]
            if abs(corr_value) > 0.7:
                strong_correlations.append({
                    "column1": correlation_matrix.columns[i],
                    "column2": correlation_matrix.columns[j],
                    "correlation": corr_value
                })
    
    return {
        "correlation_matrix": correlation_matrix.to_dict(),
        "strong_correlations": strong_correlations
    }


def distribution_analysis(df: pd.DataFrame, columns: Optional[List[str]] = None) -> Dict[str, Any]:
    """分布分析"""
    if columns:
        df = df[columns]
    
    result = {}
    
    # 数值型列的分布分析
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    for col in numeric_cols:
        col_data = df[col].dropna()
        if len(col_data) > 0:
            result[col] = {
                "skewness": float(col_data.skew()),
                "kurtosis": float(col_data.kurtosis()),
                "percentiles": {
                    "25%": float(col_data.quantile(0.25)),
                    "50%": float(col_data.quantile(0.50)),
                    "75%": float(col_data.quantile(0.75)),
                    "90%": float(col_data.quantile(0.90)),
                    "95%": float(col_data.quantile(0.95))
                }
            }
    
    # 分类型列的分布分析
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    for col in categorical_cols:
        value_counts = df[col].value_counts()
        result[col] = {
            "value_counts": value_counts.head(20).to_dict(),
            "distribution": (value_counts / len(df)).head(20).to_dict()
        }
    
    return result


def trend_analysis(df: pd.DataFrame, columns: Optional[List[str]] = None) -> Dict[str, Any]:
    """趋势分析"""
    if columns:
        df = df[columns]
    
    # 尝试找到时间列
    time_cols = []
    for col in df.columns:
        if df[col].dtype == 'datetime64[ns]':
            time_cols.append(col)
        else:
            # 尝试解析为日期时间
            try:
                pd.to_datetime(df[col].head(100))
                time_cols.append(col)
            except:
                pass
    
    if not time_cols:
        return {"error": "没有找到时间列可用于趋势分析"}
    
    result = {"time_columns": time_cols}
    
    # 对每个时间列进行分析
    for time_col in time_cols:
        try:
            # 确保时间列是datetime类型
            df_time = df.copy()
            df_time[time_col] = pd.to_datetime(df_time[time_col])
            
            # 按时间排序
            df_time = df_time.sort_values(time_col)
            
            # 只选择数值型列进行趋势分析
            numeric_cols = df_time.select_dtypes(include=[np.number]).columns.tolist()
            
            if numeric_cols:
                trend_data = {}
                for col in numeric_cols:
                    # 计算简单线性趋势
                    x = np.arange(len(df_time))
                    y = df_time[col].values
                    if len(y) > 1 and not np.isnan(y).all():
                        slope = np.polyfit(x[~np.isnan(y)], y[~np.isnan(y)], 1)[0]
                        trend_data[col] = {
                            "slope": float(slope),
                            "direction": "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable"
                        }
                
                result[f"{time_col}_trends"] = trend_data
        except Exception as e:
            result[f"{time_col}_error"] = str(e)
    
    return result


def create_visualization(df: pd.DataFrame, chart_type: str, columns: Optional[List[str]] = None, output_dir: str = "./output") -> Optional[str]:
    """创建可视化图表"""
    if columns:
        df = df[columns]
    
    # 只选择数值型列
    numeric_df = df.select_dtypes(include=[np.number])
    
    if numeric_df.empty:
        return None
    
    plt.figure(figsize=(10, 6))
    
    try:
        if chart_type == "histogram":
            # 直方图
            if len(numeric_df.columns) >= 1:
                col = numeric_df.columns[0]
                plt.hist(numeric_df[col].dropna(), bins=30, alpha=0.7)
                plt.title(f'{col} 分布直方图')
                plt.xlabel(col)
                plt.ylabel('频次')
        
        elif chart_type == "scatter":
            # 散点图
            if len(numeric_df.columns) >= 2:
                x_col = numeric_df.columns[0]
                y_col = numeric_df.columns[1]
                plt.scatter(numeric_df[x_col], numeric_df[y_col], alpha=0.7)
                plt.title(f'{x_col} vs {y_col} 散点图')
                plt.xlabel(x_col)
                plt.ylabel(y_col)
        
        elif chart_type == "line":
            # 线图
            for col in numeric_df.columns[:5]:  # 最多显示5条线
                plt.plot(numeric_df[col].dropna(), label=col)
            plt.title('数值趋势线图')
            plt.xlabel('索引')
            plt.ylabel('值')
            plt.legend()
        
        elif chart_type == "bar":
            # 柱状图
            if len(numeric_df.columns) >= 1:
                col = numeric_df.columns[0]
                numeric_df[col].dropna().value_counts().head(20).plot(kind='bar')
                plt.title(f'{col} 柱状图')
                plt.xlabel(col)
                plt.ylabel('频次')
                plt.xticks(rotation=45)
        
        elif chart_type == "heatmap":
            # 热力图
            corr_matrix = numeric_df.corr()
            sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', center=0)
            plt.title('相关性热力图')
        
        elif chart_type == "box":
            # 箱线图
            numeric_df.boxplot()
            plt.title('数值箱线图')
            plt.xticks(rotation=45)
        
        # 保存图表
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        chart_file = os.path.join(output_dir, f"chart_{chart_type}_{timestamp}.png")
        plt.tight_layout()
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        return chart_file
    except Exception as e:
        plt.close()
        return None


def process_business_logic(params: Dict[str, Any]) -> Dict[str, Any]:
    """处理业务逻辑的核心函数"""
    data_source = params.get('data_source', 'file')
    analysis_type = params.get('analysis_type', 'descriptive')
    chart_type = params.get('chart_type', 'histogram')
    output_dir = params.get('output_dir', './output')
    columns_str = params.get('columns', '')
    verbose = params.get('verbose', False)
    debug = params.get('debug', False)
    
    # 解析列名
    columns = None
    if columns_str:
        columns = [col.strip() for col in columns_str.split(',')]
    
    # 加载数据
    df = None
    if data_source == "file":
        data_file = params.get('data_file')
        df = load_data_from_file(data_file)
        data_source_info = {"type": "file", "path": data_file}
    elif data_source == "url":
        data_url = params.get('data_url')
        df = load_data_from_url(data_url)
        data_source_info = {"type": "url", "url": data_url}
    elif data_source == "api":
        api_endpoint = params.get('api_endpoint')
        df = load_data_from_api(api_endpoint)
        data_source_info = {"type": "api", "endpoint": api_endpoint}
    
    if df is None:
        return {
            "success": False,
            "error": "无法加载数据",
            "data_source": data_source_info
        }
    
    # 基本数据信息
    data_info = {
        "shape": df.shape,
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "sample_data": df.head().to_dict()
    }
    
    result_data = {
        "data_source": data_source_info,
        "data_info": data_info,
        "analysis_type": analysis_type,
        "timestamp": datetime.now().isoformat()
    }
    
    # 根据分析类型执行不同的分析
    if analysis_type == "descriptive" or analysis_type == "all":
        result_data["descriptive_analysis"] = descriptive_analysis(df, columns)
        if verbose:
            result_data["message"] = "描述性分析完成"
    
    if analysis_type == "correlation" or analysis_type == "all":
        result_data["correlation_analysis"] = correlation_analysis(df, columns)
        if verbose:
            result_data["message"] = "相关性分析完成"
    
    if analysis_type == "distribution" or analysis_type == "all":
        result_data["distribution_analysis"] = distribution_analysis(df, columns)
        if verbose:
            result_data["message"] = "分布分析完成"
    
    if analysis_type == "trend" or analysis_type == "all":
        result_data["trend_analysis"] = trend_analysis(df, columns)
        if verbose:
            result_data["message"] = "趋势分析完成"
    
    # 创建可视化图表
    if chart_type != "none":
        chart_file = create_visualization(df, chart_type, columns, output_dir)
        if chart_file:
            result_data["visualization"] = {
                "chart_type": chart_type,
                "chart_file": chart_file,
                "success": True
            }
            if verbose:
                result_data["message"] = f"{result_data.get('message', '')}，图表已生成"
        else:
            result_data["visualization"] = {
                "chart_type": chart_type,
                "success": False,
                "error": "图表生成失败"
            }
    
    return result_data


def generate_output_file(params: Dict[str, Any], result_data: Dict[str, Any]) -> Optional[str]:
    """生成输出文件（可选）"""
    output_dir = params.get('output_dir', './output')
    
    # 生成分析结果文件
    output_file = os.path.join(output_dir, 'analysis_result.json')
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        return output_file
    except Exception as e:
        if params.get('debug', False):
            print(f"生成结果文件失败: {str(e)}", file=sys.stderr)
        return None


# =============================================================================
# 主要处理函数
# =============================================================================

@handle_script_errors
def process_request(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理请求的主函数
    包含参数验证、业务逻辑处理和结果生成
    """
    # 1. 标准参数验证
    is_valid, error_result = validate_parameters(params, ARGS_MAP)
    if not is_valid:
        return error_result
    
    # 2. 自定义参数验证
    is_valid, error_result = validate_custom_parameters(params)
    if not is_valid:
        return error_result
    
    # 3. 处理业务逻辑
    try:
        result_data = process_business_logic(params)
    except Exception as e:
        if params.get('debug', False):
            print(f"业务逻辑处理失败: {str(e)}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
        
        return ResourceError(
            message=f"处理业务逻辑时发生错误: {str(e)}",
            resource_type="data_analysis"
        ).to_dict()
    
    # 4. 生成输出文件（如果需要）
    output_file = generate_output_file(params, result_data)
    
    # 5. 构建响应数据
    response_data = result_data
    if output_file:
        response_data["output_file"] = output_file
    
    # 返回成功响应
    return create_success_response(
        data=response_data
    )


# =============================================================================
# 入口函数
# =============================================================================

def main():
    """主函数 - 处理命令行参数并调用处理函数"""
    # 1. 创建参数解析器
    parser = argparse.ArgumentParser(description='数据分析脚本 - 支持数据分析和可视化')
    
    # 2. 添加所有参数
    for key, cfg in ARGS_MAP.items():
        param_type = cfg.get("type", "str")
        required = cfg.get("required", False)
        default = cfg.get("default")
        help_text = cfg.get("help", "")
        
        # 根据参数类型添加不同的参数
        if param_type == "bool":
            # 布尔参数需要特殊处理
            parser.add_argument(
                cfg["flag"], 
                help=help_text,
                action='store_true',
                default=default
            )
        elif param_type == "choice" and "choices" in cfg:
            # 选择项参数
            parser.add_argument(
                cfg["flag"], 
                help=help_text,
                choices=cfg["choices"],
                default=default
            )
        else:
            # 其他类型参数
            parser.add_argument(
                cfg["flag"], 
                help=help_text,
                required=required,
                default=default
            )
    
    # 3. 处理特殊参数 --_sys_get_schema
    if len(sys.argv) > 1 and sys.argv[1] == "--_sys_get_schema":
        print(get_schema())
        sys.exit(0)
    
    # 4. 解析命令行参数
    args = parser.parse_args()
    
    # 5. 构建参数字典
    params = {}
    for key in ARGS_MAP.keys():
        value = getattr(args, key, None)
        if value is not None:
            params[key] = value
    
    # 6. 处理请求并打印结果
    result = process_request(params)
    print_json_response(result)


if __name__ == "__main__":
    main()