<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import ProjectCreator from '$lib/components/ProjectCreator.svelte';
  import { api, API_BASE } from '$lib/api';
  import { auditTypeLabels, certaintyLabels, documentStatusLabels, moveLabels } from '$lib/labels';
  import { initialProjectId, rememberProject } from '$lib/project';

  let projects = [], documents = [], blocks = [], audits = [], candidates = [], pages = [];
  let recipes = [], outputProfiles = [];
  let projectId = '', selected = null;
  let busy = '', error = '', message = '';
  let draftDirty = false;
  let rewriteOperation = 'shorter', rewriteInstruction = '', activeProposal = null;
  let finalization = null;
  let workflowStep = 0, furthestStep = 0;
  let documentLoadToken = 0;

  let finalUserDirection = '', finalRecipeId = '', finalOutputProfile = 'lore_article';
  let finalLength = 'normal', finalCustomLength = 4000, finalDetailLevel = 3;
  let finalContextDepth = 'balanced', finalCreativity = 'conservative', finalMystery = 4;
  let finalViewpoint = 'omniscient', finalTense = 'present', finalInstruction = '';

  const workflowSteps = [
    { short: '초안 편집', title: '문단별 초안을 검토하세요.', copy: '내용과 근거를 확인하고 필요한 문단만 수정합니다.' },
    { short: '완성 설정', title: '완성본의 결과물 형태를 다시 정하세요.', copy: '처음 선택한 값은 초깃값일 뿐입니다. 이번 완성본에 맞게 모두 바꿀 수 있습니다.' },
    { short: '완성본 만들기', title: '한 편의 글로 다듬어 로어북에 보냅니다.', copy: '최신 초안 전체와 아래 설정을 Writer에게 전달합니다.' }
  ];

  $: activeWorkflow = workflowSteps[workflowStep];
  $: selectedRecipe = recipes.find((item) => item.id === finalRecipeId);
  $: selectedProfile = outputProfiles.find((item) => item.key === finalOutputProfile);
  $: finalLengthLabel = finalLength === 'custom' ? `직접 지정 · ${Number(finalCustomLength).toLocaleString()}자` : ({ short: '짧게', normal: '보통', long: '길게', very_long: '매우 길게' }[finalLength] || finalLength);

  onMount(loadInitial);

  async function loadInitial() {
    try {
      [projects, recipes, outputProfiles] = await Promise.all([
        api.get('/projects'), api.get('/writing-recipes'), api.get('/presets/output-profiles')
      ]);
      if (projects.length) {
        projectId = initialProjectId(projects);
        await loadDocuments();
      }
    } catch (e) { error = e.message; }
  }

  async function loadDocuments() {
    if (!projectId) return;
    const targetProjectId = projectId;
    const loadToken = ++documentLoadToken;
    error = ''; rememberProject(targetProjectId);
    try {
      const [loadedDocuments, loadedCandidates, loadedPages] = await Promise.all([
        api.get(`/documents?project_id=${targetProjectId}`),
        api.get(`/candidates?project_id=${targetProjectId}`),
        api.get(`/concept-pages?project_id=${targetProjectId}`)
      ]);
      if (loadToken !== documentLoadToken || projectId !== targetProjectId) return;
      documents = loadedDocuments; candidates = loadedCandidates; pages = loadedPages;
      const requestedId = $page.url.searchParams.get('document');
      await selectDocument(documents.find((document) => document.id === requestedId) || documents[0] || null);
    } catch (e) { error = e.message; }
  }

  async function changeProject() {
    if (draftDirty && !(await saveDraft({ quiet: true }))) {
      projectId = selected?.project_id || projectId;
      return;
    }
    await loadDocuments();
  }

  async function projectCreated(project) {
    projects = [project, ...projects]; projectId = project.id; await loadDocuments();
  }

  function evidenceName(id) { return pages.find((item) => item.id === id)?.title || '삭제된 자료'; }

  function loadFinalSettings(inputs = {}) {
    const settings = inputs.generation_settings || {};
    finalUserDirection = inputs.user_direction || '';
    finalRecipeId = inputs.writing_recipe?.id || finalRecipeId || recipes[0]?.id || '';
    finalOutputProfile = inputs.output_profile?.key || 'lore_article';
    finalLength = settings.length || 'normal';
    finalCustomLength = settings.custom_length || 4000;
    finalDetailLevel = settings.detail_level || 3;
    finalContextDepth = settings.context_depth || 'balanced';
    finalCreativity = settings.creativity || 'conservative';
    finalMystery = settings.mystery_preservation || 4;
    finalViewpoint = settings.viewpoint || 'omniscient';
    finalTense = settings.tense || 'present';
    finalInstruction = '';
  }

  async function selectDocument(document) {
    selected = document ? { ...document } : null;
    activeProposal = null; workflowStep = 0; furthestStep = 0; finalization = null;
    if (!selected) { blocks = []; audits = []; return; }
    busy = '초안 불러오는 중';
    try {
      [blocks, audits, finalization] = await Promise.all([
        api.get(`/documents/${selected.id}/blocks`),
        api.get(`/documents/${selected.id}/audits`),
        api.get(`/documents/${selected.id}/finalization`)
      ]);
      draftDirty = false;
      loadFinalSettings(finalization.inputs);
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  function setWorkflowStep(index) {
    if (index < 0 || index >= workflowSteps.length || index > furthestStep) return;
    workflowStep = index;
    setTimeout(() => document.querySelector('.document-workflow')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0);
  }

  async function continueTo(index) {
    if (index === 1 && draftDirty && !(await saveDraft({ quiet: true }))) return;
    furthestStep = Math.max(furthestStep, index); workflowStep = index;
    setTimeout(() => document.querySelector('.document-workflow')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0);
  }

  function markDraftDirty() {
    draftDirty = true; message = '';
  }

  function addBlock() {
    blocks = [...blocks, {
      id: null,
      clientId: crypto.randomUUID(),
      position: blocks.length,
      content_markdown: '',
      rhetorical_move: 'ANCHOR',
      evidence_ids: [],
      certainty: 'CANDIDATE',
      locked: false
    }];
    markDraftDirty();
    setTimeout(() => document.querySelector('.document-block:last-of-type textarea')?.focus(), 0);
  }

  function removeBlock(block, index) {
    if (blocks.length === 1) { error = '초안에는 문단이 하나 이상 있어야 합니다.'; return; }
    if (block.locked) { error = '잠긴 문단은 잠금을 푼 뒤 삭제할 수 있습니다.'; return; }
    if (block.id && !confirm(`${index + 1}번 문단을 삭제할까요? 저장하면 되돌릴 수 없습니다.`)) return;
    blocks = blocks.filter((item) => item !== block);
    error = ''; markDraftDirty();
  }

  async function changeDocument(document) {
    if (draftDirty && !(await saveDraft({ quiet: true }))) return;
    await selectDocument(document);
  }

  async function saveDraft({ quiet = false } = {}) {
    if (!selected) return false;
    if (!selected.title.trim()) { error = '초안 제목을 입력해 주세요.'; return false; }
    const emptyIndex = blocks.findIndex((block) => !block.content_markdown.trim());
    if (emptyIndex >= 0) { error = `${emptyIndex + 1}번 문단이 비어 있습니다. 내용을 입력하거나 삭제해 주세요.`; return false; }
    busy = '초안 전체 저장 중'; error = ''; message = '';
    try {
      const result = await api.patch(`/documents/${selected.id}/draft`, {
        title: selected.title,
        status: selected.status,
        blocks: blocks.map((block) => ({
          id: block.id || null,
          content_markdown: block.content_markdown,
          rhetorical_move: block.rhetorical_move,
          evidence_ids: block.evidence_ids,
          certainty: block.certainty,
          locked: block.locked
        }))
      });
      selected = result.document;
      blocks = result.blocks;
      documents = documents.map((item) => item.id === selected.id ? selected : item);
      finalization = await api.get(`/documents/${selected.id}/finalization`);
      draftDirty = false;
      if (!quiet) message = '제목과 모든 문단을 저장했습니다.';
      return true;
    } catch (e) { error = e.message; return false; }
    finally { busy = ''; }
  }

  async function proposeRewrite(block) {
    if (!block.id || (draftDirty && !(await saveDraft({ quiet: true })))) return;
    busy = 'AI가 원문을 보존한 변경안을 작성하는 중'; error = ''; activeProposal = null;
    try {
      activeProposal = await api.post(`/blocks/${block.id}/rewrite`, { operation: rewriteOperation, instruction: rewriteInstruction, direction_card_ids: [] });
      audits = [activeProposal, ...audits.filter((item) => item.id !== activeProposal.id)];
      setTimeout(() => window.document.querySelector('.document-inspector')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0);
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  function scrollToDocumentTools() {
    window.document.querySelector('.document-inspector')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function scrollToDraft() {
    window.document.querySelector('.document-main')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  async function decideProposal(action) {
    if (!activeProposal) return;
    busy = action === 'apply' ? '변경안 적용 중' : '변경안 폐기 중';
    try {
      const updated = await api.post(`/audits/${activeProposal.id}/${action}`, {});
      audits = audits.map((item) => item.id === updated.id ? updated : item); activeProposal = null;
      if (action === 'apply') await selectDocument(selected);
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  async function decideCandidate(candidate, decision) {
    busy = '후보 처리 중';
    try {
      const updated = await api.post(`/candidates/${candidate.id}/decide`, { decision, reason: '초안 검토 화면에서 사용자 승인' });
      candidates = candidates.map((item) => item.id === updated.id ? updated : item);
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  async function extractNewCandidates() {
    if (!selected) return;
    busy = 'AI가 초안에서 설정 후보를 찾는 중'; error = '';
    try {
      const created = await api.post(`/documents/${selected.id}/extract-candidates`, {});
      candidates = [...created, ...candidates];
      message = `${created.length}개의 후보를 추출했습니다. 아직 정식 설정에는 반영되지 않았습니다.`;
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  async function finalizeDocument() {
    if (!selected) return;
    if (draftDirty && !(await saveDraft({ quiet: true }))) return;
    busy = 'Writer가 초안 전체를 한 편의 글로 다듬는 중'; error = ''; message = '';
    try {
      const result = await api.post(`/documents/${selected.id}/finalize`, {
        instruction: finalInstruction,
        user_direction: finalUserDirection,
        writing_recipe_id: finalRecipeId,
        output_profile: finalOutputProfile,
        settings_json: {
          length: finalLength,
          custom_length: finalLength === 'custom' ? Number(finalCustomLength) : null,
          detail_level: Number(finalDetailLevel),
          context_depth: finalContextDepth,
          creativity: finalCreativity,
          mystery_preservation: Number(finalMystery),
          viewpoint: finalViewpoint,
          tense: finalTense
        }
      });
      await goto(`/lorebook?entry=${result.lorebook_entry.id}`);
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }
</script>

<div class="page workspace-page documents-page">
  <div class="page-tools">
    <div class="project-tools"><label style="min-width:260px">현재 프로젝트<select bind:value={projectId} on:change={changeProject}>{#each projects as project}<option value={project.id}>{project.name}</option>{/each}</select></label><ProjectCreator onCreated={projectCreated} /></div>
  </div>

  {#if error}<p class="notice-error">{error}</p>{/if}
  {#if busy}<div class="working-banner" role="status"><span></span><strong>{busy}…</strong><small>현재 초안과 설정은 그대로 보존됩니다.</small></div>{/if}

  <section class="wizard-shell document-workflow">
    <nav class="wizard-progress document-wizard-progress" aria-label="원고 완성 단계">
      {#each workflowSteps as step, index}
        <button class:active={workflowStep === index} class:complete={index < workflowStep || index <= furthestStep && index !== workflowStep} disabled={index > furthestStep} aria-current={workflowStep === index ? 'step' : undefined} on:click={() => setWorkflowStep(index)}>
          <span>{index + 1}</span><div><strong>{step.short}</strong><small>{index === 0 ? selected?.title || '초안 선택 필요' : index === 1 ? selectedProfile?.name || '설정 전' : finalization?.lorebook_entry ? '로어북 글 다시 만들기' : '로어북에 새 글 저장'}</small></div>
        </button>
      {/each}
    </nav>

    <header class="wizard-heading">
      <div><p class="eyebrow">{workflowStep + 1} / {workflowSteps.length}</p><h2>{activeWorkflow.title}</h2><p>{activeWorkflow.copy}</p></div>
      {#if documents.length}<label class="workflow-document-select">작업할 초안 {#if draftDirty}<span class="draft-dirty">저장 안 됨</span>{/if}<select value={selected?.id || ''} on:change={(event) => changeDocument(documents.find((item) => item.id === event.currentTarget.value) || null)}>{#each documents as document}<option value={document.id}>{document.title}</option>{/each}</select></label>{/if}
    </header>

    {#if !selected}
      <div class="empty-state workflow-empty">‘글 만들기’에서 초안을 만들면 이곳에서 편집하고 로어북 글로 완성할 수 있습니다.</div>
    {:else if workflowStep === 0}
      <div class="document-edit-stage">
        <button class="secondary mobile-inspector-jump" on:click={scrollToDocumentTools}>원고 도구 보기 · 부분 재작성 · 점검 · 설정 후보 ↓</button>
        <main class="stack document-main">
          <div class="document-toolbar">
            <input class="document-title-input" aria-label="초안 제목" bind:value={selected.title} on:input={markDraftDirty} />
            <div class="row wrap"><label class="compact-status">상태<select bind:value={selected.status} on:change={markDraftDirty}><option value="draft">초안</option><option value="review">검토 중</option><option value="approved">완료</option><option value="archived">보관</option></select></label><button class="secondary" disabled={!!busy} on:click={() => saveDraft()}>초안 전체 저장</button><a class="ghost" href={`${API_BASE}/documents/${selected.id}/export?format=markdown`} target="_blank">초안 내보내기</a></div>
          </div>
          {#each blocks as block, index}
            <article class="card stack document-block" class:locked={block.locked}>
              <div class="document-block-header"><div class="document-block-meta"><span class="badge">{String(index + 1).padStart(2, '0')}</span><strong>{moveLabels[block.rhetorical_move] || block.rhetorical_move}</strong><span class:canon={block.certainty === 'EVIDENCED'} class:candidate={block.certainty !== 'EVIDENCED'} class="badge">{certaintyLabels[block.certainty] || block.certainty}</span></div><label class="document-lock"><input type="checkbox" bind:checked={block.locked} on:change={markDraftDirty} /> 문단 잠금</label></div>
              <textarea class="document-block-editor" aria-label={`${index + 1}번 문단 내용`} bind:value={block.content_markdown} on:input={markDraftDirty} disabled={block.locked}></textarea>
              <div class="document-block-footer"><div class="document-evidence">{#each block.evidence_ids as id}<span class="badge canon">근거 · {evidenceName(id)}</span>{/each}{#if !block.evidence_ids.length}<span class="badge candidate">연결된 근거 없음</span>{/if}</div><div class="document-block-actions"><button class="ghost danger-button" disabled={block.locked} on:click={() => removeBlock(block, index)}>문단 삭제</button><button class="secondary" disabled={block.locked || !block.id} on:click={() => proposeRewrite(block)}>부분 재작성</button></div></div>
            </article>
          {/each}
          <button class="add-document-block" on:click={addBlock}>+ 새 문단 추가</button>
        </main>
        <aside class="stack document-inspector">
          <button class="ghost mobile-draft-return" on:click={scrollToDraft}>↑ 초안으로 돌아가기</button>
          <section class="card stack"><p class="eyebrow">변경안 비교</p><h3 style="margin:0">부분 재작성</h3><label>작업<select bind:value={rewriteOperation}><option value="shorter">더 짧게</option><option value="longer">더 자세히</option><option value="add_example">사례 추가</option><option value="expository">설명형으로</option><option value="scene">장면형으로</option><option value="style_only">사실 유지·문체만</option><option value="transition">앞뒤 연결만</option></select></label><label>추가 지시<textarea bind:value={rewriteInstruction}></textarea></label>{#if activeProposal}<pre style="max-height:320px">{activeProposal.proposed_diff}</pre><div class="row"><button class="primary" on:click={() => decideProposal('apply')}>변경안 적용</button><button class="ghost" on:click={() => decideProposal('dismiss')}>폐기</button></div>{:else}<p class="small">문단의 ‘부분 재작성’을 누르면 원문을 덮지 않고 변경안을 만듭니다.</p>{/if}</section>
          <section class="card stack"><p class="eyebrow">원고 점검</p><h3 style="margin:0">주의할 점과 근거</h3><div class="evidence-flow">{#each audits.filter((item) => item.audit_type !== 'REWRITE').slice(0, 8) as finding}<div class="evidence-item"><strong>{auditTypeLabels[finding.audit_type] || '원고 점검'}</strong><small>{finding.message}</small></div>{/each}{#if !audits.filter((item) => item.audit_type !== 'REWRITE').length}<div class="evidence-item"><strong>기록된 경고 없음</strong><small>점검은 원고를 자동 수정하지 않습니다.</small></div>{/if}</div></section>
          <section class="card stack"><div class="row spread"><div><p class="eyebrow">승인 대기</p><h3 style="margin:0">설정 후보</h3></div><span class="badge candidate">{candidates.filter((item) => item.status === 'CANDIDATE').length}</span></div><button class="secondary" on:click={extractNewCandidates}>현재 초안에서 설정 후보 찾기</button>{#each candidates.filter((item) => item.status === 'CANDIDATE').slice(0, 5) as candidate}<div class="evidence-item"><strong>{candidate.title}</strong><small>{candidate.summary || candidate.candidate_sentence}</small><div class="row wrap" style="margin-top:8px"><button class="ghost" on:click={() => decideCandidate(candidate, 'this_document_only')}>이번 글만</button><button class="secondary" on:click={() => decideCandidate(candidate, 'save_draft')}>설정 초안으로 저장</button><button class="primary" on:click={() => decideCandidate(candidate, 'approve_canon')}>정식 설정으로 승인</button></div></div>{/each}</section>
        </aside>
      </div>
      <footer class="wizard-actions"><small>{draftDirty ? '다음 단계로 가면 변경 내용을 자동 저장합니다.' : '모든 변경 내용이 저장되었습니다.'}</small><button class="primary" disabled={!!busy} on:click={() => continueTo(1)}>저장하고 완성 설정으로 계속 →</button></footer>
    {:else if workflowStep === 1}
      <div class="settings-grid finalization-settings">
        <section class="card stack"><h3>결과물 형태</h3><label>전개 방식<select bind:value={finalRecipeId}>{#each recipes as recipe}<option value={recipe.id}>{recipe.name}</option>{/each}</select></label>{#if selectedRecipe}<p class="field-help">{selectedRecipe.description}</p>{/if}<label>결과물 종류<select bind:value={finalOutputProfile}>{#each outputProfiles as profile}<option value={profile.key}>{profile.name}</option>{/each}</select></label><div class="grid-2"><label>시점<select bind:value={finalViewpoint}><option value="omniscient">전지적 설명자</option><option value="first_observer">1인칭 관찰자</option><option value="third_limited">3인칭 제한</option></select></label><label>시제<select bind:value={finalTense}><option value="present">현재형 중심</option><option value="past">과거형 중심</option></select></label></div><label>완성본의 추가 지시<textarea bind:value={finalUserDirection} placeholder="글 만들기 때의 지시를 바꾸거나 보완할 수 있습니다."></textarea></label></section>
        <section class="card stack"><h3>분량과 표현 범위</h3><div class="grid-2"><label>분량<select bind:value={finalLength}><option value="short">짧게</option><option value="normal">보통</option><option value="long">길게</option><option value="very_long">매우 길게</option><option value="custom">직접 지정</option></select></label>{#if finalLength === 'custom'}<label>목표 글자 수<input type="number" min="500" bind:value={finalCustomLength} /></label>{/if}<label>자료 반영 범위<select bind:value={finalContextDepth}><option value="core">선택한 핵심만</option><option value="balanced">관련 자료까지 균형 있게</option><option value="wide">세계 맥락을 넓게</option><option value="max">가능한 자료를 최대로</option></select></label><label>새 설정 제안<select bind:value={finalCreativity}><option value="strict">하지 않음</option><option value="conservative">최소한</option><option value="balanced">필요할 때</option><option value="free">적극적</option></select></label></div><label>설명의 자세함 · {finalDetailLevel}/5<input type="range" min="1" max="5" bind:value={finalDetailLevel} /></label><label>아직 답하지 않을 질문 보존 · {finalMystery}/5<input type="range" min="1" max="5" bind:value={finalMystery} /></label><label>이번 다듬기에만 추가할 요청<textarea bind:value={finalInstruction} placeholder="예: 문단 사이의 시간 흐름을 더 자연스럽게 연결해 주세요."></textarea></label></section>
      </div>
      <footer class="wizard-actions"><button class="ghost" on:click={() => setWorkflowStep(0)}>← 초안 편집</button><button class="primary" on:click={() => continueTo(2)}>설정 확인으로 계속 →</button></footer>
    {:else}
      <div class="finalization-review">
        {#if finalization?.status === 'stale'}<p class="notice-error"><strong>로어북 글을 만든 뒤 초안이 바뀌었습니다.</strong> 지금 실행하면 최신 초안으로 교체됩니다.</p>{/if}
        <div class="wizard-review-grid"><article><div><span>초안</span><strong>{selected.title}</strong></div><button class="ghost" on:click={() => setWorkflowStep(0)}>수정</button></article><article><div><span>결과물 형태</span><strong>{selectedProfile?.name || finalOutputProfile}</strong></div><button class="ghost" on:click={() => setWorkflowStep(1)}>수정</button></article><article><div><span>전개 방식</span><strong>{selectedRecipe?.name || '지정 안 함'}</strong></div><button class="ghost" on:click={() => setWorkflowStep(1)}>수정</button></article><article><div><span>시점·시제</span><strong>{finalViewpoint === 'omniscient' ? '전지적 설명자' : finalViewpoint === 'first_observer' ? '1인칭 관찰자' : '3인칭 제한'} · {finalTense === 'present' ? '현재형 중심' : '과거형 중심'}</strong></div><button class="ghost" on:click={() => setWorkflowStep(1)}>수정</button></article><article><div><span>분량</span><strong>{finalLengthLabel}</strong></div><button class="ghost" on:click={() => setWorkflowStep(1)}>수정</button></article><article><div><span>추가 지시</span><strong>{finalUserDirection || '추가 지시 없음'}</strong></div><button class="ghost" on:click={() => setWorkflowStep(1)}>수정</button></article></div>
        <section class="lorebook-destination"><div><p class="eyebrow">저장 위치</p><h3>완성본은 로어북에 별도 저장됩니다.</h3><p>초안 문단과 로어북 글은 서로 덮어쓰지 않습니다. 로어북에서 완성된 글만 읽고 편집하고 내보낼 수 있습니다.</p></div><span>초안 → Writer → 로어북</span></section>
      </div>
      <footer class="wizard-actions"><button class="ghost" on:click={() => setWorkflowStep(1)}>← 완성 설정</button><button class="primary final-generate-button" disabled={!!busy} on:click={finalizeDocument}>{finalization?.lorebook_entry ? '최신 설정으로 로어북 글 다시 만들기' : '완성본 만들어 로어북에 저장'}</button></footer>
    {/if}
  </section>
  {#if message}<p class="success">{message}</p>{/if}
</div>
