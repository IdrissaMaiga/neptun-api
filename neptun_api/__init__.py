from .client import NeptunAPI, generate_totp
from .exceptions import (
    NeptunAPIError, NeptunAuthError, NeptunRequestError,
    NeptunTwoFactorRequired, NeptunCaptchaRequired,
)
from .models import (
    Training, Message, Term, TakenSubject, ExamSubject, SubjectGrade,
    CalendarEvent, FinancialImposition, CalendarTraining,
)

__all__ = [
    "NeptunAPI", "NeptunAPIError", "NeptunAuthError", "NeptunRequestError",
    "NeptunTwoFactorRequired", "NeptunCaptchaRequired", "generate_totp",
    "Training", "Message", "Term", "TakenSubject", "ExamSubject", "SubjectGrade",
    "CalendarEvent", "FinancialImposition", "CalendarTraining",
    "fill_all_surveys",
]

def fill_all_surveys(*args, **kwargs):
    from .survey_filler import fill_all_surveys as _fill
    return _fill(*args, **kwargs)
__version__ = "0.1.1"
