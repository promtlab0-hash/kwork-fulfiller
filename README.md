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

## Ниши (профили)

10 ниш плана. Реализуется по одной; ниже статус.

| # | id | Кворк | Тип | Статус |
|---|---|---|---|---|
| 1 | `price_list` | Прайс-лист с продающими описаниями | ОБЪЁМ | ✅ реализован |
| 2 | `faq_base` | FAQ / база ответов для бизнеса | ОБЪЁМ | план |
| 3 | `content_plan` | Контент-план на месяц | ОБЪЁМ | план |
| 4 | `email_series` | Цепочка email / welcome-серия | ОБЪЁМ | план |
| 5 | `objection_bank` | Банк возражений и ответов | ОБЪЁМ | план |
| 6 | `kp` | Коммерческое предложение (КП) | штучн. | план |
| 7 | `sales_script` | Скрипты продаж | штучн. | план |
| 8 | `job_reg` | Должностная инструкция / регламент | штучн. | план |
| 9 | `tz` | Техническое задание (ТЗ) | штучн. | план |
| 10 | `chatbot_script` | Сценарий чат-бота / автоворонки | штучн. | план |

Все профили отдают DOCX через generic-билдер `docx` (`engine/outputs.py`).

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
| `py_compiles` | Python-исходник компилируется |

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

## Запуск через GitHub Actions

Публичный репозиторий = бесплатные минуты Actions; генерацию можно запускать из браузера.

1. Получите токен CLI: `claude setup-token` → скопируйте OAuth-токен.
2. `Settings → Secrets and variables → Actions → New repository secret`:
   Name `CLAUDE_CODE_OAUTH_TOKEN`, Secret — токен из шага 1.
3. `Actions → fulfill → Run workflow`: выберите профиль, вставьте бриф
   (и при желании `settings` вида `desc_max=600`).
4. Готовые файлы — в **Artifacts** запуска (архив `out/`).

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
