<script>
  import { onMount } from 'svelte';
  import { api } from '$lib/api';

  let projects = [], pages = [], cards = [], recipes = [];
  let projectId = '', recipeId = '', outputProfile = 'lore_article', userDirection = '';
  let subjectIds = [], backgroundIds = [], elementIds = [], conflictIds = [], directionCardIds = [];
  let length = 'normal', customLength = 4000, detailLevel = 3, contextDepth = 'balanced', creativity = 'conservative', mystery = 4, seed = 42;
  let session = null, preview = null, plan = null, document = null;
  let busy = '', error = '', planDirty = false;

  $: selectedCards = cards.filter((card) => directionCardIds.includes(card.id));
  $: cardConflicts = selectedCards.flatMap((card) => selectedCards.filter((other) => other.id !== card.id && (card.incompatible_tags || []).some((tag) => (other.tags || []).includes(tag))).map((other) => `${card.title} ↔ ${other.title}`));
  $: estimatedTokens = Math.ceil((length === 'custom' ? customLength : ({ short: 1200, normal: 3000, long: 6500, very_long: 12000 }[length] || 3000)) * 1.8);

  onMount(loadInitial);

  async function loadInitial() {
    try {
      [projects, recipes] = await Promise.all([api.get('/projects'), api.get('/writing-recipes')]);
      recipeId = recipes.find((item) => item.key === 'progressive_exposition')?.id || recipes[0]?.id || '';
      if (projects.length) { projectId = projects[0].id; await loadProjectData(); }
    } catch (e) { error = e.message; }
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
  function randomValue(value) { let t = value + 0x6D2B79F5; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61); return ((t ^ t >>> 14) >>> 0) / 4294967296; }
  function draw(slot) {
    const selected = new Set([...subjectIds, ...backgroundIds, ...elementIds, ...conflictIds]);
    const pool = pages.filter((page) => !selected.has(page.id) && !['DISCOURSE_REFERENCE', 'REJECTED'].includes(page.usage_role));
    if (!pool.length) return;
    const salt = [...slot].reduce((sum, char) => sum + char.charCodeAt(0), 0);
    const page = pool[Math.floor(randomValue(Number(seed) + salt) * pool.length)];
    if (slot === 'subject') subjectIds = [page.id];
    if (slot === 'background') backgroundIds = [...backgroundIds, page.id];
    if (slot === 'elements') elementIds = [...elementIds, page.id];
    if (slot === 'conflicts') conflictIds = [...conflictIds, page.id];
    resetRun();
  }
  function reroll(slot) { seed = Number(seed) + 1; draw(slot); }

  async function ensureSession() {
    if (session) return session;
    session = await api.post('/playbook-sessions', {
      project_id: projectId, name: '플레이북 실행',
      concept_slots: { subject: subjectIds, background: backgroundIds, elements: elementIds, conflicts: conflictIds, wildcards: [] },
      direction_card_ids: directionCardIds, user_direction: userDirection,
      writing_recipe_id: recipeId, output_profile: outputProfile,
      settings_json: { length, custom_length: length === 'custom' ? Number(customLength) : null, detail_level: Number(detailLevel), context_depth: contextDepth, creativity, mystery_preservation: Number(mystery) },
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
    error = ''; busy = kind === 'context-preview' ? '근거 팩 컴파일 중' : kind === 'plan' ? 'Utility 모델이 구성안 작성 중' : 'Writer 모델이 원고 작성 중';
    try {
      const current = await ensureSession();
      if (kind === 'generate' && planDirty) await savePlan();
      if (kind === 'generate') {
        await api.postEvents(`/playbook-sessions/${current.id}/generate/stream`, {}, (event, data) => {
          if (event === 'progress') busy = data.message;
          if (event === 'error') throw new Error(`${data.message} (${data.code})`);
          if (event === 'complete') {
            session = data.session;
            plan = data.plan;
            document = data.document;
          }
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

<div class="page">
  <div class="page-header">
    <div><p class="eyebrow">REPRODUCIBLE COMPOSITION</p><h1>플레이북 조립</h1><p>선택과 무작위 결과, 모델, 시드, 구성안의 모든 단계를 실행 기록으로 남깁니다.</p></div>
    <label style="min-width:260px">프로젝트<select bind:value={projectId} on:change={loadProjectData}>{#each projects as project}<option value={project.id}>{project.name}</option>{/each}</select></label>
  </div>
  {#if error}<p class="notice-error">{error}</p>{/if}
  {#if busy}<div class="notice" role="status">{busy}… 현재 선택과 세션은 저장되어 있습니다.</div>{/if}

  <div class="grid-2">
    <section class="card stack">
      <div class="row spread"><div><p class="eyebrow">STEP 1 · MATERIAL</p><h2 style="margin:0">소재</h2></div><div class="row"><span class="badge">SEED {seed}</span><input aria-label="재현용 시드" type="number" bind:value={seed} on:change={resetRun} style="width:88px" /></div></div>
      <label>주요 대상<select multiple bind:value={subjectIds} on:change={resetRun}>{#each pages as page}<option value={page.id}>{page.title} · {page.usage_role}</option>{/each}</select></label>
      <div class="row"><button class="ghost" on:click={() => draw('subject')}>풀에서 추첨</button><button class="ghost" on:click={() => reroll('subject')}>다시 뽑기</button></div>
      <div class="grid-2">
        <label>배경<select multiple bind:value={backgroundIds} on:change={resetRun}>{#each pages as page}<option value={page.id}>{page.title}</option>{/each}</select><button class="ghost" on:click={() => draw('background')}>하나 추가</button></label>
        <label>등장 요소<select multiple bind:value={elementIds} on:change={resetRun}>{#each pages as page}<option value={page.id}>{page.title}</option>{/each}</select><button class="ghost" on:click={() => draw('elements')}>하나 추가</button></label>
      </div>
      <label>갈등·변수<select multiple bind:value={conflictIds} on:change={resetRun}>{#each pages as page}<option value={page.id}>{page.title}</option>{/each}</select><button class="ghost" on:click={() => draw('conflicts')}>하나 추가</button></label>
      <p class="small">같은 프로젝트·풀·시드는 같은 결과를 만듭니다. 명시 선택은 검색 점수와 무관하게 항상 근거 팩에 들어갑니다.</p>
    </section>

    <section class="card stack">
      <p class="eyebrow">STEP 2 · DIRECTION</p><h2 style="margin:0">방향</h2>
      <label>방향성 카드<select multiple bind:value={directionCardIds} on:change={resetRun}>{#each cards as card}<option value={card.id}>{card.title} · 우선순위 {card.priority}</option>{/each}</select></label>
      {#if cardConflicts.length}<div class="notice-error">카드 충돌: {[...new Set(cardConflicts)].join(', ')}</div>{/if}
      <div class="evidence-flow">{#each selectedCards as card}<div class="evidence-item"><strong>{card.title}</strong><small>{card.body}</small></div>{/each}</div>
      <label>이번 실행의 임시 지시<textarea bind:value={userDirection} on:input={resetRun} placeholder="이번 글에서만 적용할 방향을 적으세요."></textarea></label>
    </section>

    <section class="card stack">
      <p class="eyebrow">STEP 3 · WRITING METHOD</p><h2 style="margin:0">집필 방식</h2>
      <label>집필 레시피<select bind:value={recipeId} on:change={resetRun}>{#each recipes as recipe}<option value={recipe.id}>{recipe.name} · {recipe.version}</option>{/each}</select></label>
      <label>출력 프로필<select bind:value={outputProfile} on:change={resetRun}><option value="lore_article">설정 글</option><option value="video_narration">영상 내레이션</option><option value="novel_prose">소설 산문</option><option value="in_universe_report">조사 보고서 / 내부 문서</option></select></label>
      {#if recipeId}{@const recipe = recipes.find((item) => item.id === recipeId)}{#if recipe}<div class="notice">{recipe.description}</div>{/if}{/if}
      <div class="grid-2"><label>시점<select on:change={resetRun}><option>전지적 설명자</option><option>1인칭 관찰자</option><option>3인칭 제한</option></select></label><label>시제<select on:change={resetRun}><option>현재형 중심</option><option>과거형 중심</option></select></label></div>
    </section>

    <section class="card stack">
      <div class="row spread"><div><p class="eyebrow">STEP 4 · GENERATION</p><h2 style="margin:0">생성 설정</h2></div><span class="badge">예상 {estimatedTokens.toLocaleString()} tokens</span></div>
      <div class="grid-2"><label>분량<select bind:value={length} on:change={resetRun}><option value="short">짧게</option><option value="normal">보통</option><option value="long">길게</option><option value="very_long">매우 길게</option><option value="custom">직접 지정</option></select></label>{#if length === 'custom'}<label>목표 글자 수<input type="number" min="500" bind:value={customLength} on:change={resetRun} /></label>{/if}<label>상세도 · {detailLevel}/5<input type="range" min="1" max="5" bind:value={detailLevel} on:change={resetRun} /></label></div>
      <div class="grid-2"><label>자료 반영<select bind:value={contextDepth} on:change={resetRun}><option value="core">핵심만</option><option value="balanced">균형</option><option value="wide">넓게</option><option value="max">최대</option></select></label><label>창작 자유도<select bind:value={creativity} on:change={resetRun}><option value="strict">엄격</option><option value="conservative">보수적</option><option value="balanced">균형</option><option value="free">자유</option></select></label></div>
      <label>미스터리 보존 · {mystery}/5<input type="range" min="1" max="5" bind:value={mystery} on:change={resetRun} /></label>
    </section>
  </div>

  <section class="card stack" style="margin-top:14px">
    <div class="row wrap"><button class="secondary" disabled={!!busy || !projectId || !recipeId} on:click={() => runAction('context-preview')}>1. 컨텍스트 확인</button><button class="secondary" disabled={!!busy || !projectId || !recipeId} on:click={() => runAction('plan')}>2. 구성안 생성</button><button class="primary" disabled={!!busy || !projectId || !recipeId || cardConflicts.length} on:click={() => runAction('generate')}>3. 실제 Writer로 원고 작성</button></div>

    {#if preview}
      <div class="grid-3" style="grid-template-columns:1fr 1fr 1fr">
        <div><p class="eyebrow">LOCKED FACTS</p>{#each preview.locked_facts as item}<div class="evidence-item"><strong>{item.page_title}</strong><small>{item.fact}</small></div>{/each}{#if !preview.locked_facts.length}<p class="small">잠긴 사실 없음</p>{/if}</div>
        <div><p class="eyebrow">OPEN QUESTIONS</p>{#each preview.open_questions as item}<div class="evidence-item"><strong>{item.page_title}</strong><small>{item.question}</small></div>{/each}{#if !preview.open_questions.length}<p class="small">열린 질문 없음</p>{/if}</div>
        <div><p class="eyebrow">FORBIDDEN / REFERENCE</p>{#each preview.forbidden_material as item}<div class="evidence-item"><strong>금지 변경</strong><small>{item.rule}</small></div>{/each}{#each preview.discourse_or_inspiration_references as item}<div class="evidence-item"><strong>{item.usage_role}</strong><small>{item.title} · 사실 근거 사용 안 함</small></div>{/each}</div>
      </div>
      {#each preview.warnings || [] as warning}<p class="notice-error">{warning}</p>{/each}
    {/if}

    {#if plan}
      <div class="row spread"><div><p class="eyebrow">USER EDITABLE PLAN</p><h3 style="margin:0">{plan.title}</h3><p class="small">{plan.angle}</p></div><button class="secondary" disabled={!planDirty} on:click={savePlan}>{planDirty ? '구성안 변경 저장' : '저장됨'}</button></div>
      <div class="stack">
        {#each plan.blocks as block, index}
          <div class="card" style="background:var(--paper-deep)">
            <div class="row spread"><div class="row"><span class="badge">{String(index + 1).padStart(2, '0')}</span><select value={block.move} on:change={(e) => updateBlock(index, 'move', e.currentTarget.value)} style="width:150px"><option>ORIENT</option><option>NARROW</option><option>ANCHOR</option><option>COMPLICATE</option><option>COMPARE</option><option>EXEMPLIFY</option><option>ESCALATE</option><option>INTERPRET</option><option>WITHHOLD</option><option>TURN</option><option>STING</option></select></div><div class="row"><button class="ghost" on:click={() => moveBlock(index, -1)}>↑</button><button class="ghost" on:click={() => moveBlock(index, 1)}>↓</button><button class="ghost" on:click={() => duplicateBlock(index)}>복제</button><button class="danger-button" on:click={() => removeBlock(index)}>삭제</button></div></div>
            <label style="margin-top:10px">문단 목적<input value={block.purpose} on:input={(e) => updateBlock(index, 'purpose', e.currentTarget.value)} /></label>
            <div class="row spread" style="margin-top:8px"><span class="small">근거 {block.evidence_ids.length}개</span><label style="display:flex;align-items:center"><input type="number" min="50" value={block.word_budget} on:input={(e) => updateBlock(index, 'word_budget', Number(e.currentTarget.value))} style="width:90px" /> 자</label><label style="display:flex;align-items:center"><input type="checkbox" checked={block.locked} on:change={(e) => updateBlock(index, 'locked', e.currentTarget.checked)} style="width:auto" /> 블록 잠금</label></div>
          </div>
        {/each}
      </div>
    {/if}

    {#if document}<div class="notice"><strong>{document.title}</strong> · {document.body_markdown.length.toLocaleString()}자 실제 원고를 저장했습니다. <a href="/documents" style="text-decoration:underline">문단 편집기로 이동 →</a></div>{/if}
  </section>
</div>
