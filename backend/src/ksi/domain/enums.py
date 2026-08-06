"""Wartości słownikowe dla encji domenowych."""

from enum import StrEnum


class TaskJudgeMode(StrEnum):
    """Sposób oceniania rozwiązania zadania."""

    # Proste testy: porównanie stdout z expected output.
    SIMPLE = "simple"
    # Sprawdzarka: dodatkowy program testujący rozwiązanie.
    CHECKER = "checker"


class TestVisibility(StrEnum):
    """Widoczność przypadku testowego dla użytkownika."""

    __test__ = False

    # Przykłady — pokazywane w treści i w wynikach (input/output).
    PUBLIC = "public"
    # Ukryte — sędziowanie; użytkownik widzi tylko werdykt.
    HIDDEN = "hidden"


class TestVerdict(StrEnum):
    """Werdykt pojedynczego przypadku testowego."""

    __test__ = False

    PASSED = "passed"
    WRONG_ANSWER = "wrong_answer"
    TIME_LIMIT = "time_limit"
    RUNTIME_ERROR = "runtime_error"
    MEMORY_LIMIT = "memory_limit"


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
    MEMORY_LIMIT = "memory_limit"
