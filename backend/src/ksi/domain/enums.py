"""Wartości słownikowe dla encji domenowych."""

from enum import StrEnum


class UserRole(StrEnum):
    """Rola użytkownika w systemie."""

    USER = "user"
    ADMIN = "admin"


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
    DONE = "done"
    ERROR = "error"
