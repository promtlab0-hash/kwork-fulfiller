"""Dry-run stubs.

For each niche, produce a deterministic, schema-valid payload (as the JSON
string the model would have returned) so the builders and checks can run
offline. The data is realistic enough that every declared check passes.
"""

from __future__ import annotations

import json


def _prompts_stub(settings: dict) -> dict:
    cats = max(4, int(settings.get("categories", 5)))
    per = max(1, int(settings.get("count", 50)) // cats)
    icons = ["✨", "📈", "📝", "🎯", "💡", "🚀", "🔍", "📣"]
    categories = []
    for c in range(cats):
        prompts = []
        for p in range(per):
            prompts.append({
                "title": f"Промпт {c + 1}.{p + 1}: задача для бизнеса",
                "prompt": (
                    "Ты опытный маркетолог с 10-летним стажем. "
                    f"Проанализируй продукт [ОПИСАНИЕ_ПРОДУКТА] для аудитории [ЦА] "
                    "и предложи конкретный план действий. Формат ответа: "
                    "нумерованный список из 5 шагов с обоснованием каждого. "
                    "Учитывай ограничения бюджета и сроков."
                ),
                "usage": "Когда нужно быстро получить структурированный план под нишу.",
            })
        categories.append({"name": f"Категория {c + 1}", "icon": icons[c % len(icons)], "prompts": prompts})
    return {
        "title": "Промпт-пак под бизнес-нишу",
        "subtitle": "Готовые промпты для ChatGPT и Claude под задачи заказчика.",
        "categories": categories,
    }


def _seo_core_stub(settings: dict) -> dict:
    n = max(30, int(settings.get("count", 60)))
    intents = ["commercial", "info", "mixed"]
    clusters = []
    for i in range(n):
        clusters.append({
            "кластер": f"Кластер {i % 8 + 1}",
            "запрос": f"купить услугу вариант {i + 1}",
            "частотность": 100 + (i * 37) % 5000,
            "интент": intents[i % 3],
            "тип_страницы": ["home", "category", "product", "article"][i % 4],
        })
    return {"title": "Семантическое ядро: ниша заказчика", "clusters": clusters}


def _wb_ozon_stub(settings: dict) -> dict:
    return {
        "title": "Беспроводные наушники с шумоподавлением",
        "meta": {"Площадка": settings.get("platform", "WB+Ozon"), "Объём": "~1500 знаков"},
        "sections": [
            {
                "heading": "Описание",
                "level": 2,
                "paragraphs": [
                    "Компактные беспроводные наушники с активным шумоподавлением "
                    "для города и спорта. Подходят тем, кто ценит чистый звук и "
                    "автономность в течение всего дня.",
                    "Эргономичная посадка и влагозащита позволяют использовать их "
                    "на тренировках и в дороге без дискомфорта.",
                ],
                "bullets": [
                    "Активное шумоподавление → концентрация в метро и опен-спейсе",
                    "До 30 часов с кейсом → не нужно заряжать каждый день",
                    "Влагозащита IPX5 → можно тренироваться под дождём",
                    "Bluetooth 5.3 → стабильное соединение без задержек",
                    "Сенсорное управление → переключение треков одним касанием",
                ],
            },
            {
                "heading": "Часто спрашивают",
                "level": 2,
                "bullets": [
                    "Подойдут для звонков? — Да, встроенные микрофоны с шумоочисткой.",
                    "Сколько держат заряд? — До 8 часов на одном заряде наушников.",
                ],
            },
            {
                "heading": "SEO-ключи",
                "level": 2,
                "bullets": [
                    "беспроводные наушники", "наушники с шумоподавлением",
                    "tws наушники", "наушники для спорта", "bluetooth наушники",
                ],
            },
        ],
    }


def _content_plan_stub(settings: dict) -> dict:
    days = max(20, int(settings.get("count", 30)))
    rubric = ["E", "E", "V", "V", "S"]
    plan = []
    for d in range(1, days + 1):
        plan.append({
            "день": d,
            "дата": f"{d:02d}.06",
            "рубрика": rubric[d % len(rubric)],
            "формат": ["пост", "карусель", "reel", "опрос"][d % 4],
            "тема": f"Тема дня {d}: разбор частой ошибки в нише",
            "тезисы": "• Контекст • Ошибка • Как исправить • Пример",
            "хештеги": "#ниша #экспертно #совет",
        })
    sections = [
        {"heading": f"Готовый пост #{i}", "level": 2,
         "paragraphs": [
             f"Полный текст готового поста №{i}. Цепляющий первый абзац, "
             "раскрытие пользы по пунктам и мягкий призыв к действию в конце. "
             "Текст готов к публикации без правок."]}
        for i in (1, 2, 3)
    ]
    return {"title": "Контент-план на месяц: ниша заказчика", "plan": plan, "sections": sections}


def _seo_article_stub(settings: dict) -> dict:
    para = (
        "Этот раздел подробно раскрывает тему и закрывает интент читателя. "
        "Текст написан естественно, без штампов и переспама ключевыми словами, "
        "при этом главный ключ встречается один раз в начале абзаца. Каждый "
        "абзац несёт законченную мысль и ведёт читателя к следующему разделу."
    )
    return {
        "title": "Как выбрать услугу: практическое руководство",
        "meta": {
            "Title": "Как выбрать услугу — пошаговое руководство 2026",
            "Description": "Разбираем критерии выбора услуги, частые ошибки и чек-лист. Практические советы и примеры внутри статьи.",
            "Ключи": "как выбрать услугу, выбор подрядчика, критерии выбора",
        },
        "sections": [
            {"heading": "Введение", "level": 2, "paragraphs": [para]},
            {"heading": "Критерии выбора", "level": 2, "paragraphs": [para, para],
             "bullets": ["Опыт", "Отзывы", "Прозрачность цены"]},
            {"heading": "Частые ошибки", "level": 2, "paragraphs": [para, para]},
            {"heading": "Заключение", "level": 2,
             "paragraphs": [para + " Оставьте заявку, чтобы получить расчёт."]},
        ],
    }


def _selling_stub(settings: dict) -> dict:
    emails = int(settings.get("emails", 3))
    sections = [
        {"heading": "Оффер", "level": 2, "paragraphs": [
            "Вы теряете заявки, потому что лендинг не закрывает возражения и не "
            "ведёт посетителя к действию. Мы соберём продающий текст, который "
            "превращает холодного читателя в заявку за счёт чёткого оффера, "
            "снятия сомнений и сильного призыва к действию.",
            "Текст строится по проверенной модели: сначала обозначаем боль "
            "аудитории, затем показываем измеримый результат, потом доказываем "
            "его кейсами и закрываем типовые возражения, и только после этого "
            "делаем предложение с понятным следующим шагом."]},
        {"heading": "Почему это работает", "level": 2, "bullets": [
            "Структура AIDA → читатель доходит до CTA, а не закрывает вкладку",
            "Закрытие возражений → меньше отказов на этапе принятия решения",
            "Конкретные цифры и сроки → доверие вместо общих обещаний",
            "Один оффер на экран → внимание не рассеивается между кнопками",
        ]},
    ]
    subjects = ["знакомство и польза", "кейс и доказательство", "оффер с дедлайном"]
    for i in range(emails):
        sections.append({
            "heading": f"Email #{i + 1} — тема: {subjects[i % len(subjects)]}",
            "level": 2,
            "paragraphs": [
                "Здравствуйте! В этом письме мы делимся конкретной пользой по "
                "вашей задаче и показываем на примере, как наш подход экономит "
                "время и деньги уже в первую неделю работы.",
                "Без воды и обещаний «золотых гор»: только то, что реально влияет "
                "на результат, и понятный следующий шаг. В конце письма — мягкий "
                "призыв перейти к расчёту или короткому звонку, чтобы обсудить "
                "детали под вашу ситуацию."]})
    return {"title": "Продающий текст и email-цепочка", "meta": {"Формат": settings.get("format", "landing+email")}, "sections": sections}


def _py_script_stub(settings: dict) -> dict:
    script = (
        '"""Парсер заголовков статей с сайта.\n'
        "Заказ Kwork — демонстрационная заглушка.\n"
        '"""\n'
        "import logging\n"
        "import sys\n"
        "from pathlib import Path\n\n"
        "import requests\n"
        "from bs4 import BeautifulSoup\n\n"
        "INPUT_URL = \"https://example.com\"\n"
        "OUTPUT_FILE = Path(\"output.csv\")\n"
        "HEADERS = {\"User-Agent\": \"Mozilla/5.0\"}\n\n"
        "logging.basicConfig(level=logging.INFO, format=\"%(asctime)s [%(levelname)s] %(message)s\")\n"
        "log = logging.getLogger(__name__)\n\n\n"
        "def fetch(url: str) -> list[str]:\n"
        "    \"\"\"Скачать страницу и вернуть заголовки h2.\"\"\"\n"
        "    try:\n"
        "        resp = requests.get(url, headers=HEADERS, timeout=20)\n"
        "        resp.raise_for_status()\n"
        "    except requests.RequestException as exc:\n"
        "        log.error(\"Сетевая ошибка: %s\", exc)\n"
        "        return []\n"
        "    soup = BeautifulSoup(resp.text, \"html.parser\")\n"
        "    return [h.get_text(strip=True) for h in soup.find_all(\"h2\")]\n\n\n"
        "def save(rows: list[str], path: Path) -> None:\n"
        "    \"\"\"Сохранить заголовки в CSV.\"\"\"\n"
        "    path.write_text(\"\\n\".join(rows), encoding=\"utf-8\")\n\n\n"
        "def main() -> int:\n"
        "    rows = fetch(INPUT_URL)\n"
        "    log.info(\"Найдено %d заголовков\", len(rows))\n"
        "    save(rows, OUTPUT_FILE)\n"
        "    return 0\n\n\n"
        "if __name__ == \"__main__\":\n"
        "    sys.exit(main())\n"
    )
    readme = (
        "# Парсер заголовков\n\n"
        "## Установка\n"
        "1. Python 3.10+\n"
        "2. `python -m venv venv && source venv/bin/activate`\n"
        "3. `pip install -r requirements.txt`\n\n"
        "## Запуск\n"
        "`python script.py`\n\n"
        "## Что в выходе\n"
        "Файл `output.csv` со списком заголовков h2.\n\n"
        "## Troubleshooting\n"
        "- ModuleNotFoundError — переустановите requirements в активном venv.\n"
        "- Connection timeout — проверьте сеть/VPN.\n"
    )
    return {
        "title": "Парсер заголовков статей",
        "script": script,
        "requirements": "requests==2.31.0\nbeautifulsoup4==4.12.2",
        "readme": readme,
    }


_STUBS = {
    "prompts": _prompts_stub,
    "seo_core": _seo_core_stub,
    "wb_ozon": _wb_ozon_stub,
    "content_plan": _content_plan_stub,
    "seo_article": _seo_article_stub,
    "selling": _selling_stub,
    "py_script": _py_script_stub,
}


def dry_run_stub(niche: dict, brief: str) -> str:
    """Return a JSON string standing in for the model's response."""
    builder = _STUBS.get(niche["id"])
    if builder is None:
        raise ValueError(f"No dry-run stub for niche {niche['id']!r}")
    data = builder(niche.get("settings", {}))
    return json.dumps(data, ensure_ascii=False)
