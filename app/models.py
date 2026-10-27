from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Float, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nomor_induk: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    nama_lengkap: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(120), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(25), index=True)
    kelas: Mapped[str | None] = mapped_column(String(20), nullable=True)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)

class Course(Base):
    __tablename__ = 'courses'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kode: Mapped[str] = mapped_column(String(20), unique=True)
    nama: Mapped[str] = mapped_column(String(150))
    semester: Mapped[int] = mapped_column(Integer, default=1)
    sks: Mapped[int] = mapped_column(Integer, default=2)

class ExamPacket(Base):
    __tablename__ = 'exam_packets'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey('courses.id'))
    title: Mapped[str] = mapped_column(String(180))
    room_token: Mapped[str] = mapped_column(String(12), index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    penalty_threshold: Mapped[int] = mapped_column(Integer, default=100)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))

class Question(Base):
    __tablename__ = 'question_banks'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    packet_id: Mapped[int] = mapped_column(ForeignKey('exam_packets.id', ondelete='CASCADE'), index=True)
    kind: Mapped[str] = mapped_column(String(15)) # mcq / essay
    prompt: Mapped[str] = mapped_column(Text)
    options: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    correct_option: Mapped[str | None] = mapped_column(String(1), nullable=True)
    reference_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list | None] = mapped_column(JSON, nullable=True)
    max_score: Mapped[float] = mapped_column(Float, default=1.0)

class ExamSession(Base):
    __tablename__ = 'exam_sessions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    packet_id: Mapped[int] = mapped_column(ForeignKey('exam_packets.id'))
    student_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    question_order: Mapped[list] = mapped_column(JSON)
    option_orders: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='active')
    penalty_points: Mapped[int] = mapped_column(Integer, default=0)
    integrity_index: Mapped[int] = mapped_column(Integer, default=100)
    total_score: Mapped[float | None] = mapped_column(Float, nullable=True)

class StudentAnswer(Base):
    __tablename__ = 'student_answers'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('exam_sessions.id', ondelete='CASCADE'), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey('question_banks.id'))
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)

class ViolationRule(Base):
    __tablename__ = 'violation_rules'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    label: Mapped[str] = mapped_column(String(100))
    points: Mapped[int] = mapped_column(Integer)

class ProctoringLog(Base):
    __tablename__ = 'proctoring_logs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('exam_sessions.id', ondelete='CASCADE'), index=True)
    code: Mapped[str] = mapped_column(String(20))
    points: Mapped[int] = mapped_column(Integer)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
