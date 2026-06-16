# kwork-fulfiller

Инструмент-фулфиллер для фрилансера на Kwork. Вы вручную берёте заказ,
выбираете пресет ниши — скрипт **генерирует** результат, **проверяет** его и
кладёт готовые файлы в папку `out/`.

Каждый пресет состоит из трёх частей:

| Часть | Где | Что делает |
|---|---|---|
| **СОЗДАНИЕ** | `create` в niche JSON + `templates/*.md` | промпт-шаблон и билдер выходного файла |
| **НАСТРОЙКИ** | `settings` в niche JSON | параметры (объём, язык, площадка, тон…) |
| **ПРОВЕРКА** | `checks` в niche JSON → `engine/validate.py` | валидация результата перед сдачей |

## Ниши

| id | Поставка | Билдер |
|---|---|---|
| `prompts` | HTML-пак с карточками и кнопкой копирования + `.txt` | `html_pack` |
| `seo_core` | `.xlsx` + `.csv` (кластер/запрос/частотность/интент) | `xlsx_csv` |
| `wb_ozon` | `.docx` SEO-описание карточки с ключами | `docx` |
| `content_plan` | `.xlsx` (таблица плана) + `.docx` (готовые посты) | `docx_xlsx` |
| `seo_article` | `.docx` статья с H2/H3 и мета-тегами | `docx` |
| `selling` | `.docx` продающий текст / email-цепочка | `docx` |
| `py_script` | `.zip` с `script.py` + `README.md` + `requirements.txt` | `code_zip` |

## Установка

```bash
python3 -m venv venv && source venv/bin/activate   # опционально
pip install -r requirements.txt
```

Для реальной генерации нужен установленный Claude Code CLI:

```bash
npm install -g @anthropic-ai/claude-code
# или официальный установщик с https://claude.com/claude-code
```

## Запуск локально

```bash
# Сухой прогон без сети — проверить пайплайн и валидаторы:
python3 fulfill.py --niche prompts --brief samples/prompts.txt --out ./out --dry-run

# Реальный заказ (нужен залогиненный claude CLI):
python3 fulfill.py --niche seo_article --brief brief.txt --out ./out

# Бриф из stdin:
cat brief.txt | python3 fulfill.py --niche wb_ozon --brief - --out ./out

# Переопределить настройку:
python3 fulfill.py --niche seo_core --brief samples/seo_core.txt --set count=120 --out ./out

# Интерактивное меню (без --niche):
python3 fulfill.py
```

В конце печатается отчёт `✓/✗` по каждой проверке и список созданных файлов.
**Код возврата ≠ 0**, если провалилась хотя бы одна критичная проверка
(у необязательных стоит `"critical": false`).

### Флаги CLI

| Флаг | Значение |
|---|---|
| `--niche <id>` | id ниши из папки `niches/` |
| `--brief <file\|-\|text>` | файл брифа, `-` для stdin, либо текст брифа |
| `--out <dir>` | папка для результата (по умолчанию `./out`) |
| `--set k=v` | переопределить настройку (можно несколько раз) |
| `--dry-run` | без вызова Claude — подставить осмысленную заглушку |

## Запуск через GitHub Actions

Публичный репозиторий = бесплатные минуты Actions. Генерацию можно запускать
прямо из браузера.

1. **Получите токен** для CLI в неинтерактивной среде:
   ```bash
   claude setup-token
   ```
   Скопируйте выданный OAuth-токен.

2. **Добавьте секрет** в репозиторий:
   `Settings → Secrets and variables → Actions → New repository secret`
   - Name: `CLAUDE_CODE_OAUTH_TOKEN`
   - Secret: вставьте токен из шага 1.

3. **Запустите**: вкладка `Actions → fulfill → Run workflow`. Выберите нишу,
   вставьте бриф (и при желании `settings` вида `count=80,tone=живой`).

4. Готовые файлы появятся в **Artifacts** этого запуска (архив `out/`).

> CLI сам подхватывает `CLAUDE_CODE_OAUTH_TOKEN` из окружения — никакой
> дополнительной настройки в коде не требуется.

## Структура проекта

```
kwork-fulfiller/
  fulfill.py              # CLI-оркестратор
  stubs.py                # заглушки для --dry-run (по нише)
  engine/
    llm.py                # call_claude + parse_json
    outputs.py            # билдеры: html_pack, xlsx, csv, docx, code_zip…
    validate.py           # run_checks: min_count, char_range, py_compiles…
  niches/*.json           # 7 пресетов (create / settings / checks)
  templates/*.md          # промпт-шаблоны под ниши
  samples/*.txt           # примеры брифов для теста
  .github/workflows/fulfill.yml
```

## Как добавить нишу

1. Создайте `templates/<name>.md` с промптом и контрактом ответа (JSON).
2. Создайте `niches/<N>_<id>.json` с блоками `create` / `settings` / `checks`.
3. Если формат поставки новый — добавьте билдер в `engine/outputs.BUILDERS`.
4. Добавьте заглушку в `stubs.py`, чтобы работал `--dry-run`.

## Безопасность

Токены не хранятся в репозитории — только в GitHub Secrets и в локальном
профиле CLI. Папка `out/` и `.env` игнорируются (`.gitignore`).
