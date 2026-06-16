# Публикация на GitHub (публичный репозиторий)

Публичный репо = **бесплатные минуты GitHub Actions**, поэтому генерацию можно
запускать прямо из браузера. Ниже два способа залить код. Замените `<USER>` на
свой логин GitHub.

> Перед пушем убедитесь, что в репозитории нет секретов:
> ```bash
> git grep -iE "sk-ant|ghp_|github_pat|oauth.*[A-Za-z0-9]{20}"
> ```
> Пустой вывод = чисто (имя переменной `CLAUDE_CODE_OAUTH_TOKEN` в workflow — это норма).

---

## Способ A — через `gh` CLI (проще всего)

Требуется установленный и залогиненный [GitHub CLI](https://cli.github.com/)
(`gh auth login`).

```bash
cd kwork-fulfiller
gh repo create kwork-fulfiller --public --source . --push
```

Команда создаст публичный репозиторий, привяжет его как `origin` и запушит
текущую ветку одной операцией.

---

## Способ B — через `git` + Personal Access Token (PAT)

1. Создайте репозиторий на GitHub: https://github.com/new
   - Name: `kwork-fulfiller`
   - Visibility: **Public**
   - Без README/`.gitignore`/лицензии (они уже есть в проекте).

2. Создайте PAT: `Settings → Developer settings → Tokens (classic) →
   Generate new token`, scope `repo`. Скопируйте токен (`ghp_...`).

3. Привяжите remote и запушьте (ветка по умолчанию — `main`):

   ```bash
   cd kwork-fulfiller
   git remote add origin https://github.com/<USER>/kwork-fulfiller.git
   git push -u origin main
   ```

   При запросе логина/пароля введите логин GitHub и **PAT вместо пароля**.

   > Если локальная ветка называется `master`, переименуйте её перед пушем:
   > ```bash
   > git branch -M main
   > ```

---

## После пуша — добавить секрет для Actions

Чтобы workflow мог вызывать Claude, нужен OAuth-токен CLI.

1. Получите токен в неинтерактивной среде:

   ```bash
   claude setup-token
   ```

   Скопируйте выданный OAuth-токен.

2. Добавьте секрет в репозиторий:

   `Settings → Secrets and variables → Actions → New repository secret`
   - **Name:** `CLAUDE_CODE_OAUTH_TOKEN`
   - **Secret:** вставьте токен из шага 1.

3. Запуск: вкладка `Actions → fulfill → Run workflow`. Выберите нишу, вставьте
   бриф (и при желании `settings` вида `count=80,tone=живой`). Готовые файлы
   появятся в **Artifacts** этого запуска (архив папки `out/`).

> CLI сам подхватывает `CLAUDE_CODE_OAUTH_TOKEN` из окружения — никакой
> дополнительной настройки в коде не требуется.
