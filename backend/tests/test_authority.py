import pytest
from conftest import isolated_session

from app.models import AuditLog, ConceptPage, Project
from app.services.authority import AuthorityTransitionError, promote_page


def test_candidate_cannot_jump_to_project_canon() -> None:
    db = isolated_session()
    project = Project(name="권위", slug="authority")
    db.add(project)
    db.flush()
    page = ConceptPage(
        project_id=project.id,
        title="모델 제안",
        usage_role="CANDIDATE",
        authority_state="CANDIDATE",
    )
    db.add(page)
    db.commit()

    with pytest.raises(AuthorityTransitionError):
        promote_page(db, page, target_state="PROJECT_CANON", reason="건너뛰기")

    db.refresh(page)
    assert page.authority_state == "CANDIDATE"


def test_explicit_two_step_promotion_is_audited() -> None:
    db = isolated_session()
    project = Project(name="권위", slug="authority-two")
    db.add(project)
    db.flush()
    page = ConceptPage(
        project_id=project.id,
        title="승인 후보",
        usage_role="CANDIDATE",
        authority_state="CANDIDATE",
    )
    db.add(page)
    db.commit()

    promote_page(db, page, target_state="DRAFT_SETTING", reason="초안 승인")
    promote_page(db, page, target_state="PROJECT_CANON", reason="정사 승인")

    assert page.authority_state == "PROJECT_CANON"
    assert page.usage_role == "PROJECT_CANON"
    assert db.query(AuditLog).filter_by(entity_id=page.id).count() == 2
