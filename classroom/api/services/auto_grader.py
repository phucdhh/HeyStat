"""Auto-grade a jamovi submission against the teacher's answer key and criteria.

Two kinds of evidence are graded, matching the two halves of a submission:

* ``answer_key``   – the numbers/notes the student typed into the sidebar.
* ``grading_config`` – checks against the tables inside the submitted ``.omv``.

Anything the teacher did not configure is left for manual grading, so a plain
homework assignment behaves exactly as it did before.
"""
from __future__ import annotations

from typing import Any, Optional

from services.omv_reader import find_stat, find_row, normalise, parse_number


def _compare(actual: float, op: str, value: Any, value2: Any = None, tolerance: float = 0.0) -> bool:
    if op in ("gte", ">="):
        return actual >= float(value)
    if op in ("lte", "<="):
        return actual <= float(value)
    if op == "gt":
        return actual > float(value)
    if op == "lt":
        return actual < float(value)
    if op == "between":
        return float(value) <= actual <= float(value2)
    return abs(actual - float(value)) <= tolerance


def _explain(check: dict, passed: bool, actual: Any, expected: Any, has_table: bool) -> str:
    if passed:
        return check.get("explain_ok") or ""
    if check.get("explain"):
        return check["explain"]
    if not has_table:
        return (f"Không tìm thấy bảng “{check.get('table') or check.get('analysis') or ''}” "
                "trong kết quả — có thể bạn chưa chạy phân tích này.")
    return f"Giá trị trong bài là {actual}, yêu cầu {expected}."


def _grade_checks(grading_config: dict, doc: Optional[dict]) -> list[dict]:
    items: list[dict] = []
    for check in grading_config.get("checks", []):
        points = float(check.get("points", 1))
        op = check.get("op", "present")
        passed: Optional[bool]
        actual: Any = None
        has_table = True

        if doc is None:
            items.append({"id": check.get("id"), "kind": "check", "label": check.get("label", op),
                          "passed": None, "awarded": 0.0, "points": points,
                          "expected": check.get("value"), "actual": None,
                          "explanation": "Chưa có file .omv nộp lên nên không kiểm tra được."})
            continue

        if op == "ran":
            wanted = normalise(str(check.get("analysis", "")))
            passed = any(
                wanted and wanted in normalise(t["analysis"])
                for t in doc["tables"]
            ) or any(normalise(m) == wanted for m in doc["modules"])
            actual = "có" if passed else "không"
            has_table = bool(passed)
            expected = f"chạy {check.get('analysis')}"
        elif op == "present":
            if check.get("row"):
                row = find_row(doc, check.get("table", ""), check["row"])
                passed = row is not None
                actual = row
            else:
                passed = any(
                    normalise(check.get("table", "")) in normalise(t["title"])
                    for t in doc["tables"]
                )
                actual = "có" if passed else "không"
            has_table = bool(passed)
            expected = f"bảng {check.get('table')}"
        else:
            actual = find_stat(
                doc,
                analysis=check.get("analysis"),
                table=check.get("table"),
                column=check.get("column"),
                row=check.get("row"),
            )
            has_table = actual is not None
            passed = None if actual is None else _compare(
                actual, op, check.get("value"), check.get("value2"),
                float(check.get("tolerance", 0.0)),
            )
            expected = {
                "gte": f"≥ {check.get('value')}", ">=": f"≥ {check.get('value')}",
                "lte": f"≤ {check.get('value')}", "<=": f"≤ {check.get('value')}",
                "gt": f"> {check.get('value')}", "lt": f"< {check.get('value')}",
                "eq": f"= {check.get('value')}",
                "between": f"{check.get('value')} – {check.get('value2')}",
            }.get(op, str(check.get("value")))

        items.append({
            "id": check.get("id"),
            "kind": "check",
            "label": check.get("label") or f"{check.get('column') or check.get('table') or check.get('analysis')}",
            "passed": passed,
            "awarded": points if passed else 0.0,
            "points": points,
            "expected": expected,
            "actual": actual,
            "explanation": _explain(check, bool(passed), actual, expected, has_table),
        })
    return items


def _grade_answers(answer_key: dict, answers: Optional[dict]) -> list[dict]:
    items: list[dict] = []
    answers = answers or {}
    for question in answer_key.get("questions", []):
        points = float(question.get("points", 1))
        qid = str(question.get("id"))
        given = answers.get(qid, answers.get(f"q{qid}", None))
        qtype = question.get("type", "number")
        expected = question.get("answer")

        if given in (None, ""):
            passed, why = False, "Bạn bỏ trống câu này."
        elif qtype == "number":
            actual_num = parse_number(given)
            if actual_num is None:
                passed, why = False, "Câu trả lời không phải là một số."
            else:
                tol = float(question.get("tolerance", 0.0))
                passed = abs(actual_num - float(expected)) <= tol
                why = "" if passed else f"Giá trị của bạn là {actual_num}, đáp án là {expected} (±{tol})."
                given = actual_num
        else:
            accepted = expected if isinstance(expected, list) else [expected]
            passed = any(normalise(str(a)) == normalise(str(given)) for a in accepted)
            why = "" if passed else f"Bạn viết “{given}”, đáp án là {expected}."

        items.append({
            "id": qid,
            "kind": "answer",
            "label": question.get("label", qid),
            "passed": passed,
            "awarded": points if passed else 0.0,
            "points": points,
            "expected": expected,
            "actual": given,
            "explanation": (question.get("explain") or why) if not passed else "",
        })
    return items


def auto_grade(
    assignment,
    doc: Optional[dict],
    answers: Optional[dict],
) -> Optional[dict]:
    """Grade one submission. Returns None when the assignment is fully manual."""
    grading_config = getattr(assignment, "grading_config", None) or {}
    answer_key = getattr(assignment, "answer_key", None) or {}
    if not grading_config.get("checks") and not answer_key.get("questions"):
        return None

    items = _grade_answers(answer_key, answers) + _grade_checks(grading_config, doc)
    earned = round(sum(float(i["awarded"]) for i in items), 2)
    possible = round(sum(float(i["points"]) for i in items), 2) or 1.0

    max_score = float(assignment.max_score)
    scaled = round(earned / possible * max_score, 2)
    mistakes = [i for i in items if not i["passed"]]

    feedback_lines = [
        f"Tự động chấm: {earned}/{possible} điểm tiêu chí → {scaled}/{max_score} điểm bài tập."
    ]
    if mistakes:
        feedback_lines.append("Các điểm cần sửa:")
        feedback_lines += [f"- {i['label']}: {i['explanation']}" for i in mistakes if i["explanation"]]
    else:
        feedback_lines.append("Tất cả tiêu chí đều đạt.")

    return {
        "score": scaled,
        "max_score": max_score,
        "earned": earned,
        "possible": possible,
        "items": items,
        "mistake_count": len(mistakes),
        "feedback": "\n".join(feedback_lines),
    }
