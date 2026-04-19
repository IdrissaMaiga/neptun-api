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
]
__version__ = "0.1.0"
