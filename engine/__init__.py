"""kwork-fulfiller engine package.

Three responsibilities mirror the three parts of every niche preset:
  * llm.py      — СОЗДАНИЕ: call the LLM (or a dry-run stub) and parse output
  * outputs.py  — builders that turn parsed data into deliverable files
  * validate.py — ПРОВЕРКА: run declarative checks against the result
"""

__all__ = ["llm", "outputs", "validate"]
