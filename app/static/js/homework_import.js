/* Skillik — импорт ДЗ из JSON нейросети */

(function () {
  var form = document.getElementById("hw-form");
  if (!form) return;

  var panel = document.getElementById("ai-import-panel");
  var toggleBtn = document.getElementById("ai-import-toggle");
  var parseBtn = document.getElementById("ai-import-parse");
  var rawArea = document.getElementById("ai-import-raw");
  var statusEl = document.getElementById("ai-import-status");
  var previewEl = document.getElementById("ai-import-preview");
  var packageField = document.getElementById("ai_package_json");
  var maxAq = parseInt(form.getAttribute("data-max-aq") || "20", 10);

  function showStatus(msg, isError) {
    if (!statusEl) return;
    statusEl.style.display = msg ? "block" : "none";
    statusEl.className = "alert " + (isError ? "alert-error" : "alert-success");
    statusEl.textContent = msg;
  }

  function showRow(i) {
    var row = document.querySelector('.aq-row[data-aq="' + i + '"]');
    if (row) row.style.display = "";
  }

  function hideRow(i) {
    var row = document.querySelector('.aq-row[data-aq="' + i + '"]');
    if (!row) return;
    row.style.display = "none";
    var q = row.querySelector('[name="aq_question_' + i + '"]');
    var a = row.querySelector('[name="aq_answer_' + i + '"]');
    var t = row.querySelector('[name="aq_type_' + i + '"]');
    var p = row.querySelector('[name="aq_points_' + i + '"]');
    var o = row.querySelector('[name="aq_options_' + i + '"]');
    if (q) q.value = "";
    if (a) a.value = "";
    if (t) t.value = "input";
    if (p) p.value = "1";
    if (o) o.value = "";
    var optBox = row.querySelector("[data-aq-options]");
    if (optBox) optBox.style.display = "none";
  }

  function clearAllAq() {
    for (var i = 0; i < maxAq; i++) hideRow(i);
  }

  function setField(name, value) {
    var el = form.querySelector('[name="' + name + '"]');
    if (el && value !== undefined && value !== null) el.value = value;
  }

  function fillTasks(tasks) {
    clearAllAq();
    for (var i = 0; i < tasks.length && i < maxAq; i++) {
      var t = tasks[i];
      showRow(i);
      setField("aq_question_" + i, t.question || "");
      setField("aq_answer_" + i, t.answer || "");
      setField("aq_type_" + i, t.type === "test" ? "test" : "input");
      setField("aq_points_" + i, t.points != null ? t.points : 1);
      if (t.options && t.options.length) {
        setField("aq_options_" + i, t.options.join("; "));
      }
      var typeSel = form.querySelector('[name="aq_type_' + i + '"]');
      var optBox = document.querySelector('[data-aq-options="' + i + '"]');
      if (typeSel && optBox) {
        optBox.style.display = typeSel.value === "test" ? "" : "none";
      }
    }
    var addBtn = document.getElementById("aq-add");
    if (addBtn) {
      addBtn.style.display = tasks.length >= maxAq ? "none" : "";
    }
  }

  function renderPreview(data) {
    if (!previewEl) return;
    if (!data || !data.tasks || !data.tasks.length) {
      previewEl.style.display = "none";
      previewEl.innerHTML = "";
      return;
    }
    var html = "<strong>Превью: " + escapeHtml(data.title) + "</strong>";
    html +=
      " <span class=\"text-muted text-sm\">· " +
      data.tasks_count +
      " заданий · макс. " +
      data.max_score +
      " · +" +
      data.xp_reward +
      " XP</span><ol class=\"ai-preview-list\">";
    data.tasks.forEach(function (t, idx) {
      html +=
        "<li><span class=\"badge badge-info\">" +
        escapeHtml(t.type) +
        "</span> " +
        escapeHtml(t.question) +
        " <span class=\"text-muted\">→ " +
        escapeHtml(String(t.answer)) +
        " (" +
        t.points +
        " б.)</span></li>";
    });
    html += "</ol>";
    previewEl.innerHTML = html;
    previewEl.style.display = "block";
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  if (toggleBtn && panel) {
    toggleBtn.addEventListener("click", function () {
      var open = panel.style.display !== "none";
      panel.style.display = open ? "none" : "block";
      toggleBtn.textContent = open ? "Вставить из JSON / нейросети" : "Скрыть импорт JSON";
      if (!open && rawArea) rawArea.focus();
    });
  }

  function applyParsed(data, warnings) {
    if (data.title) setField("title", data.title);
    if (data.description) setField("description", data.description);
    if (data.max_score != null) setField("max_score", data.max_score);
    if (data.xp_reward != null) setField("xp_reward", data.xp_reward);
    fillTasks(data.tasks || []);
    if (packageField) {
      packageField.value = rawArea ? rawArea.value : "";
    }
    // дублируем tasks в auto_check_json
    var rawJsonField = form.querySelector('[name="auto_check_json"]');
    if (rawJsonField && data.tasks_json) {
      rawJsonField.value = data.tasks_json;
    }
    renderPreview(data);
    var msg =
      "Готово: " +
      (data.tasks_count || 0) +
      " заданий загружено. Проверьте и нажмите «Выдать задание».";
    if (warnings && warnings.length) {
      msg += " Замечания: " + warnings.join("; ");
    }
    showStatus(msg, false);
  }

  if (parseBtn) {
    parseBtn.addEventListener("click", function () {
      var raw = rawArea ? rawArea.value : "";
      if (!raw.trim()) {
        showStatus("Вставьте JSON от нейросети", true);
        return;
      }
      showStatus("Разбираю…", false);
      parseBtn.disabled = true;

      var csrf = form.querySelector('[name="csrf_token"]');
      var body = new URLSearchParams();
      body.set("raw_json", raw);
      body.set("csrf_token", csrf ? csrf.value : "");

      fetch("/admin/homework/parse-json", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          Accept: "application/json",
        },
        body: body.toString(),
        credentials: "same-origin",
      })
        .then(function (r) {
          return r.json();
        })
        .then(function (res) {
          parseBtn.disabled = false;
          if (!res.ok) {
            showStatus((res.errors || ["Ошибка разбора"]).join(" · "), true);
            renderPreview(null);
            return;
          }
          applyParsed(res.data, res.warnings);
        })
        .catch(function (err) {
          parseBtn.disabled = false;
          // fallback: локальный parse
          tryLocalParse(raw);
        });
    });
  }

  function tryLocalParse(raw) {
    try {
      var text = raw.trim();
      if (text.indexOf("```") === 0) {
        text = text.replace(/^```(?:json)?\s*/i, "").replace(/```\s*$/, "");
      }
      var data = JSON.parse(text);
      var tasks = Array.isArray(data) ? data : data.tasks;
      if (!tasks || !tasks.length) {
        showStatus("Не найден блок tasks", true);
        return;
      }
      applyParsed(
        {
          title: data.title || "Домашнее задание",
          description: data.description || "",
          max_score: data.max_score != null ? data.max_score : 5,
          xp_reward: data.xp_reward != null ? data.xp_reward : 20,
          tasks: tasks,
          tasks_count: tasks.length,
          tasks_json: JSON.stringify(tasks),
        },
        []
      );
    } catch (e) {
      showStatus("Невалидный JSON: " + (e.message || e), true);
    }
  }

  // пример
  var exampleBtn = document.getElementById("ai-import-example");
  if (exampleBtn && rawArea) {
    exampleBtn.addEventListener("click", function () {
      rawArea.value = JSON.stringify(
        {
          title: "Дроби. Сложение",
          description: "Реши задания. Можно пользоваться черновиком.",
          max_score: 5,
          xp_reward: 25,
          tasks: [
            {
              type: "input",
              question: "Чему равна 1/2 + 1/4?",
              answer: "3/4|0.75",
              points: 1,
            },
            {
              type: "test",
              question: "Какая дробь больше: 2/3 или 3/5?",
              options: ["2/3", "3/5", "равны"],
              answer: "2/3",
              points: 1,
            },
            {
              type: "input",
              question: "Упрости 6/8",
              answer: "3/4",
              points: 1,
            },
          ],
        },
        null,
        2
      );
      showStatus("Пример вставлен — нажмите «Разобрать и заполнить»", false);
    });
  }

  // копировать промт
  var copyPrompt = document.getElementById("ai-copy-prompt");
  var promptBox = document.getElementById("ai-prompt-text");
  if (copyPrompt && promptBox) {
    copyPrompt.addEventListener("click", function () {
      var t = promptBox.textContent || promptBox.innerText;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(t).then(function () {
          copyPrompt.textContent = "Скопировано!";
          setTimeout(function () {
            copyPrompt.textContent = "Копировать промт";
          }, 1500);
        });
      } else {
        var ta = document.createElement("textarea");
        ta.value = t;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
        copyPrompt.textContent = "Скопировано!";
      }
    });
  }
})();
