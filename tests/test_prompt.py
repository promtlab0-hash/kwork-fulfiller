"""The quality standard must reach every prompt build_prompt produces."""

import fulfill


def test_quality_standard_injected():
    niche = fulfill.load_niche("price_list")
    prompt = fulfill.build_prompt(niche, "Товары:\n1. Кофеварка\n2. Чайник")
    assert "Стандарт качества текста" in prompt
    # A concrete cliché from the blacklist is spelled out for the model.
    assert "в современном мире" in prompt
    # The brief and the niche template are still present.
    assert "Кофеварка" in prompt
    assert "прайс-лист" in prompt.lower()


def test_quality_standard_in_every_niche():
    for niche_id, _ in fulfill.list_niches():
        niche = fulfill.load_niche(niche_id)
        prompt = fulfill.build_prompt(niche, "тестовый бриф из одной строки")
        assert "Стандарт качества текста" in prompt, niche_id


def test_common_advisory_are_non_blocking():
    # Both advisory checks must be declared critical: False.
    assert all(c["critical"] is False for c in fulfill.COMMON_ADVISORY)
    types = {c["type"] for c in fulfill.COMMON_ADVISORY}
    assert types == {"boilerplate", "vocabulary_richness"}
