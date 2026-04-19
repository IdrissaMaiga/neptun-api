from dataclasses import dataclass, field
from datetime import datetime


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


@dataclass
class Training:
    student_training_id: str
    code: str
    starting_date: datetime | None
    enrolment_year: str
    faculty: str

    @classmethod
    def from_dict(cls, d: dict) -> "Training":
        return cls(
            student_training_id=d.get("studentTrainingId", ""),
            code=d.get("code", ""),
            starting_date=_parse_iso(d.get("startingDate")),
            enrolment_year=d.get("enrolmentYear", ""),
            faculty=d.get("faculty", ""),
        )


@dataclass
class Message:
    message_id: str
    sender_user_id: str
    subject: str
    send_date: datetime | None
    is_current_user_creator: bool
    is_new: bool

    @classmethod
    def from_dict(cls, d: dict) -> "Message":
        return cls(
            message_id=d.get("messageId", ""),
            sender_user_id=d.get("senderUserId", ""),
            subject=d.get("subject", ""),
            send_date=_parse_iso(d.get("sendDate")),
            is_current_user_creator=d.get("isCurrentUserMessageCreator", False),
            is_new=d.get("isNew", False),
        )


@dataclass
class Term:
    value: str
    text: str
    credit_sum: int | None = None
    completed_credit: int | None = None
    is_closed: bool | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "Term":
        return cls(
            value=d.get("value", ""),
            text=d.get("text", ""),
            credit_sum=d.get("creditSum"),
            completed_credit=d.get("completedCredit"),
            is_closed=d.get("isClosed"),
        )


@dataclass
class TakenSubject:
    index_line_id: str
    subject_id: str
    subject_name: str
    subject_code: str
    subject_credit: int
    requirement_type: str
    number_of_times_taking: int
    term_id: str

    @classmethod
    def from_dict(cls, d: dict) -> "TakenSubject":
        return cls(
            index_line_id=d.get("indexLineId", ""),
            subject_id=d.get("subjectId", ""),
            subject_name=d.get("subjectName", ""),
            subject_code=d.get("subjectCode", ""),
            subject_credit=d.get("subjectCredit", 0),
            requirement_type=d.get("requirementType", ""),
            number_of_times_taking=d.get("numberOfTimesTakingSubject", 0),
            term_id=d.get("termId", ""),
        )


@dataclass
class ExamSubject:
    subject_id: str
    subject_name: str
    subject_code: str

    @classmethod
    def from_dict(cls, d: dict) -> "ExamSubject":
        return cls(
            subject_id=d.get("subjectId", ""),
            subject_name=d.get("subjectName", ""),
            subject_code=d.get("subjectCode", ""),
        )


@dataclass
class CalendarEvent:
    class_instance_id: str
    course_type: str
    course_code: str
    rooms: str | None
    on_waiting_list: bool
    webex_meeting_id: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "CalendarEvent":
        return cls(
            class_instance_id=d.get("classInstanceId", ""),
            course_type=d.get("courseType", ""),
            course_code=d.get("courseCode", ""),
            rooms=d.get("rooms"),
            on_waiting_list=d.get("onWaitingList", False),
            webex_meeting_id=d.get("webexMeetingId"),
        )


@dataclass
class FinancialImposition:
    number_of_impositions: int
    balance: float
    currency: str
    items: list[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "FinancialImposition":
        return cls(
            number_of_impositions=d.get("numberOfImpositionsRelatedToCurrency", 0),
            balance=d.get("balanceOfImpositions", 0.0),
            currency=d.get("currency", ""),
            items=d.get("items", []),
        )


@dataclass
class CalendarTraining:
    actual: bool
    student_training_id: str
    student_training_name: str

    @classmethod
    def from_dict(cls, d: dict) -> "CalendarTraining":
        return cls(
            actual=d.get("actualStudentTraining", False),
            student_training_id=d.get("studentTrainingId", ""),
            student_training_name=d.get("studentTrainingName", ""),
        )
