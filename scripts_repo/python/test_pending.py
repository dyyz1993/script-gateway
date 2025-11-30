# 这是一个测试脚本，故意不包含入口标识
# 这个脚本会被标记为"待加载"状态，因为它缺少 if __name__ == "__main__": 

def test_function():
    """测试函数"""
    print("这是一个测试函数")
    return {"status": "success", "message": "测试成功"}

# 故意不添加入口标识，以便测试待加载状态