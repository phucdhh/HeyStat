from types import SimpleNamespace

from services.auto_grader import auto_grade
from tests.test_omv_reader import make_omv
from services.omv_reader import parse_omv

DOC = parse_omv(make_omv())


def assignment(grading_config=None, answer_key=None, max_score=10.0):
    return SimpleNamespace(grading_config=grading_config, answer_key=answer_key, max_score=max_score)


def test_returns_none_for_fully_manual_assignments():
    assert auto_grade(assignment(), DOC, None) is None
    assert auto_grade(assignment(grading_config={}, answer_key={}), DOC, None) is None


def test_threshold_check_passes_and_fails_with_explanation():
    config = {"checks": [
        {"id": "anova_p", "label": "ANOVA có ý nghĩa", "op": "lte", "analysis": "One-Way ANOVA",
         "column": "p", "value": 0.05, "points": 2},
        {"id": "r2", "label": "Mức độ giải thích", "op": "gte", "table": "Model Fit",
         "column": "R²", "value": 0.5, "points": 2, "explain": "R² phải đạt ít nhất .50."},
    ]}
    result = auto_grade(assignment(grading_config=config), DOC, None)
    by_id = {i["id"]: i for i in result["items"]}
    assert by_id["anova_p"]["passed"] is True
    assert by_id["anova_p"]["awarded"] == 2.0
    assert by_id["r2"]["passed"] is False
    assert by_id["r2"]["explanation"] == "R² phải đạt ít nhất .50."
    assert result["earned"] == 2.0
    assert result["possible"] == 4.0
    assert result["score"] == 5.0  # scaled onto the assignment's 10-point max


def test_checks_can_require_an_analysis_or_a_table():
    config = {"checks": [
        {"id": "ran", "op": "ran", "analysis": "linReg", "points": 1},
        {"id": "coef", "op": "present", "table": "Model Coefficients", "points": 1},
        {"id": "missing_table", "op": "present", "table": "Post Hoc", "points": 1},
    ]}
    result = auto_grade(assignment(grading_config=config), DOC, None)
    by_id = {i["id"]: i for i in result["items"]}
    assert by_id["ran"]["passed"] is True
    assert by_id["coef"]["passed"] is True
    assert by_id["missing_table"]["passed"] is False
    assert by_id["missing_table"]["reason"] == "table"
    assert "Không tìm thấy bảng “Post Hoc”" in by_id["missing_table"]["explanation"]


def test_a_check_reads_the_number_stored_in_the_submitted_file():
    """Grading a submission is not a screenshot comparison: the .omv carries the
    statistics themselves, so a tolerance check sees 7.325754, not "7.33"."""
    from tests.test_omv_proto import doc_of, ttest_entry

    doc = doc_of(ttest_entry())
    config = {"checks": [
        {"id": "t", "label": "Giá trị t", "op": "between", "analysis": "ttestOneS",
         "table": "One Sample T-Test", "column": "Statistic", "value": 7.3, "value2": 7.4,
         "points": 2},
        {"id": "sig", "label": "p có ý nghĩa", "op": "lt", "table": "One Sample T-Test",
         "column": "p", "value": 0.05, "points": 1},
        # the student unticked the box, so the column is not in their output
        {"id": "ci", "label": "Khoảng tin cậy", "op": "present", "table": "One Sample T-Test",
         "row": "Unticked", "points": 1},
    ]}
    result = auto_grade(assignment(grading_config=config), doc, None)
    by_id = {i["id"]: i for i in result["items"]}
    assert by_id["t"]["passed"] is True
    assert by_id["t"]["actual"] == 7.325754
    assert by_id["sig"]["passed"] is True
    assert by_id["ci"]["passed"] is False
    assert by_id["ci"]["reason"] == "row"
    assert "không có dòng “Unticked”" in by_id["ci"]["explanation"]
    assert result["earned"] == 3.0


def test_between_and_tolerance():
    config = {"checks": [
        {"id": "r_between", "op": "between", "table": "Model Fit", "column": "R",
         "value": 0.1, "value2": 0.2, "points": 1},
    ]}
    result = auto_grade(assignment(grading_config=config), DOC, None)
    assert result["items"][0]["passed"] is True


def test_answer_key_numbers_and_text():
    key = {"questions": [
        {"id": "n", "label": "Số quan sát", "type": "number", "answer": 1047, "tolerance": 1, "points": 1},
        {"id": "conclusion", "label": "Kết luận", "type": "text", "answer": ["Bác bỏ H0", "bác bỏ H0"], "points": 1},
        {"id": "empty", "label": "Chưa làm", "type": "text", "answer": "x", "points": 1},
    ]}
    result = auto_grade(
        assignment(answer_key=key),
        DOC,
        {"n": "1,047", "conclusion": "Bác bỏ H0", "empty": ""},
    )
    by_id = {i["id"]: i for i in result["items"]}
    assert by_id["n"]["passed"] is True
    assert by_id["conclusion"]["passed"] is True
    assert by_id["empty"]["passed"] is False
    assert "bỏ trống" in by_id["empty"]["explanation"]
    assert result["mistake_count"] == 1


def test_text_answer_mismatch_explains_both_values():
    key = {"questions": [{"id": "q", "label": "Yêu cầu", "type": "text", "answer": "ANOVA", "points": 1}]}
    result = auto_grade(assignment(answer_key=key), DOC, {"q": "t-test"})
    item = result["items"][0]
    assert item["passed"] is False
    assert "t-test" in item["explanation"] and "ANOVA" in item["explanation"]


def test_feedback_lists_every_mistake_for_the_student():
    config = {"checks": [{"id": "c", "label": "Bảng Shapiro-Wilk", "op": "present",
                          "table": "Shapiro", "points": 1, "explain": "Chưa kiểm định chuẩn."}]}
    result = auto_grade(assignment(grading_config=config, max_score=8.0), DOC, None)
    assert result["score"] == 0.0
    assert "Bảng Shapiro-Wilk" in result["feedback"]
    assert "Chưa kiểm định chuẩn." in result["feedback"]


def test_missing_omv_is_reported_instead_of_crashing():
    config = {"checks": [{"id": "c", "label": "Bảng", "op": "lte", "table": "Model Fit",
                          "column": "p", "value": 0.05, "points": 1}]}
    result = auto_grade(assignment(grading_config=config), None, None)
    assert result["items"][0]["passed"] is None
    assert result["score"] == 0.0


def test_an_essay_question_waits_for_the_teacher_instead_of_reading_as_wrong():
    key = {"questions": [
        {"id": "q1", "label": "Giá trị trung bình", "type": "number",
         "answer": 3.43, "tolerance": 0.01, "points": 6},
        {"id": "q2", "label": "Diễn giải kết quả", "type": "essay", "points": 4},
    ]}
    result = auto_grade(assignment(answer_key=key), None,
                        {"q1": 3.43, "q2": "p < .05 nên khác có ý nghĩa"})
    by_id = {i["id"]: i for i in result["items"]}
    assert by_id["q1"]["passed"] is True
    assert by_id["q2"]["passed"] is None and by_id["q2"]["pending"] is True
    assert by_id["q2"]["awarded"] == 0.0
    assert by_id["q2"]["actual"] == "p < .05 nên khác có ý nghĩa"
    assert result["possible"] == 10.0, "the essay keeps its weight in the total"
    assert result["mistake_count"] == 0, "waiting for a human is not a mistake"
    assert "chờ thầy/cô chấm" in result["feedback"]
