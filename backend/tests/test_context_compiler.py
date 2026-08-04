from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import ConceptPage, DirectionCard, PlaybookSession, Project, WritingRecipe
from app.services.context_compiler import compile_context, tiptap_to_text


def make_db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_tiptap_to_text_extracts_nested_text() -> None:
    doc = {
        "type": "doc",
        "content": [
            {"type": "heading", "content": [{"type": "text", "text": "제목"}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "본문"}]},
        ],
    }
    text = tiptap_to_text(doc)
    assert "제목" in text
    assert "본문" in text


def test_context_separates_facts_and_discourse_references() -> None:
    db = make_db()
    project = Project(name="테스트", slug="test", universe_namespace="world-a")
    recipe = WritingRecipe(
        key="progressive_exposition",
        version="1.0.0",
        name="점층형",
        recipe_json={"key": "progressive_exposition", "required_moves": ["ORIENT", "ANCHOR"]},
        is_builtin=True,
    )
    db.add_all([project, recipe])
    db.flush()

    fact = ConceptPage(
        project_id=project.id,
        title="검은 등대",
        usage_role="PROJECT_CANON",
        namespace="world-a",
        summary="항로를 유지하는 시설",
        locked_facts=["북부 항로에 존재한다"],
        open_questions=["기억은 어디로 가는가"],
        body_json={"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "등대 본문"}]}]},
    )
    reference = ConceptPage(
        project_id=project.id,
        title="좋아하는 설정 글",
        usage_role="DISCOURSE_REFERENCE",
        namespace="external-ip",
        summary="점층적 설명 방식 참고",
        body_json={"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "외부 IP 사실"}]}]},
    )
    card = DirectionCard(project_id=project.id, title="의존", body="해결책이 의존으로 변한다")
    db.add_all([fact, reference, card])
    db.flush()

    session = PlaybookSession(
        project_id=project.id,
        writing_recipe_id=recipe.id,
        concept_slots={"subject": [fact.id], "references": [reference.id]},
        direction_card_ids=[card.id],
        settings_json={"context_depth": "balanced"},
    )
    db.add(session)
    db.commit()

    pack = compile_context(db, session)
    assert [item["title"] for item in pack["selected_concepts"]] == ["검은 등대"]
    assert [item["title"] for item in pack["discourse_or_inspiration_references"]] == ["좋아하는 설정 글"]
    assert pack["locked_facts"][0]["fact"] == "북부 항로에 존재한다"
    assert pack["policy"]["reference_facts_are_forbidden"] is True
