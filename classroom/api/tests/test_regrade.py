from types import SimpleNamespace

from routers.submissions import regrade_submission
from services.omv_reader import parse_omv
from tests.test_omv_reader import make_omv
from tests.test_omv_proto import doc_of, ttest_entry


def assignment(grading_config=None, answer_key=None, max_score=10.0, title="Bài 1"):
    return SimpleNamespace(id="a", grading_config=grading_config, answer_key=answer_key,
                           max_score=max_score, title=title)


def submission(snapshot=None, graded_by=None, answers=None):
    return SimpleNamespace(id="s", student_id="u", file_path="submissions/x.omv",
                           session_snapshot=snapshot, answers=answers, graded_by=graded_by,
                           score=None, feedback=None, auto_grade=None, graded_at=None)


DOC = parse_omv(make_omv())


def test_a_hand_graded_submission_keeps_the_teacher_mark():
    sub = submission(graded_by="teacher")
    config = {"checks": [{"id": "c", "op": "gte", "table": "Model Fit", "column": "R",
                          "value": 0.99, "points": 1}]}
    assert regrade_submission(assignment(grading_config=config), sub, DOC) is None
    assert sub.score is None


def test_no_file_or_no_criteria_leaves_the_submission_alone():
    sub = submission()
    assert regrade_submission(assignment(), sub, None) is None
    assert regrade_submission(assignment(), sub, DOC) is None
    assert sub.auto_grade is None


def test_regrading_follows_the_new_threshold():
    config = {"checks": [{"id": "r", "label": "R", "op": "gte", "table": "Model Fit",
                          "column": "R", "value": 0.5, "points": 4}]}
    sub = submission()
    assert regrade_submission(assignment(grading_config=config), sub, DOC)["score"] == 0.0

    config["checks"][0]["value"] = 0.1
    grade = regrade_submission(assignment(grading_config=config), sub, DOC)
    assert grade["score"] == 10.0
    assert sub.score == 10.0
    assert sub.auto_grade is grade


def test_regrading_rereads_the_evidence_but_keeps_what_the_student_ticked():
    """The snapshot a student chose is their claim about their own work; re-grading
    refreshes the numbers without changing which tables they stood behind."""
    old = {"tables": [{"index": 1, "analysis": "Linear Regression", "title": "Model Coefficients - outcome",
                       "columns": [], "rows": []}],
           "modules": ["linReg"], "images": []}
    sub = submission(snapshot=old)
    config = {"checks": [{"id": "t", "op": "gte", "table": "Model Coefficients",
                          "column": "t", "value": 3, "points": 1}]}
    regrade_submission(assignment(grading_config=config), sub, DOC)
    assert [t["title"] for t in sub.session_snapshot["tables"]] == ["Model Coefficients - outcome"]
    assert sub.session_snapshot["tables"][0]["rows"][1] == ["predictor1", "0.320", "0.0629", "5.09", "<.001"]


def test_a_submission_that_had_no_evidence_is_backfilled_from_the_file():
    """Snapshots taken before the .omv could be read are empty; the file on disk now
    yields the tables, so old submissions become gradeable and reviewable."""
    sub = submission(snapshot=None)
    doc = doc_of(ttest_entry())
    config = {"checks": [{"id": "t", "op": "between", "table": "One Sample T-Test",
                          "column": "Statistic", "value": 7.3, "value2": 7.4, "points": 2}]}
    grade = regrade_submission(assignment(grading_config=config), sub, doc)
    assert grade["score"] == 10.0
    assert [t["title"] for t in sub.session_snapshot["tables"]] == [
        "One Sample T-Test", "Normality Test (Shapiro-Wilk)"]
