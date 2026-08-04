import json
import re
from http.cookiejar import CookieJar
from urllib.parse import urlencode, urljoin
from urllib.request import HTTPCookieProcessor, HTTPErrorProcessor, Request, build_opener

from app.services.homework_check import import_from_ai_json

# unit
sample = """```json
{"title":"Drobi","tasks":[{"type":"input","question":"1/2+1/4?","answer":"3/4|0.75","points":1}]}
```"""
data, err = import_from_ai_json(sample)
assert data and data["tasks_count"] == 1, err
print("unit ok")

BASE = "http://127.0.0.1:8000"


class NR(HTTPErrorProcessor):
    def http_response(self, request, response):
        return response

    https_response = http_response


op = build_opener(HTTPCookieProcessor(CookieJar()), NR)


def get(path):
    url = urljoin(BASE, path)
    for _ in range(6):
        r = op.open(Request(url))
        body = r.read().decode()
        loc = r.headers.get("Location")
        if r.status in (301, 302, 303, 307, 308) and loc:
            url = urljoin(url, loc)
            continue
        return r.status, body


def post(path, data, accept=None):
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if accept:
        headers["Accept"] = accept
    r = op.open(
        Request(urljoin(BASE, path), data=urlencode(data).encode(), method="POST", headers=headers)
    )
    body = r.read().decode()
    loc = r.headers.get("Location")
    if r.status in (301, 302, 303, 307, 308) and loc:
        return get(loc)
    return r.status, body


_, html = get("/login")
csrf = re.search(r'name="csrf_token"\s+value="([^"]+)"', html).group(1)
post("/login", {"username": "admin", "password": "admin123", "csrf_token": csrf})
code, html = get("/admin/homework/new")
assert code == 200 and "ai-import-parse" in html and "Вставить из JSON" in html
print("form ok")
csrf = re.search(r'name="csrf_token"\s+value="([^"]+)"', html).group(1)
payload = json.dumps(
    {
        "title": "AI HW",
        "description": "d",
        "max_score": 5,
        "xp_reward": 25,
        "tasks": [{"type": "input", "question": "2+2?", "answer": "4", "points": 1}],
    }
)
code, body = post(
    "/admin/homework/parse-json",
    {"raw_json": payload, "csrf_token": csrf},
    accept="application/json",
)
print("parse status", code, body[:300])
res = json.loads(body)
assert res["ok"] is True
assert res["data"]["tasks_count"] == 1
print("endpoint ok")
print("ALL PASSED")
