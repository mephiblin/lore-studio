import asyncio
import json

import pytest

from app.config import settings
from app.services.model_gateway import ModelGateway
from app.services.utility_tools import analyze_image


@pytest.mark.skipif(not settings.run_local_model_tests, reason="RUN_LOCAL_MODEL_TESTS=true에서만 실행")
def test_real_writer_and_utility_profiles() -> None:
    gateway = ModelGateway()

    async def run() -> None:
        writer = await gateway.complete(
            [{"role": "user", "content": "한국어로 '연결 성공'만 답하라."}],
            role="writer",
            temperature=0,
            max_tokens=24,
        )
        assert writer.content.strip()
        utility = await gateway.complete(
            [
                {"role": "system", "content": "JSON 객체만 출력한다."},
                {"role": "user", "content": "status 값이 ok인 객체를 출력하라."},
            ],
            role="utility",
            temperature=0,
            max_tokens=80,
            response_mode="json_object",
        )
        assert json.loads(utility.content)["status"] == "ok"

    asyncio.run(run())


@pytest.mark.skipif(not settings.run_embedding_tests, reason="RUN_EMBEDDING_TESTS=true에서만 실행")
def test_real_embedding_profile() -> None:
    vectors, metadata = asyncio.run(ModelGateway().embed(["검은 등대는 북부 항로를 지킨다."]))
    assert len(vectors) == 1
    assert len(vectors[0]) == settings.embedding_dimension
    assert metadata["model"]


@pytest.mark.skipif(not settings.run_vision_tests, reason="RUN_VISION_TESTS=true에서만 실행")
def test_real_vision_profile() -> None:
    one_pixel_png = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    suggestion, result = asyncio.run(
        analyze_image(ModelGateway(), one_pixel_png, "이미지를 간단히 설명하고 불확실성을 표시하라.")
    )
    assert suggestion["caption"]
    assert result.role == "vision"
