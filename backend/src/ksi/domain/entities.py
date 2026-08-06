"""
Modele ORM encji KSI (SQLAlchemy).

Źródło wymagań: plan produktu — użytkownik, zadanie, test, zgłoszenie, wynik testu.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ksi.db.base import Base
from ksi.domain.enums import (
    SubmissionStatus,
    TaskJudgeMode,
    TestVerdict,
    TestVisibility,
)


class User(Base):
    """
    Użytkownik systemu.

    Rozwiązuje zadania, wysyła zgłoszenia i pojawia się w rankingach.
    Wersja podstawowa: bez ról i bez hasła — identyfikacja po username.
    """

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    submissions: Mapped[list[Submission]] = relationship(back_populates="user")


class Task(Base):
    """
    Zadanie programistyczne (konkursowe).

    Zawiera treść oraz zestaw testów (i opcjonalnie program sprawdzający).
    Sposób oceniania:
    - ``SIMPLE`` — proste testy: porównanie wyjścia programu z expected output;
    - ``CHECKER`` — uruchomienie dodatkowej sprawdzarki (kodu testującego).
    """

    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    judge_mode: Mapped[TaskJudgeMode] = mapped_column(
        SAEnum(TaskJudgeMode, name="task_judge_mode", native_enum=False, length=32),
        nullable=False,
        default=TaskJudgeMode.SIMPLE,
    )
    difficulty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_limit_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=2000)
    memory_limit_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=256)
    checker_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    tests: Mapped[list[TaskTest]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskTest.ordinal",
    )
    submissions: Mapped[list[Submission]] = relationship(back_populates="task")


class TaskTest(Base):
    """
    Pojedynczy przypadek testowy zadania.

    ``public`` — przykłady widoczne w treści; ``hidden`` — tylko do sędziowania.
    """

    __test__ = False

    __tablename__ = "task_tests"
    __table_args__ = (UniqueConstraint("task_id", "ordinal", name="uq_task_tests_task_ordinal"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    visibility: Mapped[TestVisibility] = mapped_column(
        SAEnum(TestVisibility, name="test_visibility", native_enum=False, length=16),
        nullable=False,
    )
    input: Mapped[str] = mapped_column(Text, nullable=False)
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    task: Mapped[Task] = relationship(back_populates="tests")
    results: Mapped[list[TestResult]] = relationship(back_populates="test")


class Submission(Base):
    """
    Zgłoszenie — rozwiązanie użytkownika do konkretnego zadania.

    Kod trafia do kolejki; w tle worker pobiera zgłoszenie, uruchamia testerkę
    (proste porównanie albo sprawdzarkę) i zapisuje wyniki testów.
    """

    __tablename__ = "submissions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[SubmissionStatus] = mapped_column(
        SAEnum(SubmissionStatus, name="submission_status", native_enum=False, length=32),
        nullable=False,
        default=SubmissionStatus.QUEUED,
    )
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    compile_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    judged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="submissions")
    task: Mapped[Task] = relationship(back_populates="submissions")
    test_results: Mapped[list[TestResult]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
        order_by="TestResult.ordinal",
    )


class TestResult(Base):
    """
    Wynik pojedynczego testu dla zgłoszenia.

    Powstaje po sprawdzeniu rozwiązania (porównanie outputu albo werdykt sprawdzarki).
    Jedno zgłoszenie ma zero lub więcej wyników testów.
    """

    __test__ = False

    __tablename__ = "test_results"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    submission_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    test_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("task_tests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    verdict: Mapped[TestVerdict] = mapped_column(
        SAEnum(TestVerdict, name="test_verdict", native_enum=False, length=32),
        nullable=False,
    )
    # Zachowane dla prostych zapytań i kompatybilności; równoważne verdict == passed.
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    points_awarded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_kb: Mapped[int | None] = mapped_column(Integer, nullable=True)

    submission: Mapped[Submission] = relationship(back_populates="test_results")
    test: Mapped[TaskTest] = relationship(back_populates="results")
