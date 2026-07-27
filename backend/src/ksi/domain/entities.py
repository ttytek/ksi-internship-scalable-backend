"""
Opis encji domenowych KSI.

Źródło wymagań: plan produktu — użytkownik, zadanie, zgłoszenie, wynik testu.
To są definicje pojęć (nie modele bazy ani endpointy).
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ksi.domain.enums import SubmissionStatus, TaskJudgeMode, UserRole


@dataclass(slots=True)
class User:
    """
    Użytkownik systemu.

    Może być zwykłym użytkownikiem albo administratorem.
    Użytkownik rozwiązuje zadania, wysyła zgłoszenia i pojawia się w rankingach.
    Administrator zarządza zadaniami (treść, testy / sprawdzarka).
    """

    id: UUID
    username: str
    role: UserRole = UserRole.USER
    created_at: datetime | None = None


@dataclass(slots=True)
class Task:
    """
    Zadanie programistyczne (konkursowe).

    Zawiera treść oraz opcjonalnie zestaw testów albo program sprawdzający.
    Sposób oceniania:
    - ``SIMPLE`` — proste testy: porównanie wyjścia programu z expected output;
    - ``CHECKER`` — uruchomienie dodatkowej sprawdzarki (kodu testującego).
    """

    id: UUID
    title: str
    statement: str
    judge_mode: TaskJudgeMode
    time_limit_ms: int = 2000
    memory_limit_mb: int = 256
    created_at: datetime | None = None


@dataclass(slots=True)
class Submission:
    """
    Zgłoszenie — rozwiązanie użytkownika do konkretnego zadania.

    Kod trafia do kolejki; w tle worker pobiera zgłoszenie, uruchamia testerkę
    (proste porównanie albo sprawdzarkę) i zapisuje wyniki testów.
    """

    id: UUID
    task_id: UUID
    user_id: UUID
    source_code: str
    language: str
    status: SubmissionStatus = SubmissionStatus.QUEUED
    score: int | None = None
    created_at: datetime | None = None
    judged_at: datetime | None = None


@dataclass(slots=True)
class TestResult:
    """
    Wynik pojedynczego testu dla zgłoszenia.

    Powstaje po sprawdzeniu rozwiązania (porównanie outputu albo werdykt sprawdzarki).
    Jedno zgłoszenie ma zero lub więcej wyników testów.
    """

    # Nie jest klasą testów pytest (nazwa zaczyna się od Test*).
    __test__ = False

    id: UUID
    submission_id: UUID
    ordinal: int
    passed: bool
    points_awarded: int = 0
    message: str | None = None
    time_ms: int | None = None
    memory_kb: int | None = None
