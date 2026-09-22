class YandexDiskApiException(Exception):
    """Базовое исключение API клиента Яндекс Диска."""


class AuthenticationError(YandexDiskApiException):
    """Выбрасывается при ошибке 401 Unauthorized (токен недействителен)."""


class PermissionDeniedError(YandexDiskApiException):
    """Выбрасывается при ошибке 403 Forbidden (недостаточно OAuth-прав)."""


class OperationTimeoutError(YandexDiskApiException):
    """Выбрасывается при превышении лимита ожидания асинхронной операции."""