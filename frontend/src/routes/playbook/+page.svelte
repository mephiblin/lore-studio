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
  let wizardStep = 0, furthestStep = 0;

  const slotLabels = { subject: '주제', background: '배경', elements: '주요 요소', conflicts: '갈등·변수' };
  const wizardSteps = [
    { key: 'subject', slot: 'subject', short: '주제', title: '무엇에 관한 글인가요?', copy: '원고의 중심이 될 자료 한 개를 선택하세요.', required: true, next: '배경으로 계속' },
    { key: 'background', slot: 'background', short: '배경', title: '어디서, 어떤 상황에서 벌어지나요?', copy: '주제를 이해하는 데 필요한 장소·시대·상황을 고르세요. 없어도 됩니다.', next: '주요 요소로 계속' },
    { key: 'elements', slot: 'elements', short: '주요 요소', title: '꼭 함께 다룰 것은 무엇인가요?', copy: '글에서 비중 있게 등장할 인물·사건·유물 등을 고르세요. 여러 개를 선택할 수 있습니다.', next: '갈등·변수로 계속' },
    { key: 'conflicts', slot: 'conflicts', short: '갈등·변수', title: '무엇이 긴장과 변화를 만드나요?', copy: '충돌, 위험, 반전의 원인이 될 자료를 고르세요. 없어도 됩니다.', next: '전개 방향으로 계속' },
    { key: 'direction', short: '전개 방향', title: '어떤 방식으로 전개할까요?', copy: '세계관 사실이 아니라 이 원고가 사실을 다루는 원칙을 고릅니다.', next: '글 형태로 계속' },
    { key: 'settings', short: '글 형태', title: '어떤 형태의 글로 만들까요?', copy: '집필 방식, 결과물, 시점·시제와 분량을 정하세요.', next: '확인·작성으로 계속' },
    { key: 'review', short: '확인·작성', title: '선택을 확인하고 원고를 만드세요.', copy: '선택한 자료와 설정을 확인한 뒤 근거 검토부터 시작합니다.' }
  ];
  $: selectedCards = cards.filter((card) => directionCardIds.includes(card.id));
  $: cardConflicts = selectedCards.flatMap((card) => selectedCards.filter((other) => other.id !== card.id && (card.incompatible_tags || []).some((tag) => (other.tags || []).includes(tag))).map((other) => `${card.title} ↔ ${other.title}`));
  $: estimatedTokens = Math.ceil((length === 'custom' ? customLength : ({ short: 1200, normal: 3000, long: 6500, very_long: 12000 }[length] || 3000)) * 1.8);
  $: visiblePages = pages.filter((page) => {
    const text = `${page.title} ${page.summary} ${(page.tags || []).join(' ')}`.toLowerCase();
    return (!conceptSearch || text.includes(conceptSearch.toLowerCase())) && (categoryFilter === 'all' || page.category_key === categoryFilter) && !['DISCOURSE_REFERENCE', 'REJECTED'].includes(page.usage_role);
  });
  $: subject = pages.find((page) => subjectIds.includes(page.id));
  $: activeStep = wizardSteps[wizardStep];
  $: activeSlot = activeStep?.slot || '';
  $: activeIds = activeSlot === 'subject' ? subjectIds : activeSlot === 'background' ? backgroundIds : activeSlot === 'elements' ? elementIds : activeSlot === 'conflicts' ? conflictIds : [];
  $: wizardPages = visiblePages.filter((page) => !slotFor(page.id) || slotFor(page.id) === activeSlot);
  $: totalSupporting = backgroundIds.length + elementIds.length + conflictIds.length;
  $: hasCurrentSelection = activeStep?.required || activeIds.length || activeStep?.key === 'settings' || activeStep?.key === 'direction' && directionCardIds.length;
  $: nextButtonLabel = activeStep?.next ? `${hasCurrentSelection ? '' : '선택 없이 '}${activeStep.next}` : '';

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
      wizardStep = 0; furthestStep = 0;
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

  function toggleConcept(pageId) {
    if (!activeSlot) return;
    if (activeIds.includes(pageId)) removeConcept(pageId);
    else assignConcept(pageId, activeSlot);
  }

  function setWizardStep(index) {
    if (index < 0 || index >= wizardSteps.length) return;
    wizardStep = index;
    furthestStep = Math.max(furthestStep, index);
    setTimeout(() => document.querySelector('.wizard-shell')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0);
  }

  function nextStep() {
    if (wizardStep === 0 && !subject) return;
    setWizardStep(wizardStep + 1);
  }

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

  <section class="wizard-shell">
    <nav class="wizard-progress" aria-label="글 만들기 선택 단계">
      {#each wizardSteps as step, index}
        <button class:active={wizardStep === index} class:complete={index < wizardStep || index <= furthestStep && index !== wizardStep} disabled={index > furthestStep} aria-current={wizardStep === index ? 'step' : undefined} on:click={() => setWizardStep(index)}>
          <span>{index + 1}</span><strong>{step.short}</strong>
        </button>
      {/each}
    </nav>

    <header class="wizard-heading">
      <div><p class="eyebrow">{wizardStep + 1} / {wizardSteps.length}</p><h2>{activeStep.title}</h2><p>{activeStep.copy}</p></div>
      {#if activeSlot}<span class="wizard-count">{activeIds.length}개 선택</span>{/if}
    </header>

    {#if activeSlot}
      <div class="wizard-layout">
        <aside class="wizard-ledger" aria-label="현재까지 선택한 자료">
          <strong>지금까지 선택</strong>
          {#each wizardSteps.slice(0, 4) as step, index}
            {@const ids = step.slot === 'subject' ? subjectIds : step.slot === 'background' ? backgroundIds : step.slot === 'elements' ? elementIds : conflictIds}
            <button class:current={wizardStep === index} disabled={index > furthestStep} on:click={() => setWizardStep(index)}>
              <span>{step.short}</span><small>{selectedPages(ids).map((page) => page.title).join(', ') || (step.required ? '선택 필요' : '선택 안 함')}</small>
            </button>
          {/each}
        </aside>

        <div class="wizard-picker card">
          <div class="library-toolbar"><div><strong>프로젝트 자료</strong><small>{wizardPages.length}개 선택 가능</small></div><input aria-label={`${activeStep.short} 자료 검색`} bind:value={conceptSearch} placeholder="제목·태그·요약 검색" /><select aria-label="자료 종류" bind:value={categoryFilter}><option value="all">모든 종류</option><option value="person">인물</option><option value="place">장소</option><option value="event">사건</option><option value="artifact">유물·기술</option><option value="free">기타</option></select></div>
          <div class="wizard-card-grid">
            {#each wizardPages as page}
              <button class:selected={activeIds.includes(page.id)} class="wizard-choice-card" aria-pressed={activeIds.includes(page.id)} on:click={() => toggleConcept(page.id)}>
                <span class="selection-mark">{activeIds.includes(page.id) ? '✓' : activeSlot === 'subject' ? '○' : '+'}</span>
                <span class="row spread"><span class="badge">{categoryLabel(page.category_key)}</span><small>{roleLabel(page.usage_role)}</small></span>
                <strong>{page.title}</strong><p>{page.summary || '요약이 없습니다.'}</p>
                <span class="selection-action">{activeIds.includes(page.id) ? '선택됨' : activeSlot === 'subject' ? '이 자료를 주제로 선택' : `${activeStep.short}에 추가`}</span>
              </button>
            {/each}
            {#if !wizardPages.length}<div class="empty-state">검색 조건에 맞는 자료가 없거나, 모든 자료가 앞 단계에 배정됐습니다.</div>{/if}
          </div>
        </div>
      </div>
    {:else if activeStep.key === 'direction'}
      <div class="direction-option-grid wizard-direction-grid">
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
    {:else if activeStep.key === 'settings'}
      <div class="settings-grid wizard-settings">
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
    {:else if activeStep.key === 'review'}
      <div class="wizard-review-grid">
        <article><div><span>주제</span><strong>{subject?.title}</strong></div><button class="ghost" on:click={() => setWizardStep(0)}>수정</button></article>
        <article><div><span>배경</span><strong>{selectedPages(backgroundIds).map((page) => page.title).join(', ') || '선택 안 함'}</strong></div><button class="ghost" on:click={() => setWizardStep(1)}>수정</button></article>
        <article><div><span>주요 요소</span><strong>{selectedPages(elementIds).map((page) => page.title).join(', ') || '선택 안 함'}</strong></div><button class="ghost" on:click={() => setWizardStep(2)}>수정</button></article>
        <article><div><span>갈등·변수</span><strong>{selectedPages(conflictIds).map((page) => page.title).join(', ') || '선택 안 함'}</strong></div><button class="ghost" on:click={() => setWizardStep(3)}>수정</button></article>
        <article><div><span>전개 방향</span><strong>{selectedCards.map((card) => card.title).join(', ') || '선택 안 함'}</strong></div><button class="ghost" on:click={() => setWizardStep(4)}>수정</button></article>
        <article><div><span>글 형태</span><strong>{outputProfile === 'lore_article' ? '세계관 설명 글' : outputProfile === 'video_narration' ? '영상 내레이션' : outputProfile === 'novel_prose' ? '소설 장면' : '세계 내부 문서'} · {viewpoint === 'omniscient' ? '전지적 설명자' : viewpoint === 'first_observer' ? '1인칭 관찰자' : '3인칭 제한'}</strong></div><button class="ghost" on:click={() => setWizardStep(5)}>수정</button></article>
      </div>
      <section class="wizard-run-panel">
        <div><strong>{subject?.title}</strong><span>보조 자료 {totalSupporting}개 · 방향 규칙 {directionCardIds.length}개</span></div>
        <div class="run-actions"><button class="secondary" disabled={!!busy || !subject} on:click={() => runAction('context-preview')}>{preview ? '✓ 근거 확인됨' : '1. 선택 근거 확인'}</button><button class="secondary" disabled={!!busy || !subject || !preview} on:click={() => runAction('plan')}>{plan ? '✓ 구성안 완료' : '2. 문단 구성 만들기'}</button><button class="primary" disabled={!!busy || !plan || cardConflicts.length} on:click={() => runAction('generate')}>3. 원고 작성</button></div>
      </section>
    {/if}

    {#if activeStep.key !== 'review'}
      <footer class="wizard-actions">
        <button class="ghost" disabled={wizardStep === 0} on:click={() => setWizardStep(wizardStep - 1)}>← 이전</button>
        <button class="primary" disabled={wizardStep === 0 && !subject || activeStep.key === 'direction' && cardConflicts.length} on:click={nextStep}>{nextButtonLabel} →</button>
      </footer>
    {/if}
  </section>

  {#if wizardStep === wizardSteps.length - 1 && preview}
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

  {#if wizardStep === wizardSteps.length - 1 && plan}
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

  {#if wizardStep === wizardSteps.length - 1 && document}<div class="completion-banner"><div><strong>{document.title}</strong><span>{document.body_markdown.length.toLocaleString()}자 원고를 저장했습니다.</span></div><a class="primary" href="/documents">원고 편집으로 이동 →</a></div>{/if}
</div>
