from collections.abc import Awaitable, Callable

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base


class HandlerTransport(httpx.AsyncBaseTransport):
    def __init__(self, handler: Callable[[httpx.Request], Awaitable[httpx.Response]]) -> None:
        self.handler = handler

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return await self.handler(request)


def isolated_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        execution_options={"schema_translate_map": {"lore_app": None, "lore_vector": None}},
    )
    Base.metadata.create_all(engine)
    return Session(engine)
