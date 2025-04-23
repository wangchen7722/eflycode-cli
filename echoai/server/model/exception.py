class ServiceException(Exception):
    """
    服务异常
    """
    def __init__(self, code: int = 400, message: str = "error"):
        self.code = code
        self.message = message
        super().__init__(f"code: {code}, message: {message}")
