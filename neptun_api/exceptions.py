class NeptunAPIError(Exception):
    def __init__(self, message: str, error_data: dict | None = None):
        super().__init__(message)
        self.error_data = error_data


class NeptunAuthError(NeptunAPIError):
    pass


class NeptunRequestError(NeptunAPIError):
    pass


class NeptunTwoFactorRequired(NeptunAuthError):
    """Login needs a second factor (6-digit authenticator code) and none was available.

    Pass ``authenticate(totp_code=...)``, or construct ``NeptunAPI`` with
    ``totp_secret=`` / ``two_factor_callback=`` so the client can supply it.
    """


class NeptunCaptchaRequired(NeptunAuthError):
    """Login needs a captcha to be solved first (usually after repeated failed logins)."""
