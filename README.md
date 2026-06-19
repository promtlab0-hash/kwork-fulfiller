# kwork-fulfiller

Инструмент-фулфиллер для фрилансера на Kwork: **один движок + сменные профили**.
Заказчик даёт бриф → вы вручную вводите его в скрипт → ИИ генерирует → автопроверка
формы → готовый **DOCX** в папке `out/` → вы проверяете смысл и сдаёте вручную.

Отстройка от «бесплатного ChatGPT» (внутри тот же ИИ) — за счёт трёх вещей:
**ОБЪЁМ** (много позиций за раз единым форматом), **ФОРМАТ** (готовый документ, а не
текст в чате), **ПОД КЛЮЧ** (заказчик не возится сам).

## Архитектура: движок + профили

Движок один (ввод → ИИ → автопроверка → DOCX). Под каждую услугу — **профиль**:
промпт для ИИ + правила автопроверки + структура документа.

| Часть | Где | Что делает |
|---|---|---|
| **СОЗДАНИЕ** | `create` в профиле + `templates/*.md` | промпт-шаблон и билдер выходного файла |
| **НАСТРОЙКИ** | `settings` в профиле | параметры (объём, тон, язык, лимиты…) |
| **ПРОВЕРКА** | `checks` в профиле → `engine/validate.py` | валидация формы перед сдачей |

Профиль — `profiles/NN_<id>.json`: `id`, `title`, `kind` (`volume`|`single`),
`create{template, builder, response_format}`, `settings{}`, `checks[]`.

## Ниши (профили) — по одному профилю на каждый живой кворк

**Реализованы все 10.** Файл профиля пронумерован = порядку кворка; внутри JSON поля
`title`/`kwork_url`/`rubric` дают однозначную привязку «профиль ↔ кворк».

| # | Файл профиля | id | Заголовок кворка | Рубрика Kwork | Тип | Deliverable |
|---|---|---|---|---|---|---|
| 1 | `profiles/01_price_list.json` | `price_list` | Сделаю прайс-лист с продающими описаниями товаров в DOCX | Продающие и бизнес-тексты | ОБЪЁМ | DOCX: карточка-описание на товар |
| 2 | `profiles/02_faq_base.json` | `faq_base` | Напишу FAQ — базу вопросов и ответов для сайта в DOCX | Тексты и наполнение сайта | ОБЪЁМ | DOCX: блоки «вопрос → ответ» |
| 3 | `profiles/03_content_plan.json` | `content_plan` | Составлю контент-план на месяц для соцсетей в DOCX-таблице | SMM → Ведение и контент | ОБЪЁМ | DOCX-**таблица** дата/тема/формат/призыв |
| 4 | `profiles/04_email_series.json` | `email_series` | Напишу цепочку писем / welcome-серию для рассылки в DOCX | Продающие и бизнес-тексты | ОБЪЁМ | DOCX: письма тема+тело+когда слать |
| 5 | `profiles/05_objection_bank.json` | `objection_bank` | Соберу банк возражений и ответов для отдела продаж в DOCX | Продающие и бизнес-тексты | ОБЪЁМ | DOCX: возражение → 2–3 ответа |
| 6 | `profiles/06_kp.json` | `kp` | Составлю коммерческое предложение (КП) под ключ в DOCX | Продающие и бизнес-тексты | штучн. | DOCX: КП со **таблицей** состава/цены |
| 7 | `profiles/07_sales_script.json` | `sales_script` | Напишу скрипт продаж для звонков и чатов под ключ в DOCX | Продающие и бизнес-тексты | штучн. | DOCX: скрипт по этапам |
| 8 | `profiles/08_job_reg.json` | `job_reg` | Составлю должностную инструкцию и регламент для сотрудника в DOCX | Персональный помощник | штучн. | DOCX: оргдокумент по разделам |
| 9 | `profiles/09_tz.json` | `tz` | Напишу техническое задание (ТЗ) для исполнителя в DOCX | Тестирование и QA (usability) | штучн. | DOCX: ТЗ со **таблицей** этапов |
| 10 | `profiles/10_chatbot_script.json` | `chatbot_script` | Напишу сценарий чат-бота и автоворонки с ветками в DOCX | Продающие и бизнес-тексты | штучн. | DOCX: сценарий с ветками |

