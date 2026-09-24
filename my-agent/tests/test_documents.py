"""Reading resumes and job descriptions from the local document store."""

import pytest

from workflows.documents import DocumentNotFoundError, DocumentStore


@pytest.fixture
def store(tmp_path):
    (tmp_path / "resumes").mkdir()
    (tmp_path / "resumes" / "ada.md").write_text(
        "\n  Backend engineer, ten years.  \n", encoding="utf-8"
    )
    return DocumentStore(tmp_path)


def test_reads_and_strips_a_nested_document(store):
    assert store.read("resumes/ada.md") == "Backend engineer, ten years."


def test_missing_document_is_reported(store):
    with pytest.raises(DocumentNotFoundError, match=r"missing\.md"):
        store.read("missing.md")


def test_empty_document_is_reported(tmp_path):
    (tmp_path / "blank.md").write_text("   \n", encoding="utf-8")

    with pytest.raises(DocumentNotFoundError, match="empty"):
        DocumentStore(tmp_path).read("blank.md")


def test_a_directory_is_not_a_document(tmp_path):
    (tmp_path / "resumes").mkdir()

    with pytest.raises(DocumentNotFoundError):
        DocumentStore(tmp_path).read("resumes")


@pytest.mark.parametrize(
    "ref", ["../outside.md", "resumes/../../outside.md", "/etc/hostname"]
)
def test_references_cannot_climb_out_of_the_store(tmp_path, ref):
    outside = tmp_path.parent / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    root = tmp_path / "documents"
    root.mkdir()

    with pytest.raises(DocumentNotFoundError):
        DocumentStore(root).read(ref)


def test_a_sibling_directory_is_not_inside_the_store(tmp_path):
    (tmp_path / "documents").mkdir()
    (tmp_path / "documents-other").mkdir()
    (tmp_path / "documents-other" / "secret.md").write_text("x", encoding="utf-8")

    with pytest.raises(DocumentNotFoundError):
        DocumentStore(tmp_path / "documents").read("../documents-other/secret.md")
