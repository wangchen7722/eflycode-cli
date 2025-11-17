from eflycode.ui.console.main_app import MainUIApplication
from eflycode.util.event_bus import EventBus



def main():
    """主函数，启动 Developer agent 的交互式会话"""

    bus = EventBus()
    main_app = MainUIApplication(bus)

    main_app.run()


if __name__ == "__main__":
    main()
