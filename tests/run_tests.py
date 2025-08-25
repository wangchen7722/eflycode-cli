#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试运行脚本"""

import sys
import os
import unittest
import argparse
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def discover_and_run_tests(test_pattern="test_*.py", verbosity=2, failfast=False):
    """发现并运行测试用例
    
    Args:
        test_pattern: 测试文件模式，默认为 "test_*.py"
        verbosity: 详细程度，0=静默，1=正常，2=详细
        failfast: 是否在第一个失败时停止
    
    Returns:
        TestResult: 测试结果对象
    """
    # 获取测试目录
    test_dir = Path(__file__).parent
    
    # 发现测试用例
    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=str(test_dir),
        pattern=test_pattern,
        top_level_dir=str(project_root)
    )
    
    # 运行测试
    runner = unittest.TextTestRunner(
        verbosity=verbosity,
        failfast=failfast,
        buffer=True  # 捕获测试期间的stdout/stderr
    )
    
    print(f"正在运行测试用例...")
    print(f"测试目录: {test_dir}")
    print(f"测试模式: {test_pattern}")
    print("-" * 70)
    
    result = runner.run(suite)
    
    # 打印测试结果摘要
    print("\n" + "=" * 70)
    print("测试结果摘要:")
    print(f"运行测试数: {result.testsRun}")
    print(f"失败数: {len(result.failures)}")
    print(f"错误数: {len(result.errors)}")
    print(f"跳过数: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("\n✅ 所有测试通过！")
    else:
        print("\n❌ 部分测试失败")
        
        if result.failures:
            print("\n失败的测试:")
            for test, traceback in result.failures:
                print(f"  - {test}: {traceback.split('AssertionError: ')[-1].split('\n')[0]}")
        
        if result.errors:
            print("\n错误的测试:")
            for test, traceback in result.errors:
                error_msg = traceback.split('\n')[-2] if '\n' in traceback else traceback
                print(f"  - {test}: {error_msg}")
    
    return result


def run_specific_test(test_module, test_class=None, test_method=None, verbosity=2):
    """运行特定的测试
    
    Args:
        test_module: 测试模块名（如 'test_compressors'）
        test_class: 测试类名（可选）
        test_method: 测试方法名（可选）
        verbosity: 详细程度
    
    Returns:
        TestResult: 测试结果对象
    """
    # 构建测试标识符
    if test_method and test_class:
        test_id = f"{test_module}.{test_class}.{test_method}"
    elif test_class:
        test_id = f"{test_module}.{test_class}"
    else:
        test_id = test_module
    
    print(f"运行特定测试: {test_id}")
    print("-" * 70)
    
    # 加载并运行测试
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(test_id)
    
    runner = unittest.TextTestRunner(
        verbosity=verbosity,
        buffer=True
    )
    
    result = runner.run(suite)
    return result


def list_available_tests():
    """列出所有可用的测试"""
    test_dir = Path(__file__).parent
    
    print("可用的测试文件:")
    print("-" * 50)
    
    test_files = list(test_dir.glob("test_*.py"))
    
    for test_file in sorted(test_files):
        print(f"📄 {test_file.name}")
        
        # 尝试导入模块并列出测试类
        try:
            module_name = test_file.stem
            spec = unittest.util.spec_from_file_location(module_name, test_file)
            module = unittest.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 查找测试类
            test_classes = []
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, unittest.TestCase) and 
                    attr != unittest.TestCase):
                    test_classes.append(attr_name)
            
            for test_class in sorted(test_classes):
                print(f"  └── 🧪 {test_class}")
                
                # 列出测试方法
                class_obj = getattr(module, test_class)
                test_methods = [method for method in dir(class_obj) 
                              if method.startswith('test_')]
                
                for method in sorted(test_methods):
                    print(f"      └── ⚡ {method}")
        
        except Exception as e:
            print(f"  └── ❌ 无法加载: {e}")
        
        print()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="EchoAI 压缩器测试运行器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python run_tests.py                           # 运行所有测试
  python run_tests.py --list                    # 列出所有可用测试
  python run_tests.py --pattern "test_comp*"    # 运行匹配模式的测试
  python run_tests.py --module test_compressors # 运行特定模块
  python run_tests.py --class TestSummaryCompressor # 运行特定类
  python run_tests.py --method test_compress_empty_messages # 运行特定方法
  python run_tests.py --failfast               # 第一个失败时停止
  python run_tests.py --quiet                  # 静默模式
        """
    )
    
    parser.add_argument(
        "--pattern", 
        default="test_*.py",
        help="测试文件模式 (默认: test_*.py)"
    )
    
    parser.add_argument(
        "--module",
        help="运行特定测试模块 (如: test_compressors)"
    )
    
    parser.add_argument(
        "--class",
        dest="test_class",
        help="运行特定测试类 (需要与 --module 一起使用)"
    )
    
    parser.add_argument(
        "--method",
        dest="test_method",
        help="运行特定测试方法 (需要与 --module 和 --class 一起使用)"
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有可用的测试"
    )
    
    parser.add_argument(
        "--failfast",
        action="store_true",
        help="在第一个失败时停止测试"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="静默模式 (最小输出)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="详细模式 (最大输出)"
    )
    
    args = parser.parse_args()
    
    # 设置详细程度
    if args.quiet:
        verbosity = 0
    elif args.verbose:
        verbosity = 2
    else:
        verbosity = 1
    
    try:
        if args.list:
            list_available_tests()
            return
        
        if args.module:
            # 运行特定测试
            result = run_specific_test(
                args.module,
                args.test_class,
                args.test_method,
                verbosity
            )
        else:
            # 运行所有测试
            result = discover_and_run_tests(
                args.pattern,
                verbosity,
                args.failfast
            )
        
        # 根据测试结果设置退出码
        if result.wasSuccessful():
            sys.exit(0)
        else:
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(130)
    
    except Exception as e:
        print(f"\n❌ 运行测试时发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()