"""Candidate endpoints."""

import pytest


def add_candidate(client, **overrides):
    payload = {"name": "Ada Lovelace", "email": "ada@example.com"}
    payload.update(overrides)
    return client.post("/candidate/add", json=payload)


def test_add_returns_the_created_candidate(api_client):
    response = add_candidate(api_client, resume_ref="resumes/ada.pdf")

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Ada Lovelace"
    assert body["email"] == "ada@example.com"
    assert body["resume_ref"] == "resumes/ada.pdf"
    assert body["id"]


def test_add_defaults_resume_ref_to_null(api_client):
    assert add_candidate(api_client).json()["resume_ref"] is None


def test_add_rejects_a_duplicate_email(api_client):
    add_candidate(api_client)
    response = add_candidate(api_client, name="Someone Else")

    assert response.status_code == 409
    assert "email" in response.json()["detail"]


@pytest.mark.parametrize("email", ["not-an-email", "missing@domain", ""])
def test_add_rejects_an_unusable_email(api_client, email):
    assert add_candidate(api_client, email=email).status_code == 422


def test_add_rejects_a_blank_name(api_client):
    assert add_candidate(api_client, name="").status_code == 422


def test_add_rejects_unknown_fields(api_client):
    assert add_candidate(api_client, nickname="Ada").status_code == 422


def test_get_returns_a_single_candidate(api_client):
    candidate_id = add_candidate(api_client, resume_ref="resumes/ada.pdf").json()["id"]

    body = api_client.get(f"/candidate/{candidate_id}").json()

    assert body["id"] == candidate_id
    assert body["name"] == "Ada Lovelace"
    assert body["resume_ref"] == "resumes/ada.pdf"


def test_get_unknown_candidate_is_not_found(api_client):
    assert api_client.get("/candidate/nope").status_code == 404


def test_list_is_not_shadowed_by_the_single_candidate_route(api_client):
    add_candidate(api_client)

    assert isinstance(api_client.get("/candidate/list").json(), list)


def test_list_is_empty_before_anything_is_added(api_client):
    assert api_client.get("/candidate/list").json() == []


def test_list_returns_candidates_ordered_by_name(api_client):
    add_candidate(api_client, name="Zoe", email="zoe@example.com")
    add_candidate(api_client, name="Ada", email="ada2@example.com")

    names = [item["name"] for item in api_client.get("/candidate/list").json()]
    assert names == ["Ada", "Zoe"]


def test_patch_updates_a_single_field(api_client):
    candidate_id = add_candidate(api_client).json()["id"]

    response = api_client.patch(f"/candidate/{candidate_id}", json={"name": "Ada King"})

    assert response.status_code == 200
    assert response.json()["name"] == "Ada King"
    assert response.json()["email"] == "ada@example.com"


def test_patch_can_clear_the_resume_ref(api_client):
    candidate_id = add_candidate(api_client, resume_ref="resumes/ada.pdf").json()["id"]

    response = api_client.patch(f"/candidate/{candidate_id}", json={"resume_ref": None})

    assert response.json()["resume_ref"] is None


def test_patch_leaves_omitted_fields_alone(api_client):
    candidate_id = add_candidate(api_client, resume_ref="resumes/ada.pdf").json()["id"]

    before = api_client.get("/candidate/list").json()[0]
    after = api_client.patch(f"/candidate/{candidate_id}", json={}).json()

    assert after == before


def test_patch_rejects_a_duplicate_email(api_client):
    add_candidate(api_client, email="taken@example.com")
    candidate_id = add_candidate(api_client).json()["id"]

    response = api_client.patch(
        f"/candidate/{candidate_id}", json={"email": "taken@example.com"}
    )

    assert response.status_code == 409


def test_patch_unknown_candidate_is_not_found(api_client):
    assert api_client.patch("/candidate/nope", json={"name": "X"}).status_code == 404


def test_delete_removes_the_candidate(api_client):
    candidate_id = add_candidate(api_client).json()["id"]

    assert api_client.delete(f"/candidate/{candidate_id}").status_code == 204
    assert api_client.get("/candidate/list").json() == []


def test_delete_unknown_candidate_is_not_found(api_client):
    assert api_client.delete("/candidate/nope").status_code == 404


def test_a_failed_update_does_not_leak_into_the_next_request(api_client):
    add_candidate(api_client, email="taken@example.com")
    candidate_id = add_candidate(api_client).json()["id"]

    failed = api_client.patch(
        f"/candidate/{candidate_id}", json={"email": "taken@example.com"}
    )
    assert failed.status_code == 409

    listed = {item["id"]: item for item in api_client.get("/candidate/list").json()}
    assert listed[candidate_id]["email"] == "ada@example.com"
