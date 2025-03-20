"""Echo - 基于控制台的交互程序"""
import time

from echo.ui.console import ConsoleUI


def main():
    """主程序入口"""
    console = ConsoleUI.get_instance()
    console.show_panel([], "欢迎使用 Echo，一款基于控制台的编码助手", "blue", "center")

    while True:
        user_input = console.acquire_user_input()
        # TODO：调用智能体等信息

        output_type = user_input

        if output_type == "text":
            content = f"用户输入：{user_input}"
            if isinstance(content, str):
                console.show_text(content)
            else:
                console.show_error("文本内容必须是字符串")
        elif output_type == "table":
            console.show_table("title", columns=["name", "age"], rows=[["Tom", "18"], ["Jerry", "20"]])
        elif output_type == "panel":
            console.show_panel(["标题1", "标题2"], "内容")
        elif output_type == "progress":
            with console.create_loading("正在处理..."):
                for i in range(100):
                    time.sleep(0.01)
        elif output_type == "success":
            console.show_success("成功")
        elif output_type == "error":
            console.show_error("错误")
        else:
            console.show_error(f"不支持的输出类型: {output_type}")
            break


if __name__ == "__main__":
    main()
