from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    date_registered = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Explicit relationship with foreign key reference
    quiz_attempts = db.relationship('QuizAttempt', backref='user', lazy=True,
                                   foreign_keys='QuizAttempt.user_id')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    
class Subject(db.Model):
    __tablename__ = 'subjects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    chapters = db.relationship('Chapter', backref='subject', lazy=True, 
                              cascade="all, delete-orphan",
                              foreign_keys='Chapter.subject_id')

class Chapter(db.Model):
    __tablename__ = 'chapters'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    
    quizzes = db.relationship('Quiz', backref='chapter', lazy=True, 
                             cascade="all, delete-orphan",
                             foreign_keys='Quiz.chapter_id')

class Quiz(db.Model):
    __tablename__ = 'quizzes'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=False)
    time_limit = db.Column(db.Integer)
    pass_percentage = db.Column(db.Float, default=50.0)
    
    questions = db.relationship('Question', backref='quiz', lazy=True, 
                               cascade="all, delete-orphan",
                               foreign_keys='Question.quiz_id')
    attempts = db.relationship('QuizAttempt', backref='quiz', lazy=True, 
                              cascade="all, delete-orphan",
                              foreign_keys='QuizAttempt.quiz_id')

class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    points = db.Column(db.Integer, default=1)
    
    options = db.relationship('Option', backref='question', lazy=True, 
                             cascade="all, delete-orphan",
                             foreign_keys='Option.question_id')
    responses = db.relationship('QuizResponse', backref='question', lazy=True,
                               foreign_keys='QuizResponse.question_id')

class Option(db.Model):
    __tablename__ = 'options'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    
    responses = db.relationship('QuizResponse', backref='selected_option', lazy=True,
                               foreign_keys='QuizResponse.option_id')

class QuizAttempt(db.Model):
    __tablename__ = 'quiz_attempts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    date_taken = db.Column(db.DateTime, default=datetime.utcnow)
    score = db.Column(db.Float)
    is_completed = db.Column(db.Boolean, default=False)
    
    responses = db.relationship('QuizResponse', backref='attempt', lazy=True, 
                               cascade="all, delete-orphan",
                               foreign_keys='QuizResponse.attempt_id')
    
    @property
    def passed(self):
        if self.score is None:
            return False
        return self.score >= self.quiz.pass_percentage

class QuizResponse(db.Model):
    __tablename__ = 'quiz_responses'
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey('options.id'), nullable=False)
