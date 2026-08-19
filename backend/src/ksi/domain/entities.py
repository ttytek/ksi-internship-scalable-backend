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
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
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
    pack_revisions: Mapped[list[TaskTestPackRevision]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskTestPackRevision.revision",
    )
    submissions: Mapped[list[Submission]] = relationship(back_populates="task")


class TaskTestPackRevision(Base):
    """Niezmienna rewizja zipa z testami głównymi (obiekt w S3)."""

    __tablename__ = "task_test_pack_revisions"
    __table_args__ = (
        UniqueConstraint("task_id", "revision", name="uq_task_test_pack_revisions_task_revision"),
        Index(
            "uq_pack_rev_current",
            "task_id",
            unique=True,
            sqlite_where=text("is_current"),
            postgresql_where=text("is_current"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    s3_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    etag: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    task: Mapped[Task] = relationship(back_populates="pack_revisions")
    tests: Mapped[list[TaskTest]] = relationship(back_populates="pack_revision")


class TaskTest(Base):
    """
    Pojedynczy przypadek testowy zadania.

    ``public`` — przykłady (I/O w kolumnach, 0 pkt); ``hidden`` — pack S3.
    """

    __test__ = False

    __tablename__ = "task_tests"
    __table_args__ = (
        Index(
            "uq_task_tests_sample_ordinal",
            "task_id",
            "ordinal",
            unique=True,
            sqlite_where=text("pack_revision_id IS NULL"),
            postgresql_where=text("pack_revision_id IS NULL"),
        ),
        Index(
            "uq_task_tests_pack_ordinal",
            "pack_revision_id",
            "ordinal",
            unique=True,
            sqlite_where=text("pack_revision_id IS NOT NULL"),
            postgresql_where=text("pack_revision_id IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    visibility: Mapped[TestVisibility] = mapped_column(
        SAEnum(TestVisibility, name="test_visibility", native_enum=False, length=16),
        nullable=False,
    )
    input: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    pack_revision_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("task_test_pack_revisions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    input_member: Mapped[str | None] = mapped_column(String(512), nullable=True)
    output_member: Mapped[str | None] = mapped_column(String(512), nullable=True)

    task: Mapped[Task] = relationship(back_populates="tests")
    pack_revision: Mapped[TaskTestPackRevision | None] = relationship(back_populates="tests")
    results: Mapped[list[TestResult]] = relationship(back_populates="test")


class Submission(Base):
    """
    Zgłoszenie — rozwiązanie użytkownika do konkretnego zadania.

    Kod trafia do kolejki; worker checkera pobiera zgłoszenie, uruchamia testerkę
    (proste porównanie albo sprawdzarkę) i zapisuje wyniki testów.
    """

    __tablename__ = "submissions"
    __table_args__ = (
        Index(
            "ix_submissions_queued_by_task",
            "task_id",
            "created_at",
            sqlite_where=text("status = 'queued'"),
            postgresql_where=text("status = 'queued'"),
        ),
    )

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
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    judge_claim_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    judge_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    queue_published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

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
    __table_args__ = (
        UniqueConstraint(
            "submission_id",
            "test_id",
            name="uq_test_results_submission_test",
        ),
    )

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
