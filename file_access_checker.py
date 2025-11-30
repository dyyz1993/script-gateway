import os
import re
from typing import List, Tuple
from config import Config


class FileAccessChecker:
    """
    文件访问限制检查器
    
    用于验证文件路径是否符合配置的访问模式，防止未授权的文件访问
    """
    
    def __init__(self, patterns: List[str] = None):
        """
        初始化文件访问检查器
        
        Args:
            patterns: 允许访问的路径模式列表，如果为空则从配置或数据库中读取
        """
        if patterns is not None:
            self.patterns = patterns
        else:
            # 使用配置中的模式
            self.patterns = Config.get_local_file_access_patterns()
        
        self.compiled_patterns = [self._compile_pattern(p) for p in self.patterns]
    
    def _compile_pattern(self, pattern: str) -> re.Pattern:
        """
        将通配符模式编译为正则表达式
        
        Args:
            pattern: 通配符模式，如 "/tmp/**"
            
        Returns:
            编译后的正则表达式
        """
        # 转义特殊字符，但保留通配符
        escaped = re.escape(pattern)
        # 将转义的通配符恢复为正则表达式
        escaped = escaped.replace(r'\*\*', '.*')  # ** 匹配任意路径
        escaped = escaped.replace(r'\*', '[^/]*')  # * 匹配除/外的任意字符
        # 确保模式匹配整个路径
        regex = f'^{escaped}$'
        return re.compile(regex)
    
    def is_path_allowed(self, file_path: str) -> Tuple[bool, str]:
        """
        检查文件路径是否被允许访问
        
        Args:
            file_path: 要检查的文件路径
            
        Returns:
            (是否允许, 错误信息)
        """
        # 如果没有配置限制模式，则允许所有路径
        if not self.patterns:
            return True, ""
        
        # 获取绝对路径
        abs_path = os.path.abspath(file_path)
        
        # 检查是否匹配任何允许的模式
        for pattern, compiled_pattern in zip(self.patterns, self.compiled_patterns):
            if compiled_pattern.match(abs_path):
                return True, ""
        
        # 如果没有匹配任何模式，则拒绝访问
        patterns_str = ", ".join(self.patterns)
        return False, f"文件路径不在允许的访问范围内。允许的路径模式: {patterns_str}"
    
    def update_patterns(self, new_patterns: List[str]) -> None:
        """
        更新访问模式
        
        Args:
            new_patterns: 新的访问模式列表
        """
        self.patterns = new_patterns
        self.compiled_patterns = [self._compile_pattern(p) for p in self.patterns]
    
    def get_allowed_patterns(self) -> List[str]:
        """
        获取当前允许的访问模式
        
        Returns:
            当前允许的访问模式列表
        """
        return self.patterns.copy()