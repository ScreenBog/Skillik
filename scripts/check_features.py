"""Quick checks for new feature pages."""

from __future__ import annotations

import re
from http.cookiejar import CookieJar
from urllib.parse import urlencode, urljoin
from urllib.request import HTTPCookieProcessor, HTTPErrorProcessor, Request, build_opener

BASE = "http://127.0.0.1:8000"


class NR(HTTPErrorProcessor):
    def http_response(self, request, response):  # noqa: ARG002
        return response

    https_response = http_response


class C:
    def __init__(self) -> None:
        self.op = build_opener(HTTPCookieProcessor(CookieJar()), NR)

    def get(self, path: str):
        url = urljoin(BASE, path)
        for _ in range(6):
            r = self.op.open(Request(url))
            body = r.read().decode("utf-8", "replace")
            loc = r.headers.get("Location")
            if r.status in (301, 302, 303, 307, 308) and loc:
                url = urljoin(url, loc)
                continue
            return r.status, body

    def post(self, path: str, data):
        payload = urlencode(data).encode()
        r = self.op.open(
            Request(
                urljoin(BASE, path),
                data=payload,
                method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        )
        body = r.read().decode("utf-8", "replace")
        loc = r.headers.get("Location")
        if r.status in (301, 302, 303, 307, 308) and loc:
            return self.get(loc)
        return r.status, body

    def csrf(self, html: str) -> str:
        m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
        return m.group(1) if m else ""


def main() -> None:
    c = C()
    _, html = c.get("/login")
    c.post("/login", {"username": "admin", "password": "admin123", "csrf_token": c.csrf(html)})

    for p in (
        "/admin/homework/new",
        "/admin/calendar",
        "/admin/lessons/new",
        "/admin/templates",
        "/admin/calendar?filter=all",
    ):
        code, html = c.get(p)
        flags = []
        if "aq_question_0" in html:
            flags.append("aq-ui")
        if "Предстоящие" in html:
            flags.append("cal-filters")
        if "Шаблон" in html or "шаблон" in html.lower():
            flags.append("templates")
        print(f"{p}: {code} {' '.join(flags)}")

    _, html = c.get("/admin/homework/new")
    code, html = c.post(
        "/admin/homework/new",
        [
            ("csrf_token", c.csrf(html)),
            ("title", "UI-автопроверка"),
            ("description", "test"),
            ("max_score", "5"),
            ("xp_reward", "15"),
            ("all_students", "on"),
            ("aq_question_0", "3+3?"),
            ("aq_answer_0", "6"),
            ("aq_type_0", "input"),
            ("aq_points_0", "1"),
            ("due_at", ""),
            ("topic_id", ""),
            ("lesson_id", ""),
            ("auto_check_json", ""),
        ],
    )
    print("create aq hw:", code, "ok" if "UI-автопроверка" in html else "missing title")

    # student shop avatars
    c2 = C()
    _, html = c2.get("/login")
    c2.post("/login", {"username": "ivan", "password": "ivan123", "csrf_token": c2.csrf(html)})
    code, html = c2.get("/student/shop")
    print("shop:", code, "emoji" if "🦊" in html or "shop-preview" in html else "no-preview")


if __name__ == "__main__":
    main()
