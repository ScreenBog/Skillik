from app.services.homework_check import import_from_ai_json

sample = """```json
{
  "title": "Drobi",
  "description": "desc",
  "max_score": 5,
  "xp_reward": 25,
  "tasks": [
    {"type": "input", "question": "1/2+1/4?", "answer": "3/4|0.75", "points": 1},
    {"type": "test", "question": "2/3 or 3/5?", "options": ["2/3", "3/5", "eq"], "answer": "2/3", "points": 1}
  ]
}
```"""

data, err = import_from_ai_json(sample)
assert data is not None, err
assert data["tasks_count"] == 2
print("fence ok", data["title"], data["tasks_count"])

data2, err2 = import_from_ai_json("{bad")
assert data2 is None
print("bad ok", err2[0][:40])

data3, err3 = import_from_ai_json(
    '[{"type":"input","question":"2+2","answer":"4"}]'
)
assert data3 and data3["tasks_count"] == 1
print("array ok", data3["title"])

data4, err4 = import_from_ai_json(
    '{"tasks":[{"type":"test","question":"Q","answer":"A","options":["B"]}]}'
)
assert data4 is None
print("invalid test ok", err4)

print("ALL PASSED")
