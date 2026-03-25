"""Auto-grade engine for quiz submissions (Phase 12)."""
from typing import Any


def grade_answer(question_type: str, choices: list[dict], chosen_ids: list[str]) -> bool:
    """Return True if the chosen answer(s) are correct."""
    correct_ids = {c["id"] for c in choices if c.get("is_correct")}

    if not chosen_ids:
        return False

    if question_type in ("mcq", "truefalse"):
        # Exactly one correct answer; chosen must be that one
        return set(chosen_ids) == correct_ids

    if question_type == "multi":
        # All correct choices must be selected, no incorrect ones
        return set(chosen_ids) == correct_ids

    return False


def calculate_score(questions: list[dict], answers: list[dict]) -> tuple[float, float, list[dict]]:
    """
    questions: [{"id": "...", "type": ..., "choices": [...], "points": 1.0}, ...]
    answers:   [{"question_id": "...", "chosen_ids": [...]}, ...]
    Returns: (earned_score, max_score, graded_answers)
    """
    ans_map = {a["question_id"]: a.get("chosen_ids", []) for a in answers}
    max_score = 0.0
    earned = 0.0
    graded = []

    for q in questions:
        pts = float(q.get("points", 1.0))
        max_score += pts
        chosen = ans_map.get(str(q["id"]), [])
        correct = grade_answer(q["question_type"], q["choices"], chosen)
        if correct:
            earned += pts
        graded.append({
            "question_id": str(q["id"]),
            "chosen_ids": chosen,
            "is_correct": correct,
        })

    return round(earned, 2), round(max_score, 2), graded
