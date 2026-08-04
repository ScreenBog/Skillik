"""Модели базы данных Skillik."""

from app.models.achievement import Achievement, UserAchievement
from app.models.extras import Announcement, HelpRequest, LessonAttendance, StudentNote
from app.models.feedback import LessonFeedback
from app.models.homework import Homework, HomeworkSubmission
from app.models.lesson import Lesson, LessonFile, LessonTemplate, LessonTopic
from app.models.message import Message, UrgentQuestion
from app.models.shop import ShopItem, UserPurchase
from app.models.topic import Topic, UserTopicProgress
from app.models.user import ParentStudent, User
from app.models.xp import Streak, XPLog

__all__ = [
    "User",
    "ParentStudent",
    "Topic",
    "UserTopicProgress",
    "Lesson",
    "LessonFile",
    "LessonTopic",
    "LessonTemplate",
    "Homework",
    "HomeworkSubmission",
    "Achievement",
    "UserAchievement",
    "XPLog",
    "Streak",
    "ShopItem",
    "UserPurchase",
    "Message",
    "UrgentQuestion",
    "LessonFeedback",
    "Announcement",
    "StudentNote",
    "LessonAttendance",
    "HelpRequest",
]
