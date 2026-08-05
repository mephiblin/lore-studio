<script>
  import { onMount } from 'svelte';
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
      await selectDocument(documents[0] || null);
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
    if (!selected) { blocks = []; audits = []; return; }
    busy = '문서 불러오는 중';
    try {
      [blocks, audits] = await Promise.all([
        api.get(`/documents/${selected.id}/blocks`),
        api.get(`/documents/${selected.id}/audits`)
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
</script>

<div class="page">
  <div class="page-header">
    <div><p class="eyebrow">원고 편집</p><h1>원고를 문단별로 다듬습니다.</h1><p>근거를 확인하며 수정하고, AI가 낸 변경안은 직접 승인한 뒤에만 반영합니다.</p></div>
    <div class="project-tools"><label style="min-width:260px">현재 프로젝트<select bind:value={projectId} on:change={loadDocuments}>{#each projects as project}<option value={project.id}>{project.name}</option>{/each}</select></label><ProjectCreator onCreated={projectCreated} /></div>
  </div>

  {#if error}<p class="notice-error">{error}</p>{/if}
  {#if busy}<div class="notice" role="status">{busy}… 입력과 현재 문서는 안전하게 보존됩니다.</div>{/if}

  <div class="grid-3" style="grid-template-columns:250px minmax(520px,1fr) 330px">
    <aside class="card stack">
      <div class="row spread"><h3 style="margin:0">문서</h3><span class="badge">{documents.length}</span></div>
      <div class="list">
        {#each documents as document}
          <button class:active={selected?.id === document.id} on:click={() => selectDocument(document)}>
            <strong>{document.title}</strong><div class="small">{documentStatusLabels[document.status] || document.status} · {new Date(document.updated_at).toLocaleDateString('ko-KR')}</div>
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

    <section class="stack">
      {#if selected}
        <div class="card row spread">
          <input aria-label="문서 제목" bind:value={selected.title} style="font:600 22px Georgia,serif;border:0;padding:4px" />
          <div class="row wrap">
            <a class="ghost" href={`${API_BASE}/documents/${selected.id}/export?format=markdown`} target="_blank">Markdown</a>
            <a class="ghost" href={`${API_BASE}/documents/${selected.id}/export?format=html`} target="_blank">HTML</a>
            <a class="ghost" href={`${API_BASE}/documents/${selected.id}/export?format=json`} target="_blank">JSON</a>
          </div>
        </div>

        {#each blocks as block, index}
          <article class="card stack" style={`border-left:3px solid ${block.locked ? 'var(--lichen)' : 'var(--signal)'}`}>
            <div class="row spread">
              <div class="row"><span class="badge">{String(index + 1).padStart(2, '0')}</span><strong>{moveLabels[block.rhetorical_move] || block.rhetorical_move}</strong><span class:canon={block.certainty === 'EVIDENCED'} class:candidate={block.certainty !== 'EVIDENCED'} class="badge">{certaintyLabels[block.certainty] || block.certainty}</span></div>
              <label style="display:flex;align-items:center"><input type="checkbox" bind:checked={block.locked} style="width:auto" /> 문단 잠금</label>
            </div>
            <textarea bind:value={block.content_markdown} disabled={block.locked} style="min-height:150px;border:0;background:var(--paper-deep);font:16px/1.8 Georgia,'Noto Serif KR',serif"></textarea>
            <div class="row spread wrap">
              <div class="row wrap">{#each block.evidence_ids as id}<span class="badge canon">근거 · {evidenceName(id)}</span>{/each}{#if !block.evidence_ids.length}<span class="badge candidate">연결된 근거 없음</span>{/if}</div>
              <div class="row"><button class="ghost" on:click={() => saveBlock(block)}>문단 저장</button><button class="secondary" disabled={block.locked} on:click={() => proposeRewrite(block)}>부분 재작성</button></div>
            </div>
          </article>
        {/each}
      {:else}<div class="card"><p class="small">왼쪽에서 문서를 선택하십시오.</p></div>{/if}
    </section>

    <aside class="stack">
      <section class="card stack">
        <p class="eyebrow">변경안 비교</p><h3 style="margin:0">부분 재작성</h3>
        <label>작업<select bind:value={rewriteOperation}><option value="shorter">더 짧게</option><option value="longer">더 자세히</option><option value="add_example">사례 추가</option><option value="expository">설명형으로</option><option value="scene">장면형으로</option><option value="style_only">사실 유지·문체만</option><option value="transition">앞뒤 연결만</option></select></label>
        <label>추가 지시<textarea bind:value={rewriteInstruction} placeholder="바꾸지 말아야 할 사실을 적으세요."></textarea></label>
        {#if activeProposal}
          <pre style="max-height:320px">{activeProposal.proposed_diff}</pre>
          <div class="row"><button class="primary" on:click={() => decideProposal('apply')}>변경안 적용</button><button class="ghost" on:click={() => decideProposal('dismiss')}>폐기</button></div>
        {:else}<p class="small">문단의 ‘부분 재작성’을 누르면 원문을 덮지 않고 비교할 변경안을 만듭니다.</p>{/if}
      </section>

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
