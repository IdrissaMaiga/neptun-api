class NeptunAPIError(Exception):
    def __init__(self, message: str, error_data: dict | None = None):
        super().__init__(message)
        self.error_data = error_data


class NeptunAuthError(NeptunAPIError):
    pass


class NeptunRequestError(NeptunAPIError):
    pass
