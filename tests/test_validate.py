"""Validators are the safety net before delivery — pin their behaviour."""

from engine import validate


def _result(checks, data, brief=""):
    """Run checks and return {name: ok} for easy assertions."""
    out = validate.run_checks(data, checks, brief=brief)
    return {name: ok for name, ok, _detail, _crit in out}


def test_min_count_pass_and_fail():
    data = {"sections": [1, 2, 3]}
    assert _result([{"type": "min_count", "field": "sections", "value": 3}], data) == {
        "min_count[sections]": True
    }
    assert _result([{"type": "min_count", "field": "sections", "value": 5}], data) == {
        "min_count[sections]": False
    }


def test_no_duplicates_flags_identical_blocks():
    data = {"sections": [{"heading": "A", "paragraphs": ["один и тот же текст тут"]},
                         {"heading": "B", "paragraphs": ["один и тот же текст тут"]}]}
    res = _result([{"type": "no_duplicates", "field": "sections", "threshold": 0.85}], data)
    assert res["no_duplicates[sections]"] is False


def test_no_duplicates_ok_for_distinct_blocks():
    data = {"sections": [{"paragraphs": ["альфа бета гамма дельта"]},
                         {"paragraphs": ["совершенно другой смысл и слова"]}]}
    res = _result([{"type": "no_duplicates", "field": "sections", "threshold": 0.85}], data)
    assert res["no_duplicates[sections]"] is True


def test_no_duplicates_single_block_passes():
    data = {"sections": [{"paragraphs": ["один блок"]}]}
    res = _result([{"type": "no_duplicates", "field": "sections"}], data)
    assert res["no_duplicates[sections]"] is True


def test_completeness_counts_brief_positions():
    brief = "Товары:\n1. Кофеварка\n2. Чайник\n3. Тостер"
    data = {"sections": [{}, {}, {}]}
    res = _result([{"type": "completeness", "field": "sections"}], data, brief=brief)
    assert res["completeness[sections]"] is True
    short = {"sections": [{}]}
    res2 = _result([{"type": "completeness", "field": "sections"}], short, brief=brief)
    assert res2["completeness[sections]"] is False


def test_has_sections_substring_match():
    data = {"sections": [{"heading": "1. Цель и назначение"},
                         {"heading": "5. Критерии приёмки"}]}
    checks = [{"type": "has_sections", "sections": ["цель", "критери"]}]
    assert _result(checks, data)["has_sections"] is True
    miss = [{"type": "has_sections", "sections": ["цель", "бюджет"]}]
    assert _result(miss, data)["has_sections"] is False


def test_no_placeholders_catches_handlebars_and_todo():
    bad = {"body": "Текст с {{переменной}} и TODO внутри"}
    assert _result([{"type": "no_placeholders"}], bad)["no_placeholders"] is False
    good = {"body": "Чистый готовый текст без заглушек"}
    assert _result([{"type": "no_placeholders"}], good)["no_placeholders"] is True


def test_no_ai_artifacts_catches_chatter_and_fences():
    bad = {"body": "Конечно, вот ваш текст для рассылки"}
    assert _result([{"type": "no_ai_artifacts"}], bad)["no_ai_artifacts"] is False
    fenced = {"body": "нормальный текст\n```\nутечка фенса\n```"}
    assert _result([{"type": "no_ai_artifacts"}], fenced)["no_ai_artifacts"] is False
    good = {"body": "Уважаемые клиенты, представляем новинку сезона."}
    assert _result([{"type": "no_ai_artifacts"}], good)["no_ai_artifacts"] is True


def test_char_range_bounds():
    data = {"body": "x" * 600}
    assert _result([{"type": "char_range", "min": 500, "max": 1000}], data)[
        "char_range[result]"
    ] is True
    assert _result([{"type": "char_range", "min": 700, "max": 1000}], data)[
        "char_range[result]"
    ] is False


def test_boilerplate_flags_cliches():
    bad = {"body": "В современном мире не секрет, что наша команда профессионалов "
                   "предлагает широкий спектр услуг на сегодняшний день."}
    res = _result([{"type": "boilerplate", "max_matches": 2}], bad)
    assert res["boilerplate"] is False
    good = {"body": "Собираем мебель за один выезд. Замер бесплатный, оплата после сборки."}
    res2 = _result([{"type": "boilerplate", "max_matches": 2}], good)
    assert res2["boilerplate"] is True


def test_vocabulary_richness_flags_repetitive_filler():
    poor = {"body": ("вода вода вода вода вода вода вода вода вода вода "
                     "вода вода вода вода вода вода вода вода вода вода")}
    res = _result([{"type": "vocabulary_richness", "min_ratio": 0.4}], poor)
    assert res["vocabulary_richness"] is False
    rich = {"body": ("Замер бесплатный, мастер приедет завтра. Соберём шкаф, "
                     "повесим полки, подключим технику — оплата после проверки результата.")}
    res2 = _result([{"type": "vocabulary_richness", "min_ratio": 0.4}], rich)
    assert res2["vocabulary_richness"] is True


def test_advisory_checks_do_not_flip_exit(tmp_path):
    # boilerplate failing while marked critical:false stays advisory in run_checks.
    bad = {"sections": [{"paragraphs": ["в современном мире " * 5]}]}
    out = validate.run_checks(bad, [{"type": "boilerplate", "critical": False, "max_matches": 1}])
    name, ok, _detail, critical = out[0]
    assert name == "boilerplate" and critical is False


def test_unknown_check_type_reported_as_failure():
    out = validate.run_checks({"a": 1}, [{"type": "bogus"}])
    assert out[0][1] is False  # ok == False
    assert "unknown" in out[0][0]