Все профили отдают DOCX через generic-билдер `docx` (`engine/outputs.py`). Билдер умеет
**таблицы**: секция с ключом `"table": {"columns", "rows"}` либо верхнеуровневые `"tables"`/
плоские `"columns"`+`"rows"` рендерятся как оформленная Word-таблица (для #3, #6, #9).

`kind`: **ОБЪЁМ** (`volume`) — много однотипных блоков из списка заказчика (проверка количества/
полноты + антидубль); **штучн.** (`single`) — один документ фиксированной структуры (проверка
наличия обязательных разделов). Юр-ниши (`job_reg`, `tz`) — только организационные документы,
без правовых заключений (см. дисклеймеры в шаблонах).

## Автопроверка

После генерации печатается отчёт **✓/✗** по каждой проверке. Код возврата ≠ 0,
если провалилась критичная проверка (у необязательных — `"critical": false`).
Проверка ловит **форму**, не смысл — смысловой взгляд делает оператор (или `--review`).

| Тип | Что проверяет |
|---|---|
| `valid_json` / `nonempty` | результат — корректный непустой JSON |
| `min_count` / `min_items` | число элементов в поле ≥ порога |
| `completeness` | обработаны ВСЕ позиции из брифа (для ОБЪЁМ-ниш) |
| `char_range` | длина блоков в заданных рамках |
| `has_sections` / `contains_keywords` | присутствуют нужные блоки/ключи |
| `no_placeholders` | нет `{{...}}`, `[вставь]`, lorem ipsum, обрывов |
| `no_ai_artifacts` | нет служебных фраз ИИ («вот ваш текст», «как ИИ», `here is your`…) |
| `no_duplicates` | нет повторяющихся блоков (нечёткое сравнение) |
| `boilerplate` | мало штампов/канцелярита (советная, не блокирует) |
| `vocabulary_richness` | доля уникальных слов выше порога (советная, не блокирует) |
| `py_compiles` | Python-исходник компилируется |

**Стандарт качества текста.** В каждый промпт автоматически вшивается единый блок
требований (анти-штампы, деловой тон, конкретика, уникальность формулировок) —
`QUALITY_STANDARD` в `fulfill.py`; в шаблонах есть блок «Эталон» с примерами
«как надо / как нельзя» под нишу. Проверки `boilerplate` и `vocabulary_richness`
добавляются ко всем нишам как **советные** (видны в отчёте, не блокируют сдачу).

**Смысл-ревью (`--review`):** опциональная вторая прогонка `claude -p`
(`engine/review.py`) — читает готовый результат и брифом и возвращает короткий
список замечаний по смыслу. Не блокирует сдачу, информирует оператора.

## Установка

```bash
python3 -m venv venv && source venv/bin/activate   # опционально
pip install -r requirements.txt
npm install -g @anthropic-ai/claude-code           # для реальной генерации
```

## Запуск локально

```bash
# Сухой прогон без сети — проверить пайплайн и валидаторы:
python3 fulfill.py --niche price_list --brief samples/price_list.txt --out ./out --dry-run

# Реальный заказ (нужен залогиненный claude CLI):
python3 fulfill.py --niche price_list --brief brief.txt --out ./out

# Со смысл-ревью второй прогонкой:
python3 fulfill.py --niche price_list --brief brief.txt --out ./out --review

# Бриф из stdin / интерактивное меню:
cat brief.txt | python3 fulfill.py --niche price_list --brief - --out ./out
python3 fulfill.py
```

### Флаги CLI

| Флаг | Значение |
|---|---|
| `--niche` / `--profile <id>` | id профиля из папки `profiles/` |
| `--brief <file\|-\|text>` | файл брифа, `-` для stdin, либо текст брифа |
| `--out <dir>` | папка для результата (по умолчанию `./out`) |
| `--set k=v` | переопределить настройку (можно несколько раз) |
| `--dry-run` | без вызова Claude — подставить осмысленную заглушку |
| `--review` | вторая ИИ-прогонка на смысл (не в `--dry-run`) |

## Тесты

```bash
pip install -r requirements-dev.txt
pytest -q
```

Покрывают: парсинг JSON из ответа модели (`parse_json` — фенсы, проза вокруг, битые
спаны), валидаторы (`no_duplicates`, `completeness`, `has_sections`, `no_placeholders`,
`no_ai_artifacts`…), билдер DOCX (секции, таблицы, плоский формат) и **dry-run по всем 10
профилям** — последнее ловит рассинхрон «проверка ↔ заглушка» (как было с `content_plan`).
Те же тесты гоняет CI (`.github/workflows/ci.yml`) на каждый push/PR.

## Бэкенды генерации (Claude / Qwen / любой OpenAI-совместимый)

Движок провайдеро-независимый. Бэкенд выбирается переменными окружения (или флагами
`--backend/--model/--base-url`, или файлом `.env` — см. `.env.example`).
Приоритет: флаги CLI → переменные окружения → `.env`.

| Бэкенд | Чем хорош | Минусы | Как включить |
|---|---|---|---|
| **Claude** (по умолч.) | топ-качество | нужен залогиненный `claude` CLI / платный токен | ничего не задавать |
| **OpenRouter + Qwen** | бесплатно, в облаке и локально | лимиты free-тира, потолок токенов | `LLM_BACKEND=openai`, ключ OpenRouter |
| **Ollama + Qwen** | бесплатно, безлимитно, оффлайн | качество ниже, нужен запас RAM | `LLM_BACKEND=openai`, локальный Ollama |

```bash
# Qwen через OpenRouter (ключ: https://openrouter.ai/keys):
LLM_BACKEND=openai LLM_BASE_URL=https://openrouter.ai/api/v1 \
LLM_API_KEY=sk-or-... LLM_MODEL=qwen/qwen-2.5-72b-instruct:free \
python3 fulfill.py --niche price_list --brief briefs/01_price_list.txt --out ./out

# Qwen локально через Ollama (ollama pull qwen2.5):
python3 fulfill.py --niche price_list --brief briefs/01_price_list.txt --out ./out \
  --backend openai --base-url http://localhost:11434/v1 --model qwen2.5

# Claude (по умолчанию, локальный вход):
python3 fulfill.py --niche price_list --brief briefs/01_price_list.txt --out ./out
```

Удобнее — скопировать `.env.example` в `.env` и раскомментировать нужный блок.
Набор бесплатных Qwen на OpenRouter меняется — актуальные ищите на
`openrouter.ai/models?q=qwen` (помечены `:free`). Большие ниши (контент-план на 28 постов)
могут упереться в потолок токенов free-тира.

## Запуск через GitHub Actions

Публичный репозиторий = бесплатные минуты Actions; генерацию можно запускать из браузера.
В форме `Run workflow` есть выбор `backend`: **openai** (по умолчанию, бесплатный Qwen через
OpenRouter) или **claude**.

**Вариант A — Qwen/OpenRouter (бесплатно, рекомендуется):**
1. Ключ: https://openrouter.ai/keys → добавьте секрет `LLM_API_KEY`
   (`Settings → Secrets and variables → Actions → New repository secret`).
2. `Actions → fulfill → Run workflow`: профиль, бриф, `backend=openai`,
   при желании поменяйте `model` (по умолч. `qwen/qwen-2.5-72b-instruct:free`).

**Вариант B — Claude:**
1. `claude setup-token` → секрет `CLAUDE_CODE_OAUTH_TOKEN`.
2. `Run workflow` с `backend=claude`.

Готовые файлы — в **Artifacts** запуска (архив `out/`). Ollama в облаке недоступен — он только
для локального запуска.

## Структура проекта

```
kwork-fulfiller/
  fulfill.py              # CLI-оркестратор (✅ОК / ⚠️НА ДОРАБОТКУ)
  stubs.py                # заглушки для --dry-run (по профилю)
  engine/
    llm.py                # call_claude + parse_json
    outputs.py            # билдеры: docx (основной), xlsx, csv, html_pack, code_zip
    validate.py           # run_checks: completeness, no_ai_artifacts, no_duplicates…
    review.py             # опц. смысл-ревью второй прогонкой
  profiles/NN_*.json      # профили (create / settings / checks)
  templates/*.md          # промпт-шаблоны под профили
  samples/*.txt           # примеры брифов
  .github/workflows/fulfill.yml
```

## Как добавить профиль

1. `templates/<id>.md` — промпт с контрактом ответа (строгий JSON).
2. `profiles/<NN>_<id>.json` — блоки `create` / `settings` / `checks`.
3. Заглушка в `stubs.py` (`_STUBS`), чтобы работал `--dry-run`.
4. Добавьте `id` в choice-список `.github/workflows/fulfill.yml`.
   Новый билдер нужен редко — DOCX рендерится generic-билдером `docx`.

## Ограничения

Только публичные данные или ввод заказчика; без парсинга закрытых площадок;
никаких юридических документов; вывод — DOCX (`python-docx`); скрипт не касается Kwork.

## Безопасность

Токены не в репозитории — только в GitHub Secrets и локальном профиле CLI.
Папка `out/` и `.env` игнорируются (`.gitignore`).
