from conftest import isolated_session
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import get_db
from app.main import app
from app.models import LoreBlock, LoreDocument, LoreRevision, Project


def test_complete_draft_save_updates_adds_deletes_and_snapshots_blocks() -> None:
    db = isolated_session()

    def override_db():  # type: ignore[no-untyped-def]
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        project = Project(name="초안 편집", slug="draft-editing", universe_namespace="test")
        db.add(project)
        db.flush()
        document = LoreDocument(
            project_id=project.id,
            title="수정 전 제목",
            body_markdown="첫 문단\n\n삭제할 문단",
            body_json={"type": "doc", "content": []},
            document_kind="draft",
        )
        db.add(document)
        db.flush()
        first = LoreBlock(
            document_id=document.id,
            position=0,
            content_markdown="첫 문단",
            rhetorical_move="ORIENT",
            evidence_ids=["evidence-1"],
            certainty="EVIDENCED",
        )
        removed = LoreBlock(
            document_id=document.id,
            position=1,
            content_markdown="삭제할 문단",
            rhetorical_move="ANCHOR",
        )
        db.add_all([first, removed])
        db.commit()

        response = client.patch(
            f"/api/v1/documents/{document.id}/draft",
            json={
                "title": "수정된 제목",
                "status": "review",
                "blocks": [
                    {
                        "id": first.id,
                        "content_markdown": "수정된 첫 문단",
                        "rhetorical_move": "ORIENT",
                        "evidence_ids": ["evidence-1"],
                        "certainty": "EVIDENCED",
                        "locked": False,
                    },
                    {
                        "content_markdown": "새로 추가한 문단",
                        "rhetorical_move": "ANCHOR",
                        "evidence_ids": [],
                        "certainty": "CANDIDATE",
                        "locked": False,
                    },
                ],
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["document"]["title"] == "수정된 제목"
        assert payload["document"]["status"] == "review"
        assert payload["document"]["body_markdown"] == "수정된 첫 문단\n\n새로 추가한 문단"
        assert [block["position"] for block in payload["blocks"]] == [0, 1]
        assert [block["content_markdown"] for block in payload["blocks"]] == [
            "수정된 첫 문단",
            "새로 추가한 문단",
        ]
        assert payload["document"]["body_json"]["content"][1]["attrs"]["sourceRole"] == "CANDIDATE"
        assert db.get(LoreBlock, removed.id) is None
        revision = db.scalar(
            select(LoreRevision)
            .where(LoreRevision.document_id == document.id)
            .order_by(LoreRevision.revision_number.desc())
        )
        assert revision is not None
        assert revision.reason == "user_draft_save"
        assert revision.body_markdown == payload["document"]["body_markdown"]
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_locked_block_must_be_unlocked_before_edit_or_delete() -> None:
    db = isolated_session()

    def override_db():  # type: ignore[no-untyped-def]
        yield db

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        project = Project(name="잠금", slug="draft-lock", universe_namespace="test")
        db.add(project)
        db.flush()
        document = LoreDocument(project_id=project.id, title="잠금 초안", document_kind="draft")
        db.add(document)
        db.flush()
        block = LoreBlock(
            document_id=document.id,
            position=0,
            content_markdown="잠긴 내용",
            locked=True,
        )
        db.add(block)
        db.commit()

        response = client.patch(
            f"/api/v1/documents/{document.id}/draft",
            json={
                "title": document.title,
                "status": "draft",
                "blocks": [
                    {
                        "id": block.id,
                        "content_markdown": "몰래 바꾼 내용",
                        "locked": True,
                    }
                ],
            },
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "BLOCK_LOCKED"

        unlocked = client.patch(
            f"/api/v1/documents/{document.id}/draft",
            json={
                "title": document.title,
                "status": "draft",
                "blocks": [
                    {
                        "id": block.id,
                        "content_markdown": "잠금 해제 후 수정",
                        "locked": False,
                    }
                ],
            },
        )
        assert unlocked.status_code == 200
        assert unlocked.json()["blocks"][0]["content_markdown"] == "잠금 해제 후 수정"
    finally:
        app.dependency_overrides.clear()
        db.close()
