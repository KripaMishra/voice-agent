import pytest

from prompts import PromptCatalog, PromptNotFoundError, catalog


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


def test_renders_a_prompt_with_values(tmp_path):
    (tmp_path / "greet.md").write_text("Hello $name.", encoding="utf-8")

    assert PromptCatalog(tmp_path).render("greet", name="Ada") == "Hello Ada."


def test_rendering_reports_a_value_the_prompt_needs(tmp_path):
    (tmp_path / "greet.md").write_text("Hello $name.", encoding="utf-8")

    with pytest.raises(KeyError):
        PromptCatalog(tmp_path).render("greet")


def test_the_shipped_checklist_prompt_renders_without_leftover_placeholders():
    rendered = catalog.render(
        "checklist_generation", budget_seconds=300, capacity=5, pool=10
    )

    assert "300 seconds" in rendered
    assert "about 5 questions" in rendered
    assert "about 10 questions" in rendered
    assert "$" not in rendered


def test_the_shipped_interviewer_prompt_renders_without_leftover_placeholders():
    rendered = catalog.render("interviewer", budget=300, checklist="- [abc] Why?")

    assert "300 seconds" in rendered
    assert "- [abc] Why?" in rendered
    assert "$" not in rendered


def test_the_shipped_evaluation_prompt_has_no_placeholders_to_fill():
    assert "$" not in catalog.load("evaluation")
