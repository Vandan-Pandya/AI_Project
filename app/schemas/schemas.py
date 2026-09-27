"""
Pydantic Schemas for EduMentor Backend (9 Endpoints with Full Database Tables).
"""

from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# 1. Auth & Profile Schemas
# ---------------------------------------------------------------------------
class UserRegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="Unique email address", example="student@school.edu")
    password: str = Field(..., min_length=6, description="Password (min 6 chars)", example="Password123")
    full_name: str = Field(..., min_length=2, description="User full name", example="Alex Rivera")
    role: Literal["student", "teacher", "admin"] = Field(default="student", description="Role")
    grade: Optional[str] = Field("Grade 10", description="Student Grade Level", example="Grade 10")
    department: Optional[str] = Field(None, description="Teacher Department", example="Science")


class UserLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User email", example="student@school.edu")
    password: str = Field(..., description="User password", example="Password123")


class StudentProfileOut(BaseModel):
    student_id: uuid.UUID
    full_name: str
    grade: str
    created_at: datetime

    class Config:
        from_attributes = True


class TeacherProfileOut(BaseModel):
    teacher_id: uuid.UUID
    full_name: str
    department: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UserOut(BaseModel):
    user_id: uuid.UUID
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime
    student_profile: Optional[StudentProfileOut] = None
    teacher_profile: Optional[TeacherProfileOut] = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------------------------------------------------------------------------
# 2. Chat Schemas
# ---------------------------------------------------------------------------
class HistoryMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., description="Academic question or study topic", example="Explain photosynthesis step by step")
    history: List[HistoryMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str


# ---------------------------------------------------------------------------
# 3. Exam & Evaluation Schemas
# ---------------------------------------------------------------------------
class ExamGenerateRequest(BaseModel):
    subject: str = Field(default="Mathematics", example="Mathematics")
    grade: str = Field(default="Grade 10", example="Grade 10")
    topic: str = Field(..., example="Quadratic Equations")
    difficulty: Literal["Easy", "Medium", "Hard"] = Field(default="Medium")
    question_count: int = Field(default=5, ge=1, le=10, example=5)


class ExamCreate(BaseModel):
    title: str = Field(..., example="Grade 10 Math Quiz: Quadratic Equations")
    subject: str = Field(default="Mathematics", example="Mathematics")
    grade: str = Field(default="Grade 10", example="Grade 10")
    difficulty: str = Field(default="Medium", example="Medium")
    questions_json: List[Dict[str, Any]] = Field(
        ...,
        description="Array of structured question items",
        example=[
            {
                "question_id": 1,
                "type": "mcq",
                "question": "What is the formula for discriminant?",
                "options": ["b^2 - 4ac", "b^2 + 4ac", "2a - 4bc", "4ac - b^2"],
                "correct_answer": "b^2 - 4ac",
                "points": 20
            }
        ]
    )
    total_marks: float = Field(default=100.0, example=100.0)


class ExamOut(BaseModel):
    exam_id: uuid.UUID
    title: str
    subject: str
    grade: Optional[str] = None
    difficulty: str
    questions_json: Any
    total_marks: float
    created_at: datetime

    class Config:
        from_attributes = True


class ExamSubmissionCreate(BaseModel):
    student_answers_json: List[Dict[str, Any]] = Field(
        ...,
        example=[
            {"question_id": 1, "answer": "b^2 - 4ac"}
        ]
    )


class ExamSubmissionOut(BaseModel):
    submission_id: uuid.UUID
    exam_id: uuid.UUID
    student_id: uuid.UUID
    student_answers_json: Any
    ai_score: Optional[float] = None
    max_score: float
    ai_insights_json: Optional[Any] = None
    attempt_number: int
    submitted_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# 4. System Schemas
# ---------------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str
    provider: str
    model: str
    mode: str
