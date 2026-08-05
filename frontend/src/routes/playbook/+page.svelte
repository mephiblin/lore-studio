<script>
  import { onMount } from 'svelte';
  import ProjectCreator from '$lib/components/ProjectCreator.svelte';
  import { api } from '$lib/api';
  import { categoryLabel, moveLabels, roleLabel } from '$lib/labels';
  import { initialProjectId, rememberProject } from '$lib/project';

  let projects = [], pages = [], cards = [], recipes = [];
  let projectId = '', recipeId = '', outputProfile = 'lore_article', userDirection = '';
  let subjectIds = [], backgroundIds = [], elementIds = [], conflictIds = [], directionCardIds = [];
  let length = 'normal', customLength = 4000, detailLevel = 3, contextDepth = 'balanced', creativity = 'conservative', mystery = 4, seed = 42;
  let viewpoint = 'omniscient', tense = 'present';
  let conceptSearch = '', categoryFilter = 'all';
  let session = null, preview = null, plan = null, document = null;
  let busy = '', error = '', planDirty = false;

  const slotLabels = { subject: '주제', background: '배경', elements: '주요 요소', conflicts: '갈등·변수' };
  $: selectedCards = cards.filter((card) => directionCardIds.includes(card.id));
  $: cardConflicts = selectedCards.flatMap((card) => selectedCards.filter((other) => other.id !== card.id && (card.incompatible_tags || []).some((tag) => (other.tags || []).includes(tag))).map((other) => `${card.title} ↔ ${other.title}`));
  $: estimatedTokens = Math.ceil((length === 'custom' ? customLength : ({ short: 1200, normal: 3000, long: 6500, very_long: 12000 }[length] || 3000)) * 1.8);
  $: visiblePages = pages.filter((page) => {
    const text = `${page.title} ${page.summary} ${(page.tags || []).join(' ')}`.toLowerCase();
    return (!conceptSearch || text.includes(conceptSearch.toLowerCase())) && (categoryFilter === 'all' || page.category_key === categoryFilter) && !['DISCOURSE_REFERENCE', 'REJECTED'].includes(page.usage_role);
  });
  $: subject = pages.find((page) => subjectIds.includes(page.id));

  onMount(loadInitial);

  async function loadInitial() {
    try {
      [projects, recipes] = await Promise.all([api.get('/projects'), api.get('/writing-recipes')]);
      recipeId = recipes.find((item) => item.key === 'progressive_exposition')?.id || recipes[0]?.id || '';
      projectId = initialProjectId(projects);
      if (projectId) await loadProjectData();
    } catch (e) { error = e.message; }
  }

  async function changeProject() {
    rememberProject(projectId);
    await loadProjectData();
  }

  async function projectCreated(project) {
    projects = [project, ...projects];
    projectId = project.id;
    await loadProjectData();
  }

  async function loadProjectData() {
    if (!projectId) return;
    try {
      [pages, cards] = await Promise.all([api.get(`/concept-pages?project_id=${projectId}`), api.get(`/direction-cards?project_id=${projectId}`)]);
      subjectIds = []; backgroundIds = []; elementIds = []; conflictIds = []; directionCardIds = [];
      resetRun();
    } catch (e) { error = e.message; }
  }

  function resetRun() { session = preview = plan = document = null; planDirty = false; }

  function slotFor(pageId) {
    if (subjectIds.includes(pageId)) return 'subject';
    if (backgroundIds.includes(pageId)) return 'background';
    if (elementIds.includes(pageId)) return 'elements';
    if (conflictIds.includes(pageId)) return 'conflicts';
    return '';
  }

  function removeEverywhere(pageId) {
    subjectIds = subjectIds.filter((id) => id !== pageId);
    backgroundIds = backgroundIds.filter((id) => id !== pageId);
    elementIds = elementIds.filter((id) => id !== pageId);
    conflictIds = conflictIds.filter((id) => id !== pageId);
  }

  function assignConcept(pageId, slot) {
    removeEverywhere(pageId);
    if (slot === 'subject') subjectIds = [pageId];
    if (slot === 'background') backgroundIds = [...backgroundIds, pageId];
    if (slot === 'elements') elementIds = [...elementIds, pageId];
    if (slot === 'conflicts') conflictIds = [...conflictIds, pageId];
    resetRun();
  }

  function removeConcept(pageId) { removeEverywhere(pageId); resetRun(); }
  function selectedPages(ids) { return ids.map((id) => pages.find((page) => page.id === id)).filter(Boolean); }

  function toggleDirection(cardId) {
    directionCardIds = directionCardIds.includes(cardId) ? directionCardIds.filter((id) => id !== cardId) : [...directionCardIds, cardId];
    resetRun();
  }

  async function ensureSession() {
    if (session) return session;
    session = await api.post('/playbook-sessions', {
      project_id: projectId, name: `${subject?.title || '새 원고'} 플레이북`,
      concept_slots: { subject: subjectIds, background: backgroundIds, elements: elementIds, conflicts: conflictIds, wildcards: [] },
      direction_card_ids: directionCardIds, user_direction: userDirection,
      writing_recipe_id: recipeId, output_profile: outputProfile,
      settings_json: {
        length, custom_length: length === 'custom' ? Number(customLength) : null,
        detail_level: Number(detailLevel), context_depth: contextDepth, creativity,
        mystery_preservation: Number(mystery), viewpoint, tense
      },
      seed: Number(seed) || 0
    });
    return session;
  }

  async function savePlan() {
    if (!session || !plan) return;
    session = await api.patch(`/playbook-sessions/${session.id}/plan`, { plan_json: plan });
    planDirty = false;
  }

  async function runAction(kind) {
    error = '';
    busy = kind === 'context-preview' ? '선택한 자료를 검토하는 중' : kind === 'plan' ? 'AI가 문단 구성을 만드는 중' : 'Writer가 원고를 작성하는 중';
    try {
      const current = await ensureSession();
      if (kind === 'generate' && planDirty) await savePlan();
      if (kind === 'generate') {
        await api.postEvents(`/playbook-sessions/${current.id}/generate/stream`, {}, (event, data) => {
          if (event === 'progress') busy = data.message;
          if (event === 'error') throw new Error(`${data.message} (${data.code})`);
          if (event === 'complete') { session = data.session; plan = data.plan; document = data.document; }
        });
        return;
      }
      const result = await api.post(`/playbook-sessions/${current.id}/${kind}`, {});
      session = result.session;
      if (kind === 'context-preview') preview = result.context_preview;
      if (kind === 'plan') { plan = result.plan; planDirty = false; }
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  function updateBlock(index, key, value) { plan.blocks[index][key] = value; plan = { ...plan }; planDirty = true; }
  function moveBlock(index, delta) { const target = index + delta; if (target < 0 || target >= plan.blocks.length) return; const next = [...plan.blocks]; [next[index], next[target]] = [next[target], next[index]]; plan = { ...plan, blocks: next }; planDirty = true; }
  function duplicateBlock(index) { const next = [...plan.blocks]; next.splice(index + 1, 0, { ...plan.blocks[index], locked: false }); plan = { ...plan, blocks: next }; planDirty = true; }
  function removeBlock(index) { plan = { ...plan, blocks: plan.blocks.filter((_, i) => i !== index) }; planDirty = true; }
</script>

<div class="page playbook-page">
  <div class="page-header">
    <div><p class="eyebrow">글 만들기</p><h1>쓸 대상과 방향을 고르세요.</h1><p>자료를 섞는 이유를 확인하고, 문단 구성을 검토한 뒤 원고를 작성합니다.</p></div>
    <div class="project-tools"><label class="project-select">현재 프로젝트<select bind:value={projectId} on:change={changeProject}>{#each projects as project}<option value={project.id}>{project.name}</option>{/each}</select></label><ProjectCreator onCreated={projectCreated} /></div>
  </div>

  {#if error}<p class="notice-error">{error}</p>{/if}
  {#if busy}<div class="working-banner" role="status"><span></span><strong>{busy}…</strong><small>선택한 자료와 현재 단계는 저장됩니다.</small></div>{/if}

  <div class="route-rail" aria-label="원고 생성 단계">
    <span class:done={!!subject}>1 <strong>자료 선택</strong></span>
    <span class:done={!!preview}>2 <strong>근거 확인</strong></span>
    <span class:done={!!plan}>3 <strong>문단 구성</strong></span>
    <span class:done={!!document}>4 <strong>원고 완성</strong></span>
  </div>

  <section class="playbook-section material-workspace">
    <div class="section-copy"><span class="step-number">1</span><div><h2>원고에 쓸 자료</h2><p>주제는 한 개가 필요합니다. 나머지 자료는 글에서 맡을 역할을 지정해 추가하세요.</p></div></div>
    <div class="selection-board">
      <div class="selection-slot subject-slot">
        <span>주제 · 필수</span>
        {#if subject}<button class="selected-chip prominent" on:click={() => removeConcept(subject.id)}><strong>{subject.title}</strong><small>{subject.summary}</small><i>×</i></button>{:else}<p>아래 자료에서 <strong>주제로 쓰기</strong>를 누르세요.</p>{/if}
      </div>
      {#each [['background', backgroundIds], ['elements', elementIds], ['conflicts', conflictIds]] as [slot, ids]}
        <div class="selection-slot"><span>{slotLabels[slot]} · 선택</span><div class="chip-row">{#each selectedPages(ids) as page}<button class="selected-chip" on:click={() => removeConcept(page.id)}>{page.title} <i>×</i></button>{/each}{#if !ids.length}<small>선택 안 함</small>{/if}</div></div>
      {/each}
    </div>

    <div class="concept-library card">
      <div class="library-toolbar"><div><strong>프로젝트 자료</strong><small>{visiblePages.length}개 보임</small></div><input aria-label="원고 자료 검색" bind:value={conceptSearch} placeholder="제목·태그·요약 검색" /><select aria-label="자료 종류" bind:value={categoryFilter}><option value="all">모든 종류</option><option value="person">인물</option><option value="place">장소</option><option value="event">사건</option><option value="artifact">유물·기술</option><option value="free">기타</option></select></div>
      <div class="concept-card-grid">
        {#each visiblePages as page}
          <article class:assigned={!!slotFor(page.id)} class="concept-choice-card">
            <div class="row spread"><span class="badge">{categoryLabel(page.category_key)}</span>{#if slotFor(page.id)}<span class="assigned-label">{slotLabels[slotFor(page.id)]}</span>{/if}</div>
            <h3>{page.title}</h3><p>{page.summary || '요약이 없습니다.'}</p><small>{roleLabel(page.usage_role)}</small>
            <div class="assign-actions">
              <button class="primary" on:click={() => assignConcept(page.id, 'subject')}>주제로 쓰기</button>
              <button class="ghost" on:click={() => assignConcept(page.id, 'background')}>배경</button>
              <button class="ghost" on:click={() => assignConcept(page.id, 'elements')}>요소</button>
              <button class="ghost" on:click={() => assignConcept(page.id, 'conflicts')}>갈등</button>
            </div>
          </article>
        {/each}
      </div>
    </div>
  </section>

  <section class="playbook-section">
    <div class="section-copy"><span class="step-number">2</span><div><h2>글의 방향</h2><p>세계관 사실이 아니라 전개 원칙입니다. 선택하지 않아도 원고를 만들 수 있습니다.</p></div></div>
    <div class="direction-option-grid">
      {#each cards as card}
        <button class:selected={directionCardIds.includes(card.id)} class="direction-option" aria-pressed={directionCardIds.includes(card.id)} on:click={() => toggleDirection(card.id)}>
          <span class="choice-check">{directionCardIds.includes(card.id) ? '✓' : '+'}</span>
          <strong>{card.title}</strong><p>{card.body}</p>
          {#if card.parsed_rules?.must_include?.length}<small>반드시 포함 · {card.parsed_rules.must_include.slice(0, 2).join(' · ')}</small>{/if}
        </button>
      {/each}
      {#if !cards.length}<a class="empty-state" href="/editor">아직 방향 규칙이 없습니다. 세계관 자료에서 만들기 →</a>{/if}
    </div>
    {#if cardConflicts.length}<div class="notice-error">함께 쓸 수 없는 규칙: {[...new Set(cardConflicts)].join(', ')}</div>{/if}
    <label class="wide-field">이번 원고에만 추가할 지시 <textarea bind:value={userDirection} on:input={resetRun} placeholder="예: 레아의 추적보다 백야항 시민의 일상을 중심에 둔다."></textarea></label>
  </section>

  <section class="playbook-section settings-section">
    <div class="section-copy"><span class="step-number">3</span><div><h2>글의 형태</h2><p>어떤 문서로 쓸지와 얼마나 자세히 다룰지 정합니다.</p></div></div>
    <div class="settings-grid">
      <div class="card stack">
        <h3>집필 방식</h3>
        <label>정보를 풀어낼 순서<select bind:value={recipeId} on:change={resetRun}>{#each recipes as recipe}<option value={recipe.id}>{recipe.name}</option>{/each}</select></label>
        {#if recipeId}{@const recipe = recipes.find((item) => item.id === recipeId)}{#if recipe}<p class="field-help">{recipe.description}</p>{/if}{/if}
        <label>결과물<select bind:value={outputProfile} on:change={resetRun}><option value="lore_article">세계관 설명 글</option><option value="video_narration">영상 내레이션</option><option value="novel_prose">소설 장면</option><option value="in_universe_report">세계 내부 문서</option></select></label>
        <div class="grid-2"><label>시점<select bind:value={viewpoint} on:change={resetRun}><option value="omniscient">전지적 설명자</option><option value="first_observer">1인칭 관찰자</option><option value="third_limited">3인칭 제한</option></select></label><label>시제<select bind:value={tense} on:change={resetRun}><option value="present">현재형 중심</option><option value="past">과거형 중심</option></select></label></div>
      </div>
      <div class="card stack">
        <div class="row spread"><h3>분량과 자유도</h3><span class="badge">예상 {estimatedTokens.toLocaleString()} tokens</span></div>
        <div class="grid-2"><label>분량<select bind:value={length} on:change={resetRun}><option value="short">짧게 · 약 1,200자</option><option value="normal">보통 · 약 3,000자</option><option value="long">길게 · 약 6,500자</option><option value="very_long">매우 길게 · 약 12,000자</option><option value="custom">직접 지정</option></select></label>{#if length === 'custom'}<label>목표 글자 수<input type="number" min="500" bind:value={customLength} on:change={resetRun} /></label>{/if}<label>자료 반영 범위<select bind:value={contextDepth} on:change={resetRun}><option value="core">선택한 핵심만</option><option value="balanced">관련 자료까지 균형 있게</option><option value="wide">세계 맥락을 넓게</option><option value="max">가능한 자료를 최대로</option></select></label><label>새 설정 제안<select bind:value={creativity} on:change={resetRun}><option value="strict">하지 않음</option><option value="conservative">최소한</option><option value="balanced">필요할 때</option><option value="free">적극적</option></select></label></div>
        <label>설명의 자세함 · {detailLevel}/5<input type="range" min="1" max="5" bind:value={detailLevel} on:change={resetRun} /></label>
        <label>아직 답하지 않을 질문 보존 · {mystery}/5<input type="range" min="1" max="5" bind:value={mystery} on:change={resetRun} /></label>
        <details><summary>재현용 시드</summary><div class="details-body"><label>같은 선택과 이 번호는 같은 조합을 만듭니다.<input type="number" bind:value={seed} on:change={resetRun} /></label></div></details>
      </div>
    </div>
  </section>

  <section class="review-dock">
    <div class="review-summary"><span class:missing={!subject}><strong>{subject ? subject.title : '주제를 선택하세요'}</strong><small>{subject ? `보조 자료 ${backgroundIds.length + elementIds.length + conflictIds.length}개 · 방향 규칙 ${directionCardIds.length}개` : '원고를 만들려면 주제 하나가 필요합니다.'}</small></span></div>
    <div class="run-actions"><button class="secondary" disabled={!!busy || !subject} on:click={() => runAction('context-preview')}>{preview ? '✓ 근거 확인됨' : '1. 선택 근거 확인'}</button><button class="secondary" disabled={!!busy || !subject || !preview} on:click={() => runAction('plan')}>{plan ? '✓ 구성안 완료' : '2. 문단 구성 만들기'}</button><button class="primary" disabled={!!busy || !plan || cardConflicts.length} on:click={() => runAction('generate')}>3. 원고 작성</button></div>
  </section>

  {#if preview}
    <section class="playbook-section evidence-review">
      <div class="section-copy"><span class="step-number">✓</span><div><h2>원고에 들어갈 근거</h2><p>확정된 사실과 아직 답하지 않을 질문을 섞지 않고 확인하세요.</p></div></div>
      <div class="evidence-columns">
        <div><h3>확정된 사실</h3>{#each preview.locked_facts as item}<div class="evidence-item"><strong>{item.page_title}</strong><small>{item.fact}</small></div>{/each}{#if !preview.locked_facts.length}<p class="empty-mini">확정된 사실이 없습니다.</p>{/if}</div>
        <div><h3>열린 질문</h3>{#each preview.open_questions as item}<div class="evidence-item"><strong>{item.page_title}</strong><small>{item.question}</small></div>{/each}{#if !preview.open_questions.length}<p class="empty-mini">열린 질문이 없습니다.</p>{/if}</div>
        <div><h3>바꾸면 안 되는 것</h3>{#each preview.forbidden_material as item}<div class="evidence-item"><strong>금지 변경</strong><small>{item.rule}</small></div>{/each}{#if !preview.forbidden_material.length}<p class="empty-mini">지정된 금지 변경이 없습니다.</p>{/if}</div>
      </div>
      {#each preview.warnings || [] as warning}<p class="notice-error">{warning}</p>{/each}
    </section>
  {/if}

  {#if plan}
    <section class="playbook-section plan-editor">
      <div class="row spread wrap"><div><p class="eyebrow">문단 구성</p><h2>{plan.title}</h2><p>{plan.angle}</p></div><button class="secondary" disabled={!planDirty} on:click={savePlan}>{planDirty ? '변경한 구성 저장' : '저장됨'}</button></div>
      <div class="plan-blocks">
        {#each plan.blocks as block, index}
          <article class="plan-block">
            <div class="plan-index">{String(index + 1).padStart(2, '0')}</div>
            <div class="stack"><label>문단 역할<select value={block.move} on:change={(e) => updateBlock(index, 'move', e.currentTarget.value)}>{#each Object.entries(moveLabels) as [value, label]}<option {value}>{label}</option>{/each}</select></label><label>이 문단이 할 일<input value={block.purpose} on:input={(e) => updateBlock(index, 'purpose', e.currentTarget.value)} /></label><div class="row wrap"><span class="badge">근거 {block.evidence_ids.length}개</span><label class="inline-label"><input type="number" min="50" value={block.word_budget} on:input={(e) => updateBlock(index, 'word_budget', Number(e.currentTarget.value))} /> 자</label><label class="inline-label"><input type="checkbox" checked={block.locked} on:change={(e) => updateBlock(index, 'locked', e.currentTarget.checked)} /> 구성 잠금</label></div></div>
            <div class="block-actions"><button class="icon-button" aria-label="위로 이동" on:click={() => moveBlock(index, -1)}>↑</button><button class="icon-button" aria-label="아래로 이동" on:click={() => moveBlock(index, 1)}>↓</button><button class="ghost" on:click={() => duplicateBlock(index)}>복제</button><button class="danger-button" on:click={() => removeBlock(index)}>삭제</button></div>
          </article>
        {/each}
      </div>
    </section>
  {/if}

  {#if document}<div class="completion-banner"><div><strong>{document.title}</strong><span>{document.body_markdown.length.toLocaleString()}자 원고를 저장했습니다.</span></div><a class="primary" href="/documents">원고 편집으로 이동 →</a></div>{/if}
</div>
