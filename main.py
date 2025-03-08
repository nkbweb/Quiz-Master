from flask import Flask, render_template, redirect, url_for, flash, request, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
from datetime import datetime
import os
from models import db, User, Subject, Chapter, Quiz, Question, Option, QuizAttempt, QuizResponse
from forms import LoginForm, RegistrationForm, SubjectForm, ChapterForm, QuizForm, QuestionForm, OptionForm

app = Flask(__name__)
app.config['APP_NAME'] = 'Quiz Master V1 by Nishchay Kumar Bhardwaj'
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://nkbdata_user:FnQsBhzhV6OH9L71A6ai2uhAAJYhWBIr@dpg-cv3f228gph6c738qcheg-a.oregon-postgres.render.com/nkbdata'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

# Initialize Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You need admin privileges to access this page.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Create database tables and initial data
with app.app_context():
    # Create all tables in PostgreSQL
    try:
        db.create_all()
        print("Database tables created successfully!")
    except Exception as e:
        print(f"Error creating database tables: {str(e)}")
    
    # Create admin user if not exists
    admin = User.query.filter_by(email='admin@example.com').first()
    if not admin:
        admin = User(name='Admin', email='admin@example.com', is_admin=True)
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
    
    # Auto-generate demo data if no subjects exist
    if Subject.query.count() == 0:
        from utils import create_demo_data
        try:
            create_demo_data()
            print("Demo data generated automatically!")
        except Exception as e:
            print(f"Error generating demo data: {str(e)}")

# Routes
@app.route('/')
def index():
    return render_template('index.html')

