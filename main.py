from eflycode.app import MainApplication


def main():
    """主函数，启动 Developer agent 的交互式会话"""
    application = MainApplication()
    application.run(use_mock_agent=True)


if __name__ == "__main__":
    main()
