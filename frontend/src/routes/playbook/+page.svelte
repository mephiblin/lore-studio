<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import HelpTip from '$lib/components/HelpTip.svelte';
  import ProjectCreator from '$lib/components/ProjectCreator.svelte';
  import { api } from '$lib/api';
  import { moveDescriptions, moveLabels, roleLabel } from '$lib/labels';
  import { initialProjectId, rememberProject } from '$lib/project';

  let projects = [], pages = [], cards = [], recipes = [], categories = [];
  let projectId = '', recipeId = '', outputProfile = 'lore_article', userDirection = '';
  let subjectIds = [], backgroundIds = [], elementIds = [], conflictIds = [], directionCardIds = [];
  let length = 'normal', customLength = 4000, detailLevel = 3, contextDepth = 'balanced', creativity = 'conservative', mystery = 4, seed = 42;
  let viewpoint = 'omniscient', tense = 'present';
  let conceptSearch = '', categoryFilter = 'all', conceptScope = 'recommended', pageLimit = 18;
  let session = null, preview = null, plan = null, generatedDocument = null;
  let busy = '', error = '', planDirty = false;
  let wizardStep = 0, furthestStep = 0;

  const slotLabels = { subject: '주제', background: '배경', elements: '주요 요소', conflicts: '갈등·변수' };
  const wizardSteps = [
    { key: 'subject', slot: 'subject', short: '주제', title: '무엇에 관한 글인가요?', copy: '원고의 중심이 될 자료 한 개를 선택하세요.', required: true, next: '배경으로 계속' },
    { key: 'background', slot: 'background', short: '배경', title: '어디서, 어떤 상황에서 벌어지나요?', copy: '주제를 이해하는 데 필요한 장소·시대·상황을 고르세요. 없어도 됩니다.', next: '주요 요소로 계속' },
    { key: 'elements', slot: 'elements', short: '주요 요소', title: '꼭 함께 다룰 것은 무엇인가요?', copy: '글에서 비중 있게 등장할 인물·사건·유물 등을 고르세요. 여러 개를 선택할 수 있습니다.', next: '갈등·변수로 계속' },
    { key: 'conflicts', slot: 'conflicts', short: '갈등·변수', title: '무엇이 긴장과 변화를 만드나요?', copy: '충돌, 위험, 반전의 원인이 될 자료를 고르세요. 없어도 됩니다.', next: '집필 지침으로 계속' },
    { key: 'guidance', short: '집필 지침', title: '이번 글에서 무엇을 강조하거나 피할까요?', copy: '현재 프로젝트에 저장한 강조점과 금지 원칙입니다. 여러 개를 고르거나 건너뛸 수 있습니다.', next: '전개 방식으로 계속' },
    { key: 'recipe', short: '전개 방식', title: '글을 어떤 방식으로 풀어갈까요?', copy: '세계관 자료와 무관한 공통 전개 방식입니다. 정보가 드러나는 순서 하나를 고르세요.', required: true, next: '결과물 형태로 계속' },
    { key: 'settings', short: '결과물 형태', title: '어떤 결과물로 만들까요?', copy: '결과물 종류, 시점·시제와 분량을 정하세요.', next: '확인·작성으로 계속' },
    { key: 'review', short: '확인·작성', title: '선택을 확인하고 초안을 만드세요.', copy: '사용할 세계관을 확인하고, 글의 흐름을 정한 뒤 초안을 작성합니다.' }
  ];
  $: selectedCards = cards.filter((card) => directionCardIds.includes(card.id));
  $: selectedRecipe = recipes.find((recipe) => recipe.id === recipeId);
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
  $: wizardCandidates = visiblePages
    .filter((page) => !slotFor(page.id) || slotFor(page.id) === activeSlot)
    .filter((page) => conceptScope === 'all' || !!conceptSearch || activeIds.includes(page.id) || recommendedForSlot(page, activeSlot));
  $: wizardPages = wizardCandidates.slice(0, pageLimit);
  $: totalSupporting = backgroundIds.length + elementIds.length + conflictIds.length;
  $: hasCurrentSelection = activeIds.length || activeStep?.key === 'settings' || activeStep?.key === 'guidance' && directionCardIds.length || activeStep?.key === 'recipe' && !!recipeId;
  $: nextButtonLabel = activeStep?.next ? `${hasCurrentSelection ? '' : '선택 없이 '}${activeStep.next}` : '';
  $: progressSummaries = [
    subject?.title || '선택 필요',
    selectionSummary(backgroundIds),
    selectionSummary(elementIds),
    selectionSummary(conflictIds),
    selectedCards.length ? selectedCards.length === 1 ? selectedCards[0].title : `${selectedCards[0].title} 외 ${selectedCards.length - 1}개` : '선택 안 함',
    selectedRecipe?.name || '선택 필요',
    outputProfile === 'lore_article' ? '세계관 설명 글' : outputProfile === 'video_narration' ? '영상 내레이션' : outputProfile === 'novel_prose' ? '소설 장면' : '세계 내부 문서',
    generatedDocument ? '원고 완성' : plan ? '글의 흐름 준비됨' : preview ? '사용할 설정 확인됨' : '작성 전'
  ];

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
      [pages, cards, categories] = await Promise.all([
        api.get(`/concept-pages?project_id=${projectId}`),
        api.get(`/direction-cards?project_id=${projectId}`),
        api.get(`/categories?project_id=${projectId}`)
      ]);
      subjectIds = []; backgroundIds = []; elementIds = []; conflictIds = []; directionCardIds = [];
      wizardStep = 0; furthestStep = 0; conceptScope = 'recommended'; pageLimit = 18;
      resetRun();
    } catch (e) { error = e.message; }
  }

  function resetRun() { session = preview = plan = generatedDocument = null; planDirty = false; }

  function recommendedForSlot(page, slot) {
    const category = categories.find((item) => item.key === page.category_key);
    const slots = category?.template_json?.recommended_slots;
    return !Array.isArray(slots) || slots.includes(slot);
  }

  function recommendationCopy(slot) {
    const names = categories
      .filter((category) => (category.template_json?.recommended_slots || []).includes(slot))
      .map((category) => category.name);
    return names.length ? `${names.join(' · ')} 종류로 지정한 자료` : '현재 단계에 추천하도록 지정한 자료';
  }

  function categoryName(page) {
    return categories.find((item) => item.key === page?.category_key)?.name || page?.custom_category || page?.category_key || '종류 없음';
  }

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
  function selectionSummary(ids) {
    const selected = selectedPages(ids);
    if (!selected.length) return '선택 안 함';
    return selected.length === 1 ? selected[0].title : `${selected[0].title} 외 ${selected.length - 1}개`;
  }

  function toggleConcept(pageId) {
    if (!activeSlot) return;
    if (activeIds.includes(pageId)) removeConcept(pageId);
    else assignConcept(pageId, activeSlot);
  }

  function setWizardStep(index) {
    if (index < 0 || index >= wizardSteps.length) return;
    wizardStep = index;
    furthestStep = Math.max(furthestStep, index);
    conceptSearch = ''; categoryFilter = 'all'; conceptScope = 'recommended'; pageLimit = 18;
    setTimeout(() => window.document.querySelector('.wizard-shell')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0);
  }

  function nextStep() {
    if (wizardStep === 0 && !subject) return;
    setWizardStep(wizardStep + 1);
  }

  function toggleDirection(cardId) {
    directionCardIds = directionCardIds.includes(cardId) ? directionCardIds.filter((id) => id !== cardId) : [...directionCardIds, cardId];
    resetRun();
  }

  function selectRecipe(selectedId) {
    recipeId = selectedId;
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
    busy = kind === 'context-preview' ? '선택한 세계관을 정리하는 중' : kind === 'plan' ? 'AI가 글의 흐름을 만드는 중' : 'Writer가 초안을 작성하는 중';
    try {
      const current = await ensureSession();
      if (kind === 'generate' && planDirty) await savePlan();
      if (kind === 'generate') {
        let completedDocument = null;
        await api.postEvents(`/playbook-sessions/${current.id}/generate/stream`, {}, (event, data) => {
          if (event === 'progress') busy = data.message;
          if (event === 'error') throw new Error(`${data.message} (${data.code})`);
          if (event === 'complete') { session = data.session; plan = data.plan; generatedDocument = data.document; completedDocument = data.document; }
        });
        if (completedDocument) {
          busy = '완성된 원고를 여는 중';
          await goto(`/documents?document=${completedDocument.id}`);
        }
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

<div class="page playbook-page workspace-page">
  <div class="page-tools">
    <div class="project-tools"><label class="project-select">현재 프로젝트<select bind:value={projectId} on:change={changeProject}>{#each projects as project}<option value={project.id}>{project.name}</option>{/each}</select></label><ProjectCreator onCreated={projectCreated} /></div>
  </div>

  {#if error}<p class="notice-error">{error}</p>{/if}
  {#if busy}<div class="working-banner" role="status"><span></span><strong>{busy}…</strong><small>선택한 자료와 현재 단계는 저장됩니다.</small></div>{/if}

  <div class="playbook-workspace">
  <section class="wizard-shell">
    <nav class="wizard-progress" aria-label="글 만들기 선택 단계">
      {#each wizardSteps as step, index}
        <div class="wizard-progress-item">
          <button class="wizard-step-button" class:active={wizardStep === index} class:complete={index < wizardStep || index <= furthestStep && index !== wizardStep} disabled={index > furthestStep} aria-current={wizardStep === index ? 'step' : undefined} on:click={() => setWizardStep(index)}>
            <span>{index + 1}</span><div><strong>{step.short}</strong><small>{progressSummaries[index]}</small></div>
          </button>
          <HelpTip label={`${step.short} 단계 설명`} text={`${step.title} ${step.copy}`} />
        </div>
      {/each}
    </nav>

    {#if activeSlot}
      <div class="wizard-layout">
        <div class="wizard-picker card">
          <div class="library-toolbar">
            <div><strong>세계관 자료</strong><small>{wizardCandidates.length}개 중 {wizardPages.length}개 표시</small></div>
            <input aria-label={`${activeStep.short} 자료 검색`} bind:value={conceptSearch} on:input={() => pageLimit = 18} placeholder="제목·태그·요약 검색" />
            <select aria-label="자료 종류" bind:value={categoryFilter} on:change={() => pageLimit = 18}><option value="all">모든 종류</option>{#each categories as category}<option value={category.key}>{category.name}</option>{/each}</select>
          </div>
          <div class="wizard-scope-bar">
            <div><strong>{conceptScope === 'recommended' ? '이 단계의 추천 자료' : '모든 세계관 자료'}</strong><small>{conceptScope === 'recommended' ? recommendationCopy(activeSlot) : '종류나 역할과 관계없이 배정되지 않은 자료 전체'}</small></div>
            <div class="scope-switch" role="group" aria-label="자료 표시 범위"><button class:active={conceptScope === 'recommended'} on:click={() => { conceptScope = 'recommended'; pageLimit = 18; }}>추천</button><button class:active={conceptScope === 'all'} on:click={() => { conceptScope = 'all'; pageLimit = 18; }}>전체</button></div>
          </div>
          <div class="wizard-card-grid">
            {#each wizardPages as page}
              <button class:selected={activeIds.includes(page.id)} class="wizard-choice-card" aria-pressed={activeIds.includes(page.id)} on:click={() => toggleConcept(page.id)}>
                <span class="selection-mark">{activeIds.includes(page.id) ? '✓' : activeSlot === 'subject' ? '○' : '+'}</span>
                <span class="row spread"><span class="badge">{categoryName(page)}</span><small>{roleLabel(page.usage_role)}</small></span>
                <strong>{page.title}</strong><p>{page.summary || '요약이 없습니다.'}</p>
              </button>
            {/each}
            {#if !wizardPages.length}<div class="empty-state">검색 조건에 맞는 자료가 없거나, 모든 자료가 앞 단계에 배정됐습니다.</div>{/if}
          </div>
          {#if wizardPages.length < wizardCandidates.length}<button class="secondary wizard-load-more" on:click={() => pageLimit += 18}>자료 더 보기 · {wizardCandidates.length - wizardPages.length}개 남음</button>{/if}
        </div>
      </div>
    {:else if activeStep.key === 'guidance'}
      <div class="direction-option-grid wizard-direction-grid">
        {#each cards as card}
          <button class:selected={directionCardIds.includes(card.id)} class="direction-option" aria-pressed={directionCardIds.includes(card.id)} on:click={() => toggleDirection(card.id)}>
            <span class="choice-check">{directionCardIds.includes(card.id) ? '✓' : '+'}</span>
            <strong>{card.title}</strong><p>{card.body}</p>
            {#if card.parsed_rules?.must_include?.length}<small>반드시 포함 · {card.parsed_rules.must_include.slice(0, 2).join(' · ')}</small>{/if}
          </button>
        {/each}
        {#if !cards.length}<a class="empty-state" href="/editor">아직 집필 지침이 없습니다. 세계관 자료에서 만들기 →</a>{/if}
      </div>
      {#if cardConflicts.length}<div class="notice-error">함께 쓸 수 없는 지침: {[...new Set(cardConflicts)].join(', ')}</div>{/if}
      <label class="wide-field">이번 원고에만 추가할 지시 <textarea bind:value={userDirection} on:input={resetRun} placeholder="예: 레아의 추적보다 백야항 시민의 일상을 중심에 둔다."></textarea></label>
    {:else if activeStep.key === 'recipe'}
      <div class="recipe-option-grid">
        {#each recipes as recipe}
          <button class:selected={recipeId === recipe.id} class="recipe-option" aria-pressed={recipeId === recipe.id} on:click={() => selectRecipe(recipe.id)}>
            <span class="choice-check">{recipeId === recipe.id ? '✓' : '○'}</span>
            <span class="recipe-scope">모든 프로젝트에서 사용</span>
            <strong>{recipe.name}</strong>
            <p>{recipe.description}</p>
            <span class="recipe-flow" aria-label={`${recipe.name} 순서`}>
              {#each recipe.recipe_json?.pattern_preview || [] as part, index}
                <span>{part}</span>{#if index < (recipe.recipe_json?.pattern_preview || []).length - 1}<i>→</i>{/if}
              {/each}
            </span>
            {#if recipe.recipe_json?.best_for}<small><b>잘 맞는 글</b> {recipe.recipe_json.best_for}</small>{/if}
          </button>
        {/each}
        {#if !recipes.length}<div class="empty-state">사용할 수 있는 공유 전개 방식이 없습니다.</div>{/if}
      </div>
    {:else if activeStep.key === 'settings'}
      <div class="settings-grid wizard-settings">
        <div class="card stack">
          <h3>결과물 형태</h3>
          <label>결과물 종류<select bind:value={outputProfile} on:change={resetRun}><option value="lore_article">세계관 설명 글</option><option value="video_narration">영상 내레이션</option><option value="novel_prose">소설 장면</option><option value="in_universe_report">세계 내부 문서</option></select></label>
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
        <article><div><span>집필 지침</span><strong>{selectedCards.map((card) => card.title).join(', ') || '선택 안 함'}</strong></div><button class="ghost" on:click={() => setWizardStep(4)}>수정</button></article>
        <article><div><span>전개 방식</span><strong>{selectedRecipe?.name || '선택 필요'}</strong></div><button class="ghost" on:click={() => setWizardStep(5)}>수정</button></article>
        <article><div><span>결과물 형태</span><strong>{outputProfile === 'lore_article' ? '세계관 설명 글' : outputProfile === 'video_narration' ? '영상 내레이션' : outputProfile === 'novel_prose' ? '소설 장면' : '세계 내부 문서'} · {viewpoint === 'omniscient' ? '전지적 설명자' : viewpoint === 'first_observer' ? '1인칭 관찰자' : '3인칭 제한'}</strong></div><button class="ghost" on:click={() => setWizardStep(6)}>수정</button></article>
      </div>
      <section class="wizard-run-panel">
        <div class="run-summary"><strong>{subject?.title}</strong><span>보조 자료 {totalSupporting}개 · 집필 지침 {directionCardIds.length}개 · {selectedRecipe?.name}</span><small>세 단계를 차례로 진행합니다. 작성된 초안은 원고 작업 화면에서 바로 열립니다.</small></div>
        <div class="run-actions">
          <div class="run-action"><div><span>1</span><HelpTip label="사용할 설정 확인 설명" text="선택한 자료에서 AI가 사실로 쓸 내용과 임의로 바꾸면 안 되는 내용을 먼저 보여 줍니다." /></div><button class="secondary" disabled={!!busy || !subject} on:click={() => runAction('context-preview')}>{preview ? '✓ 사용할 설정 확인됨' : '사용할 설정 확인'}</button></div>
          <div class="run-action"><div><span>2</span><HelpTip label="글의 흐름 만들기 설명" text="원고를 쓰기 전에 각 문단이 어떤 순서로 무엇을 설명할지 목록으로 만듭니다." /></div><button class="secondary" disabled={!!busy || !subject || !preview} on:click={() => runAction('plan')}>{plan ? '✓ 글의 흐름 준비됨' : '글의 흐름 만들기'}</button></div>
          <div class="run-action"><div><span>3</span><HelpTip label="초안 작성 설명" text="확인한 세계관과 글의 흐름을 바탕으로 초안을 쓰고, 원고 작업 화면으로 이동합니다." /></div><button class="primary" disabled={!!busy || !plan || cardConflicts.length} on:click={() => runAction('generate')}>초안 작성</button></div>
        </div>
      </section>
    {/if}

    {#if activeStep.key !== 'review'}
      <footer class="wizard-actions">
        <button class="ghost" disabled={wizardStep === 0} on:click={() => setWizardStep(wizardStep - 1)}>← 이전</button>
        <button class="primary" disabled={wizardStep === 0 && !subject || activeStep.key === 'guidance' && cardConflicts.length || activeStep.key === 'recipe' && !recipeId} on:click={nextStep}>{nextButtonLabel} →</button>
      </footer>
    {/if}
  </section>

  {#if wizardStep === wizardSteps.length - 1 && preview}
    <section class="playbook-section evidence-review">
      <div class="section-copy"><span class="step-number">✓</span><div><div class="heading-with-help"><h2>이 글이 참고할 세계관</h2><HelpTip label="참고할 세계관 설명" text="AI가 원고를 쓸 때 사실로 사용할 내용과 지켜야 할 경계를 모아 보여 주는 단계입니다." /></div><p>AI가 사실로 사용할 내용, 답을 정하지 않을 내용, 변경하면 안 되는 설정을 확인하세요.</p></div></div>
      <div class="evidence-columns">
        <div><div class="heading-with-help"><h3>사실로 사용할 내용</h3><HelpTip label="사실로 사용할 내용 설명" text="원고가 이미 확정된 세계관 사실로 다루는 내용입니다." /></div>{#each preview.locked_facts as item}<div class="evidence-item"><strong>{item.page_title}</strong><small>{item.fact}</small></div>{/each}{#if !preview.locked_facts.length}<p class="empty-mini">사실로 확인된 내용이 없습니다.</p>{/if}</div>
        <div><div class="heading-with-help"><h3>답을 정하지 않을 내용</h3><HelpTip label="답을 정하지 않을 내용 설명" text="세계관에서 아직 정하지 않은 질문입니다. AI가 임의로 결론 내리지 않습니다." /></div>{#each preview.open_questions as item}<div class="evidence-item"><strong>{item.page_title}</strong><small>{item.question}</small></div>{/each}{#if !preview.open_questions.length}<p class="empty-mini">열어 둘 질문이 없습니다.</p>{/if}</div>
        <div><div class="heading-with-help"><h3>변경 금지 설정</h3><HelpTip label="변경 금지 설정 설명" text="원고를 흥미롭게 만들기 위해서도 바꾸면 안 되는 설정입니다." /></div>{#each preview.forbidden_material as item}<div class="evidence-item"><strong>지켜야 할 설정</strong><small>{item.rule}</small></div>{/each}{#if !preview.forbidden_material.length}<p class="empty-mini">지정된 변경 금지 설정이 없습니다.</p>{/if}</div>
      </div>
      {#each preview.warnings || [] as warning}<p class="notice-error">{warning}</p>{/each}
    </section>
  {/if}

  {#if wizardStep === wizardSteps.length - 1 && plan}
    <section class="playbook-section plan-editor">
      <header class="plan-heading"><div><p class="eyebrow">글의 흐름</p><div class="heading-with-help"><h2>{plan.title}</h2><HelpTip label="글의 흐름 설명" text="완성 원고가 아니라 AI에게 줄 문단별 작업 순서입니다. 설명할 내용과 순서를 바꿀 수 있습니다." /></div><p>{plan.angle}</p><small>각 줄은 원고의 한 문단입니다. 위에서 아래 순서로 작성됩니다.</small></div><button class="secondary" disabled={!planDirty} on:click={savePlan}>{planDirty ? '바꾼 흐름 저장' : '저장됨'}</button></header>
      <div class="flow-list">
        {#each plan.blocks as block, index}
          <article class="flow-row">
            <div class="flow-index">{String(index + 1).padStart(2, '0')}</div>
            <label class="flow-move"><span class="compact-label">문단 방식 <HelpTip label={`${index + 1}번 문단 방식 설명`} text={moveDescriptions[block.move] || '이 문단이 글에서 맡을 설명 방식입니다.'} /></span><select aria-label={`${index + 1}번 문단 방식`} value={block.move} on:change={(e) => updateBlock(index, 'move', e.currentTarget.value)}>{#each Object.entries(moveLabels) as [value, label]}<option {value}>{label}</option>{/each}</select></label>
            <label class="flow-purpose"><span class="compact-label">이 문단에서 설명할 내용</span><input aria-label={`${index + 1}번 문단에서 설명할 내용`} value={block.purpose} on:input={(e) => updateBlock(index, 'purpose', e.currentTarget.value)} /></label>
            <label class="flow-budget"><span class="compact-label">분량</span><span class="input-suffix"><input aria-label={`${index + 1}번 문단 분량`} type="number" min="50" value={block.word_budget} on:input={(e) => updateBlock(index, 'word_budget', Number(e.currentTarget.value))} /><small>자</small></span></label>
            <div class="flow-meta"><span class="badge">설정 {block.evidence_ids.length}개</span><label><input type="checkbox" checked={block.locked} on:change={(e) => updateBlock(index, 'locked', e.currentTarget.checked)} /> 이 문단 고정</label></div>
            <div class="flow-actions"><button class="icon-button" aria-label={`${index + 1}번 문단 위로 이동`} on:click={() => moveBlock(index, -1)}>↑</button><button class="icon-button" aria-label={`${index + 1}번 문단 아래로 이동`} on:click={() => moveBlock(index, 1)}>↓</button><button class="ghost" on:click={() => duplicateBlock(index)}>복제</button><button class="danger-button" on:click={() => removeBlock(index)}>삭제</button></div>
          </article>
        {/each}
      </div>
    </section>
  {/if}

  {#if wizardStep === wizardSteps.length - 1 && generatedDocument}<div class="completion-banner"><div><strong>{generatedDocument.title}</strong><span>{generatedDocument.body_markdown.length.toLocaleString()}자 초안을 저장했습니다.</span></div><a class="primary" href={`/documents?document=${generatedDocument.id}`}>이 초안 작업하기 →</a></div>{/if}
  </div>
</div>
