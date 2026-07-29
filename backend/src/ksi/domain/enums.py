"""Wartości słownikowe dla encji domenowych."""

from enum import StrEnum


class TaskJudgeMode(StrEnum):
    """Sposób oceniania rozwiązania zadania."""

    # Proste testy: porównanie stdout z expected output.
    SIMPLE = "simple"
    # Sprawdzarka: dodatkowy program testujący rozwiązanie.
    CHECKER = "checker"


class SubmissionStatus(StrEnum):
    """Stan zgłoszenia w pipeline oceniania."""

    QUEUED = "queued"
    RUNNING = "running"
    ACCEPTED = "accepted"
    WRONG_ANSWER = "wrong_answer"
    TIME_LIMIT = "time_limit"
    RUNTIME_ERROR = "runtime_error"
    COMPILATION_ERROR = "compilation_error"
    INTERNAL_ERROR = "internal_error"
    MEMORY_LIMIT_EXCEEDED = "memory limit exceeded"
