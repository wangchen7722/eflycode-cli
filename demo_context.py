"""
ApplicationContext使用演示

展示如何使用ApplicationContext管理应用程序组件
"""

from eflycode import get_application_context
from eflycode.util.logger import logger


def demo_basic_usage():
    """演示基本用法"""
    print("=== ApplicationContext基本用法演示 ===")
    
    # 获取应用程序上下文单例
    app_context = get_application_context()
    
    # 启动上下文
    app_context.start()
    
    # 获取核心组件
    event_bus = app_context.get_event_bus()
    environment = app_context.get_environment()
    
    print(f"EventBus实例: {event_bus}")
    print(f"Environment实例: {environment}")
    
    # 注册自定义组件
    class MyService:
        def __init__(self, name: str):
            self.name = name
            
        def greet(self):
            return f"Hello from {self.name}!"
    
    my_service = MyService("DemoService")
    app_context.register_bean("my_service", my_service)
    
    # 获取注册的组件
    retrieved_service = app_context.get_bean("my_service")
    print(f"获取的服务: {retrieved_service.greet()}")
    
    # 按类型获取组件
    service_by_type = app_context.get_bean_by_type(MyService)
    print(f"按类型获取的服务: {service_by_type.greet()}")
    
    # 查看所有注册的Bean
    print(f"所有Bean名称: {app_context.get_bean_names()}")
    
    print("=== 基本用法演示完成 ===\n")


def demo_lifecycle_callbacks():
    """演示生命周期回调"""
    print("=== ApplicationContext生命周期回调演示 ===")
    
    app_context = get_application_context()
    
    # 添加启动回调
    def on_startup():
        print("应用程序启动回调执行")
        
    def on_shutdown():
        print("应用程序关闭回调执行")
    
    app_context.add_startup_callback(on_startup)
    app_context.add_shutdown_callback(on_shutdown)
    
    # 启动（如果还未启动）
    if not app_context.is_started():
        app_context.start()
    
    print(f"上下文是否已启动: {app_context.is_started()}")
    print(f"上下文是否已关闭: {app_context.is_shutdown()}")
    
    print("=== 生命周期回调演示完成 ===\n")


def demo_event_bus_integration():
    """演示事件总线集成"""
    print("=== ApplicationContext事件总线集成演示 ===")
    
    app_context = get_application_context()
    event_bus = app_context.get_event_bus()
    
    # 定义事件处理器
    def handle_demo_event(event: str, data: dict):
        print(f"收到事件 '{event}': {data}")
    
    # 订阅事件
    event_bus.subscribe("demo_event", handle_demo_event)
    
    # 发送事件
    event_bus.emit("demo_event", {"message": "这是一个演示事件", "timestamp": "2024-01-01"})
    
    # 等待事件处理完成
    import time
    time.sleep(0.1)
    
    print("=== 事件总线集成演示完成 ===\n")


def main():
    """主演示函数"""
    print("ApplicationContext演示程序启动\n")
    
    try:
        # 基本用法演示
        demo_basic_usage()
        
        # 生命周期回调演示
        demo_lifecycle_callbacks()
        
        # 事件总线集成演示
        demo_event_bus_integration()
        
    except Exception as e:
        logger.error(f"演示过程中发生错误: {e}")
        
    finally:
        # 关闭应用程序上下文
        app_context = get_application_context()
        app_context.shutdown()
        print("ApplicationContext演示程序结束")


if __name__ == "__main__":
    main()