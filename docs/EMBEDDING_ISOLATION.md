# 임베딩 격리

Lore Studio는 기존 임베딩 **추론 endpoint만** 재사용할 수 있습니다. 벡터와 작업 상태는 `lore_studio_pgdata` 안의 `lore_vector.embedding_chunks`와 `lore_app.index_jobs`에만 저장하며 다른 앱의 DB, Qdrant collection, cache, volume을 읽거나 쓰지 않습니다.

격리 키는 `project_id + namespace + source_role + source_type + source_id + embedding_version + chunk_hash`입니다. `DISCOURSE_REFERENCE`는 별도 index scope이고 factual 검색에서 제외됩니다. 명시 선택 페이지는 검색 점수와 무관하게 포함되며, 후보·참고 문서는 정사 근거로 자동 합류하지 않습니다.

모델/차원/version이 바뀌면 `.env`의 `EMBEDDING_VERSION`을 바꾸고 `make reindex`를 실행합니다. 작업은 PENDING/RUNNING/COMPLETED/FAILED 상태와 오류를 남기며 페이지 재색인 시 이전 버전 청크를 정리합니다. `EMBEDDING_ENABLED=false`에서는 lexical 검색으로 정상 축소됩니다.
