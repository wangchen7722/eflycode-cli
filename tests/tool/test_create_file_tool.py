#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import tempfile
import shutil
from echo.tool.file.file_tool import CreateFileTool
from echo.tool.schema import ToolParameterError, ToolExecutionError

def test_create_file_tool():
    """测试CreateFileTool的功能"""
    tool = CreateFileTool()
    
    # 测试工具属性
    print("=== 测试工具属性 ===")
    print(f"工具名称: {tool.name}")
    print(f"工具类型: {tool.type}")
    print(f"需要审批: {tool.should_approval}")
    print(f"工具描述: {tool.description}")
    print(f"显示名称: {tool.display()}")
    print(f"参数定义: {tool.parameters}")
    print(f"示例: {tool.examples}")
    print()
    
    # 创建临时目录用于测试
    temp_dir = tempfile.mkdtemp()
    print(f"测试目录: {temp_dir}")
    
    try:
        # 测试1: 创建新文件
        print("=== 测试1: 创建新文件 ===")
        test_file = os.path.join(temp_dir, "test.txt")
        content = "这是测试文件的内容。\n包含多行文本。"
        result = tool.run(path=test_file, content=content)
        print(f"结果: {result}")
        
        # 验证文件是否创建成功
        assert os.path.exists(test_file), "文件未创建成功"
        with open(test_file, 'r', encoding='utf-8') as f:
            file_content = f.read()
        assert file_content == content, "文件内容不匹配"
        print("✓ 文件创建成功")
        print()
        
        # 测试2: 创建带子目录的文件
        print("=== 测试2: 创建带子目录的文件 ===")
        subdir_file = os.path.join(temp_dir, "subdir", "nested", "file.py")
        python_content = "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n\nprint('Hello, World!')\n"
        result = tool.run(path=subdir_file, content=python_content)
        print(f"结果: {result}")
        
        # 验证文件和目录是否创建成功
        assert os.path.exists(subdir_file), "嵌套文件未创建成功"
        assert os.path.exists(os.path.dirname(subdir_file)), "父目录未创建成功"
        with open(subdir_file, 'r', encoding='utf-8') as f:
            file_content = f.read()
        assert file_content == python_content, "Python文件内容不匹配"
        print("✓ 嵌套文件创建成功")
        print()
        
        # 测试3: 创建空文件
        print("=== 测试3: 创建空文件 ===")
        empty_file = os.path.join(temp_dir, "empty.txt")
        result = tool.run(path=empty_file, content="")
        print(f"结果: {result}")
        
        # 验证空文件是否创建成功
        assert os.path.exists(empty_file), "空文件未创建成功"
        assert os.path.getsize(empty_file) == 0, "空文件大小不为0"
        print("✓ 空文件创建成功")
        print()
        
        # 测试4: 尝试创建已存在的文件（应该失败）
        print("=== 测试4: 尝试创建已存在的文件 ===")
        try:
            result = tool.run(path=test_file, content="新内容")
            print("ERROR: 应该抛出异常但没有")
        except ToolParameterError as e:
            print(f"✓ 正确捕获异常: {e}")
        print()
        
        # 测试5: 创建文件到只读目录（模拟权限错误）
        print("=== 测试5: 测试权限错误处理 ===")
        readonly_dir = os.path.join(temp_dir, "readonly")
        os.makedirs(readonly_dir, exist_ok=True)
        os.chmod(readonly_dir, 0o444)  # 设置为只读
        
        try:
            readonly_file = os.path.join(readonly_dir, "test.txt")
            result = tool.run(path=readonly_file, content="测试内容")
            print("WARNING: 在某些系统上可能不会抛出权限错误")
        except ToolExecutionError as e:
            print(f"✓ 正确捕获权限异常: {e}")
        except Exception as e:
            print(f"✓ 捕获到其他异常: {e}")
        finally:
            # 恢复权限以便清理
            os.chmod(readonly_dir, 0o755)
        print()
        
        print("=== 所有测试完成 ===")
        
    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir)
        print(f"已清理测试目录: {temp_dir}")

if __name__ == "__main__":
    test_create_file_tool()