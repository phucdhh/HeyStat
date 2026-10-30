"""Students see the time they handed in; the marks stay with the teacher.

Both audiences share one response model, so `_without_marks` and the question
prompt whitelist in `_to_response` are the only things keeping điểm, đáp án and
the pass/fail detail out of the student payload.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

from routers.assignments import _to_response
from routers.submissions import SubmissionResponse, _without_marks

NOW = datetime(2026, 10, 30, 9, 0, tzinfo=timezone.utc)


def _payload() -> SubmissionResponse:
    return SubmissionResponse(
        id="s1", assignment_id="a1", student_id="u1", student_name="Trần A",
        submitted_at=NOW, is_final=True, score=8.5, feedback="Đạt yêu cầu",
        file_path="/uploads/a1.omv",
        answers={"q1": 3.14, "q1_note": "Mình chạy Descriptives rồi đọc cột mean"},
        auto_grade={"score": 8.5, "items": [{"id": "q1", "passed": False}]},
        outputs=[{"index": 0}],
    )


def test_student_payload_keeps_the_submission_time_but_no_marks():
    out = _without_marks(_payload())
    assert out.submitted_at == NOW
    assert out.is_final is True
    assert (out.score, out.feedback, out.auto_grade) == (None, None, None)


def test_the_written_explanation_is_an_answer_not_a_mark():
    out = _without_marks(_payload())
    assert out.answers["q1_note"].startswith("Mình chạy")


def _assignment(answer_key: dict) -> SimpleNamespace:
    return SimpleNamespace(
        id="a1", class_id="c1", title="Bài 1", description="",
        assignment_type="homework", max_score=10.0, deadline=NOW,
        allow_resubmit=True, group_size=1, allow_sharing=True, file_id=None,
        answer_key=answer_key, grading_config=None, created_at=NOW,
    )


def test_a_student_gets_the_note_box_but_never_the_expected_answer():
    a = _assignment({"questions": [{
        "id": "q1", "label": "Giá trị trung bình?", "type": "number",
        "answer": 3.14, "tolerance": 0.01, "points": 2,
        "comment": True, "comment_hint": "Cách bạn làm",
    }]})
    q = _to_response(a, with_key=False).questions[0]
    assert set(q) == {"id", "label", "type", "points", "comment", "comment_hint"}
    assert q["comment"] is True and q["comment_hint"] == "Cách bạn làm"


def test_a_question_without_the_note_box_does_not_send_the_keys():
    a = _assignment({"questions": [{"id": "q1", "label": "?", "type": "number", "answer": 1, "points": 1}]})
    assert set(_to_response(a, with_key=False).questions[0]) == {"id", "label", "type", "points"}
