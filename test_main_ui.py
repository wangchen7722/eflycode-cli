#!/usr/bin/env python3
"""
测试 MainApplicationUI 的基本功能
"""

import time
import threading
from eflycode.util.event_bus import EventBus
from eflycode.ui.main_application_ui import MainApplicationUI


def test_main_ui():
    """测试主 UI 功能"""
    
    # 创建事件总线
    event_bus = EventBus()
    
    # 创建主 UI
    main_ui = MainApplicationUI(event_bus)
    
    # 添加一些测试输出
    main_ui.add_output("Welcome to EflyCode MainApplicationUI Test!", "class:welcome")
    main_ui.add_output("This is a test of the unified UI system.", "class:info")
    main_ui.add_output("You can type commands and see the output here.", "class:info")
    
    # 模拟一些事件
    def simulate_events():
        """模拟事件触发"""
        time.sleep(2)
        
        # 模拟思考开始
        event_bus.publish("think_start", {"content": "Starting to think..."})
        time.sleep(3)
        
        # 模拟思考结束
        event_bus.publish("think_end", {})
        time.sleep(1)
        
        # 模拟工具调用
        event_bus.publish("tool_call_start", {"name": "test_tool"})
        time.sleep(2)
        
        event_bus.publish("tool_call_end", {"name": "test_tool", "args": "test_args"})
        time.sleep(1)
        
        event_bus.publish("tool_call_finish", {
            "name": "test_tool", 
            "args": "test_args", 
            "result": "Tool executed successfully!"
        })
    
    # 在后台线程中模拟事件
    event_thread = threading.Thread(target=simulate_events, daemon=True)
    event_thread.start()
    
    try:
        # 运行主 UI
        print("Starting MainApplicationUI...")
        print("Press Ctrl+C to exit")
        main_ui.run()
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        main_ui.exit()


if __name__ == "__main__":
    test_main_ui()