<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import HelpTip from '$lib/components/HelpTip.svelte';
  import ProjectCreator from '$lib/components/ProjectCreator.svelte';
  import { api, API_BASE } from '$lib/api';
  import { auditTypeLabels, certaintyLabels, documentStatusLabels, moveLabels } from '$lib/labels';
  import { initialProjectId, rememberProject } from '$lib/project';

  let projects = [], documents = [], blocks = [], audits = [], candidates = [], pages = [];
  let recipes = [], outputProfiles = [], voiceProfiles = [];
  let projectId = '', selected = null;
  let busy = '', error = '', message = '';
  let draftDirty = false;
  let rewriteOperation = 'shorter', rewriteInstruction = '', activeProposal = null;
  let finalization = null;
  let workflowStep = 0, furthestStep = 0;
  let inspectorTab = 'rewrite';
  let documentLoadToken = 0;

  let finalRecipeId = '', finalVoiceProfileId = '', finalOutputProfile = 'lore_article';
  let finalLength = 'normal', finalCustomLength = 4000;
  let finalViewpoint = 'omniscient', finalTense = 'present', finalInstruction = '';
  let finalRefinementPriorities = ['coherence', 'deduplicate', 'rhythm'];
  let finalRefinementIntensity = 'balanced', finalLengthPolicy = 'preserve';

  const workflowSteps = [
    { short: '초안 편집', title: '문단별 초안을 검토하세요.', copy: '내용과 근거를 확인하고 필요한 문단만 수정합니다.' },
    { short: '완성 다듬기', title: '초안에서 무엇을 보강할까요?', copy: '처음 설계한 형식은 유지하고 연결·문장·장면·결말의 완성도를 높입니다.' },
    { short: '완성본 만들기', title: '보강 방향을 확인하고 로어북에 보냅니다.', copy: '최신 초안 전체와 선택한 다듬기 기준을 Writer에게 전달합니다.' }
  ];
  const viewpointOptions = [
    { value: 'omniscient', title: '전지적 설명자', copy: '세계 전체를 내려다봅니다.' },
    { value: 'first_observer', title: '1인칭 관찰자', copy: '목격자의 언어로 제한합니다.' },
    { value: 'third_limited', title: '3인칭 제한', copy: '한 인물 가까이 머뭅니다.' }
  ];
  const tenseOptions = [
    { value: 'present', title: '현재형 중심', copy: '지금 벌어지는 듯한 밀도' },
    { value: 'past', title: '과거형 중심', copy: '기록하고 회고하는 안정감' }
  ];
  const lengthOptions = [
    { value: 'short', title: '짧게', copy: '약 1,200자' },
    { value: 'normal', title: '보통', copy: '약 3,000자' },
    { value: 'long', title: '길게', copy: '약 6,500자' },
    { value: 'very_long', title: '매우 길게', copy: '약 12,000자' },
    { value: 'custom', title: '직접 지정', copy: '원하는 길이' }
  ];
  const refinementPriorityOptions = [
    { value: 'coherence', title: '문단 연결', copy: '시간·관점·논리의 이동을 자연스럽게 잇습니다.' },
    { value: 'causality', title: '인과 선명화', copy: '사건과 주장 사이의 원인·결과를 분명히 합니다.' },
    { value: 'imagery', title: '장면·감각', copy: '새 사실 없이 구체적인 장면과 감각을 보강합니다.' },
    { value: 'rhythm', title: '문장 리듬', copy: '문장 길이와 문단 호흡의 단조로움을 다듬습니다.' },
    { value: 'deduplicate', title: '중복 제거', copy: '겹치는 도입과 설명을 합쳐 밀도를 높입니다.' },
    { value: 'ending', title: '결말 강화', copy: '마지막 문단의 수렴과 여운을 강화합니다.' }
  ];
  const refinementIntensityOptions = [
    { value: 'light', title: '가볍게', copy: '문장 표현과 접속만 손봅니다.' },
    { value: 'balanced', title: '균형 있게', copy: '필요하면 문단을 합치거나 나눕니다.' },
    { value: 'strong', title: '적극적으로', copy: '핵심을 지키며 문단 순서도 재배열합니다.' }
  ];
  const finalLengthPolicyOptions = [
    { value: 'preserve', title: '분량 유지', copy: '초안의 전체 길이를 대체로 유지합니다.' },
    { value: 'tighten', title: '더 간결하게', copy: '중복과 군더더기를 줄입니다.' },
    { value: 'expand', title: '필요한 곳 보강', copy: '새 사실 없이 연결·장면·근거를 보탭니다.' }
  ];

  $: selectedRecipe = recipes.find((item) => item.id === finalRecipeId);
  $: selectedProfile = outputProfiles.find((item) => item.key === finalOutputProfile);
  $: selectedVoiceProfile = voiceProfiles.find((item) => item.id === finalVoiceProfileId);
  $: selectedViewpoint = viewpointOptions.find((item) => item.value === finalViewpoint) || viewpointOptions[0];
  $: selectedTense = tenseOptions.find((item) => item.value === finalTense) || tenseOptions[0];
  $: selectedLength = lengthOptions.find((item) => item.value === finalLength) || lengthOptions[1];
  $: finalLengthCopy = finalLength === 'custom' ? `${Number(finalCustomLength || 0).toLocaleString()}자` : selectedLength.copy;
  $: selectedRefinementLabels = refinementPriorityOptions.filter((item) => finalRefinementPriorities.includes(item.value)).map((item) => item.title);
  $: finalRefinementIntensityLabel = refinementIntensityOptions.find((item) => item.value === finalRefinementIntensity)?.title || '균형 있게';
  $: finalLengthPolicyLabel = finalLengthPolicyOptions.find((item) => item.value === finalLengthPolicy)?.title || '분량 유지';

  onMount(loadInitial);

  async function loadInitial() {
    try {
      [projects, outputProfiles] = await Promise.all([
        api.get('/projects'), api.get('/presets/output-profiles')
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
      const [loadedDocuments, loadedCandidates, loadedPages, loadedRecipes, loadedVoices] = await Promise.all([
        api.get(`/documents?project_id=${targetProjectId}`),
        api.get(`/candidates?project_id=${targetProjectId}`),
        api.get(`/concept-pages?project_id=${targetProjectId}`),
        api.get(`/writing-recipes?project_id=${targetProjectId}`),
        api.get(`/voice-profiles?project_id=${targetProjectId}&status=APPROVED`)
      ]);
      if (loadToken !== documentLoadToken || projectId !== targetProjectId) return;
      documents = loadedDocuments; candidates = loadedCandidates; pages = loadedPages; recipes = loadedRecipes; voiceProfiles = loadedVoices;
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
  function outputMark(key) { return ({ video_narration: '영상', novel_prose: '장면', personal_essay: '수필', analytical_report: '보고', in_universe_report: '기록', lore_article: '설정집' }[key] || '원고'); }

  function loadFinalSettings(inputs = {}) {
    const settings = inputs.generation_settings || {};
    finalRecipeId = inputs.writing_recipe?.id || finalRecipeId || recipes[0]?.id || '';
    finalVoiceProfileId = inputs.voice_profile?.id || '';
    finalOutputProfile = inputs.output_profile?.key || 'lore_article';
    finalLength = settings.length || 'normal';
    finalCustomLength = settings.custom_length || 4000;
    finalViewpoint = settings.viewpoint || 'omniscient';
    finalTense = settings.tense || 'present';
    const refinement = inputs.refinement || {};
    finalRefinementPriorities = refinement.priorities?.length ? [...refinement.priorities] : ['coherence', 'deduplicate', 'rhythm'];
    finalRefinementIntensity = refinement.intensity || 'balanced';
    finalLengthPolicy = refinement.length_policy || 'preserve';
    finalInstruction = '';
  }

  function toggleRefinementPriority(value) {
    if (finalRefinementPriorities.includes(value)) {
      if (finalRefinementPriorities.length === 1) return;
      finalRefinementPriorities = finalRefinementPriorities.filter((item) => item !== value);
    } else {
      finalRefinementPriorities = [...finalRefinementPriorities, value];
    }
  }

  async function selectDocument(document) {
    selected = document ? { ...document } : null;
    activeProposal = null; workflowStep = 0; furthestStep = 0; inspectorTab = 'rewrite'; finalization = null;
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
    revealWorkflowStart();
  }

  async function continueTo(index) {
    if (index === 1 && draftDirty && !(await saveDraft({ quiet: true }))) return;
    furthestStep = Math.max(furthestStep, index); workflowStep = index;
    revealWorkflowStart();
  }

  function revealWorkflowStart() {
    setTimeout(() => {
      const workflow = document.querySelector('.document-workflow');
      workflow?.scrollIntoView({ behavior: 'auto', block: 'start' });
      workflow?.querySelector('.document-main, .final-polish-studio, .finalization-review')?.scrollTo?.({ top: 0 });
    }, 0);
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
    inspectorTab = 'rewrite';
    busy = 'AI가 원문을 보존한 변경안을 작성하는 중'; error = ''; activeProposal = null;
    try {
      activeProposal = await api.post(`/blocks/${block.id}/rewrite`, { operation: rewriteOperation, instruction: rewriteInstruction, direction_card_ids: [], voice_profile_id: finalVoiceProfileId || null });
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
    inspectorTab = 'candidates';
    busy = 'AI가 초안에서 설정 후보를 찾는 중'; error = '';
    try {
      const created = await api.post(`/documents/${selected.id}/extract-candidates`, {});
      candidates = [...created, ...candidates];
      message = `${created.length}개의 후보를 추출했습니다. 아직 정식 설정에는 반영되지 않았습니다.`;
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  async function runProseAudit() {
    if (!selected || (draftDirty && !(await saveDraft({ quiet: true })))) return;
    inspectorTab = 'audit';
    busy = '문장 호흡과 표현 원칙을 점검하는 중'; error = ''; message = '';
    try {
      const result = await api.post(`/documents/${selected.id}/prose-audit`, {
        document_hash: finalization.current_draft_hash,
        voice_profile_id: finalVoiceProfileId || null,
        voice_profile_version: selectedVoiceProfile?.version || null
      });
      audits = await api.get(`/documents/${selected.id}/audits`);
      message = `필력 점검을 마쳤습니다. 검토할 항목 ${result.findings.length}개를 찾았습니다.`;
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  async function proposeProseRevision(finding) {
    if (!selected) return;
    inspectorTab = 'rewrite';
    busy = '점검 항목에 맞춘 부분 수정안을 만드는 중'; error = '';
    try {
      activeProposal = await api.post(`/documents/${selected.id}/prose-revision`, {
        finding_id: finding.id,
        document_hash: finalization.current_draft_hash,
        instruction: rewriteInstruction,
        voice_profile_id: finalVoiceProfileId || null
      });
      audits = [activeProposal, ...audits.filter((item) => item.id !== activeProposal.id)];
      workflowStep = 0; furthestStep = Math.max(furthestStep, 0);
      setTimeout(() => window.document.querySelector('.document-inspector')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0);
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
        refinement: {
          priorities: finalRefinementPriorities,
          intensity: finalRefinementIntensity,
          length_policy: finalLengthPolicy
        }
      });
      await goto(`/lorebook?entry=${result.lorebook_entry.id}`);
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }
</script>

<div class="page workspace-page documents-page">
  <div class="page-tools workflow-commandbar document-commandbar">
    <nav class="wizard-progress document-wizard-progress" aria-label="원고 완성 단계">
      {#each workflowSteps as step, index}
        <div class="wizard-progress-item">
          <button class="wizard-step-button" class:active={workflowStep === index} class:complete={index < workflowStep || index <= furthestStep && index !== workflowStep} disabled={index > furthestStep} aria-current={workflowStep === index ? 'step' : undefined} on:click={() => setWorkflowStep(index)}>
            <span>{index + 1}</span><div><strong>{step.short}</strong><small>{index === 0 ? selected?.title || '초안 선택 필요' : index === 1 ? `${selectedRefinementLabels.length}개 보강 목표` : finalization?.lorebook_entry ? '로어북 글 다시 다듬기' : '로어북에 새 글 저장'}</small></div>
          </button>
          <HelpTip label={`${step.short} 단계 설명`} text={`${step.title} ${step.copy}`} />
        </div>
      {/each}
    </nav>
    <div class="project-tools"><label style="min-width:260px">현재 프로젝트<select bind:value={projectId} on:change={changeProject}>{#each projects as project}<option value={project.id}>{project.name}</option>{/each}</select></label><ProjectCreator onCreated={projectCreated} /></div>
  </div>

  {#if error}<p class="notice-error">{error}</p>{/if}
  {#if busy}<div class="working-banner" role="status"><span></span><strong>{busy}…</strong><small>현재 초안과 설정은 그대로 보존됩니다.</small></div>{/if}

  <section class="wizard-shell document-workflow">
    {#if documents.length}<div class="document-contextbar"><label class="workflow-document-select">작업할 초안 {#if draftDirty}<span class="draft-dirty">저장 안 됨</span>{/if}<select value={selected?.id || ''} on:change={(event) => changeDocument(documents.find((item) => item.id === event.currentTarget.value) || null)}>{#each documents as document}<option value={document.id}>{document.title}</option>{/each}</select></label></div>{/if}

    {#if !selected}
      <div class="empty-state workflow-empty">‘글 만들기’에서 초안을 만들면 이곳에서 편집하고 로어북 글로 완성할 수 있습니다.</div>
    {:else if workflowStep === 0}
      <div class="document-edit-stage">
        <button class="secondary mobile-inspector-jump" on:click={scrollToDocumentTools}>원고 도구 보기 · 부분 재작성 · 점검 · 설정 후보 ↓</button>
        <main class="stack document-main">
          <div class="document-toolbar">
            <label class="document-title-field"><span>초안 제목</span><input class="document-title-input" aria-label="초안 제목" bind:value={selected.title} on:input={markDraftDirty} /></label>
            <div class="document-toolbar-actions"><label class="compact-status"><span>상태</span><select bind:value={selected.status} on:change={markDraftDirty}><option value="draft">초안</option><option value="review">검토 중</option><option value="approved">완료</option><option value="archived">보관</option></select></label><button class="secondary" disabled={!!busy} on:click={() => saveDraft()}>저장</button><a class="ghost" href={`${API_BASE}/documents/${selected.id}/export?format=markdown`} target="_blank">내보내기</a></div>
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
        <aside class="document-inspector" aria-label="원고 도구">
          <button class="ghost mobile-draft-return" on:click={scrollToDraft}>↑ 초안으로 돌아가기</button>
          <header class="document-inspector-heading"><div><span>원고 도구</span><strong>{inspectorTab === 'rewrite' ? '부분 재작성' : inspectorTab === 'audit' ? '문장 점검' : '설정 후보'}</strong></div><small>필요한 도구 하나만 열어 둡니다.</small></header>
          <div class="document-inspector-tabs" role="tablist" aria-label="원고 도구 선택">
            <button role="tab" aria-selected={inspectorTab === 'rewrite'} class:active={inspectorTab === 'rewrite'} on:click={() => inspectorTab = 'rewrite'}>재작성</button>
            <button role="tab" aria-selected={inspectorTab === 'audit'} class:active={inspectorTab === 'audit'} on:click={() => inspectorTab = 'audit'}>문장 점검</button>
            <button role="tab" aria-selected={inspectorTab === 'candidates'} class:active={inspectorTab === 'candidates'} on:click={() => inspectorTab = 'candidates'}>설정 후보 <span>{candidates.filter((item) => item.status === 'CANDIDATE').length}</span></button>
          </div>
          {#if inspectorTab === 'rewrite'}
            <section class="document-tool-panel stack" role="tabpanel"><label>작업<select bind:value={rewriteOperation}><option value="shorter">더 짧게</option><option value="longer">더 자세히</option><option value="add_example">사례 추가</option><option value="expository">설명형으로</option><option value="scene">장면형으로</option><option value="style_only">사실 유지·문체만</option><option value="transition">앞뒤 연결만</option></select></label><label>추가 지시<textarea bind:value={rewriteInstruction} placeholder="바꿀 방향이 있을 때만 적으세요."></textarea></label>{#if activeProposal}<pre class="document-proposal">{activeProposal.proposed_diff}</pre><div class="row"><button class="primary" on:click={() => decideProposal('apply')}>변경안 적용</button><button class="ghost" on:click={() => decideProposal('dismiss')}>폐기</button></div>{:else}<p class="small">원하는 문단의 ‘부분 재작성’을 누르면 원문을 보존한 변경안이 이곳에 나타납니다.</p>{/if}</section>
          {:else if inspectorTab === 'audit'}
            <section class="document-tool-panel stack" role="tabpanel"><div class="document-tool-action"><p>현재 선택한 <strong>{selectedVoiceProfile?.name || '모델 기본 문체'}</strong>를 기준으로 호흡과 반복을 점검합니다. 원문은 자동으로 바뀌지 않습니다.</p><button class="secondary" disabled={!!busy} on:click={runProseAudit}>필력 점검</button></div><div class="evidence-flow">{#each audits.filter((item) => item.audit_type !== 'REWRITE').slice(0, 12) as finding}<div class="evidence-item"><strong>{finding.audit_type === 'PROSE' ? '필력 점검' : auditTypeLabels[finding.audit_type] || '원고 점검'}</strong><small>{finding.message}</small>{#if finding.audit_type === 'PROSE' && finding.block_id}<button class="ghost" on:click={() => proposeProseRevision(finding)}>이 항목 수정안 만들기</button>{/if}</div>{/each}{#if !audits.filter((item) => item.audit_type !== 'REWRITE').length}<div class="evidence-item"><strong>기록된 경고 없음</strong><small>필요할 때 점검을 실행하세요.</small></div>{/if}</div></section>
          {:else}
            <section class="document-tool-panel stack" role="tabpanel"><div class="document-tool-action"><p>초안에서 새 설정으로 검토할 문장을 찾습니다. 승인 전에는 세계관 설정에 반영되지 않습니다.</p><button class="secondary" on:click={extractNewCandidates}>설정 후보 찾기</button></div>{#each candidates.filter((item) => item.status === 'CANDIDATE').slice(0, 5) as candidate}<div class="evidence-item"><strong>{candidate.title}</strong><small>{candidate.summary || candidate.candidate_sentence}</small><div class="candidate-actions"><button class="ghost" on:click={() => decideCandidate(candidate, 'this_document_only')}>이번 글만</button><button class="secondary" on:click={() => decideCandidate(candidate, 'save_draft')}>설정 초안</button><button class="primary" on:click={() => decideCandidate(candidate, 'approve_canon')}>정식 설정 승인</button></div></div>{/each}{#if !candidates.filter((item) => item.status === 'CANDIDATE').length}<div class="evidence-item"><strong>승인 대기 후보 없음</strong><small>후보 찾기를 실행해도 자동 승인되지 않습니다.</small></div>{/if}</section>
          {/if}
        </aside>
      </div>
      <footer class="wizard-actions"><small>{draftDirty ? '다음 단계로 가면 변경 내용을 자동 저장합니다.' : '모든 변경 내용이 저장되었습니다.'}</small><button class="primary" disabled={!!busy} on:click={() => continueTo(1)}>저장하고 완성 다듬기로 계속 →</button></footer>
    {:else if workflowStep === 1}
      <div class="final-polish-studio">
        <aside class="output-specimen final-output-specimen final-polish-source" aria-label="초안에서 이어받은 원고 기준">
          <span class="specimen-mark">{outputMark(finalOutputProfile)}</span>
          <div><p>{selected.title}</p><h2>초안에서 이어받은 기준</h2><blockquote>글 만들기에서 정한 형식과 관점은 다시 고르지 않습니다. 최신 초안의 설계를 보존한 채 필요한 완성도만 높입니다.</blockquote></div>
          <dl class="specimen-selection-summary" aria-label="이어받은 원고 설정"><div><dt>형식</dt><dd>{selectedProfile?.name || finalOutputProfile}</dd></div><div><dt>시점</dt><dd>{selectedViewpoint.title}</dd></div><div><dt>시제</dt><dd>{selectedTense.title}</dd></div><div><dt>목표 분량</dt><dd>{selectedLength.title} · {finalLengthCopy}</dd></div><div><dt>전개 방식</dt><dd>{selectedRecipe?.name || '미지정'}</dd></div><div><dt>문체·필력</dt><dd>{selectedVoiceProfile?.name || '모델 기본 문체'}</dd></div></dl>
          <footer><span>초안 설계 유지</span><span>새 설정 자동 추가 금지</span></footer>
        </aside>
        <div class="final-polish-deck">
          <header class="final-polish-heading"><span>완성 다듬기</span><h2>초안의 무엇을 더 강하게 만들까요?</h2><p>선택한 항목만 Writer가 집중해서 손봅니다. 프로젝트 사실과 원래 주제는 바꾸지 않습니다.</p></header>
          <section class="final-polish-section"><header><span>보강 목표</span><strong>한 개 이상 선택하세요.</strong></header><div class="refinement-priority-grid" role="group" aria-label="보강 목표">{#each refinementPriorityOptions as option}<button class:selected={finalRefinementPriorities.includes(option.value)} aria-pressed={finalRefinementPriorities.includes(option.value)} on:click={() => toggleRefinementPriority(option.value)}><strong>{option.title}</strong><small>{option.copy}</small></button>{/each}</div></section>
          <div class="final-polish-pair">
            <section class="final-polish-section"><header><span>다듬기 강도</span><strong>초안 구조를 얼마나 손볼까요?</strong></header><div class="refinement-choice-grid" role="group" aria-label="다듬기 강도">{#each refinementIntensityOptions as option}<button class:selected={finalRefinementIntensity === option.value} aria-pressed={finalRefinementIntensity === option.value} on:click={() => finalRefinementIntensity = option.value}><strong>{option.title}</strong><small>{option.copy}</small></button>{/each}</div></section>
            <section class="final-polish-section"><header><span>분량 방향</span><strong>기존 목표 안에서 조정합니다.</strong></header><div class="refinement-choice-grid" role="group" aria-label="분량 방향">{#each finalLengthPolicyOptions as option}<button class:selected={finalLengthPolicy === option.value} aria-pressed={finalLengthPolicy === option.value} on:click={() => finalLengthPolicy = option.value}><strong>{option.title}</strong><small>{option.copy}</small></button>{/each}</div></section>
          </div>
          <section class="final-polish-instruction"><label>이번 다듬기에만 추가할 요청<textarea bind:value={finalInstruction} placeholder="예: 마지막 문단이 첫 장면의 이미지를 되받도록 다듬어 주세요."></textarea></label><small>형식·주제·시점·시제와 세계관 사실은 변경하지 않습니다.</small></section>
        </div>
      </div>
      <footer class="wizard-actions"><button class="ghost" on:click={() => setWorkflowStep(0)}>← 초안 편집</button><button class="primary" on:click={() => continueTo(2)}>다듬기 확인으로 계속 →</button></footer>
    {:else}
      <div class="finalization-review">
        {#if finalization?.status === 'stale'}<p class="notice-error"><strong>로어북 글을 만든 뒤 초안이 바뀌었습니다.</strong> 지금 실행하면 최신 초안으로 교체됩니다.</p>{/if}
        <article class="final-review-sheet"><header><span>로어북에 보낼 원고</span><h2>{selected.title}</h2><p>{selectedProfile?.name || finalOutputProfile} · {selectedViewpoint.title} · {selectedTense.title} · 초안 설계 유지</p></header><dl><div><dt>보강 목표</dt><dd>{selectedRefinementLabels.join(' · ')}</dd></div><div><dt>다듬기 범위</dt><dd>{finalRefinementIntensityLabel} · {finalLengthPolicyLabel}</dd></div><div><dt>유지할 설계</dt><dd>{selectedRecipe?.name || '전개 방식 미지정'} · {selectedVoiceProfile?.name || '모델 기본 문체'}</dd></div><div><dt>추가 요청</dt><dd>{finalInstruction || '없음'}</dd></div></dl></article>
        <section class="lorebook-destination"><div><p class="eyebrow">저장 위치</p><h3>완성본은 로어북에 별도 저장됩니다.</h3><p>초안 문단과 로어북 글은 서로 덮어쓰지 않습니다. 로어북에서 완성된 글만 읽고 편집하고 내보낼 수 있습니다.</p></div><span>초안 → Writer → 로어북</span></section>
      </div>
      <footer class="wizard-actions"><button class="ghost" on:click={() => setWorkflowStep(1)}>← 완성 다듬기</button><button class="primary final-generate-button" disabled={!!busy} on:click={finalizeDocument}>{finalization?.lorebook_entry ? '최신 초안으로 완성본 다시 다듬기' : '초안 다듬어 로어북에 저장'}</button></footer>
    {/if}
  </section>
  {#if message}<p class="success">{message}</p>{/if}
</div>
