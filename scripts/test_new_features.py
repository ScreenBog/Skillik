import re
from http.cookiejar import CookieJar
from urllib.parse import urlencode, urljoin
from urllib.request import HTTPCookieProcessor, HTTPErrorProcessor, Request, build_opener

BASE = "http://127.0.0.1:8000"


class NR(HTTPErrorProcessor):
    def http_response(self, request, response):
        return response

    https_response = http_response


def client():
    return build_opener(HTTPCookieProcessor(CookieJar()), NR)


def get(op, path):
    url = urljoin(BASE, path)
    for _ in range(6):
        r = op.open(Request(url))
        body = r.read().decode()
        loc = r.headers.get("Location")
        if r.status in (301, 302, 303, 307, 308) and loc:
            url = urljoin(url, loc)
            continue
        return r.status, body


def post(op, path, data):
    r = op.open(
        Request(
            urljoin(BASE, path),
            data=urlencode(data).encode(),
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    )
    body = r.read().decode()
    loc = r.headers.get("Location")
    if r.status in (301, 302, 303, 307, 308) and loc:
        return get(op, loc)
    return r.status, body


def csrf(html):
    return re.search(r'name="csrf_token"\s+value="([^"]+)"', html).group(1)


def login(op, user, password, path="/login"):
    _, html = get(op, path)
    return post(op, path, {"username": user, "password": password, "csrf_token": csrf(html)})


op = client()
login(op, "admin", "admin123")
for p in ("/admin/announcements", "/admin/help"):
    code, body = get(op, p)
    assert code == 200 and "Traceback" not in body, p
    print(p, "ok")

_, html = get(op, "/admin/announcements")
code, body = post(
    op,
    "/admin/announcements/new",
    {
        "csrf_token": csrf(html),
        "title": "Тест-объявление",
        "body": "Завтра урок",
        "audience": "all",
    },
)
assert "Тест-объявление" in body
print("announcement create ok")

op2 = client()
login(op2, "ivan", "ivan123")
for p in ("/student", "/student/notes"):
    code, body = get(op2, p)
    assert code == 200, p
    print(p, "ok")
assert "Тест-объявление" in get(op2, "/student")[1] or "От преподавателя" in get(op2, "/student")[1]
print("student sees board ok")

_, html = get(op2, "/student/notes")
code, body = post(
    op2,
    "/student/notes/new",
    {"csrf_token": csrf(html), "title": "Формула", "body": "a2+b2=c2", "color": "yellow"},
)
assert "Формула" in body
print("note create ok")
print("ALL PASSED")
