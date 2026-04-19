from .client import NeptunAPI
from .exceptions import NeptunAPIError, NeptunAuthError, NeptunRequestError
from .models import (
    Training, Message, Term, TakenSubject, ExamSubject,
    CalendarEvent, FinancialImposition, CalendarTraining,
)

__all__ = [
    "NeptunAPI", "NeptunAPIError", "NeptunAuthError", "NeptunRequestError",
    "Training", "Message", "Term", "TakenSubject", "ExamSubject",
    "CalendarEvent", "FinancialImposition", "CalendarTraining",
    "fill_all_surveys",
]

def fill_all_surveys(*args, **kwargs):
    from .survey_filler import fill_all_surveys as _fill
    return _fill(*args, **kwargs)
__version__ = "0.1.0"
