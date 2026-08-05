from conftest import isolated_session
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import WritingRecipe


def test_project_category_page_recipe_and_authority_api() -> None:
    db = isolated_session()

    def override_db():  # type: ignore[no-untyped-def]
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        project_response = client.post(
            "/api/v1/projects",
            json={"name": "API 통합", "slug": "api-integration", "universe_namespace": "test"},
        )
        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        category_response = client.post(
            "/api/v1/categories",
            json={
                "project_id": project_id,
                "key": "phenomenon",
                "name": "현상",
                "template_json": {"fields": []},
            },
        )
        assert category_response.status_code == 201
        assert client.get("/api/v1/categories", params={"project_id": project_id}).json()[0]["name"] == "현상"

        page_response = client.post(
            "/api/v1/concept-pages",
            json={
                "project_id": project_id,
                "title": "빈 필드도 저장되는 자유 본문",
                "category_key": "phenomenon",
                "usage_role": "CANDIDATE",
                "body_json": {
                    "type": "doc",
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": "본문"}]}],
                },
            },
        )
        assert page_response.status_code == 201
        page_id = page_response.json()["id"]

        direct_canon = client.patch(
            f"/api/v1/concept-pages/{page_id}", json={"usage_role": "PROJECT_CANON"}
        )
        assert direct_canon.status_code == 409
        assert direct_canon.json()["detail"]["code"] == "AUTHORITY_TRANSITION_REQUIRES_PROMOTION"

        draft = client.post(
            f"/api/v1/concept-pages/{page_id}/promote",
            json={"target_state": "DRAFT_SETTING", "reason": "사용자 검토"},
        )
        assert draft.status_code == 200
        canon = client.post(
            f"/api/v1/concept-pages/{page_id}/promote",
            json={"target_state": "PROJECT_CANON", "reason": "사용자 최종 승인"},
        )
        assert canon.status_code == 200

        recipe_response = client.post(
            "/api/v1/writing-recipes",
            json={
                "project_id": project_id,
                "key": "api-recipe",
                "version": "1.0.0",
                "name": "API 레시피",
                "recipe_json": {"moves": ["ORIENT", "ANCHOR"]},
            },
        )
        assert recipe_response.status_code == 201
        assert recipe_response.json()["version"] == "1.0.0"

        shared_recipe = WritingRecipe(
            project_id=None,
            key="shared-pattern",
            version="1.0.0",
            name="공유 전개 방식",
            recipe_json={"pattern_preview": ["시작", "전환", "결말"]},
            is_builtin=True,
            approved=True,
        )
        db.add(shared_recipe)
        db.commit()

        shared_list = client.get("/api/v1/writing-recipes")
        assert shared_list.status_code == 200
        assert [item["name"] for item in shared_list.json()] == ["공유 전개 방식"]

        project_list = client.get(
            "/api/v1/writing-recipes", params={"project_id": project_id}
        )
        assert {item["name"] for item in project_list.json()} == {
            "API 레시피",
            "공유 전개 방식",
        }

        rejected_session = client.post(
            "/api/v1/playbook-sessions",
            json={
                "project_id": project_id,
                "writing_recipe_id": recipe_response.json()["id"],
            },
        )
        assert rejected_session.status_code == 422
        assert rejected_session.json()["detail"]["code"] == "SHARED_WRITING_RECIPE_REQUIRED"

        accepted_session = client.post(
            "/api/v1/playbook-sessions",
            json={
                "project_id": project_id,
                "writing_recipe_id": shared_recipe.id,
            },
        )
        assert accepted_session.status_code == 201
    finally:
        app.dependency_overrides.clear()
        db.close()
