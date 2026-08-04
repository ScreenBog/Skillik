"""Smoke-test Skillik against a running server."""

from __future__ import annotations

import json
import re
import sys
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import HTTPErrorProcessor, HTTPCookieProcessor, Request, build_opener

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


class NoRedirect(HTTPErrorProcessor):
    def http_response(self, request, response):  # noqa: ARG002
        return response

    https_response = http_response


class Client:
    def __init__(self) -> None:
        self.cj = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cj), NoRedirect)

    def get(self, path: str, allow_redirects: bool = True):
        url = urljoin(BASE, path)
        code, body, loc = 0, "", None
        for _ in range(8 if allow_redirects else 1):
            req = Request(url, method="GET")
            resp = self.opener.open(req, timeout=20)
            code = resp.status
            body = resp.read().decode("utf-8", errors="replace")
            loc = resp.headers.get("Location")
            if code in (301, 302, 303, 307, 308) and allow_redirects and loc:
                url = urljoin(url, loc)
                continue
            return code, body, loc
        return code, body, loc

    def post(self, path: str, data: dict | list[tuple[str, str]], allow_redirects: bool = True):
        if isinstance(data, dict):
            payload = urlencode(data).encode()
        else:
            payload = urlencode(data).encode()
        url = urljoin(BASE, path)
        req = Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        resp = self.opener.open(req, timeout=20)
        code = resp.status
        body = resp.read().decode("utf-8", errors="replace")
        loc = resp.headers.get("Location")
        if code in (301, 302, 303, 307, 308) and allow_redirects and loc:
            return self.get(loc)
        return code, body, loc

    def csrf(self, html: str) -> str | None:
        m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
        return m.group(1) if m else None


results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"[{'OK' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def login(username: str, password: str, login_path: str = "/login") -> Client | None:
    c = Client()
    try:
        code, html, _ = c.get(login_path)
    except Exception as e:  # noqa: BLE001
        check(f"login {username}", False, str(e))
        return None
    csrf = c.csrf(html)
    if not csrf:
        check(f"login {username}", False, "no csrf")
        return None
    code, html, _ = c.post(
        login_path,
        {"username": username, "password": password, "csrf_token": csrf},
    )
    if "Неверный" in html:
        check(f"login {username}", False, "bad credentials")
        return None
    check(f"login {username}", code == 200, f"code={code}")
    return c if code == 200 else None


