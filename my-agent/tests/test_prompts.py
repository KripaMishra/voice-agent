import pytest

from prompts import PromptCatalog, PromptNotFoundError


def test_loads_and_strips_prompt_text(tmp_path):
    (tmp_path / "greeting.md").write_text("\n  Hello there.  \n\n", encoding="utf-8")
    assert PromptCatalog(tmp_path).load("greeting") == "Hello there."


def test_lists_names_as_sorted_stems(tmp_path):
    for name in ["beta", "alpha"]:
        (tmp_path / f"{name}.md").write_text("text", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")
    assert PromptCatalog(tmp_path).names() == ["alpha", "beta"]


def test_missing_prompt_reports_what_is_available(tmp_path):
    (tmp_path / "greeting.md").write_text("Hello", encoding="utf-8")
    with pytest.raises(PromptNotFoundError) as excinfo:
        PromptCatalog(tmp_path).load("missing")
    assert "missing" in str(excinfo.value)
    assert "greeting" in str(excinfo.value)


def test_missing_prompt_with_empty_catalog_says_none(tmp_path):
    with pytest.raises(PromptNotFoundError, match="none"):
        PromptCatalog(tmp_path).load("missing")


def test_empty_prompt_is_rejected(tmp_path):
    (tmp_path / "blank.md").write_text("   \n", encoding="utf-8")
    with pytest.raises(PromptNotFoundError, match="blank"):
        PromptCatalog(tmp_path).load("blank")


def test_prompt_lookup_does_not_fall_back_to_other_suffixes(tmp_path):
    (tmp_path / "greeting.txt").write_text("Hello", encoding="utf-8")
    with pytest.raises(PromptNotFoundError):
        PromptCatalog(tmp_path).load("greeting")
