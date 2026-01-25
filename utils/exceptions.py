class PublishError(Exception):
    """Базовая ошибка публикации/удаления для конкретной платформы."""
    def __init__(self, platform, message, code = None):
        self.platform = platform
        self.message = message
        self.code = code
        super().__init__(f"{platform}: {message}" + (f" (code={code})" if code else ""))


class NetworkError(PublishError):
    pass


class AuthError(PublishError):
    pass


class ApiError(PublishError):
    pass
