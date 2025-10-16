"""
Environment 测试文件

测试Environment配置系统的功能
"""

from eflycode.env.environment import Environment


def test_environment():
    """测试Environment配置系统"""
    
    # 获取Environment实例
    environment = Environment.get_instance()
    
    print("=" * 50)
    print("Environment 配置测试")
    print("=" * 50)
    
    # 打印配置摘要
    print("\n1. 配置摘要:")
    config_summary = environment.get_config_summary()
    for key, value in config_summary.items():
        print(f"   {key}: {value}")
    
    # 打印完整配置
    print("\n2. 完整配置:")
    full_config = environment.get_full_config()
    for key, value in full_config.items():
        print(f"   {key}: {value}")
    
    # 打印日志配置
    print("\n3. 日志配置:")
    logging_config = environment.get_logging_config()
    print(f"   类型: {type(logging_config)}")
    print(f"   日志目录: {logging_config.dirpath}")
    print(f"   日志文件: {logging_config.filename}")
    print(f"   日志级别: {logging_config.level}")
    print(f"   日志格式: {logging_config.format}")
    print(f"   日志轮转: {logging_config.rotation}")
    print(f"   日志保留: {logging_config.retention}")
    print(f"   编码: {logging_config.encoding}")
    
    # 打印模型配置
    print("\n4. 模型配置:")
    model_config = environment.get_model_config()
    print(f"   类型: {type(model_config)}")
    print(f"   默认模型: {model_config.default}")
    print(f"   模型数量: {len(model_config.entries)}")
    
    for i, entry in enumerate(model_config.entries):
        print(f"\n   模型 {i+1}:")
        print(f"     模型ID: {entry.model}")
        print(f"     模型名称: {entry.name}")
        print(f"     提供方: {entry.provider}")
        print(f"     API密钥: {entry.api_key[:10]}..." if len(entry.api_key) > 10 else f"     API密钥: {entry.api_key}")
        print(f"     基础URL: {entry.base_url}")
        print(f"     最大上下文长度: {entry.max_context_length}")
        print(f"     温度: {entry.temperature}")
        print(f"     支持原生工具调用: {entry.supports_native_tool_call}")
    
    # 测试运行时配置
    print("\n5. 运行时配置测试:")
    print("   设置运行时配置...")
    environment.set("test.runtime_key", "runtime_value")
    environment.set("logging.level", "DEBUG")
    
    print(f"   test.runtime_key: {environment.get('test.runtime_key')}")
    print(f"   logging.level: {environment.get('logging.level')}")
    
    # 测试配置路径
    print("\n6. 配置文件路径:")
    config_paths = environment._config_loader.get_config_paths()
    for key, path in config_paths.items():
        print(f"   {key}: {path}")
    
    print("\n" + "=" * 50)
    print("Environment 测试完成")
    print("=" * 50)


if __name__ == "__main__":
    test_environment()