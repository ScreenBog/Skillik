"""Начальные данные: админ, темы, достижения, магазин."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.achievement import Achievement
from app.models.shop import ShopItem
from app.models.topic import Topic
from app.models.user import User, UserRole
from app.security import hash_password


def seed_if_empty(db: Session) -> None:
    """Заполнить справочники и создать админа, если БД пустая."""
    if db.query(User).filter(User.role == UserRole.ADMIN).first():
        return

    admin = User(
        username="admin",
        email="admin@skillik.local",
        password_hash=hash_password("admin123"),
        full_name="Репетитор Skillik",
        role=UserRole.ADMIN,
        level_key="legend",
        xp=0,
    )
    db.add(admin)

    # Демо-ученик
    student = User(
        username="ivan",
        email="ivan@skillik.local",
        password_hash=hash_password("ivan123"),
        full_name="Иван Петров",
        role=UserRole.STUDENT,
        xp=50,
        level_key="novice",
    )
    db.add(student)

    # Демо-родитель
    parent = User(
        username="parent_ivan",
        email="parent@skillik.local",
        password_hash=hash_password("parent123"),
        full_name="Мария Петрова",
        role=UserRole.PARENT,
    )
    db.add(parent)
    db.flush()

    from app.models.user import ParentStudent

    db.add(ParentStudent(parent_id=parent.id, student_id=student.id))

    # Темы — математика
    math_root = Topic(
        title="Математика",
        slug="math",
        subject="math",
        description="Основные разделы математики 5–7 класс",
        icon="calculator",
        order_index=0,
    )
    db.add(math_root)
    db.flush()

    math_topics = [
        ("Дроби", "fractions", "Обыкновенные и десятичные дроби", 1),
        ("Проценты", "percents", "Проценты и пропорции", 2),
        ("Уравнения", "equations", "Линейные уравнения", 3),
        ("Геометрия", "geometry", "Углы, треугольники, площади", 4),
        ("Отрицательные числа", "negatives", "Целые числа и операции", 5),
    ]
    for title, slug, desc, order in math_topics:
        db.add(
            Topic(
                title=title,
                slug=slug,
                description=desc,
                subject="math",
                parent_id=math_root.id,
                order_index=order,
                icon="puzzle",
            )
        )

    # Информатика
    inf_root = Topic(
        title="Информатика",
        slug="informatics",
        subject="informatics",
        description="Основы информатики 5–7 класс",
        icon="cpu",
        order_index=1,
    )
    db.add(inf_root)
    db.flush()

    for title, slug, desc, order in [
        ("Алгоритмы", "algorithms", "Блок-схемы и шаги решения", 1),
        ("Python старт", "python-start", "Первые программы на Python", 2),
        ("Логика", "logic", "Истина, ложь, условия", 3),
        ("Таблицы и данные", "tables", "Таблицы, сортировка, поиск", 4),
    ]:
        db.add(
            Topic(
                title=title,
                slug=slug,
                description=desc,
                subject="informatics",
                parent_id=inf_root.id,
                order_index=order,
                icon="code",
            )
        )

    # Достижения
    achievements = [
        ("first_steps", "Первые шаги", "Войти в платформу", "sparkles", 10, "first_login", 1),
        ("streak_3", "Три дня подряд", "Стрик 3 дня", "flame", 15, "streak", 3),
        ("streak_7", "Неделя силы", "Стрик 7 дней", "fire", 40, "streak", 7),
        ("hw_5", "Пятёрка заданий", "Сдать 5 ДЗ", "check-badge", 25, "homework_count", 5),
        ("hw_10", "Десятка", "Сдать 10 ДЗ", "trophy", 50, "homework_count", 10),
        ("xp_100", "Сотня XP", "Набрать 100 XP", "star", 0, "xp", 100),
        ("level_student", "Настоящий ученик", "Достичь уровня «Ученик»", "academic-cap", 20, "level_key", 1),
    ]
    for code, title, desc, icon, xp, ctype, cval in achievements:
        db.add(
            Achievement(
                code=code,
                title=title,
                description=desc,
                icon=icon,
                xp_bonus=xp,
                condition_type=ctype,
                condition_value=cval,
            )
        )

    # Магазин
    shop = [
        ("avatar_fox", "Аватар: Лиса", "Милая лиса", "avatar", 80, "fox", "user"),
        ("avatar_owl", "Аватар: Сова", "Мудрая сова", "avatar", 80, "owl", "user"),
        ("avatar_robot", "Аватар: Робот", "Техно-робот", "avatar", 100, "robot", "cpu"),
        ("frame_gold", "Рамка: Золото", "Золотая рамка аватара", "frame", 120, "gold", "sparkles"),
        ("frame_teal", "Рамка: Бирюза", "Бирюзовая рамка", "frame", 90, "teal", "sparkles"),
        ("sticker_star", "Стикер: Звезда", "Декор профиля", "sticker", 40, "star", "star"),
        ("defer_hw", "Отсрочка ДЗ +1 день", "Одноразовая отсрочка дедлайна", "defer_hw", 150, "defer_1d", "clock"),
        ("accent_coral", "Акцент: Коралл", "Сменить акцентный цвет", "accent_color", 100, "#e07a5f", "swatch"),
        ("accent_violet", "Акцент: Фиолет", "Сменить акцентный цвет", "accent_color", 100, "#7c3aed", "swatch"),
    ]
    for i, (code, title, desc, itype, price, value, icon) in enumerate(shop):
        db.add(
            ShopItem(
                code=code,
                title=title,
                description=desc,
                item_type=itype,
                price_xp=price,
                value=value,
                icon=icon,
                sort_order=i,
            )
        )

    db.commit()
