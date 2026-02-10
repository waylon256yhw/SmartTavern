"""应用级异常，可映射到 HTTP 状态码。"""


class ApiError(Exception):
    """API 业务异常，由 gateway 错误中间件捕获并转为对应 HTTP 响应。"""

    def __init__(self, message: str, status_code: int = 400, error_code: str = "API_ERROR"):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
