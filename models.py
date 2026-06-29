from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    login = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="employee")

    assignments = db.relationship(
        "CourseAssignment",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    attempts = db.relationship(
        "Attempt",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def set_password(self, raw_password):
        self.password = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        if not self.password:
            return False

        if self.password.startswith(("pbkdf2:", "scrypt:")):
            return check_password_hash(self.password, raw_password)

        return self.password == raw_password

    def __repr__(self):
        return f"<User {self.login}>"


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    materials = db.relationship(
        "Material",
        back_populates="course",
        cascade="all, delete-orphan"
    )
    tests = db.relationship(
        "Test",
        back_populates="course",
        cascade="all, delete-orphan"
    )
    assignments = db.relationship(
        "CourseAssignment",
        back_populates="course",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Course {self.title}>"


class Material(db.Model):
    __tablename__ = "materials"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    file_name = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    course_id = db.Column(
        db.Integer,
        db.ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False
    )

    course = db.relationship("Course", back_populates="materials")

    def __repr__(self):
        return f"<Material {self.title}>"


class Test(db.Model):
    __tablename__ = "tests"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    pass_score = db.Column(db.Integer, nullable=False, default=70)
    question_count = db.Column(db.Integer, nullable=False, default=10)
    max_attempts = db.Column(db.Integer, nullable=False, default=3)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    course_id = db.Column(
        db.Integer,
        db.ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False
    )

    course = db.relationship("Course", back_populates="tests")
    questions = db.relationship(
        "Question",
        back_populates="test",
        cascade="all, delete-orphan",
        order_by="Question.id.asc()"
    )
    attempts = db.relationship(
        "Attempt",
        back_populates="test",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Test {self.title}>"


class Question(db.Model):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)

    test_id = db.Column(
        db.Integer,
        db.ForeignKey("tests.id", ondelete="CASCADE"),
        nullable=False
    )

    test = db.relationship("Test", back_populates="questions")
    options = db.relationship(
        "AnswerOption",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="AnswerOption.id.asc()"
    )
    attempt_answers = db.relationship(
        "AttemptAnswer",
        back_populates="question",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Question {self.id}>"


class AnswerOption(db.Model):
    __tablename__ = "answer_options"

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(300), nullable=False)
    is_correct = db.Column(db.Boolean, default=False, nullable=False)

    question_id = db.Column(
        db.Integer,
        db.ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False
    )

    question = db.relationship("Question", back_populates="options")
    selected_answers = db.relationship(
        "AttemptAnswer",
        back_populates="selected_option"
    )

    def __repr__(self):
        return f"<AnswerOption {self.id}>"


class CourseAssignment(db.Model):
    __tablename__ = "course_assignments"
    __table_args__ = (
        db.UniqueConstraint("user_id", "course_id", name="uq_user_course"),
    )

    id = db.Column(db.Integer, primary_key=True)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    course_id = db.Column(
        db.Integer,
        db.ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False
    )

    user = db.relationship("User", back_populates="assignments")
    course = db.relationship("Course", back_populates="assignments")

    def __repr__(self):
        return f"<CourseAssignment user={self.user_id} course={self.course_id}>"


class Attempt(db.Model):
    __tablename__ = "attempts"

    id = db.Column(db.Integer, primary_key=True)
    attempt_number = db.Column(db.Integer, nullable=False, default=1)
    correct_answers = db.Column(db.Integer, nullable=False, default=0)
    total_questions = db.Column(db.Integer, nullable=False, default=0)
    score_percent = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(30), nullable=False, default="Не пройдено")
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    finished_at = db.Column(db.DateTime)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    test_id = db.Column(
        db.Integer,
        db.ForeignKey("tests.id", ondelete="CASCADE"),
        nullable=False
    )

    user = db.relationship("User", back_populates="attempts")
    test = db.relationship("Test", back_populates="attempts")
    answers = db.relationship(
        "AttemptAnswer",
        back_populates="attempt",
        cascade="all, delete-orphan",
        order_by="AttemptAnswer.id.asc()"
    )

    def __repr__(self):
        return f"<Attempt {self.id}>"


class AttemptAnswer(db.Model):
    __tablename__ = "attempt_answers"

    id = db.Column(db.Integer, primary_key=True)
    is_correct = db.Column(db.Boolean, default=False, nullable=False)

    attempt_id = db.Column(
        db.Integer,
        db.ForeignKey("attempts.id", ondelete="CASCADE"),
        nullable=False
    )
    question_id = db.Column(
        db.Integer,
        db.ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False
    )
    selected_option_id = db.Column(
        db.Integer,
        db.ForeignKey("answer_options.id", ondelete="SET NULL"),
        nullable=True
    )

    attempt = db.relationship("Attempt", back_populates="answers")
    question = db.relationship("Question", back_populates="attempt_answers")
    selected_option = db.relationship("AnswerOption", back_populates="selected_answers")

    def __repr__(self):
        return f"<AttemptAnswer {self.id}>"
