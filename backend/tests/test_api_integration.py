from conftest import isolated_session
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import AuditLog, LoreDocument, Project, WritingRecipe


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
        cover = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB"
        cover_response = client.patch(
            f"/api/v1/projects/{project_id}",
            json={
                "settings_json": {
                    "canon_policy": "user_approved_only",
                    "cover_image": cover,
                    "cover_image_name": "cover.png",
                }
            },
        )
        assert cover_response.status_code == 200
        assert cover_response.json()["settings_json"]["cover_image"] == cover
        invalid_cover = client.patch(
            f"/api/v1/projects/{project_id}",
            json={"settings_json": {"cover_image": "https://example.com/cover.jpg"}},
        )
        assert invalid_cover.status_code == 422
        starter_categories = client.get(
            "/api/v1/categories", params={"project_id": project_id}
        ).json()
        assert {item["name"] for item in starter_categories} >= {
            "인물",
            "장소",
            "사건",
            "유물·기술",
            "자유 페이지",
        }

        category_response = client.post(
            "/api/v1/categories",
            json={
                "project_id": project_id,
                "name": "현상",
                "template_json": {},
            },
        )
        assert category_response.status_code == 201
        category = category_response.json()
        assert category["key"].startswith("custom-")
        assert "현상" in {
            item["name"]
            for item in client.get(
                "/api/v1/categories", params={"project_id": project_id}
            ).json()
        }

        page_response = client.post(
            "/api/v1/concept-pages",
            json={
                "project_id": project_id,
                "title": "빈 필드도 저장되는 자유 본문",
                "category_key": category["key"],
                "usage_role": "CANDIDATE",
                "body_json": {
                    "type": "doc",
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": "본문"}]}],
                },
            },
        )
        assert page_response.status_code == 201
        page_id = page_response.json()["id"]

        renamed = client.patch(
            f"/api/v1/categories/{category['id']}", json={"name": "초자연 현상"}
        )
        assert renamed.status_code == 200
        assert renamed.json()["key"] == category["key"]
        assert client.get(f"/api/v1/concept-pages/{page_id}").json()["category_key"] == category["key"]

        used_delete = client.delete(f"/api/v1/categories/{category['id']}")
        assert used_delete.status_code == 409
        assert used_delete.json()["detail"]["code"] == "CATEGORY_IN_USE"

        other_project = client.post(
            "/api/v1/projects", json={"name": "다른 세계", "slug": "other-world"}
        ).json()
        cross_project_category = client.post(
            "/api/v1/concept-pages",
            json={
                "project_id": other_project["id"],
                "title": "잘못된 분류 연결",
                "category_key": category["key"],
            },
        )
        assert cross_project_category.status_code == 422
        assert cross_project_category.json()["detail"]["code"] == "PROJECT_CATEGORY_REQUIRED"

        unused = client.post(
            "/api/v1/categories",
            json={"project_id": project_id, "name": "임시 종류"},
        ).json()
        assert client.delete(f"/api/v1/categories/{unused['id']}").status_code == 204

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
                "name": "API 레시피",
                "recipe_json": {
                    "pattern_preview": ["맥락", "핵심", "의미"],
                    "required_moves": ["ORIENT", "ANCHOR", "INTERPRET"],
                    "optional_moves": [],
                    "moves": [
                        {"id": "ORIENT", "purpose": "맥락을 설명한다."},
                        {"id": "ANCHOR", "purpose": "핵심 사실을 제시한다."},
                        {"id": "INTERPRET", "purpose": "의미를 해석한다."},
                    ],
                    "planner_rules": [],
                    "audit_rules": [],
                },
            },
        )
        assert recipe_response.status_code == 201
        assert recipe_response.json()["version"] == "1.0.0"
        assert recipe_response.json()["key"].startswith("custom-")
        assert recipe_response.json()["recipe_json"]["key"] == recipe_response.json()["key"]
        assert recipe_response.json()["recipe_json"]["version"] == "1.0.0"
        assert recipe_response.json()["recipe_json"]["pattern_preview"] == [
            "배경 설명",
            "핵심 사실 제시",
            "의미 해설",
        ]
        assert recipe_response.json()["recipe_json"]["moves"][0]["purpose"] == (
            "독자가 상황을 이해하도록 장소·시대·배경부터 설명합니다."
        )

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

        project_session = client.post(
            "/api/v1/playbook-sessions",
            json={
                "project_id": project_id,
                "writing_recipe_id": recipe_response.json()["id"],
            },
        )
        assert project_session.status_code == 201

        versioned_recipe = client.patch(
            f"/api/v1/writing-recipes/{recipe_response.json()['id']}",
            json={"name": "API 레시피 개정"},
        )
        assert versioned_recipe.status_code == 200
        assert versioned_recipe.json()["id"] != recipe_response.json()["id"]
        assert versioned_recipe.json()["version"] == "1.0.1"
        assert versioned_recipe.json()["recipe_json"]["version"] == "1.0.1"
        assert project_session.json()["writing_recipe_id"] == recipe_response.json()["id"]
        assert {
            item["name"]
            for item in client.get(
                "/api/v1/writing-recipes", params={"project_id": project_id}
            ).json()
        } == {"API 레시피 개정", "공유 전개 방식"}

        rejected_session = client.post(
            "/api/v1/playbook-sessions",
            json={
                "project_id": other_project["id"],
                "writing_recipe_id": recipe_response.json()["id"],
            },
        )
        assert rejected_session.status_code == 422
        assert rejected_session.json()["detail"]["code"] == "PROJECT_WRITING_RECIPE_REQUIRED"

        accepted_session = client.post(
            "/api/v1/playbook-sessions",
            json={
                "project_id": project_id,
                "writing_recipe_id": shared_recipe.id,
            },
        )
        assert accepted_session.status_code == 201

        used_recipe_delete = client.delete(
            f"/api/v1/writing-recipes/{recipe_response.json()['id']}"
        )
        assert used_recipe_delete.status_code == 409
        assert used_recipe_delete.json()["detail"]["code"] == "WRITING_RECIPE_IN_USE"
        assert client.delete(f"/api/v1/projects/{project_id}").status_code == 204
        assert client.get(f"/api/v1/projects/{project_id}").status_code == 404
        project_audit = db.query(AuditLog).filter_by(
            entity_id=project_id, entity_type="Project", action="DELETE"
        ).one()
        assert project_audit.before_json["name"] == "API 통합"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_lorebook_delete_keeps_source_draft_and_records_audit() -> None:
    db = isolated_session()

    def override_db():  # type: ignore[no-untyped-def]
        yield db

    project = Project(name="로어북 삭제", slug="lorebook-delete")
    db.add(project)
    db.flush()
    draft = LoreDocument(
        project_id=project.id,
        title="보존할 초안",
        body_markdown="초안 본문",
        document_kind="draft",
    )
    db.add(draft)
    db.flush()
    entry = LoreDocument(
        project_id=project.id,
        title="삭제할 완성본",
        body_markdown="완성본 본문",
        document_kind="lorebook",
        source_document_id=draft.id,
    )
    db.add(entry)
    db.commit()
    draft_id, entry_id = draft.id, entry.id

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        response = client.delete(f"/api/v1/lorebook/{entry_id}")
        assert response.status_code == 204
        assert db.get(LoreDocument, entry_id) is None
        assert db.get(LoreDocument, draft_id) is not None
        audit = db.query(AuditLog).filter_by(entity_id=entry_id, action="DELETE").one()
        assert audit.before_json["source_document_id"] == draft_id
    finally:
        app.dependency_overrides.clear()
        db.close()
