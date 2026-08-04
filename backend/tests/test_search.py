import asyncio

from conftest import isolated_session

from app.config import settings
from app.models import ConceptPage, Project
from app.services.search import hybrid_search


def test_selected_page_is_included_and_discourse_is_excluded(monkeypatch) -> None:
    monkeypatch.setattr(settings, "embedding_enabled", False)
    db = isolated_session()
    project = Project(name="검색", slug="search", universe_namespace="world")
    db.add(project)
    db.flush()
    selected = ConceptPage(
        project_id=project.id,
        title="명시 선택",
        usage_role="PROJECT_CANON",
        authority_state="PROJECT_CANON",
        namespace="world",
    )
    matched = ConceptPage(
        project_id=project.id,
        title="검은 등대",
        summary="북부 항로의 검은 등대",
        usage_role="PROJECT_CANON",
        authority_state="PROJECT_CANON",
        namespace="world",
    )
    discourse = ConceptPage(
        project_id=project.id,
        title="검은 등대 참고 글",
        usage_role="DISCOURSE_REFERENCE",
        authority_state="DISCOURSE_REFERENCE",
        namespace="external",
    )
    db.add_all([selected, matched, discourse])
    db.commit()

    result = asyncio.run(
        hybrid_search(
            db,
            project_id=project.id,
            query="검은 등대",
            selected_page_ids=[selected.id],
        )
    )

    ids = [item["page_id"] for item in result["results"]]
    assert ids[0] == selected.id
    assert matched.id in ids
    assert discourse.id not in ids
