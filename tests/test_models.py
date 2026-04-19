from datetime import datetime
from neptun_api.models import (
    _parse_iso, Training, Message, Term, TakenSubject,
    ExamSubject, CalendarEvent, FinancialImposition, CalendarTraining,
)


def test_parse_iso_valid():
    assert _parse_iso("2023-09-01T00:00:00") == datetime(2023, 9, 1)


def test_parse_iso_none():
    assert _parse_iso(None) is None


def test_parse_iso_empty():
    assert _parse_iso("") is None


def test_parse_iso_invalid():
    assert _parse_iso("not-a-date") is None


def test_training_from_dict():
    t = Training.from_dict({
        "studentTrainingId": "abc-123",
        "code": "NBNFMA",
        "startingDate": "2023-09-01T00:00:00",
        "enrolmentYear": "2023/24/1",
        "faculty": "Nappali",
    })
    assert t.student_training_id == "abc-123"
    assert t.code == "NBNFMA"
    assert t.starting_date == datetime(2023, 9, 1)
    assert t.faculty == "Nappali"


def test_training_from_dict_empty():
    t = Training.from_dict({})
    assert t.student_training_id == ""
    assert t.code == ""
    assert t.starting_date is None


def test_message_from_dict():
    m = Message.from_dict({
        "messageId": "msg-1",
        "senderUserId": "user-1",
        "subject": "Hello",
        "sendDate": "2026-04-16T10:00:00",
        "isCurrentUserMessageCreator": False,
        "isNew": True,
    })
    assert m.message_id == "msg-1"
    assert m.subject == "Hello"
    assert m.is_new is True
    assert m.send_date == datetime(2026, 4, 16, 10, 0)


def test_message_from_dict_empty():
    m = Message.from_dict({})
    assert m.message_id == ""
    assert m.is_new is False


def test_term_from_dict():
    t = Term.from_dict({
        "value": "term-guid",
        "text": "2023/24/1",
        "creditSum": 30,
        "completedCredit": 28,
        "isClosed": True,
    })
    assert t.value == "term-guid"
    assert t.text == "2023/24/1"
    assert t.credit_sum == 30
    assert t.is_closed is True


def test_term_from_dict_minimal():
    t = Term.from_dict({"value": "x", "text": "y"})
    assert t.credit_sum is None
    assert t.is_closed is None


def test_taken_subject_from_dict():
    s = TakenSubject.from_dict({
        "indexLineId": "il-1",
        "subjectId": "s-1",
        "subjectName": "Databases",
        "subjectCode": "DB101",
        "subjectCredit": 5,
        "requirementType": "Exam",
        "numberOfTimesTakingSubject": 1,
        "termId": "t-1",
    })
    assert s.subject_name == "Databases"
    assert s.subject_credit == 5
    assert s.number_of_times_taking == 1


def test_exam_subject_from_dict():
    e = ExamSubject.from_dict({
        "subjectId": "s-1",
        "subjectName": "Math",
        "subjectCode": "MATH01",
    })
    assert e.subject_name == "Math"
    assert e.subject_code == "MATH01"


def test_calendar_event_from_dict():
    c = CalendarEvent.from_dict({
        "classInstanceId": "ci-1",
        "courseType": "Lecture",
        "courseCode": "CS101",
        "rooms": "Room A",
        "onWaitingList": False,
        "webexMeetingId": None,
    })
    assert c.class_instance_id == "ci-1"
    assert c.course_type == "Lecture"
    assert c.rooms == "Room A"
    assert c.on_waiting_list is False


def test_calendar_event_from_dict_empty():
    c = CalendarEvent.from_dict({})
    assert c.class_instance_id == ""
    assert c.rooms is None


def test_financial_imposition_from_dict():
    f = FinancialImposition.from_dict({
        "numberOfImpositionsRelatedToCurrency": 2,
        "balanceOfImpositions": 80000.0,
        "currency": "HUF",
        "items": [{"name": "fee"}],
    })
    assert f.number_of_impositions == 2
    assert f.balance == 80000.0
    assert f.currency == "HUF"
    assert len(f.items) == 1


def test_financial_imposition_from_dict_empty():
    f = FinancialImposition.from_dict({})
    assert f.balance == 0.0
    assert f.items == []


def test_calendar_training_from_dict():
    ct = CalendarTraining.from_dict({
        "actualStudentTraining": True,
        "studentTrainingId": "st-1",
        "studentTrainingName": "CS BSc",
    })
    assert ct.actual is True
    assert ct.student_training_id == "st-1"
    assert ct.student_training_name == "CS BSc"
