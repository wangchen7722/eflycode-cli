import time
import threading
from prompt_toolkit.shortcuts import print_formatted_text

from eflycode.ui.console import ConsoleAgentUI


def main():
    ui = ConsoleAgentUI()

    def simulate():
        """模拟工具调用的生命周期"""
        time.sleep(1)
        print_formatted_text("=== 🧩 启动工具调用 ===")

        # 启动动画
        ui.start_tool_call("正在调用 SmartCodeAnalyzer() ...")

        # 模拟执行过程
        time.sleep(2)
        ui.execute_tool_call("SmartCodeAnalyzer", "code='print(1+1)'")

        # 模拟执行中
        time.sleep(2)
        ui.execute_tool_call("SmartCodeAnalyzer", "code='sum(range(10))'")

        # 模拟执行结束
        time.sleep(2)
        ui.fail_tool_call("SmartCodeAnalyzer", "code='sum(range(10))'", "55")

        ui.print("=== ✅ 工具调用完成 ===")

        # 延迟退出
        time.sleep(1)
        ui.exit()

    # 后台线程运行模拟逻辑
    threading.Thread(target=simulate, daemon=True).start()

    # 启动 UI 应用（主线程）
    ui.run()


if __name__ == "__main__":
    main()
