import random


def role_label(role):
    labels = {
        "admin": "Администратор",
        "employee": "Сотрудник",
        "manager": "Руководитель",
    }
    return labels.get(role, role)


def status_label(score_percent, pass_score):
    if score_percent >= pass_score:
        return "Пройдено"
    return "Не пройдено"


def calculate_score(correct_answers, total_questions):
    if total_questions <= 0:
        return 0.0
    return round((correct_answers / total_questions) * 100, 2)


def count_correct_answers(attempt_answers):
    return sum(1 for answer in attempt_answers if answer.is_correct)


def get_random_questions(questions, question_count):
    questions_list = list(questions)

    if not questions_list:
        return []

    count = min(question_count, len(questions_list))
    return random.sample(questions_list, count)


def can_take_more_attempts(existing_attempts_count, max_attempts):
    return existing_attempts_count < max_attempts


def get_next_attempt_number(last_attempt_number):
    if not last_attempt_number:
        return 1
    return last_attempt_number + 1


def get_user_statistics(attempts):
    total_attempts = len(attempts)
    passed_attempts = sum(1 for attempt in attempts if attempt.status == "Пройдено")
    failed_attempts = sum(1 for attempt in attempts if attempt.status == "Не пройдено")

    average_score = 0.0
    if total_attempts > 0:
        average_score = round(
            sum(attempt.score_percent for attempt in attempts) / total_attempts,
            2
        )

    return {
        "total_attempts": total_attempts,
        "passed_attempts": passed_attempts,
        "failed_attempts": failed_attempts,
        "average_score": average_score,
    }


def get_test_statistics(attempts):
    total_attempts = len(attempts)
    passed_count = sum(1 for attempt in attempts if attempt.status == "Пройдено")
    failed_count = sum(1 for attempt in attempts if attempt.status == "Не пройдено")

    pass_rate = 0.0
    if total_attempts > 0:
        pass_rate = round((passed_count / total_attempts) * 100, 2)

    average_score = 0.0
    if total_attempts > 0:
        average_score = round(
            sum(attempt.score_percent for attempt in attempts) / total_attempts,
            2
        )

    return {
        "total_attempts": total_attempts,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "pass_rate": pass_rate,
        "average_score": average_score,
    }


def is_allowed_file(filename, allowed_extensions=None):
    if not filename:
        return False

    if allowed_extensions is None:
        allowed_extensions = {
            "pdf", "doc", "docx", "txt",
            "png", "jpg", "jpeg", "ppt", "pptx"
        }

    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()
    return extension in allowed_extensions