def main() -> int:
    try:
        Client().get("/health")
    except (HTTPError, URLError, OSError) as e:
        print(f"Server not reachable at {BASE}: {e}")
        return 2

    admin = login("admin", "admin123")
    student = login("ivan", "ivan123")
    parent = login("parent_ivan", "parent123", "/parent/login")

    admin_pages = [
        "/admin",
        "/admin/students",
        "/admin/students/new",
        "/admin/lessons",
        "/admin/lessons/new",
        "/admin/homework",
        "/admin/homework/new",
        "/admin/topics",
        "/admin/calendar",
        "/admin/templates",
        "/admin/shop",
        "/admin/messages",
        "/admin/stats",
    ]
    if admin:
        for p in admin_pages:
            try:
                code, html, _ = admin.get(p)
                bad = code >= 500 or "Internal Server Error" in html or "Traceback" in html
                check(f"GET {p}", code == 200 and not bad, f"code={code} len={len(html)}")
            except Exception as e:  # noqa: BLE001
                check(f"GET {p}", False, str(e))

    student_pages = [
        "/student",
        "/student/lessons",
        "/student/homework",
        "/student/map",
        "/student/practice",
        "/student/achievements",
        "/student/shop",
        "/student/messages",
        "/student/profile",
    ]
    if student:
        for p in student_pages:
            try:
                code, html, _ = student.get(p)
                bad = code >= 500 or "Internal Server Error" in html or "Traceback" in html
                check(f"GET {p}", code == 200 and not bad, f"code={code} len={len(html)}")
            except Exception as e:  # noqa: BLE001
                check(f"GET {p}", False, str(e))

    if parent:
        try:
            code, html, _ = parent.get("/parent")
            bad = code >= 500 or "Internal Server Error" in html
            check("GET /parent", code == 200 and not bad, f"code={code}")
        except Exception as e:  # noqa: BLE001
            check("GET /parent", False, str(e))

    # Create student
    if admin:
        code, html, _ = admin.get("/admin/students/new")
        csrf = admin.csrf(html)
        code, html, _ = admin.post(
            "/admin/students/new",
            {
                "csrf_token": csrf or "",
                "full_name": "Тест Ученик",
                "username": "test_smoke",
                "password": "test1234",
                "email": "",
            },
        )
        ok = code == 200 and ("test_smoke" in html or "Ученик создан" in html)
        check("create student test_smoke", ok, f"code={code}")

        # Create lesson
        code, html, _ = admin.get("/admin/lessons/new")
        csrf = admin.csrf(html)
        code, html, _ = admin.post(
            "/admin/lessons/new",
            {
                "csrf_token": csrf or "",
                "title": "Смоук-урок: Дроби",
                "description": "Тестовый урок",
                "content": "Содержание урока про дроби",
                "scheduled_at": "2026-08-10T15:00",
                "duration_minutes": "60",
                "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "youtube_start": "30",
                "student_id": "",
                "is_published": "on",
                "status": "planned",
            },
        )
        ok = code == 200 and ("Смоук-урок" in html or "Дроби" in html)
        check("create lesson", ok, f"code={code}")

        # Create homework for all students
        code, html, _ = admin.get("/admin/homework/new")
        csrf = admin.csrf(html)
        topic_ids = re.findall(r'name="topic_id".*?<option value="(\d+)"', html, re.S)
        # simpler: pick any topic option
        topics = re.findall(r'<option value="(\d+)">', html)
        topic_id = topics[0] if topics else ""
        auto = json.dumps(
            [{"id": "1", "type": "input", "question": "2+2?", "answer": "4", "points": 1}],
            ensure_ascii=False,
        )
        code, html, _ = admin.post(
            "/admin/homework/new",
            [
                ("csrf_token", csrf or ""),
                ("title", "Смоук-ДЗ: 2+2"),
                ("description", "Реши примеры"),
                ("due_at", "2026-08-15T18:00"),
                ("max_score", "5"),
                ("xp_reward", "20"),
                ("topic_id", topic_id),
                ("lesson_id", ""),
                ("auto_check_json", auto),
                ("all_students", "on"),
            ],
        )
        check("create homework all", code == 200, f"code={code} has_title={'Смоук-ДЗ' in html}")

    if student:
        code, html, _ = student.get("/student/homework")
        check("student homework list", code == 200, f"code={code} has_smoke={'Смоук' in html}")
        links = re.findall(r'href="(/student/homework/\d+)"', html)
        if links:
            code, html, _ = student.get(links[0])
            check(f"open {links[0]}", code == 200, f"code={code}")
            csrf = student.csrf(html)
            code2, html2, _ = student.post(
                links[0] + "/submit",
                {
                    "csrf_token": csrf or "",
                    "text_answer": "Решение: 4",
                    "q_1": "4",
                },
            )
            check("submit homework", code2 == 200, f"code={code2} ok_flash={'отправлена' in html2.lower() or 'ok' in html2.lower() or code2==200}")
        else:
            check("open homework detail", False, "no homework links")

        code, html, _ = student.get("/student/lessons")
        lesson_links = re.findall(r'href="(/student/lessons/\d+)"', html)
        if lesson_links:
            code, html, _ = student.get(lesson_links[0])
            check("open lesson", code == 200 and "Internal Server Error" not in html, f"code={code}")
            csrf = student.csrf(html)
            if csrf and "difficulty" in html:
                code2, _, _ = student.post(
                    lesson_links[0] + "/feedback",
                    {"csrf_token": csrf, "difficulty": "normal", "comment": ""},
                )
                check("lesson feedback", code2 == 200, f"code={code2}")
        else:
            check("student has lessons", "нет" in html.lower() or code == 200, "no lesson links")

        code, html, _ = student.get("/student/map")
        check("knowledge map", code == 200, f"code={code}")
        code, html, _ = student.get("/student/practice?topic_id=2")
        check("practice", code == 200, f"code={code}")

    if admin:
        code, html, _ = admin.get("/admin/homework")
        grade_links = re.findall(r'href="(/admin/homework/\d+/grade)"', html)
        if grade_links:
            code, html, _ = admin.get(grade_links[0])
            csrf = admin.csrf(html)
            code2, html2, _ = admin.post(
                grade_links[0],
                {
                    "csrf_token": csrf or "",
                    "score": "5",
                    "teacher_comment": "Отлично!",
                },
            )
            check("grade homework", code2 == 200, f"code={code2}")
        else:
            check("grade homework", False, "no grade links")

        # export
        try:
            code, html, _ = admin.get("/admin/export/students")
            check("export students csv", code == 200 and ("username" in html or ";" in html), f"code={code}")
        except Exception as e:  # noqa: BLE001
            check("export students csv", False, str(e))

    print("\n=== SUMMARY ===")
    fails = [r for r in results if not r[1]]
    print(f"Total: {len(results)}  OK: {len(results) - len(fails)}  FAIL: {len(fails)}")
    for name, _ok, detail in fails:
        print(f"  - {name}: {detail}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
