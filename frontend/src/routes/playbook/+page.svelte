<script>
  import { onMount } from 'svelte';
  import HelpTip from '$lib/components/HelpTip.svelte';
  import ProjectCreator from '$lib/components/ProjectCreator.svelte';
  import WritingBriefSpecimen from '$lib/components/WritingBriefSpecimen.svelte';
  import { api } from '$lib/api';
  import { coverFallbackLabel, moveDescriptions, moveLabels, roleLabel } from '$lib/labels';
  import { initialProjectId, rememberProject } from '$lib/project';

  let projects = [], pages = [], cards = [], recipes = [], categories = [], voiceProfiles = [];
  let projectId = '', recipeId = '', voiceProfileId = '', outputProfile = 'lore_article', userDirection = '';
  let subjectIds = [], backgroundIds = [], elementIds = [], conflictIds = [], directionCardIds = [];
  let length = 'normal', customLength = 4000, detailLevel = 3, contextDepth = 'balanced', creativity = 'conservative', mystery = 4, seed = 42;
  let viewpoint = 'omniscient', tense = 'present';
  let conceptSearch = '', categoryFilter = 'all', pageLimit = 18;
  let session = null, plan = null, generatedDocument = null;
  let busy = '', error = '', planDirty = false;
  let wizardStep = 0, furthestStep = 0;
  let editingFromReview = false;
  let reviewEditSnapshot = null;
  let reviewPane = 'plan';

  const slotLabels = { subject: '주제', background: '배경', elements: '주요 요소', conflicts: '갈등·변수' };
  const wizardSteps = [
    { key: 'subject', slot: 'subject', short: '주제', title: '무엇에 관한 글인가요?', copy: '원고의 중심이 될 자료 한 개를 선택하세요.', required: true, next: '배경으로 계속' },
    { key: 'background', slot: 'background', short: '배경', title: '어디서, 어떤 상황에서 벌어지나요?', copy: '주제를 이해하는 데 필요한 장소·시대·상황을 고르세요. 없어도 됩니다.', next: '주요 요소로 계속' },
    { key: 'elements', slot: 'elements', short: '주요 요소', title: '꼭 함께 다룰 것은 무엇인가요?', copy: '글에서 비중 있게 등장할 인물·사건·유물 등을 고르세요. 여러 개를 선택할 수 있습니다.', next: '갈등·변수로 계속' },
    { key: 'conflicts', slot: 'conflicts', short: '갈등·변수', title: '무엇이 긴장과 변화를 만드나요?', copy: '충돌, 위험, 반전의 원인이 될 자료를 고르세요. 없어도 됩니다.', next: '집필 지침으로 계속' },
    { key: 'guidance', short: '집필 지침', title: '이번 글에서 무엇을 강조하거나 피할까요?', copy: '현재 프로젝트에 저장한 강조점과 금지 원칙입니다. 여러 개를 고르거나 건너뛸 수 있습니다.', next: '전개 방식으로 계속' },
    { key: 'recipe', short: '전개 방식', title: '글을 어떤 방식으로 풀어갈까요?', copy: '공용 기본 방식과 이 프로젝트에서 만든 방식 중 정보가 드러나는 순서 하나를 고르세요.', required: true, next: '문체·필력으로 계속' },
    { key: 'voice', short: '문체·필력', title: '어떤 문장 감각으로 전달할까요?', copy: '승인된 표현 원칙 하나를 고르거나 모델 기본 문체로 진행하세요. 세계관 사실과 전개 순서는 바꾸지 않습니다.', next: '결과물 형태로 계속' },
    { key: 'settings', short: '결과물 형태', title: '어떤 결과물로 만들까요?', copy: '결과물 종류, 시점·시제와 분량을 정하세요.', next: '확인·작성으로 계속' },
    { key: 'review', short: '확인·작성', title: '선택을 확인하고 초안을 만드세요.', copy: '원고 설계를 확인하고, 글의 흐름을 정한 뒤 초안을 작성합니다.' }
  ];
  const outputProfiles = [
    { value: 'lore_article', mark: '설정집', title: '세계관 설명 글', copy: '사실과 맥락을 차분하게 정리합니다.' },
    { value: 'video_narration', mark: '영상', title: '영상 내레이션', copy: '소리 내어 읽기 좋은 호흡으로 씁니다.' },
    { value: 'novel_prose', mark: '장면', title: '소설 장면', copy: '인물의 행동과 감각이 보이게 씁니다.' },
    { value: 'personal_essay', mark: '수필', title: '수필·에세이', copy: '구체적인 경험에서 생각의 변화를 끌어냅니다.' },
    { value: 'analytical_report', mark: '보고', title: '분석 보고서', copy: '근거와 한계를 분리해 판단 과정을 보여 줍니다.' },
    { value: 'in_universe_report', mark: '기록', title: '세계 내부 문서', copy: '세계 안의 작성자가 남긴 기록처럼 씁니다.' }
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
  $: selectedCards = cards.filter((card) => directionCardIds.includes(card.id));
  $: selectedRecipe = recipes.find((recipe) => recipe.id === recipeId);
  $: selectedVoiceProfile = voiceProfiles.find((profile) => profile.id === voiceProfileId);
  $: cardConflicts = selectedCards.flatMap((card) => selectedCards.filter((other) => other.id !== card.id && (card.incompatible_tags || []).some((tag) => (other.tags || []).includes(tag))).map((other) => `${card.title} ↔ ${other.title}`));
  $: targetCharacters = Number(length === 'custom' ? customLength : ({ short: 1200, normal: 3000, long: 6500, very_long: 12000 }[length] || 3000));
  $: estimatedTokens = Math.ceil(targetCharacters * 1.8);
  $: visiblePages = pages.filter((page) => {
    const text = `${page.title} ${page.summary} ${(page.tags || []).join(' ')}`.toLowerCase();
    return (!conceptSearch || text.includes(conceptSearch.toLowerCase())) && (categoryFilter === 'all' || page.category_key === categoryFilter) && !['DISCOURSE_REFERENCE', 'REJECTED'].includes(page.usage_role);
  });
  $: subject = pages.find((page) => subjectIds.includes(page.id));
  $: activeStep = wizardSteps[wizardStep];
  $: activeSlot = activeStep?.slot || '';
  $: activeIds = activeSlot === 'subject' ? subjectIds : activeSlot === 'background' ? backgroundIds : activeSlot === 'elements' ? elementIds : activeSlot === 'conflicts' ? conflictIds : [];
  $: wizardCandidates = visiblePages
    .filter((page) => !slotFor(page.id) || slotFor(page.id) === activeSlot);
  $: wizardPages = wizardCandidates.slice(0, pageLimit);
  $: totalSupporting = backgroundIds.length + elementIds.length + conflictIds.length;
  $: selectedConceptCount = subjectIds.length + totalSupporting;
  $: selectedOutputProfile = outputProfiles.find((item) => item.value === outputProfile) || outputProfiles[0];
  $: selectedViewpoint = viewpointOptions.find((item) => item.value === viewpoint) || viewpointOptions[0];
  $: selectedTense = tenseOptions.find((item) => item.value === tense) || tenseOptions[0];
  $: selectedLength = lengthOptions.find((item) => item.value === length) || lengthOptions[1];
  $: selectedLengthCopy = length === 'custom' ? `${Number(customLength || 0).toLocaleString()}자` : selectedLength.copy;
  $: planBudgetTotal = (plan?.blocks || []).reduce((total, block) => total + Number(block.word_budget || 0), 0);
  $: hasCurrentSelection = activeIds.length || ['settings', 'voice'].includes(activeStep?.key) || activeStep?.key === 'guidance' && directionCardIds.length || activeStep?.key === 'recipe' && !!recipeId;
  $: nextButtonLabel = activeStep?.next ? `${hasCurrentSelection ? '' : '선택 없이 '}${activeStep.next}` : '';
  $: progressSummaries = [
    subject?.title || '선택 필요',
    selectionSummary(backgroundIds),
    selectionSummary(elementIds),
    selectionSummary(conflictIds),
    selectedCards.length ? selectedCards.length === 1 ? selectedCards[0].title : `${selectedCards[0].title} 외 ${selectedCards.length - 1}개` : '선택 안 함',
    selectedRecipe?.name || '선택 필요',
    selectedVoiceProfile?.name || '모델 기본 문체',
    selectedOutputProfile.title,
    generatedDocument ? '원고 완성' : plan ? '글의 흐름 준비됨' : '작성 전'
  ];

  onMount(loadInitial);

  async function loadInitial() {
    try {
      projects = await api.get('/projects');
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
      [pages, cards, categories, recipes, voiceProfiles] = await Promise.all([
        api.get(`/concept-pages?project_id=${projectId}`),
        api.get(`/direction-cards?project_id=${projectId}`),
        api.get(`/categories?project_id=${projectId}`),
        api.get(`/writing-recipes?project_id=${projectId}`),
        api.get(`/voice-profiles?project_id=${projectId}&status=APPROVED`)
      ]);
      recipeId = recipes.some((item) => item.id === recipeId)
        ? recipeId
        : recipes.find((item) => item.key === 'progressive_exposition')?.id || recipes[0]?.id || '';
      voiceProfileId = '';
      subjectIds = []; backgroundIds = []; elementIds = []; conflictIds = []; directionCardIds = [];
      wizardStep = 0; furthestStep = 0; pageLimit = 18;
      editingFromReview = false;
      reviewEditSnapshot = null;
      resetRun();
    } catch (e) { error = e.message; }
  }

  function resetRun() { session = plan = generatedDocument = null; planDirty = false; reviewPane = 'plan'; }

  function categoryName(page) {
    return categories.find((item) => item.key === page?.category_key)?.name || page?.custom_category || page?.category_key || '종류 없음';
  }

  function conceptCover(page) {
    const propertyCover = page?.properties_json?.cover_image;
    const attachment = (page?.attachment_refs || []).find((item) => item?.kind === 'image' || String(item?.mime_type || '').startsWith('image/'));
    const source = propertyCover || attachment?.data_url || attachment?.external_uri || '';
    return typeof source === 'string' && (source.startsWith('data:image/') || source.startsWith('/')) ? source : '';
  }

  function conceptInitial(page) {
    return coverFallbackLabel(page.title, '자료');
  }

  function cardRoleLabel(page) {
    return page.usage_role === 'CANON_EVIDENCE' ? '사용' : roleLabel(page.usage_role);
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
  function selectionNames(ids) {
    const selected = selectedPages(ids);
    return selected.length ? selected.map((page) => page.title).join(' · ') : '선택 안 함';
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
    conceptSearch = ''; categoryFilter = 'all'; pageLimit = 18;
    setTimeout(() => window.document.querySelector('.wizard-shell')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0);
  }

  function editReviewSelection(index) {
    reviewEditSnapshot = {
      subjectIds: [...subjectIds], backgroundIds: [...backgroundIds], elementIds: [...elementIds], conflictIds: [...conflictIds],
      directionCardIds: [...directionCardIds], recipeId, voiceProfileId, outputProfile, userDirection,
      length, customLength, detailLevel, contextDepth, creativity, mystery, seed, viewpoint, tense,
      session, plan, generatedDocument, planDirty, reviewPane
    };
    setWizardStep(index);
    editingFromReview = true;
  }

  function returnToReview() {
    editingFromReview = false;
    reviewEditSnapshot = null;
    setWizardStep(wizardSteps.length - 1);
  }

  function cancelReviewEdit() {
    if (reviewEditSnapshot) {
      ({
        subjectIds, backgroundIds, elementIds, conflictIds, directionCardIds, recipeId, voiceProfileId,
        outputProfile, userDirection, length, customLength, detailLevel, contextDepth, creativity,
        mystery, seed, viewpoint, tense, session, plan, generatedDocument, planDirty, reviewPane
      } = reviewEditSnapshot);
    }
    returnToReview();
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

  function selectVoiceProfile(selectedId) {
    voiceProfileId = selectedId;
    resetRun();
  }

  function selectOutputProfile(value) { outputProfile = value; resetRun(); }
  function selectViewpoint(value) { viewpoint = value; resetRun(); }
  function selectTense(value) { tense = value; resetRun(); }
  function selectLength(value) { length = value; resetRun(); }

  function runReviewNext() {
    if (generatedDocument) { reviewPane = 'draft'; return; }
    if (!plan) return runAction('plan');
    return runAction('generate');
  }

  async function ensureSession() {
    if (session) return session;
    session = await api.post('/playbook-sessions', {
      project_id: projectId, name: `${subject?.title || '새 원고'} 플레이북`,
      concept_slots: { subject: subjectIds, background: backgroundIds, elements: elementIds, conflicts: conflictIds, wildcards: [] },
      direction_card_ids: directionCardIds, user_direction: userDirection,
      writing_recipe_id: recipeId, output_profile: outputProfile,
      voice_profile_id: voiceProfileId || null,
      voice_selection_mode: voiceProfileId ? 'profile_default' : 'model_default',
      voice_example_ids: [],
      settings_json: {
        length, custom_length: length === 'custom' ? Number(customLength) : null,
        detail_level: Number(detailLevel), context_depth: selectedConceptCount ? contextDepth : 'core', creativity,
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
    busy = kind === 'plan' ? '자료 경계를 확인하고 글의 흐름을 만드는 중' : 'Writer가 초안을 작성하는 중';
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
        if (completedDocument) reviewPane = 'draft';
        return;
      }
      const result = await api.post(`/playbook-sessions/${current.id}/${kind}`, {});
      session = result.session;
      if (kind === 'plan') {
        plan = result.plan;
        reviewPane = 'plan';
        planDirty = false;
      }
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  function updateBlock(index, key, value) { plan.blocks[index][key] = value; plan = { ...plan }; planDirty = true; }
  function moveBlock(index, delta) { const target = index + delta; if (target < 0 || target >= plan.blocks.length) return; const next = [...plan.blocks]; [next[index], next[target]] = [next[target], next[index]]; plan = { ...plan, blocks: next }; planDirty = true; }
  function duplicateBlock(index) { const next = [...plan.blocks]; next.splice(index + 1, 0, { ...plan.blocks[index], locked: false }); plan = { ...plan, blocks: next }; planDirty = true; }
  function removeBlock(index) { plan = { ...plan, blocks: plan.blocks.filter((_, i) => i !== index) }; planDirty = true; }
</script>

<div class="page playbook-page workspace-page">
  <div class="page-tools workflow-commandbar">
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
    <div class="project-tools"><label class="project-select">현재 프로젝트<select bind:value={projectId} on:change={changeProject}>{#each projects as project}<option value={project.id}>{project.name}</option>{/each}</select></label><ProjectCreator onCreated={projectCreated} /></div>
  </div>

  {#if error}<p class="notice-error">{error}</p>{/if}
  {#if busy}<div class="working-banner" role="status"><span></span><strong>{busy}…</strong><small>선택한 자료와 현재 단계는 저장됩니다.</small></div>{/if}

  <div class="playbook-workspace">
  <section class="wizard-shell">
    {#if activeSlot}
      <div class="wizard-layout">
        <div class="wizard-picker card">
          <div class="library-toolbar">
            <div><strong>세계관 자료</strong><small>{wizardCandidates.length}개 중 {wizardPages.length}개 표시</small></div>
            <input aria-label={`${activeStep.short} 자료 검색`} bind:value={conceptSearch} on:input={() => pageLimit = 18} placeholder="제목·태그·요약 검색" />
            <select aria-label="자료 종류" bind:value={categoryFilter} on:change={() => pageLimit = 18}><option value="all">모든 종류</option>{#each categories as category}<option value={category.key}>{category.name}</option>{/each}</select>
          </div>
          <div class="wizard-card-grid">
            {#each wizardPages as page}
              <button class:selected={activeIds.includes(page.id)} class="wizard-choice-card" aria-pressed={activeIds.includes(page.id)} on:click={() => toggleConcept(page.id)}>
                <span class="wizard-card-cover">
                  {#if conceptCover(page)}
                    <img src={conceptCover(page)} alt={`${page.title} 자료 이미지`} />
                  {:else}
                    <span class="project-cover-placeholder" aria-hidden="true"><span>{conceptInitial(page)}</span></span>
                  {/if}
                </span>
                <span class="wizard-card-copy"><strong>{page.title}</strong><span class="wizard-card-summary">{page.summary || '요약이 없습니다.'}</span></span>
                <span class="row spread wizard-card-meta">
                  <span class="badge">{categoryName(page)}</span>
                  <span class="wizard-card-authority"><small>{cardRoleLabel(page)}</small><span class="selection-mark">{activeIds.includes(page.id) ? '✓' : activeSlot === 'subject' ? '○' : '+'}</span></span>
                </span>
              </button>
            {/each}
            {#if !wizardPages.length}<div class="empty-state">검색 조건에 맞는 자료가 없거나, 모든 자료가 앞 단계에 배정됐습니다.</div>{/if}
          </div>
          {#if wizardPages.length < wizardCandidates.length}<div class="wizard-picker-footer"><button class="secondary wizard-load-more" on:click={() => pageLimit += 18}>자료 더 보기 · {wizardCandidates.length - wizardPages.length}개 남음</button></div>{/if}
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
            <span class="recipe-scope">{recipe.project_id ? '이 프로젝트에서 사용' : '모든 프로젝트에서 사용'}</span>
            <strong>{recipe.name}</strong>
            <p>{recipe.description}</p>
            <span class="recipe-flow" aria-label={`${recipe.name} 순서`}>
              {#each recipe.recipe_json?.required_moves || [] as move, index}
                <span>{moveLabels[move] || move}</span>{#if index < (recipe.recipe_json?.required_moves || []).length - 1}<i>→</i>{/if}
              {/each}
            </span>
            {#if recipe.recipe_json?.best_for}<small><b>잘 맞는 글</b> {recipe.recipe_json.best_for}</small>{/if}
          </button>
        {/each}
        {#if !recipes.length}<a class="empty-state" href="/editor">사용할 수 있는 전개 방식이 없습니다. 세계관 자료에서 만들기 →</a>{/if}
      </div>
    {:else if activeStep.key === 'voice'}
      <div class="voice-option-grid">
        <button class:selected={!voiceProfileId} class="voice-option model-default" aria-pressed={!voiceProfileId} on:click={() => selectVoiceProfile('')}>
          <span class="choice-check">{!voiceProfileId ? '✓' : '○'}</span>
          <div class="voice-option-cover" aria-hidden="true"><span style="width:68%"></span><span style="width:46%"></span><span style="width:80%"></span><span style="width:38%"></span></div>
          <span class="voice-scope">별도 표현 지침 없음</span><strong>모델 기본 문체</strong><p>선택한 결과물 형태와 시점·시제만 사용합니다. 숨은 기본 프로필은 추가하지 않습니다.</p>
        </button>
        {#each voiceProfiles as profile}
          <button class:selected={voiceProfileId === profile.id} class="voice-option" aria-pressed={voiceProfileId === profile.id} on:click={() => selectVoiceProfile(profile.id)}>
            <span class="choice-check">{voiceProfileId === profile.id ? '✓' : '○'}</span>
            <div class="voice-option-cover" aria-hidden="true"><span style={`width:${46 + (profile.name.length % 5) * 8}%`}></span><span style={`width:${82 - (Number(profile.version) % 4) * 7}%`}></span><span style={`width:${58 + ((profile.description || '').length % 4) * 7}%`}></span><span style="width:38%"></span></div>
            <span class="voice-scope">{profile.project_id ? '이 프로젝트' : '모든 프로젝트'} · v{profile.version}</span>
            <strong>{profile.name}</strong><p>{profile.profile_json?.reader_effect || profile.description}</p>
            <div class="tag-row">{#each (profile.profile_json?.best_for || []).slice(0, 3) as tag}<span class="badge">{tag}</span>{/each}</div>
          </button>
        {/each}
        {#if !voiceProfiles.length}<a class="empty-state" href="/editor">승인된 문체 프로필이 없습니다. 모델 기본 문체를 쓰거나 세계관 자료에서 만들기 →</a>{/if}
      </div>
    {:else if activeStep.key === 'settings'}
      <div class="output-studio">
        <WritingBriefSpecimen
          mark={selectedOutputProfile.mark}
          subject={subject?.title || '새 원고'}
          outputTitle={selectedOutputProfile.title}
          outputCopy={selectedOutputProfile.copy}
          background={selectionNames(backgroundIds)}
          elements={selectionNames(elementIds)}
          conflicts={selectionNames(conflictIds)}
          guidance={selectedCards.length ? selectedCards.map((card) => card.title).join(' · ') : '선택 안 함'}
          recipe={selectedRecipe?.name || '선택 필요'}
          voice={selectedVoiceProfile?.name || '모델 기본 문체'}
          viewpoint={selectedViewpoint.title}
          tense={selectedTense.title}
          length={`${selectedLength.title} · ${selectedLengthCopy}`}
          tokenEstimate={estimatedTokens}
        />

        <div class="output-control-deck">
          <section class="output-choice-section">
            <header><span>형식</span><strong>어떤 독서 경험으로 만들까요?</strong></header>
            <div class="output-format-grid" role="group" aria-label="결과물 종류">
              {#each outputProfiles as profile}
                <button class:selected={outputProfile === profile.value} aria-pressed={outputProfile === profile.value} on:click={() => selectOutputProfile(profile.value)}>
                  <span>{profile.mark}</span><strong>{profile.title}</strong><small>{profile.copy}</small>
                </button>
              {/each}
            </div>
          </section>

          <div class="output-choice-pair">
            <section class="output-choice-section">
              <header><span>시점</span><strong>누구의 거리에서 볼까요?</strong></header>
              <div class="voice-card-grid" role="group" aria-label="시점">
                {#each viewpointOptions as option}
                  <button class:selected={viewpoint === option.value} aria-pressed={viewpoint === option.value} on:click={() => selectViewpoint(option.value)}><strong>{option.title}</strong><small>{option.copy}</small></button>
                {/each}
              </div>
            </section>
            <section class="output-choice-section">
              <header><span>시제</span><strong>시간의 결을 고르세요.</strong></header>
              <div class="tense-card-grid" role="group" aria-label="시제">
                {#each tenseOptions as option}
                  <button class:selected={tense === option.value} aria-pressed={tense === option.value} on:click={() => selectTense(option.value)}><strong>{option.title}</strong><small>{option.copy}</small></button>
                {/each}
              </div>
            </section>
          </div>

          <section class="output-choice-section output-length-section">
            <header><span>분량</span><strong>원고가 숨 쉴 길이를 정하세요.</strong></header>
            <div class="length-card-grid" role="group" aria-label="분량">
              {#each lengthOptions as option}
                <button class:selected={length === option.value} aria-pressed={length === option.value} on:click={() => selectLength(option.value)}><strong>{option.title}</strong><small>{option.copy}</small></button>
              {/each}
            </div>
            {#if length === 'custom'}<label class="custom-length-field">목표 글자 수<input type="number" min="500" bind:value={customLength} on:change={resetRun} /></label>{/if}
          </section>

          <section class="output-tuning-card">
            <div class="output-selectors"><label>선택 자료 본문 반영<select bind:value={contextDepth} disabled={!selectedConceptCount} on:change={resetRun}><option value="core">요약과 작성 경계만</option><option value="balanced">선택 자료 본문 일부</option><option value="wide">선택 자료 본문 넓게</option><option value="max">선택 자료 본문 최대</option></select><small>{selectedConceptCount ? `주제를 포함해 선택한 ${selectedConceptCount}개 자료에 적용됩니다.` : '자료가 없으면 자동으로 꺼집니다.'}</small></label><label>새 설정 제안<select bind:value={creativity} on:change={resetRun}><option value="strict">하지 않음</option><option value="conservative">최소한</option><option value="balanced">필요할 때</option><option value="free">적극적</option></select></label></div>
            <div class="output-ranges"><label><span>설명의 자세함 <b>{detailLevel}/5</b></span><input type="range" min="1" max="5" bind:value={detailLevel} on:change={resetRun} /></label><label><span>미스터리 보존 <b>{mystery}/5</b></span><input type="range" min="1" max="5" bind:value={mystery} on:change={resetRun} /></label></div>
            <details><summary>재현용 시드</summary><div class="details-body"><label>같은 선택과 이 번호는 같은 조합을 만듭니다.<input type="number" bind:value={seed} on:change={resetRun} /></label></div></details>
          </section>
        </div>
      </div>
    {:else if activeStep.key === 'review'}
      <div class="review-workbench">
        <WritingBriefSpecimen
          ariaLabel="선택한 결과물 견본"
          mark={selectedOutputProfile.mark}
          subject={subject?.title || '새 원고'}
          outputTitle={selectedOutputProfile.title}
          outputCopy={selectedOutputProfile.copy}
          background={selectionNames(backgroundIds)}
          elements={selectionNames(elementIds)}
          conflicts={selectionNames(conflictIds)}
          guidance={selectedCards.length ? selectedCards.map((card) => card.title).join(' · ') : '선택 안 함'}
          recipe={selectedRecipe?.name || '선택 필요'}
          voice={selectedVoiceProfile?.name || '모델 기본 문체'}
          viewpoint={selectedViewpoint.title}
          tense={selectedTense.title}
          length={`${selectedLength.title} · ${selectedLengthCopy}`}
          tokenEstimate={estimatedTokens}
        />

        <section class="review-generation-desk" aria-label="확인에서 초안까지">
          <header class="review-generation-heading">
            <div><span>확인·작성</span><h2>설계를 흐름으로, 흐름을 초안으로</h2><p>왼쪽 설계는 유지되고 오른쪽 카드의 결과만 교체됩니다.</p></div>
            <div class="review-edit-actions"><button class="ghost" on:click={() => editReviewSelection(0)}>주제·소재 수정</button><button class="ghost" on:click={() => editReviewSelection(4)}>집필 지침 수정</button><button class="ghost" on:click={() => editReviewSelection(5)}>전개·문체 수정</button><button class="ghost" on:click={() => editReviewSelection(7)}>출력 설정 수정</button></div>
          </header>

          <nav class="review-stage-cards" aria-label="초안 작성 단계">
            <button class:active={reviewPane === 'plan'} class:complete={!!plan} disabled={!!busy} aria-pressed={reviewPane === 'plan'} on:click={() => plan ? reviewPane = 'plan' : runAction('plan')}>
              <span>01</span><strong>글의 흐름 설계</strong><p>자료 경계를 적용해 편집 가능한 문단 순서를 만듭니다.</p><small>{plan ? `${plan.blocks.length}개 문단 · ${planBudgetTotal.toLocaleString()}자` : '클릭하여 흐름 만들기'}</small>
            </button>
            <button class:active={reviewPane === 'draft'} class:complete={!!generatedDocument} disabled={!plan || !!busy} aria-pressed={reviewPane === 'draft'} on:click={() => generatedDocument ? reviewPane = 'draft' : runAction('generate')}>
              <span>02</span><strong>초안 작성</strong><p>확정한 흐름과 설계로 편집 가능한 초안을 만듭니다.</p><small>{generatedDocument ? `${generatedDocument.body_markdown.length.toLocaleString()}자 초안` : plan ? '클릭하여 초안 작성' : '글의 흐름 뒤 진행'}</small>
            </button>
          </nav>

          {#each plan?.warnings || [] as warning}<p class="notice-error">{warning}</p>{/each}

          <div class="review-result-slot" aria-live="polite">
            {#if busy}
              <div class="review-result-wait"><span></span><strong>{busy}</strong><p>현재 결과 카드는 완료되는 즉시 같은 자리에서 교체됩니다.</p></div>
            {:else if reviewPane === 'draft' && generatedDocument}
              <article class="review-draft-result">
                <header><div><p class="eyebrow">초안 · {generatedDocument.body_markdown.length.toLocaleString()}자</p><h2>{generatedDocument.title}</h2></div><a class="primary" href={`/documents?document=${generatedDocument.id}`}>원고 작업에서 편집 →</a></header>
                <div class="review-draft-body">{generatedDocument.body_markdown}</div>
              </article>
            {:else if plan}
              <section class="review-plan-editor plan-editor">
                <header class="plan-heading"><div><p class="eyebrow">글의 흐름 · {plan.blocks.length}개 문단 · 총 {planBudgetTotal.toLocaleString()}자 / 목표 {Number(plan.target_length || targetCharacters).toLocaleString()}자</p><div class="heading-with-help"><h2>{plan.title}</h2><HelpTip label="글의 흐름 설명" text="완성 원고가 아니라 AI에게 줄 문단별 작업 순서입니다. 설명할 내용과 순서, 문단별 글자 수를 바꿀 수 있습니다." /></div><p>{plan.angle}</p><small>각 줄은 원고의 한 문단입니다. 위에서 아래 순서로 작성됩니다.</small></div><button class="secondary" disabled={!planDirty} on:click={savePlan}>{planDirty ? '바꾼 흐름 저장' : '저장됨'}</button></header>
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
            {:else}
              <div class="review-result-empty"><span>01</span><h2>먼저 글의 흐름을 만드세요.</h2><p>전개 방식과 목표 분량을 문단별 작업 순서로 바꿉니다. 생성된 흐름은 이 자리에서 직접 수정할 수 있습니다.</p></div>
            {/if}
          </div>
        </section>
      </div>
    {/if}

  </section>

  </div>

  <footer class="wizard-actions playbook-navigation">
    {#if editingFromReview}
      <button class="ghost" disabled={!!busy} on:click={cancelReviewEdit}>← 수정 취소</button>
      <button class="primary" disabled={!!busy || wizardStep === 0 && !subject || activeStep.key === 'recipe' && !recipeId || activeStep.key === 'guidance' && cardConflicts.length} on:click={returnToReview}>수정 완료 · 확인·작성으로 돌아가기 →</button>
    {:else}
    <button class="ghost" disabled={wizardStep === 0 || !!busy} on:click={() => setWizardStep(wizardStep - 1)}>← 이전</button>
    {#if activeStep.key === 'review'}
      {#if generatedDocument}<a class="primary" href={`/documents?document=${generatedDocument.id}`}>원고 작업에서 편집 →</a>{:else}<button class="primary" disabled={!!busy || !subject || !!plan && cardConflicts.length} on:click={runReviewNext}>{!plan ? '글의 흐름 만들기' : '초안 작성'} →</button>{/if}
    {:else}
      <button class="primary" disabled={wizardStep === 0 && !subject || activeStep.key === 'guidance' && cardConflicts.length || activeStep.key === 'recipe' && !recipeId} on:click={nextStep}>{nextButtonLabel} →</button>
    {/if}
    {/if}
  </footer>
</div>
