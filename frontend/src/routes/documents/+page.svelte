<script>
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import ProjectCreator from '$lib/components/ProjectCreator.svelte';
  import { api, API_BASE } from '$lib/api';
  import { auditTypeLabels, certaintyLabels, documentStatusLabels, moveLabels } from '$lib/labels';
  import { initialProjectId, rememberProject } from '$lib/project';

  let projects = [];
  let projectId = '';
  let documents = [];
  let selected = null;
  let blocks = [];
  let audits = [];
  let candidates = [];
  let pages = [];
  let busy = '';
  let error = '';
  let message = '';
  let rewriteOperation = 'shorter';
  let rewriteInstruction = '';
  let activeProposal = null;
  let documentStage = 'draft';
  let finalization = null;
  let finalInstruction = '';

  const settingValueLabels = {
    short: '짧게', normal: '보통', long: '길게', very_long: '매우 길게', custom: '직접 지정',
    omniscient: '전지적 설명자', first_observer: '1인칭 관찰자', third_limited: '3인칭 제한',
    present: '현재형 중심', past: '과거형 중심',
    core: '선택한 핵심만', balanced: '관련 자료까지 균형 있게', wide: '세계 맥락을 넓게', max: '가능한 자료를 최대로',
    strict: '새 설정 제안 안 함', conservative: '새 설정 제안 최소한', free: '새 설정 제안 적극적'
  };

  onMount(loadInitial);

  async function loadInitial() {
    try {
      projects = await api.get('/projects');
      if (projects.length) {
        projectId = initialProjectId(projects);
        await loadDocuments();
      }
    } catch (e) { error = e.message; }
  }

  async function loadDocuments() {
    if (!projectId) return;
    error = '';
    try {
      rememberProject(projectId);
      [documents, candidates, pages] = await Promise.all([
        api.get(`/documents?project_id=${projectId}`),
        api.get(`/candidates?project_id=${projectId}`),
        api.get(`/concept-pages?project_id=${projectId}`)
      ]);
      const requestedId = $page.url.searchParams.get('document');
      await selectDocument(documents.find((document) => document.id === requestedId) || documents[0] || null);
    } catch (e) { error = e.message; }
  }

  async function projectCreated(project) {
    projects = [project, ...projects];
    projectId = project.id;
    await loadDocuments();
  }

  function evidenceName(id) {
    return pages.find((page) => page.id === id)?.title || '삭제된 자료';
  }

  async function selectDocument(document) {
    selected = document ? { ...document } : null;
    activeProposal = null;
    documentStage = 'draft';
    finalInstruction = '';
    finalization = null;
    if (!selected) { blocks = []; audits = []; return; }
    busy = '문서 불러오는 중';
    try {
      [blocks, audits, finalization] = await Promise.all([
        api.get(`/documents/${selected.id}/blocks`),
        api.get(`/documents/${selected.id}/audits`),
        api.get(`/documents/${selected.id}/finalization`).catch((e) => ({ status: 'unavailable', inputs: {}, error: e.message }))
      ]);
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  async function saveDocument() {
    if (!selected) return;
    busy = '문서 저장 중'; error = ''; message = '';
    try {
      selected = await api.patch(`/documents/${selected.id}`, { title: selected.title, status: selected.status });
      documents = documents.map((item) => item.id === selected.id ? selected : item);
      message = '문서를 저장했습니다.';
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  async function saveBlock(block) {
    busy = '문단 저장 중'; error = '';
    try {
      const updated = await api.patch(`/blocks/${block.id}`, {
        content_markdown: block.content_markdown,
        rhetorical_move: block.rhetorical_move,
        evidence_ids: block.evidence_ids,
        certainty: block.certainty,
        locked: block.locked
      });
      blocks = blocks.map((item) => item.id === updated.id ? updated : item);
      finalization = await api.get(`/documents/${selected.id}/finalization`).catch(() => finalization);
      message = '문단을 저장했습니다.';
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  async function proposeRewrite(block) {
    busy = 'AI가 원문을 보존한 변경안을 작성하는 중'; error = ''; activeProposal = null;
    try {
      activeProposal = await api.post(`/blocks/${block.id}/rewrite`, {
        operation: rewriteOperation,
        instruction: rewriteInstruction,
        direction_card_ids: []
      });
      audits = [activeProposal, ...audits.filter((item) => item.id !== activeProposal.id)];
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  async function decideProposal(action) {
    if (!activeProposal) return;
    busy = action === 'apply' ? '변경안 적용 중' : '변경안 폐기 중';
    try {
      const updated = await api.post(`/audits/${activeProposal.id}/${action}`, {});
      audits = audits.map((item) => item.id === updated.id ? updated : item);
      activeProposal = null;
      if (action === 'apply') await selectDocument(selected);
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  async function decideCandidate(candidate, decision) {
    busy = '후보 처리 중';
    try {
      const updated = await api.post(`/candidates/${candidate.id}/decide`, { decision, reason: '문서 검토 화면에서 사용자 승인' });
      candidates = candidates.map((item) => item.id === updated.id ? updated : item);
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  async function extractNewCandidates() {
    if (!selected) return;
    busy = 'AI가 원고에서 새 설정 후보를 찾는 중'; error = '';
    try {
      const created = await api.post(`/documents/${selected.id}/extract-candidates`, {});
      candidates = [...created, ...candidates];
      message = `${created.length}개의 후보를 추출했습니다. 아직 정사에는 반영되지 않았습니다.`;
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  function settingValue(value, field = '') {
    if (field === 'context_depth' && value === 'balanced') return '관련 자료까지 균형 있게';
    if (field === 'creativity' && value === 'balanced') return '새 설정 제안이 필요할 때';
    return settingValueLabels[value] || value || '지정 안 함';
  }

  function lengthValue(settings = {}) {
    return settings.length === 'custom' && settings.custom_length
      ? `직접 지정 · ${Number(settings.custom_length).toLocaleString()}자`
      : settingValue(settings.length);
  }

  async function finalizeDocument() {
    if (!selected) return;
    busy = selected.final_body_markdown ? 'Writer가 완성본을 다시 다듬는 중' : 'Writer가 초안을 한 편의 글로 다듬는 중';
    error = ''; message = '';
    try {
      finalization = await api.post(`/documents/${selected.id}/finalize`, { instruction: finalInstruction });
      selected = { ...finalization.document };
      documents = documents.map((item) => item.id === selected.id ? selected : item);
      message = '완성본을 만들었습니다. 초안은 그대로 보존됩니다.';
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  async function saveFinalBody() {
    if (!selected?.final_body_markdown?.trim()) return;
    busy = '완성본 저장 중'; error = ''; message = '';
    try {
      finalization = await api.patch(`/documents/${selected.id}/final`, { body_markdown: selected.final_body_markdown });
      selected = { ...finalization.document };
      documents = documents.map((item) => item.id === selected.id ? selected : item);
      message = '완성본을 저장했습니다.';
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }
</script>

<div class="page">
  <div class="page-header">
    <div><p class="eyebrow">원고 편집</p><h1>초안을 고치고, 한 편의 글로 완성합니다.</h1><p>문단별 초안을 편집한 뒤 전체 흐름을 다시 다듬어 완성본을 만듭니다.</p></div>
    <div class="project-tools"><label style="min-width:260px">현재 프로젝트<select bind:value={projectId} on:change={loadDocuments}>{#each projects as project}<option value={project.id}>{project.name}</option>{/each}</select></label><ProjectCreator onCreated={projectCreated} /></div>
  </div>

  {#if error}<p class="notice-error">{error}</p>{/if}
  {#if busy}<div class="notice" role="status">{busy}… 입력과 현재 문서는 안전하게 보존됩니다.</div>{/if}

  <div class="document-layout">
    <aside class="card stack document-sidebar">
      <div class="row spread"><h3 style="margin:0">문서</h3><span class="badge">{documents.length}</span></div>
      <label class="mobile-document-picker">편집할 원고
        <select value={selected?.id || ''} on:change={(event) => selectDocument(documents.find((document) => document.id === event.currentTarget.value) || null)}>
          {#each documents as document}<option value={document.id}>{document.title}</option>{/each}
        </select>
      </label>
      <div class="list document-list">
        {#each documents as document}
          <button class:active={selected?.id === document.id} on:click={() => selectDocument(document)}>
            <strong>{document.title}</strong><div class="small">{document.final_body_markdown ? '완성본 있음' : documentStatusLabels[document.status] || document.status} · {new Date(document.updated_at).toLocaleDateString('ko-KR')}</div>
          </button>
        {/each}
      </div>
      {#if !documents.length}<p class="small">‘글 만들기’에서 원고를 생성하면 이곳에 문서와 문단이 만들어집니다.</p>{/if}
      {#if selected}
        <hr />
        <label>문서 상태<select bind:value={selected.status}><option value="draft">초안</option><option value="review">검토</option><option value="approved">완료</option><option value="archived">보관</option></select></label>
        <button class="secondary" on:click={saveDocument}>문서 정보 저장</button>
      {/if}
    </aside>

    <section class="stack document-main">
      {#if selected}
        <div class="card document-toolbar">
          <input class="document-title-input" aria-label="문서 제목" bind:value={selected.title} />
          <div class="document-export-actions">
            <a class="ghost" href={`${API_BASE}/documents/${selected.id}/export?format=markdown&version=${documentStage === 'final' && selected.final_body_markdown ? 'final' : 'draft'}`} target="_blank">Markdown</a>
            <a class="ghost" href={`${API_BASE}/documents/${selected.id}/export?format=html&version=${documentStage === 'final' && selected.final_body_markdown ? 'final' : 'draft'}`} target="_blank">HTML</a>
            <a class="ghost" href={`${API_BASE}/documents/${selected.id}/export?format=json&version=${documentStage === 'final' && selected.final_body_markdown ? 'final' : 'draft'}`} target="_blank">JSON</a>
          </div>
        </div>

        <nav class="document-stage-switch" aria-label="원고 완성 단계">
          <button class:active={documentStage === 'draft'} aria-pressed={documentStage === 'draft'} on:click={() => documentStage = 'draft'}><span>1</span><div><strong>초안 편집</strong><small>문단별 내용과 근거 수정</small></div></button>
          <button class:active={documentStage === 'final'} class:complete={!!selected.final_body_markdown} aria-pressed={documentStage === 'final'} on:click={() => documentStage = 'final'}><span>2</span><div><strong>완성본</strong><small>{selected.final_body_markdown ? '전체 흐름 다듬기 완료' : '한 편의 글로 다시 다듬기'}</small></div></button>
        </nav>

        {#if documentStage === 'draft'}
          {#each blocks as block, index}
            <article class="card stack document-block" class:locked={block.locked}>
              <div class="document-block-header">
                <div class="document-block-meta"><span class="badge">{String(index + 1).padStart(2, '0')}</span><strong>{moveLabels[block.rhetorical_move] || block.rhetorical_move}</strong><span class:canon={block.certainty === 'EVIDENCED'} class:candidate={block.certainty !== 'EVIDENCED'} class="badge">{certaintyLabels[block.certainty] || block.certainty}</span></div>
                <label class="document-lock"><input type="checkbox" bind:checked={block.locked} /> 문단 잠금</label>
              </div>
              <textarea class="document-block-editor" aria-label={`${index + 1}번 문단 내용`} bind:value={block.content_markdown} disabled={block.locked}></textarea>
              <div class="document-block-footer">
                <div class="document-evidence">{#each block.evidence_ids as id}<span class="badge canon">근거 · {evidenceName(id)}</span>{/each}{#if !block.evidence_ids.length}<span class="badge candidate">연결된 근거 없음</span>{/if}</div>
                <div class="document-block-actions"><button class="ghost" on:click={() => saveBlock(block)}>문단 저장</button><button class="secondary" disabled={block.locked} on:click={() => proposeRewrite(block)}>부분 재작성</button></div>
              </div>
            </article>
          {/each}
          <button class="draft-to-final" on:click={() => documentStage = 'final'}><span>초안 편집을 마쳤나요?</span><strong>전체 글 다듬기로 계속 →</strong></button>
        {:else}
          {#if finalization?.status === 'stale'}<div class="notice-error final-stale"><strong>초안이 바뀌었습니다.</strong> 현재 완성본은 이전 초안을 기준으로 만들었습니다. 다시 다듬으면 최신 문단이 반영됩니다.</div>{/if}
          {#if selected.final_body_markdown}
            <article class="card final-article">
              <div class="final-article-heading"><div><p class="eyebrow">완성본</p><h2>{selected.title}</h2><span>{selected.final_body_markdown.length.toLocaleString()}자 · {selected.finalized_at ? new Date(selected.finalized_at).toLocaleString('ko-KR') : ''}</span></div><span class="final-seal">FINAL</span></div>
              <textarea class="final-body-editor" aria-label="완성본 내용" bind:value={selected.final_body_markdown}></textarea>
              <div class="final-article-actions"><button class="secondary" on:click={saveFinalBody}>완성본 저장</button><button class="primary" on:click={finalizeDocument}>최신 초안으로 다시 다듬기</button></div>
            </article>
          {:else}
            <section class="card final-empty-state">
              <p class="eyebrow">다음 단계</p><h2>문단 초안을 한 편의 글로 연결합니다.</h2><p>현재 초안 전체와 글 만들기에서 정한 지시·글 형태·시점·시제·분량을 Writer에게 다시 전달합니다. 중복을 줄이고 문단 사이의 원인과 흐름을 다듬으며, 초안은 그대로 남겨 둡니다.</p>
              {#if finalization?.status === 'unavailable'}<p class="notice-error">{finalization.error}</p>{/if}
            </section>
          {/if}

          {#if finalization?.status !== 'unavailable'}
            <section class="card final-controls">
              <div class="final-input-overview">
                <div><small>결과물</small><strong>{finalization?.inputs?.output_profile?.name || '지정 안 함'}</strong></div>
                <div><small>시점</small><strong>{settingValue(finalization?.inputs?.generation_settings?.viewpoint)}</strong></div>
                <div><small>시제</small><strong>{settingValue(finalization?.inputs?.generation_settings?.tense)}</strong></div>
                <div><small>분량</small><strong>{lengthValue(finalization?.inputs?.generation_settings)}</strong></div>
              </div>
              <details class="final-input-details"><summary>다듬기에 다시 사용하는 값</summary><div class="details-body stack"><div><small>집필 방식</small><strong>{finalization?.inputs?.writing_recipe?.name || '지정 안 함'}</strong></div><div><small>이번 원고에만 추가한 지시</small><p>{finalization?.inputs?.user_direction || '추가한 지시 없음'}</p></div><div><small>자료 반영 범위 · 새 설정 제안 · 자세함 · 미스터리 보존</small><p>{settingValue(finalization?.inputs?.generation_settings?.context_depth, 'context_depth')} · {settingValue(finalization?.inputs?.generation_settings?.creativity, 'creativity')} · {finalization?.inputs?.generation_settings?.detail_level || '-'} / 5 · {finalization?.inputs?.generation_settings?.mystery_preservation || '-'} / 5</p></div></div></details>
              <label>이번 다듬기에만 추가할 요청<textarea bind:value={finalInstruction} placeholder="예: 문단 사이의 시간 흐름을 더 자연스럽게 연결해 주세요."></textarea></label>
              <button class="primary final-generate-button" disabled={!!busy} on:click={finalizeDocument}>{selected.final_body_markdown ? '다시 전체 다듬기' : '완성본 만들기'}</button>
              <p class="small">초안은 덮어쓰지 않습니다. 완성본을 만든 뒤에도 1단계로 돌아가 문단을 다시 수정할 수 있습니다.</p>
            </section>
          {/if}
        {/if}
      {:else}<div class="card"><p class="small">왼쪽에서 문서를 선택하십시오.</p></div>{/if}
    </section>

    <aside class="stack document-inspector">
      {#if documentStage === 'draft'}<section class="card stack">
        <p class="eyebrow">변경안 비교</p><h3 style="margin:0">부분 재작성</h3>
        <label>작업<select bind:value={rewriteOperation}><option value="shorter">더 짧게</option><option value="longer">더 자세히</option><option value="add_example">사례 추가</option><option value="expository">설명형으로</option><option value="scene">장면형으로</option><option value="style_only">사실 유지·문체만</option><option value="transition">앞뒤 연결만</option></select></label>
        <label>추가 지시<textarea bind:value={rewriteInstruction} placeholder="바꾸지 말아야 할 사실을 적으세요."></textarea></label>
        {#if activeProposal}
          <pre style="max-height:320px">{activeProposal.proposed_diff}</pre>
          <div class="row"><button class="primary" on:click={() => decideProposal('apply')}>변경안 적용</button><button class="ghost" on:click={() => decideProposal('dismiss')}>폐기</button></div>
        {:else}<p class="small">문단의 ‘부분 재작성’을 누르면 원문을 덮지 않고 비교할 변경안을 만듭니다.</p>{/if}
      </section>{:else}<section class="card stack final-side-note"><p class="eyebrow">완성 단계</p><h3>무엇이 달라지나요?</h3><p>문단을 하나씩 다시 쓰는 대신 초안 전체를 한 번에 읽고 연결합니다. 선택한 사실과 금지 설정은 그대로 지키며, 새 설정을 정식 설정으로 저장하지 않습니다.</p></section>{/if}

      <section class="card stack">
        <p class="eyebrow">원고 점검</p><h3 style="margin:0">주의할 점과 근거</h3>
        <div class="evidence-flow">
          {#each audits.filter((item) => item.audit_type !== 'REWRITE').slice(0, 8) as finding}
            <div class="evidence-item"><strong>{auditTypeLabels[finding.audit_type] || '원고 점검'}</strong><small>{finding.message}</small></div>
          {/each}
          {#if !audits.filter((item) => item.audit_type !== 'REWRITE').length}<div class="evidence-item"><strong>기록된 경고 없음</strong><small>감사는 원고를 자동 수정하지 않습니다.</small></div>{/if}
        </div>
      </section>

      <section class="card stack">
        <div class="row spread"><div><p class="eyebrow">승인 대기</p><h3 style="margin:0">새 설정 후보</h3></div><span class="badge candidate">{candidates.filter((item) => item.status === 'CANDIDATE').length}</span></div>
        <button class="secondary" disabled={!selected} on:click={extractNewCandidates}>현재 원고에서 후보 추출</button>
        {#each candidates.filter((item) => item.status === 'CANDIDATE').slice(0, 5) as candidate}
          <div class="evidence-item"><strong>{candidate.title}</strong><small>{candidate.summary || candidate.candidate_sentence}</small><div class="row wrap" style="margin-top:8px"><button class="ghost" on:click={() => decideCandidate(candidate, 'this_document_only')}>이번 글만</button><button class="secondary" on:click={() => decideCandidate(candidate, 'save_draft')}>설정 초안으로 저장</button><button class="primary" on:click={() => decideCandidate(candidate, 'approve_canon')}>정식 설정으로 승인</button></div></div>
        {/each}
        {#if !candidates.filter((item) => item.status === 'CANDIDATE').length}<p class="small">추출된 후보가 없습니다. 후보는 승인 전까지 검색 근거가 되지 않습니다.</p>{/if}
      </section>
      {#if message}<p class="success">{message}</p>{/if}
    </aside>
  </div>
</div>
