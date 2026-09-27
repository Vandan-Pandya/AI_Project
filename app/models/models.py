"""
SQLAlchemy ORM models for PostgreSQL database.
Uses SQLAlchemy 2.0 Uuid and JSON types for cross-database resilience.
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Boolean,
    Float,
    Integer,
    ForeignKey,
    DateTime,
    UniqueConstraint,
    Enum as SQLEnum,
    Uuid,
    JSON,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Resilient JSON type: JSONB on PostgreSQL, standard JSON fallback on other engines
JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class User(Base):
    """
    Core Users table handling authentication credentials and system role.
    """
    __tablename__ = "users"

    user_id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(
        SQLEnum("student", "teacher", "admin", name="user_role_enum"),
        nullable=False,
        default="student"
    )
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    # 1:1 Profile Relationships
    student_profile = relationship("Student", back_populates="user", uselist=False, cascade="all, delete-orphan")
    teacher_profile = relationship("Teacher", back_populates="user", uselist=False, cascade="all, delete-orphan")
    created_exams = relationship("Exam", back_populates="creator", cascade="all, delete-orphan")


class Student(Base):
    """
    Student-specific details linked 1:1 to Users.
    """
    __tablename__ = "students"

    student_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True
    )
    full_name = Column(String(255), nullable=False)
    grade = Column(String(50), nullable=False, default="Grade 10")
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    user = relationship("User", back_populates="student_profile")
    enrollments = relationship("Enrollment", back_populates="student", cascade="all, delete-orphan")
    submissions = relationship("ExamSubmission", back_populates="student", cascade="all, delete-orphan")


class Teacher(Base):
    """
    Teacher-specific details linked 1:1 to Users.
    """
    __tablename__ = "teachers"

    teacher_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True
    )
    full_name = Column(String(255), nullable=False)
    department = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    user = relationship("User", back_populates="teacher_profile")
    classes = relationship("ClassRoom", back_populates="teacher", cascade="all, delete-orphan")


class ClassRoom(Base):
    """
    Classes managed by teachers (e.g., "Class 10A").
    """
    __tablename__ = "classes"

    class_id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    class_name = Column(String(100), nullable=False)
    teacher_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("teachers.teacher_id", ondelete="CASCADE"),
        nullable=False
    )
    academic_year = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    teacher = relationship("Teacher", back_populates="classes")
    enrollments = relationship("Enrollment", back_populates="classroom", cascade="all, delete-orphan")


class Enrollment(Base):
    """
    Linking Students to Classes with unique constraint to prevent duplicate enrollments.
    """
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("class_id", "student_id", name="uq_class_student_enrollment"),
    )

    enrollment_id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    class_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("classes.class_id", ondelete="CASCADE"),
        nullable=False
    )
    student_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("students.student_id", ondelete="CASCADE"),
        nullable=False
    )
    enrolled_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    classroom = relationship("ClassRoom", back_populates="enrollments")
    student = relationship("Student", back_populates="enrollments")


class Subject(Base):
    """
    Curriculum Subjects (e.g., "Mathematics", "Science").
    """
    __tablename__ = "subjects"

    subject_id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    grade = Column(String(50), nullable=False)
    subject_name = Column(String(100), nullable=False)

    exams = relationship("Exam", back_populates="subject_ref", cascade="all, delete-orphan")


class Exam(Base):
    """
    AI-Generated or Teacher-Created Exam Blueprint / Questions.
    """
    __tablename__ = "exams"

    exam_id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    title = Column(String(255), nullable=False)
    subject_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("subjects.subject_id", ondelete="SET NULL"),
        nullable=True
    )
    subject = Column(String(100), nullable=False, default="General")
    grade = Column(String(50), nullable=True, default="Grade 10")
    difficulty = Column(String(50), default="Medium", nullable=False)
    questions_json = Column(JSON_TYPE, nullable=False)
    total_marks = Column(Float, default=100.0, nullable=False)
    created_by = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True
    )
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    subject_ref = relationship("Subject", back_populates="exams")
    creator = relationship("User", back_populates="created_exams")
    submissions = relationship("ExamSubmission", back_populates="exam", cascade="all, delete-orphan")


class ExamSubmission(Base):
    """
    Student Submissions & AI-Assessed Grading with Diagnostic Insights.
    """
    __tablename__ = "exam_submissions"

    submission_id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    exam_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("exams.exam_id", ondelete="CASCADE"),
        nullable=False
    )
    student_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("students.student_id", ondelete="CASCADE"),
        nullable=False
    )
    student_answers_json = Column(JSON_TYPE, nullable=False)
    ai_score = Column(Float, nullable=True)
    max_score = Column(Float, default=100.0, nullable=False)
    ai_insights_json = Column(JSON_TYPE, nullable=True)
    attempt_number = Column(Integer, default=1, nullable=False)
    submitted_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    exam = relationship("Exam", back_populates="submissions")
    student = relationship("Student", back_populates="submissions")
