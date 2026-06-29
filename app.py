import os
import random
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from config import Config
from models import (
    db,
    User,
    Course,
    Material,
    Test,
    Question,
    AnswerOption,
    CourseAssignment,
    Attempt,
    AttemptAnswer,
)
from utils import is_allowed_file


app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)


with app.app_context():
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    db.create_all()


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("Сначала войдите в систему.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapper


def roles_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                flash("Сначала войдите в систему.", "warning")
                return redirect(url_for("login"))

            if user.role not in roles:
                flash("У вас нет доступа к этому разделу.", "danger")
                return redirect(url_for("dashboard"))

            return view_func(*args, **kwargs)

        return wrapper

    return decorator


def save_uploaded_file(file_obj):
    if not file_obj or not file_obj.filename:
        return None

    filename = secure_filename(file_obj.filename)
    if not filename:
        return None

    base, ext = os.path.splitext(filename)
    unique_name = f"{base}_{int(datetime.utcnow().timestamp())}{ext}"
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
    file_obj.save(file_path)
    return unique_name


def get_next_attempt_number(user_id, test_id):
    last_attempt = (
        Attempt.query.filter_by(user_id=user_id, test_id=test_id)
        .order_by(Attempt.attempt_number.desc())
        .first()
    )
    if not last_attempt:
        return 1
    return last_attempt.attempt_number + 1


def can_user_take_test(user, test_obj):
    if user.role == "admin":
        return True

    return can_access_course(user, test_obj.course_id)


def can_access_course(user, course_id):
    if user.role in ("admin", "manager"):
        return True

    assignment = CourseAssignment.query.filter_by(
        user_id=user.id,
        course_id=course_id,
    ).first()
    return assignment is not None


def can_access_material(user, material):
    return can_access_course(user, material.course_id)


def get_random_questions_for_test(test_obj):
    questions = list(test_obj.questions)
    if not questions:
        return []

    count = min(test_obj.question_count, len(questions))
    return random.sample(questions, count)


def build_test_attempt_stats(user_id, tests_list):
    stats = {
        test_obj.id: {
            "used": 0,
            "remaining": test_obj.max_attempts,
            "latest_status": "—",
            "best_score": 0.0,
        }
        for test_obj in tests_list
    }

    attempts = (
        Attempt.query.filter_by(user_id=user_id)
        .order_by(Attempt.finished_at.desc().nullslast(), Attempt.id.desc())
        .all()
    )

    for attempt in attempts:
        entry = stats.get(attempt.test_id)
        if not entry:
            continue

        entry["used"] += 1
        entry["best_score"] = max(entry["best_score"], attempt.score_percent)

        if entry["latest_status"] == "—":
            entry["latest_status"] = attempt.status

    for test_obj in tests_list:
        stats[test_obj.id]["remaining"] = max(test_obj.max_attempts - stats[test_obj.id]["used"], 0)

    return stats


def build_report_summary_rows(attempts):
    summary_map = {}

    for attempt in attempts:
        key = (attempt.user_id, attempt.test_id)
        attempt_date = attempt.finished_at or attempt.started_at
        row = summary_map.get(key)

        if not row:
            summary_map[key] = {
                "user": attempt.user,
                "course": attempt.test.course,
                "test": attempt.test,
                "attempts_count": 1,
                "best_score": attempt.score_percent,
                "latest_status": attempt.status,
                "latest_score": attempt.score_percent,
                "latest_date": attempt_date,
                "latest_attempt_id": attempt.id,
                "passed_ever": attempt.status == "Пройдено",
            }
            continue

        row["attempts_count"] += 1
        row["best_score"] = max(row["best_score"], attempt.score_percent)
        row["passed_ever"] = row["passed_ever"] or attempt.status == "Пройдено"

        if row["latest_date"] is None or (attempt_date and attempt_date >= row["latest_date"]):
            row["latest_status"] = attempt.status
            row["latest_score"] = attempt.score_percent
            row["latest_date"] = attempt_date
            row["latest_attempt_id"] = attempt.id

    return sorted(
        summary_map.values(),
        key=lambda item: item["latest_date"] or datetime.min,
        reverse=True,
    )


@app.route("/")
def index():
    if current_user():
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        login_value = request.form.get("login", "").strip()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(login=login_value).first()

        if user and user.check_password(password):
            session["user_id"] = user.id
            flash("Вход выполнен успешно.", "success")
            return redirect(url_for("dashboard"))

        flash("Неверный логин или пароль.", "danger")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Вы вышли из системы.", "info")
    return redirect(url_for("login"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        password = request.form.get("password", "").strip()

        if not full_name:
            flash("ФИО не может быть пустым.", "danger")
            return render_template("profile.html", user_obj=user)

        user.full_name = full_name

        if password:
            user.set_password(password)

        db.session.commit()
        flash("Профиль обновлён.", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html", user_obj=user)


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()

    if user.role == "admin":
        users_count = User.query.count()
        courses_count = Course.query.count()
        tests_count = Test.query.count()
        attempts_count = Attempt.query.count()

        return render_template(
            "dashboard.html",
            users_count=users_count,
            courses_count=courses_count,
            tests_count=tests_count,
            attempts_count=attempts_count,
        )

    if user.role == "manager":
        results = (
            Attempt.query.join(User)
            .filter(User.role == "employee")
            .order_by(Attempt.finished_at.desc().nullslast())
            .limit(10)
            .all()
        )
        summary_rows = build_report_summary_rows(
            Attempt.query.join(User)
            .filter(User.role == "employee")
            .order_by(Attempt.finished_at.desc().nullslast())
            .all()
        )
        manager_stats = {
            "employees_count": User.query.filter_by(role="employee").count(),
            "courses_count": Course.query.count(),
            "tests_count": Test.query.count(),
            "passed_count": sum(1 for row in summary_rows if row["latest_status"] == "Пройдено"),
            "failed_count": sum(1 for row in summary_rows if row["latest_status"] == "Не пройдено"),
        }
        return render_template(
            "dashboard.html",
            results=results,
            manager_stats=manager_stats,
        )

    assignments = CourseAssignment.query.filter_by(user_id=user.id).all()
    assigned_courses = [assignment.course for assignment in assignments]

    my_attempts = (
        Attempt.query.filter_by(user_id=user.id)
        .order_by(Attempt.finished_at.desc().nullslast())
        .all()
    )

    return render_template(
        "dashboard.html",
        assigned_courses=assigned_courses,
        my_attempts=my_attempts,
    )


@app.route("/users")
@login_required
@roles_required("admin")
def users():
    users_list = User.query.order_by(User.full_name.asc()).all()
    return render_template("users.html", users=users_list)


@app.route("/users/create", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def create_user():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        login_value = request.form.get("login", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "employee").strip()

        if not full_name or not login_value or not password:
            flash("Заполните обязательные поля.", "danger")
            return render_template("user_form.html", user_obj=None)

        existing_user = User.query.filter_by(login=login_value).first()
        if existing_user:
            flash("Пользователь с таким логином уже существует.", "danger")
            return render_template("user_form.html", user_obj=None)

        user = User(
            full_name=full_name,
            login=login_value,
            role=role,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Пользователь успешно создан.", "success")
        return redirect(url_for("users"))

    return render_template("user_form.html", user_obj=None)


@app.route("/users/edit/<int:user_id>", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_user(user_id):
    user_obj = User.query.get_or_404(user_id)

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        login_value = request.form.get("login", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "employee").strip()

        if not full_name or not login_value:
            flash("Заполните обязательные поля.", "danger")
            return render_template("user_form.html", user_obj=user_obj)

        existing_user = User.query.filter_by(login=login_value).first()
        if existing_user and existing_user.id != user_obj.id:
            flash("Пользователь с таким логином уже существует.", "danger")
            return render_template("user_form.html", user_obj=user_obj)

        user_obj.full_name = full_name
        user_obj.login = login_value
        user_obj.role = role

        if password:
            user_obj.set_password(password)

        db.session.commit()
        flash("Данные пользователя обновлены.", "success")
        return redirect(url_for("users"))

    return render_template("user_form.html", user_obj=user_obj)


@app.route("/users/delete/<int:user_id>", methods=["POST"])
@login_required
@roles_required("admin")
def delete_user(user_id):
    user_obj = User.query.get_or_404(user_id)

    if current_user().id == user_obj.id:
        flash("Нельзя удалить текущего пользователя.", "danger")
        return redirect(url_for("users"))

    db.session.delete(user_obj)
    db.session.commit()
    flash("Пользователь удалён.", "success")
    return redirect(url_for("users"))


@app.route("/courses")
@login_required
def courses():
    user = current_user()

    if user.role == "admin":
        courses_list = Course.query.order_by(Course.title.asc()).all()
    elif user.role == "manager":
        courses_list = Course.query.order_by(Course.title.asc()).all()
    else:
        assignments = CourseAssignment.query.filter_by(user_id=user.id).all()
        courses_list = [assignment.course for assignment in assignments]

    return render_template("courses.html", courses=courses_list)


@app.route("/courses/create", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def create_course():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()

        if not title:
            flash("Название курса обязательно.", "danger")
            return render_template("course_form.html", course=None)

        course = Course(title=title, description=description)
        db.session.add(course)
        db.session.commit()

        flash("Курс успешно создан.", "success")
        return redirect(url_for("courses"))

    return render_template("course_form.html", course=None)


@app.route("/courses/edit/<int:course_id>", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_course(course_id):
    course = Course.query.get_or_404(course_id)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()

        if not title:
            flash("Название курса обязательно.", "danger")
            return render_template("course_form.html", course=course)

        course.title = title
        course.description = description
        db.session.commit()

        flash("Курс обновлён.", "success")
        return redirect(url_for("courses"))

    return render_template("course_form.html", course=course)


@app.route("/courses/delete/<int:course_id>", methods=["POST"])
@login_required
@roles_required("admin")
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    db.session.delete(course)
    db.session.commit()

    flash("Курс удалён.", "success")
    return redirect(url_for("courses"))


@app.route("/courses/assign/<int:course_id>", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def assign_course(course_id):
    course = Course.query.get_or_404(course_id)
    employees = User.query.filter_by(role="employee").order_by(User.full_name.asc()).all()
    assigned_user_ids = {
        assignment.user_id
        for assignment in CourseAssignment.query.filter_by(course_id=course.id).all()
    }

    if request.method == "POST":
        selected_user_ids = {
            int(user_id)
            for user_id in request.form.getlist("user_ids")
            if user_id.isdigit()
        }
        existing_assignments = {
            assignment.user_id: assignment
            for assignment in CourseAssignment.query.filter_by(course_id=course.id).all()
        }

        for user_id, assignment in existing_assignments.items():
            if user_id not in selected_user_ids:
                db.session.delete(assignment)

        for user_id in selected_user_ids - set(existing_assignments):
            assignment = CourseAssignment(user_id=user_id, course_id=course.id)
            db.session.add(assignment)

        db.session.commit()
        flash("Назначения курса обновлены.", "success")
        return redirect(url_for("courses"))

    return render_template(
        "course_form.html",
        course=course,
        employees=employees,
        assigned_user_ids=assigned_user_ids,
        assign_mode=True,
    )


@app.route("/materials")
@login_required
def materials():
    user = current_user()
    course_id = request.args.get("course_id", type=int)

    query = Material.query.order_by(Material.created_at.desc())

    if user.role == "employee":
        assigned_course_ids = [
            assignment.course_id
            for assignment in CourseAssignment.query.filter_by(user_id=user.id).all()
        ]
        query = query.filter(Material.course_id.in_(assigned_course_ids if assigned_course_ids else [-1]))

    if course_id:
        query = query.filter_by(course_id=course_id)

    materials_list = query.all()
    return render_template("materials.html", materials=materials_list)


@app.route("/materials/create", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def create_material():
    courses_list = Course.query.order_by(Course.title.asc()).all()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        course_id = request.form.get("course_id", type=int)
        uploaded_file = request.files.get("file")

        if not title or not course_id:
            flash("Заполните обязательные поля.", "danger")
            return render_template("material_form.html", material=None, courses=courses_list)

        if uploaded_file and uploaded_file.filename and not is_allowed_file(uploaded_file.filename):
            flash("Недопустимый тип файла для учебного материала.", "danger")
            return render_template("material_form.html", material=None, courses=courses_list)

        file_name = save_uploaded_file(uploaded_file)

        material = Material(
            title=title,
            content=content,
            file_name=file_name,
            course_id=course_id,
        )
        db.session.add(material)
        db.session.commit()

        flash("Материал успешно добавлен.", "success")
        return redirect(url_for("materials"))

    return render_template("material_form.html", material=None, courses=courses_list)


@app.route("/materials/edit/<int:material_id>", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_material(material_id):
    material = Material.query.get_or_404(material_id)
    courses_list = Course.query.order_by(Course.title.asc()).all()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        course_id = request.form.get("course_id", type=int)
        uploaded_file = request.files.get("file")

        if not title or not course_id:
            flash("Заполните обязательные поля.", "danger")
            return render_template("material_form.html", material=material, courses=courses_list)

        if uploaded_file and uploaded_file.filename and not is_allowed_file(uploaded_file.filename):
            flash("Недопустимый тип файла для учебного материала.", "danger")
            return render_template("material_form.html", material=material, courses=courses_list)

        file_name = save_uploaded_file(uploaded_file)
        if file_name:
            material.file_name = file_name

        material.title = title
        material.content = content
        material.course_id = course_id

        db.session.commit()
        flash("Материал обновлён.", "success")
        return redirect(url_for("materials"))

    return render_template("material_form.html", material=material, courses=courses_list)


@app.route("/materials/<int:material_id>")
@login_required
def material_detail(material_id):
    material = Material.query.get_or_404(material_id)
    user = current_user()

    if not can_access_material(user, material):
        flash("У вас нет доступа к этому материалу.", "danger")
        return redirect(url_for("materials"))

    return render_template("material_view.html", material=material)


@app.route("/materials/delete/<int:material_id>", methods=["POST"])
@login_required
@roles_required("admin")
def delete_material(material_id):
    material = Material.query.get_or_404(material_id)
    db.session.delete(material)
    db.session.commit()

    flash("Материал удалён.", "success")
    return redirect(url_for("materials"))


@app.route("/uploads/materials/<path:filename>")
@login_required
def uploaded_material(filename):
    material = Material.query.filter_by(file_name=filename).first_or_404()

    if not can_access_material(current_user(), material):
        flash("У вас нет доступа к этому файлу.", "danger")
        return redirect(url_for("materials"))

    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/tests")
@login_required
def tests():
    user = current_user()
    course_id = request.args.get("course_id", type=int)
    attempt_stats = {}

    query = Test.query.order_by(Test.title.asc())

    if user.role == "employee":
        assigned_course_ids = [
            assignment.course_id
            for assignment in CourseAssignment.query.filter_by(user_id=user.id).all()
        ]
        query = query.filter(Test.course_id.in_(assigned_course_ids if assigned_course_ids else [-1]))

    if course_id:
        query = query.filter_by(course_id=course_id)

    tests_list = query.all()

    if user.role == "employee":
        attempt_stats = build_test_attempt_stats(user.id, tests_list)

    return render_template("tests.html", tests=tests_list, attempt_stats=attempt_stats)


@app.route("/tests/create", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def create_test():
    courses_list = Course.query.order_by(Course.title.asc()).all()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        course_id = request.form.get("course_id", type=int)
        pass_score = request.form.get("pass_score", type=int) or 70
        question_count = request.form.get("question_count", type=int) or 10
        max_attempts = request.form.get("max_attempts", type=int) or 3

        if not title or not course_id:
            flash("Заполните обязательные поля.", "danger")
            return render_template("test_form.html", test=None, courses=courses_list)

        if pass_score < 1 or pass_score > 100 or question_count < 1 or max_attempts < 1:
            flash("Проверьте корректность параметров теста.", "danger")
            return render_template("test_form.html", test=None, courses=courses_list)

        test_obj = Test(
            title=title,
            description=description,
            course_id=course_id,
            pass_score=pass_score,
            question_count=question_count,
            max_attempts=max_attempts,
        )
        db.session.add(test_obj)
        db.session.commit()

        flash("Тест успешно создан.", "success")
        return redirect(url_for("tests"))

    return render_template("test_form.html", test=None, courses=courses_list)


@app.route("/tests/edit/<int:test_id>", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_test(test_id):
    test_obj = Test.query.get_or_404(test_id)
    courses_list = Course.query.order_by(Course.title.asc()).all()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        course_id = request.form.get("course_id", type=int)
        pass_score = request.form.get("pass_score", type=int) or 70
        question_count = request.form.get("question_count", type=int) or 10
        max_attempts = request.form.get("max_attempts", type=int) or 3
        is_active = bool(request.form.get("is_active"))

        if not title or not course_id:
            flash("Заполните обязательные поля.", "danger")
            return render_template("test_form.html", test=test_obj, courses=courses_list)

        if pass_score < 1 or pass_score > 100 or question_count < 1 or max_attempts < 1:
            flash("Проверьте корректность параметров теста.", "danger")
            return render_template("test_form.html", test=test_obj, courses=courses_list)

        test_obj.title = title
        test_obj.description = description
        test_obj.course_id = course_id
        test_obj.pass_score = pass_score
        test_obj.question_count = question_count
        test_obj.max_attempts = max_attempts
        test_obj.is_active = is_active

        db.session.commit()
        flash("Тест обновлён.", "success")
        return redirect(url_for("tests"))

    return render_template("test_form.html", test=test_obj, courses=courses_list)


@app.route("/tests/delete/<int:test_id>", methods=["POST"])
@login_required
@roles_required("admin")
def delete_test(test_id):
    test_obj = Test.query.get_or_404(test_id)
    db.session.delete(test_obj)
    db.session.commit()

    flash("Тест удалён.", "success")
    return redirect(url_for("tests"))


@app.route("/questions")
@login_required
@roles_required("admin")
def questions():
    test_id = request.args.get("test_id", type=int)
    tests_list = Test.query.order_by(Test.title.asc()).all()

    query = Question.query.order_by(Question.id.desc())
    if test_id:
        query = query.filter_by(test_id=test_id)

    questions_list = query.all()
    return render_template("questions.html", questions=questions_list, tests=tests_list, test_id=test_id)


@app.route("/questions/create", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def create_question():
    tests_list = Test.query.order_by(Test.title.asc()).all()

    if request.method == "POST":
        test_id = request.form.get("test_id", type=int)
        text = request.form.get("text", "").strip()

        options = [
            request.form.get("option_1", "").strip(),
            request.form.get("option_2", "").strip(),
            request.form.get("option_3", "").strip(),
            request.form.get("option_4", "").strip(),
        ]
        correct_index = request.form.get("correct_option", type=int)

        if not test_id or not text:
            flash("Заполните обязательные поля.", "danger")
            return render_template("question_form.html", question=None, tests=tests_list)

        if sum(1 for item in options if item) < 2:
            flash("Нужно указать минимум два варианта ответа.", "danger")
            return render_template("question_form.html", question=None, tests=tests_list)

        if correct_index not in [1, 2, 3, 4]:
            flash("Нужно выбрать правильный вариант ответа.", "danger")
            return render_template("question_form.html", question=None, tests=tests_list)

        if not options[correct_index - 1]:
            flash("Правильный ответ должен ссылаться на заполненный вариант.", "danger")
            return render_template("question_form.html", question=None, tests=tests_list)

        question = Question(test_id=test_id, text=text)
        db.session.add(question)
        db.session.flush()

        for index, option_text in enumerate(options, start=1):
            if option_text:
                option = AnswerOption(
                    question_id=question.id,
                    text=option_text,
                    is_correct=(index == correct_index),
                )
                db.session.add(option)

        db.session.commit()
        flash("Вопрос добавлен.", "success")
        return redirect(url_for("questions", test_id=test_id))

    return render_template("question_form.html", question=None, tests=tests_list)


@app.route("/questions/edit/<int:question_id>", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def edit_question(question_id):
    question = Question.query.get_or_404(question_id)
    tests_list = Test.query.order_by(Test.title.asc()).all()
    options = question.options

    if request.method == "POST":
        test_id = request.form.get("test_id", type=int)
        text = request.form.get("text", "").strip()
        new_options = [
            request.form.get("option_1", "").strip(),
            request.form.get("option_2", "").strip(),
            request.form.get("option_3", "").strip(),
            request.form.get("option_4", "").strip(),
        ]
        correct_index = request.form.get("correct_option", type=int)

        if not test_id or not text:
            flash("Заполните обязательные поля.", "danger")
            return render_template(
                "question_form.html",
                question=question,
                tests=tests_list,
                options=options,
            )

        if sum(1 for item in new_options if item) < 2:
            flash("Нужно указать минимум два варианта ответа.", "danger")
            return render_template(
                "question_form.html",
                question=question,
                tests=tests_list,
                options=options,
            )

        if correct_index not in [1, 2, 3, 4]:
            flash("Нужно выбрать правильный вариант ответа.", "danger")
            return render_template(
                "question_form.html",
                question=question,
                tests=tests_list,
                options=options,
            )

        if not new_options[correct_index - 1]:
            flash("Правильный ответ должен ссылаться на заполненный вариант.", "danger")
            return render_template(
                "question_form.html",
                question=question,
                tests=tests_list,
                options=options,
            )

        question.test_id = test_id
        question.text = text

        for option in list(question.options):
            db.session.delete(option)
        db.session.flush()

        for index, option_text in enumerate(new_options, start=1):
            if option_text:
                option = AnswerOption(
                    question_id=question.id,
                    text=option_text,
                    is_correct=(index == correct_index),
                )
                db.session.add(option)

        db.session.commit()
        flash("Вопрос обновлён.", "success")
        return redirect(url_for("questions", test_id=test_id))

    return render_template(
        "question_form.html",
        question=question,
        tests=tests_list,
        options=options,
    )


@app.route("/questions/delete/<int:question_id>", methods=["POST"])
@login_required
@roles_required("admin")
def delete_question(question_id):
    question = Question.query.get_or_404(question_id)
    test_id = question.test_id

    db.session.delete(question)
    db.session.commit()

    flash("Вопрос удалён.", "success")
    return redirect(url_for("questions", test_id=test_id))


@app.route("/tests/take/<int:test_id>", methods=["GET", "POST"])
@login_required
@roles_required("employee", "admin")
def take_test(test_id):
    test_obj = Test.query.get_or_404(test_id)
    user = current_user()

    if not test_obj.is_active:
        flash("Тест сейчас недоступен.", "warning")
        return redirect(url_for("tests"))

    if not can_user_take_test(user, test_obj):
        flash("Этот тест вам не назначен.", "danger")
        return redirect(url_for("tests"))

    attempts_count = Attempt.query.filter_by(user_id=user.id, test_id=test_obj.id).count()
    if user.role != "admin" and attempts_count >= test_obj.max_attempts:
        flash("Количество попыток исчерпано.", "danger")
        return redirect(url_for("results"))

    if request.method == "GET":
        selected_questions = get_random_questions_for_test(test_obj)

        if not selected_questions:
            flash("Для этого теста пока нет вопросов.", "warning")
            return redirect(url_for("tests"))

        session_questions = [question.id for question in selected_questions]
        session[f"test_{test_obj.id}_questions"] = session_questions

        return render_template(
            "take_test.html",
            test=test_obj,
            questions=selected_questions,
        )

    question_ids = session.get(f"test_{test_obj.id}_questions", [])
    if not question_ids:
        flash("Сессия тестирования истекла. Запустите тест заново.", "warning")
        return redirect(url_for("take_test", test_id=test_obj.id))

    selected_questions = Question.query.filter(Question.id.in_(question_ids)).all()
    selected_questions_map = {question.id: question for question in selected_questions}
    ordered_questions = [selected_questions_map[qid] for qid in question_ids if qid in selected_questions_map]

    attempt = Attempt(
        user_id=user.id,
        test_id=test_obj.id,
        attempt_number=get_next_attempt_number(user.id, test_obj.id),
        total_questions=len(ordered_questions),
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
    )
    db.session.add(attempt)
    db.session.flush()

    correct_answers = 0

    for question in ordered_questions:
        selected_option_id = request.form.get(f"question_{question.id}", type=int)
        selected_option = None
        is_correct = False

        if selected_option_id:
            selected_option = AnswerOption.query.filter_by(
                id=selected_option_id,
                question_id=question.id
            ).first()
            if selected_option and selected_option.is_correct:
                is_correct = True
                correct_answers += 1

        attempt_answer = AttemptAnswer(
            attempt_id=attempt.id,
            question_id=question.id,
            selected_option_id=selected_option.id if selected_option else None,
            is_correct=is_correct,
        )
        db.session.add(attempt_answer)

    score_percent = 0.0
    if attempt.total_questions > 0:
        score_percent = round((correct_answers / attempt.total_questions) * 100, 2)

    attempt.correct_answers = correct_answers
    attempt.score_percent = score_percent
    attempt.status = "Пройдено" if score_percent >= test_obj.pass_score else "Не пройдено"

    db.session.commit()
    session.pop(f"test_{test_obj.id}_questions", None)

    flash("Тест завершён.", "success")
    return redirect(url_for("test_result", attempt_id=attempt.id))


@app.route("/results")
@login_required
def results():
    user = current_user()

    if user.role == "admin":
        attempts = Attempt.query.order_by(Attempt.finished_at.desc().nullslast()).all()
    elif user.role == "manager":
        attempts = Attempt.query.order_by(Attempt.finished_at.desc().nullslast()).all()
    else:
        attempts = (
            Attempt.query.filter_by(user_id=user.id)
            .order_by(Attempt.finished_at.desc().nullslast())
            .all()
        )

    return render_template("results.html", attempts=attempts)


@app.route("/results/<int:attempt_id>")
@login_required
def test_result(attempt_id):
    attempt = Attempt.query.get_or_404(attempt_id)
    user = current_user()

    if user.role == "employee" and attempt.user_id != user.id:
        flash("У вас нет доступа к этому результату.", "danger")
        return redirect(url_for("results"))

    return render_template("test_result.html", attempt=attempt)


@app.route("/reports")
@login_required
@roles_required("admin", "manager")
def reports():
    all_users = User.query.filter_by(role="employee").order_by(User.full_name.asc()).all()
    all_courses = Course.query.order_by(Course.title.asc()).all()
    all_tests = Test.query.order_by(Test.title.asc()).all()

    selected_user_id = request.args.get("user_id", type=int)
    selected_course_id = request.args.get("course_id", type=int)
    selected_test_id = request.args.get("test_id", type=int)

    query = (
        Attempt.query.join(Test)
        .join(User)
        .filter(User.role == "employee")
        .order_by(Attempt.finished_at.desc().nullslast())
    )

    if selected_user_id:
        query = query.filter(Attempt.user_id == selected_user_id)

    if selected_test_id:
        query = query.filter(Attempt.test_id == selected_test_id)

    if selected_course_id:
        query = query.filter(Test.course_id == selected_course_id)

    attempts = query.all()
    summary_rows = build_report_summary_rows(attempts)

    passed_count = sum(1 for item in attempts if item.status == "Пройдено")
    failed_count = sum(1 for item in attempts if item.status == "Не пройдено")
    average_score = round(
        sum(item.score_percent for item in attempts) / len(attempts),
        2
    ) if attempts else 0.0
    latest_passed_count = sum(1 for item in summary_rows if item["latest_status"] == "Пройдено")
    latest_failed_count = sum(1 for item in summary_rows if item["latest_status"] == "Не пройдено")

    return render_template(
        "reports.html",
        attempts=attempts,
        summary_rows=summary_rows,
        users=all_users,
        courses=all_courses,
        tests=all_tests,
        passed_count=passed_count,
        failed_count=failed_count,
        average_score=average_score,
        latest_passed_count=latest_passed_count,
        latest_failed_count=latest_failed_count,
        selected_user_id=selected_user_id,
        selected_course_id=selected_course_id,
        selected_test_id=selected_test_id,
    )


if __name__ == "__main__":
    app.run(debug=True)