# Auth routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        flash('Invalid email or password', 'danger')
    return render_template('auth/login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(name=form.name.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! You can now login.', 'success')
        return redirect(url_for('login'))
    return render_template('auth/register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('user_dashboard'))

# User routes
@app.route('/user/dashboard')
@login_required
def user_dashboard():
    recent_attempts = QuizAttempt.query.filter_by(user_id=current_user.id).order_by(QuizAttempt.date_taken.desc()).limit(5).all()
    available_quizzes = Quiz.query.all()
    return render_template('user/dashboard.html', recent_attempts=recent_attempts, available_quizzes=available_quizzes)

@app.route('/user/quizzes')
@login_required
def quiz_list():
    subjects = Subject.query.all()
    return render_template('user/quiz_list.html', subjects=subjects)

@app.route('/user/quiz/<int:quiz_id>')
@login_required
def take_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    
    # Check if user has already completed this quiz
    previous_attempt = QuizAttempt.query.filter_by(
        user_id=current_user.id,
        quiz_id=quiz_id,
        is_completed=True
    ).first()
    
    if previous_attempt:
        flash('You have already completed this quiz. You cannot retake it.', 'warning')
        return redirect(url_for('quiz_results', attempt_id=previous_attempt.id))
    
    # Check if quiz has questions
    if not quiz.questions:
        flash('This quiz has no questions yet.', 'warning')
        return redirect(url_for('quiz_list'))
    
    # Check if there's an incomplete attempt
    incomplete_attempt = QuizAttempt.query.filter_by(
        user_id=current_user.id,
        quiz_id=quiz_id,
        is_completed=False
    ).first()
    
    if incomplete_attempt:
        # Convert incomplete attempt to completed with current responses
        incomplete_attempt.is_completed = True
        incomplete_attempt.score = 0  # Default score for abandoned attempts
        db.session.commit()
        flash('You previously left an attempt incomplete. It has been recorded as a submission.', 'warning')
    
    # Show the quiz info page with "Start Quiz" button
    return render_template('user/take_quiz.html', quiz=quiz)

@app.route('/user/quiz/<int:quiz_id>/start')
@login_required
def start_quiz_attempt(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    
    # Check if user has already completed this quiz
    previous_attempt = QuizAttempt.query.filter_by(
        user_id=current_user.id,
        quiz_id=quiz_id,
        is_completed=True
    ).first()
    
    if previous_attempt:
        flash('You have already completed this quiz. You cannot retake it.', 'warning')
        return redirect(url_for('quiz_results', attempt_id=previous_attempt.id))
    
    # Check for and remove any incomplete attempts
    incomplete_attempts = QuizAttempt.query.filter_by(
        user_id=current_user.id,
        quiz_id=quiz_id,
        is_completed=False
    ).all()
    
    for old_attempt in incomplete_attempts:
        db.session.delete(old_attempt)
    
    db.session.commit()
    
    # Create a new quiz attempt
    attempt = QuizAttempt(
        user_id=current_user.id,
        quiz_id=quiz_id,
        date_taken=datetime.now(),
        is_completed=False
    )
    db.session.add(attempt)
    db.session.commit()
    
    session['current_attempt_id'] = attempt.id
    session['time_remaining'] = quiz.time_limit * 60 if quiz.time_limit else None
    
    return render_template('user/attempt_quiz.html', quiz=quiz, attempt=attempt)

@app.route('/user/quiz/<int:quiz_id>/submit', methods=['POST'])
@login_required
def submit_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    attempt_id = session.get('current_attempt_id')
    
    if not attempt_id:
        flash('Invalid quiz attempt.', 'danger')
        return redirect(url_for('quiz_list'))
    
    attempt = QuizAttempt.query.get(attempt_id)
    
    # Calculate score
    total_questions = len(quiz.questions)
    correct_answers = 0
    
    for question in quiz.questions:
        selected_option_id = request.form.get(f'question_{question.id}')
        if selected_option_id:
            selected_option = Option.query.get(int(selected_option_id))
            response = QuizResponse(
                attempt_id=attempt_id,
                question_id=question.id,
                option_id=selected_option.id
            )
            db.session.add(response)
            if selected_option.is_correct:
                correct_answers += 1
    
    # Update attempt
    score_percentage = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
    attempt.score = score_percentage
    attempt.is_completed = True
    db.session.commit()
    
    # Clear session data
    session.pop('current_attempt_id', None)
    session.pop('time_remaining', None)
    
    flash(f'Quiz submitted! Your score: {score_percentage:.1f}%', 'success')
    return redirect(url_for('quiz_results', attempt_id=attempt_id))

@app.route('/user/results/<int:attempt_id>')
@login_required
def quiz_results(attempt_id):
    attempt = QuizAttempt.query.get_or_404(attempt_id)
    
    # Ensure the user can only see their own results
    if attempt.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to view these results.', 'danger')
        return redirect(url_for('user_dashboard'))
    
    return render_template('user/results.html', attempt=attempt)

@app.route('/user/history')
@login_required
def quiz_history():
    attempts = QuizAttempt.query.filter_by(user_id=current_user.id).order_by(QuizAttempt.date_taken.desc()).all()
    return render_template('user/history.html', attempts=attempts)

# Admin routes
@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    users_count = User.query.count()
    quizzes_count = Quiz.query.count()
    subjects_count = Subject.query.count()
    attempts_count = QuizAttempt.query.count()
    
    return render_template('admin/dashboard.html', 
                          users_count=users_count, 
                          quizzes_count=quizzes_count,
                          subjects_count=subjects_count,
                          attempts_count=attempts_count)

# Admin - User Management
@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/toggle/<int:user_id>')
@login_required
@admin_required
def toggle_admin(user_id):
    user = User.query.get_or_404(user_id)
    if user.id != current_user.id:  # Prevent admin from removing their own admin status
        user.is_admin = not user.is_admin
        db.session.commit()
        flash(f"Admin status for {user.name} has been {'granted' if user.is_admin else 'revoked'}.", 'success')
    else:
        flash("You cannot change your own admin status.", 'danger')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id != current_user.id:  # Prevent admin from deleting themselves
        db.session.delete(user)
        db.session.commit()
        flash(f"User {user.name} has been deleted.", 'success')
    else:
        flash("You cannot delete your own account while logged in.", 'danger')
    return redirect(url_for('admin_users'))

# Admin - Subject Management
@app.route('/admin/subjects')
@login_required
@admin_required
def admin_subjects():
    subjects = Subject.query.all()
    return render_template('admin/subjects.html', subjects=subjects)

@app.route('/admin/subjects/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_subject():
    form = SubjectForm()
    if form.validate_on_submit():
        subject = Subject(name=form.name.data, description=form.description.data)
        db.session.add(subject)
        db.session.commit()
        flash('Subject added successfully!', 'success')
        return redirect(url_for('admin_subjects'))
    return render_template('admin/subject_form.html', form=form, title='Add Subject')

@app.route('/admin/subjects/edit/<int:subject_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    form = SubjectForm(obj=subject)
    if form.validate_on_submit():
        subject.name = form.name.data
        subject.description = form.description.data
        db.session.commit()
        flash('Subject updated successfully!', 'success')
        return redirect(url_for('admin_subjects'))
    return render_template('admin/subject_form.html', form=form, title='Edit Subject')

@app.route('/admin/subjects/delete/<int:subject_id>', methods=['POST'])
@login_required
@admin_required
def delete_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    db.session.delete(subject)
    db.session.commit()
    flash('Subject deleted successfully!', 'success')
    return redirect(url_for('admin_subjects'))

# Admin - Chapter Management
@app.route('/admin/chapters')
@login_required
@admin_required
def admin_chapters():
    chapters = Chapter.query.all()
    return render_template('admin/chapters.html', chapters=chapters)

@app.route('/admin/chapters/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_chapter():
    form = ChapterForm()
    form.subject_id.choices = [(s.id, s.name) for s in Subject.query.all()]
    if form.validate_on_submit():
        chapter = Chapter(
            name=form.name.data,
            description=form.description.data,
            subject_id=form.subject_id.data
        )
        db.session.add(chapter)
        db.session.commit()
        flash('Chapter added successfully!', 'success')
        return redirect(url_for('admin_chapters'))
    return render_template('admin/chapter_form.html', form=form, title='Add Chapter')

@app.route('/admin/chapters/edit/<int:chapter_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_chapter(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    form = ChapterForm(obj=chapter)
    form.subject_id.choices = [(s.id, s.name) for s in Subject.query.all()]
    if form.validate_on_submit():
        chapter.name = form.name.data
        chapter.description = form.description.data
        chapter.subject_id = form.subject_id.data
        db.session.commit()
        flash('Chapter updated successfully!', 'success')
        return redirect(url_for('admin_chapters'))
    return render_template('admin/chapter_form.html', form=form, title='Edit Chapter')

@app.route('/admin/chapters/delete/<int:chapter_id>', methods=['POST'])
@login_required
@admin_required
def delete_chapter(chapter_id):
    chapter = Chapter.query.get_or_404(chapter_id)
    db.session.delete(chapter)
    db.session.commit()
    flash('Chapter deleted successfully!', 'success')
    return redirect(url_for('admin_chapters'))

# Admin - Quiz Management
@app.route('/admin/quizzes')
@login_required
@admin_required
def admin_quizzes():
    quizzes = Quiz.query.all()
    return render_template('admin/quizzes.html', quizzes=quizzes)

@app.route('/admin/quizzes/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_quiz():
    form = QuizForm()
    form.chapter_id.choices = [(c.id, f"{c.name} ({c.subject.name})") for c in Chapter.query.all()]
    if form.validate_on_submit():
        quiz = Quiz(
            title=form.title.data,
            description=form.description.data,
            chapter_id=form.chapter_id.data,
            time_limit=form.time_limit.data,
            pass_percentage=form.pass_percentage.data
        )
        db.session.add(quiz)
        db.session.commit()
        flash('Quiz added successfully!', 'success')
        return redirect(url_for('admin_quizzes'))
    return render_template('admin/quiz_form.html', form=form, title='Add Quiz')

@app.route('/admin/quizzes/edit/<int:quiz_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    form = QuizForm(obj=quiz)
    form.chapter_id.choices = [(c.id, f"{c.name} ({c.subject.name})") for c in Chapter.query.all()]
    if form.validate_on_submit():
        quiz.title = form.title.data
        quiz.description = form.description.data
        quiz.chapter_id = form.chapter_id.data
        quiz.time_limit = form.time_limit.data
        quiz.pass_percentage = form.pass_percentage.data
        db.session.commit()
        flash('Quiz updated successfully!', 'success')
        return redirect(url_for('admin_quizzes'))
    return render_template('admin/quiz_form.html', form=form, title='Edit Quiz')

@app.route('/admin/quizzes/delete/<int:quiz_id>', methods=['POST'])
@login_required
@admin_required
def delete_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    db.session.delete(quiz)
    db.session.commit()
    flash('Quiz deleted successfully!', 'success')
    return redirect(url_for('admin_quizzes'))

# Admin - Question Management
@app.route('/admin/quizzes/<int:quiz_id>/questions')
@login_required
@admin_required
def admin_questions(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    return render_template('admin/questions.html', quiz=quiz)

@app.route('/admin/quizzes/<int:quiz_id>/questions/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_question(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    form = QuestionForm()
    if form.validate_on_submit():
        question = Question(
            quiz_id=quiz_id,
            text=form.text.data,
            points=form.points.data
        )
        db.session.add(question)
        db.session.commit()
        flash('Question added successfully! Now add options for this question.', 'success')
        return redirect(url_for('add_options', question_id=question.id))
    return render_template('admin/question_form.html', form=form, quiz=quiz, title='Add Question')

@app.route('/admin/questions/<int:question_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_question(question_id):
    question = Question.query.get_or_404(question_id)
    form = QuestionForm(obj=question)
    if form.validate_on_submit():
        question.text = form.text.data
        question.points = form.points.data
        db.session.commit()
        flash('Question updated successfully!', 'success')
        return redirect(url_for('admin_questions', quiz_id=question.quiz_id))
    return render_template('admin/question_form.html', form=form, quiz=question.quiz, title='Edit Question')

@app.route('/admin/questions/<int:question_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_question(question_id):
    question = Question.query.get_or_404(question_id)
    quiz_id = question.quiz_id
    db.session.delete(question)
    db.session.commit()
    flash('Question deleted successfully!', 'success')
    return redirect(url_for('admin_questions', quiz_id=quiz_id))

# Admin - Option Management
@app.route('/admin/questions/<int:question_id>/options')
@login_required
@admin_required
def admin_options(question_id):
    question = Question.query.get_or_404(question_id)
    return render_template('admin/options.html', question=question)

@app.route('/admin/questions/<int:question_id>/options/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_options(question_id):
    question = Question.query.get_or_404(question_id)
    form = OptionForm()
    if form.validate_on_submit():
        option = Option(
            question_id=question_id,
            text=form.text.data,
            is_correct=form.is_correct.data
        )
        db.session.add(option)
        db.session.commit()
        flash('Option added successfully!', 'success')
        return redirect(url_for('admin_options', question_id=question_id))
    return render_template('admin/option_form.html', form=form, question=question, title='Add Option')

@app.route('/admin/options/<int:option_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_option(option_id):
    option = Option.query.get_or_404(option_id)
    form = OptionForm(obj=option)
    if form.validate_on_submit():
        option.text = form.text.data
        option.is_correct = form.is_correct.data
        db.session.commit()
        flash('Option updated successfully!', 'success')
        return redirect(url_for('admin_options', question_id=option.question_id))
    return render_template('admin/option_form.html', form=form, question=option.question, title='Edit Option')

@app.route('/admin/options/<int:option_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_option(option_id):
    option = Option.query.get_or_404(option_id)
    question_id = option.question_id
    db.session.delete(option)
    db.session.commit()
    flash('Option deleted successfully!', 'success')
    return redirect(url_for('admin_options', question_id=question_id))

@app.route('/admin/attempts')
@login_required
def admin_attempts():
    if not current_user.is_admin:
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('index'))
    
    # Get filter parameters
    subject_id = request.args.get('subject_id', type=int)
    chapter_id = request.args.get('chapter_id', type=int)
    quiz_id = request.args.get('quiz_id', type=int)
    user_id = request.args.get('user_id', type=int)
    status = request.args.get('status')
    
    # Base query
    attempts_query = db.session.query(
        QuizAttempt, Quiz, Subject, Chapter, User
    ).join(
        Quiz, QuizAttempt.quiz_id == Quiz.id
    ).join(
        Chapter, Quiz.chapter_id == Chapter.id
    ).join(
        Subject, Chapter.subject_id == Subject.id
    ).join(
        User, QuizAttempt.user_id == User.id
    ).order_by(QuizAttempt.date_taken.desc())
    
    # Apply filters
    if subject_id:
        attempts_query = attempts_query.filter(Subject.id == subject_id)
    if chapter_id:
        attempts_query = attempts_query.filter(Chapter.id == chapter_id)
    if quiz_id:
        attempts_query = attempts_query.filter(Quiz.id == quiz_id)
    if user_id:
        attempts_query = attempts_query.filter(User.id == user_id)
    if status:
        if status == 'pass':
            attempts_query = attempts_query.filter(
                QuizAttempt.score >= Quiz.pass_score
            )
        elif status == 'fail':
            attempts_query = attempts_query.filter(
                QuizAttempt.score < Quiz.pass_score
            )
    
    attempts = attempts_query.all()
    
    # Calculate pass/fail status for each attempt
    attempt_results = []
    for attempt, quiz, subject, chapter, user in attempts:
        total_questions = len(quiz.questions)
        # Use the attempt.score directly as it's already a percentage
        passed = attempt.score >= quiz.pass_percentage if attempt.score is not None else False
        attempt_results.append({
            'attempt': attempt,
            'quiz': quiz,
            'subject': subject,
            'chapter': chapter,
            'user': user,
            'percentage': attempt.score if attempt.score is not None else 0,
            'passed': passed
        })
    
    # Get filter options
    subjects = Subject.query.order_by(Subject.name).all()
    chapters = Chapter.query.order_by(Chapter.name).all()
    quizzes = Quiz.query.order_by(Quiz.title).all()
    users = User.query.order_by(User.name).all()
    
    return render_template(
        'admin/attempts.html',
        attempt_results=attempt_results,
        subjects=subjects,
        chapters=chapters,
        quizzes=quizzes,
        users=users,
        subject_id=subject_id,
        chapter_id=chapter_id,
        quiz_id=quiz_id,
        user_id=user_id,
        status=status
    )

@app.route('/result/<int:attempt_id>')
@login_required
def view_result(attempt_id):
    attempt = QuizAttempt.query.get_or_404(attempt_id)
    
    # Check if the user is the owner of the attempt or an admin
    if attempt.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to view this result.', 'danger')
        return redirect(url_for('index'))
    
    quiz = Quiz.query.get(attempt.quiz_id)
    user = User.query.get(attempt.user_id)
    
    # Get the detailed responses (assuming you have a model for this)
    responses = QuizResponse.query.filter_by(attempt_id=attempt.id).all()
    
    return render_template(
        'result.html',
        attempt=attempt,
        quiz=quiz,
        user=user,
        responses=responses
    )

# Demo data is now generated automatically when the database is empty

if __name__ == '__main__':
    app.run(debug=True)
