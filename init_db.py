from app import app
from models import db, User, Course, Material, Test, Question, AnswerOption, CourseAssignment


def seed_data():
    if User.query.first():
        print("База уже заполнена.")
        return

    admin = User(
        full_name="Администратор системы",
        login="admin",
        role="admin"
    )
    admin.set_password("admin")

    manager = User(
        full_name="Руководитель отдела",
        login="manager",
        role="manager"
    )
    manager.set_password("manager")

    employee = User(
        full_name="Иванов Иван Иванович",
        login="employee",
        role="employee"
    )
    employee.set_password("employee")

    db.session.add_all([admin, manager, employee])
    db.session.flush()

    course = Course(
        title="Охрана труда",
        description="Базовый курс по требованиям охраны труда для сотрудников организации."
    )
    db.session.add(course)
    db.session.flush()

    material = Material(
        title="Вводный материал по охране труда",
        content=(
            "Охрана труда представляет собой систему сохранения жизни и здоровья работников "
            "в процессе трудовой деятельности. Сотрудник обязан соблюдать требования "
            "инструкций, использовать средства защиты и выполнять внутренние регламенты."
        ),
        file_name=None,
        course_id=course.id
    )
    db.session.add(material)
    db.session.flush()

    test_obj = Test(
        title="Итоговый тест по охране труда",
        description="Проверка базовых знаний по охране труда.",
        pass_score=70,
        question_count=3,
        max_attempts=3,
        is_active=True,
        course_id=course.id
    )
    db.session.add(test_obj)
    db.session.flush()

    question_1 = Question(
        text="Что является основной целью охраны труда?",
        test_id=test_obj.id
    )
    question_2 = Question(
        text="Обязан ли сотрудник соблюдать внутренние инструкции организации?",
        test_id=test_obj.id
    )
    question_3 = Question(
        text="Когда необходимо использовать средства индивидуальной защиты?",
        test_id=test_obj.id
    )

    db.session.add_all([question_1, question_2, question_3])
    db.session.flush()

    options = [
        AnswerOption(
            question_id=question_1.id,
            text="Сохранение жизни и здоровья работников",
            is_correct=True
        ),
        AnswerOption(
            question_id=question_1.id,
            text="Увеличение количества отчетов",
            is_correct=False
        ),
        AnswerOption(
            question_id=question_1.id,
            text="Сокращение рабочего дня",
            is_correct=False
        ),
        AnswerOption(
            question_id=question_2.id,
            text="Да, это обязательно",
            is_correct=True
        ),
        AnswerOption(
            question_id=question_2.id,
            text="Нет, это необязательно",
            is_correct=False
        ),
        AnswerOption(
            question_id=question_2.id,
            text="Только по желанию руководителя",
            is_correct=False
        ),
        AnswerOption(
            question_id=question_3.id,
            text="Только после завершения работы",
            is_correct=False
        ),
        AnswerOption(
            question_id=question_3.id,
            text="Когда это предусмотрено требованиями безопасности",
            is_correct=True
        ),
        AnswerOption(
            question_id=question_3.id,
            text="Только в конце месяца",
            is_correct=False
        ),
    ]
    db.session.add_all(options)

    assignment = CourseAssignment(
        user_id=employee.id,
        course_id=course.id
    )
    db.session.add(assignment)

    db.session.commit()
    print("База данных успешно создана и заполнена тестовыми данными.")


if __name__ == "__main__":
    with app.app_context():
        db.drop_all()
        db.create_all()
        seed_data()
