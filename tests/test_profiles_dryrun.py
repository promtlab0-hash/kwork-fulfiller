"""Every profile must pass its own checks on its sample brief in --dry-run.

This is the regression net for profile/stub/check drift (e.g. the content_plan
rows-vs-sections mismatch): if a check no longer matches what the stub emits,
the dry-run exit code flips to 1 and this test fails.
"""

import pathlib

import pytest

import fulfill

ROOT = pathlib.Path(fulfill.__file__).resolve().parent
NICHE_IDS = [nid for nid, _ in fulfill.list_niches()]


def test_all_ten_profiles_present():
    assert len(NICHE_IDS) == 10, f"ожидалось 10 профилей, найдено {NICHE_IDS}"


@pytest.mark.parametrize("niche_id", NICHE_IDS)
def test_profile_dry_run_passes(niche_id, tmp_path):
    sample = ROOT / "samples" / f"{niche_id}.txt"
    assert sample.exists(), f"нет образца брифа: {sample}"
    code = fulfill.run(
        niche_id=niche_id,
        brief_arg=str(sample),
        out_dir=str(tmp_path),
        overrides={},
        dry_run=True,
    )
    assert code == 0, f"профиль {niche_id} провалил dry-run (код {code})"
    produced = list(tmp_path.glob(f"{niche_id}*"))
    assert produced, f"профиль {niche_id} не создал файл результата"


def test_empty_brief_returns_code_2(tmp_path):
    code = fulfill.run("price_list", "   ", str(tmp_path), {}, dry_run=True)
    assert code == 2
