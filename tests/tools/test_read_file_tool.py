#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试ReadFileTool的新功能
"""

import os
import tempfile
from echo.tools.file.file_tool import ReadFileTool

def test_read_file_tool():
    """测试ReadFileTool的功能"""
    tool = ReadFileTool()
    
    # 创建一个测试文件，包含150行内容
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as f:
        test_file_path = f.name
        for i in range(1, 151):
            f.write(f"这是第 {i} 行内容\n")
    
    try:
        print("=== 测试1: 默认读取（前100行）===")
        result1 = tool.do_run(test_file_path)
        print(result1[:200] + "..." if len(result1) > 200 else result1)
        
        print("\n=== 测试2: 读取指定范围（第50-80行）===")
        result2 = tool.do_run(test_file_path, start_line=50, end_line=80)
        print(result2)
        
        print("\n=== 测试3: 读取更多行（前120行）===")
        result3 = tool.do_run(test_file_path, max_lines=120)
        print(result3[:300] + "..." if len(result3) > 300 else result3)
        
        print("\n=== 测试4: 读取全部内容 ===")
        result4 = tool.do_run(test_file_path, max_lines=200)
        lines = result4.split('\n')
        print(f"前几行：{lines[0]}")
        print(f"后几行：{lines[-3]}")
        print(f"总共返回了 {len(lines)} 行")
        
    finally:
        # 清理测试文件
        os.unlink(test_file_path)
    
    print("\n=== 测试工具属性 ===")
    print(f"工具名称: {tool.name}")
    print(f"工具类型: {tool.type}")
    print(f"需要审批: {tool.should_approval}")
    print(f"描述: {tool.description.strip()}")
    print(f"参数: {tool.parameters}")

if __name__ == "__main__":
    test_read_file_tool()