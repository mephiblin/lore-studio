<script>
  import { onMount } from 'svelte';
  import { api } from '$lib/api';

  let projects = [];
  let projectId = '';
  let pages = [];
  let cards = [];
  let recipes = [];
  let subjectIds = [];
  let backgroundIds = [];
  let elementIds = [];
  let conflictIds = [];
  let directionCardIds = [];
  let recipeId = '';
  let userDirection = '';
  let outputProfile = 'lore_article';
  let length = 'normal';
  let detailLevel = 3;
  let contextDepth = 'balanced';
  let creativity = 'conservative';
  let seed = 0;
  let session = null;
  let preview = null;
  let plan = null;
  let document = null;
  let error = '';
  let busy = false;

  onMount(loadInitial);

  async function loadInitial() {
    try {
      [projects, recipes] = await Promise.all([
        api.get('/projects'),
        api.get('/writing-recipes')
      ]);
      recipeId = recipes[0]?.id || '';
      if (projects.length) {
        projectId = projects[0].id;
        await loadProjectData();
      }
    } catch (e) {
      error = e.message;
    }
  }

  async function loadProjectData() {
    if (!projectId) return;
    try {
      [pages, cards] = await Promise.all([
        api.get(`/concept-pages?project_id=${projectId}`),
        api.get(`/direction-cards?project_id=${projectId}`)
      ]);
      subjectIds = [];
      backgroundIds = [];
      elementIds = [];
      conflictIds = [];
      directionCardIds = [];
      session = preview = plan = document = null;
    } catch (e) {
      error = e.message;
    }
  }

  async function ensureSession() {
    if (session) return session;
    const created = await api.post('/playbook-sessions', {
      project_id: projectId,
      name: '플레이북 실행',
      concept_slots: {
        subject: subjectIds,
        background: backgroundIds,
        elements: elementIds,
        conflicts: conflictIds,
        wildcards: []
      },
      direction_card_ids: directionCardIds,
      user_direction: userDirection,
      writing_recipe_id: recipeId,
      output_profile: outputProfile,
      settings_json: {
        length,
        detail_level: Number(detailLevel),
        context_depth: contextDepth,
        creativity
      },
      seed: Number(seed) || 0
    });
    session = created;
    return created;
  }

  async function runAction(kind) {
    error = '';
    busy = true;
    try {
      const current = await ensureSession();
      const result = await api.post(`/playbook-sessions/${current.id}/${kind}`, {});
      session = result.session;
      if (kind === 'context-preview') preview = result.context_preview;
      if (kind === 'plan') plan = result.plan;
      if (kind === 'generate') {
        plan = result.plan;
        document = result.document;
      }
    } catch (e) {
      error = e.message;
    } finally {
      busy = false;
    }
  }
</script>

<div class="page">
  <div class="page-header">
    <div>
      <h1>플레이북</h1>
      <p>소재·방향·작문 방식·출력 설정을 조합해 재현 가능한 생성 세션을 만듭니다.</p>
    </div>
    <label style="min-width:260px">
      프로젝트
      <select bind:value={projectId} on:change={loadProjectData}>
        {#each projects as project}<option value={project.id}>{project.name}</option>{/each}
      </select>
    </label>
  </div>

  {#if error}<p class="error">{error}</p>{/if}

  <div class="grid-2">
    <section class="card stack">
      <h2>1. 컨셉 페이지 선택</h2>
      <label>
        주요 대상
        <select multiple bind:value={subjectIds}>
          {#each pages as page}<option value={page.id}>{page.title} · {page.usage_role}</option>{/each}
        </select>
      </label>
      <div class="grid-2">
        <label>
          배경
          <select multiple bind:value={backgroundIds}>
            {#each pages as page}<option value={page.id}>{page.title}</option>{/each}
          </select>
        </label>
        <label>
          등장 요소
          <select multiple bind:value={elementIds}>
            {#each pages as page}<option value={page.id}>{page.title}</option>{/each}
          </select>
        </label>
      </div>
      <label>
        갈등·변수
        <select multiple bind:value={conflictIds}>
          {#each pages as page}<option value={page.id}>{page.title}</option>{/each}
        </select>
      </label>
    </section>

    <section class="card stack">
      <h2>2. 방향</h2>
      <label>
        방향성 카드
        <select multiple bind:value={directionCardIds}>
          {#each cards as card}<option value={card.id}>{card.title}</option>{/each}
        </select>
      </label>
      <label>
        이번 실행의 추가 지시
        <textarea bind:value={userDirection} placeholder="예: 개인의 타락보다 사회 전체가 이 기술에 의존하는 과정에 집중한다."></textarea>
      </label>
      <p class="small">직접 입력한 문장은 저장 가능한 임시 방향성 카드로 확장할 수 있습니다.</p>
    </section>

    <section class="card stack">
      <h2>3. 집필 방식</h2>
      <label>
        집필 레시피
        <select bind:value={recipeId}>
          {#each recipes as recipe}<option value={recipe.id}>{recipe.name} · {recipe.version}</option>{/each}
        </select>
      </label>
      <label>
        출력 형식
        <select bind:value={outputProfile}>
          <option value="lore_article">설정 글</option>
          <option value="video_narration">영상 내레이션</option>
          <option value="novel_prose">소설 산문</option>
        </select>
      </label>
      {#if recipeId}
        {@const recipe = recipes.find((item) => item.id === recipeId)}
        {#if recipe}<p class="small">{recipe.description}</p>{/if}
      {/if}
    </section>

    <section class="card stack">
      <h2>4. 생성 설정</h2>
      <div class="grid-2">
        <label>
          분량
          <select bind:value={length}>
            <option value="short">짧게</option>
            <option value="normal">보통</option>
            <option value="long">길게</option>
            <option value="very_long">매우 길게</option>
          </select>
        </label>
        <label>
          상세도 · {detailLevel}/5
          <input type="range" min="1" max="5" bind:value={detailLevel} />
        </label>
      </div>
      <div class="grid-2">
        <label>
          자료 반영 범위
          <select bind:value={contextDepth}>
            <option value="core">핵심만</option>
            <option value="balanced">균형</option>
            <option value="wide">넓게</option>
            <option value="max">최대</option>
          </select>
        </label>
        <label>
          창작 자유도
          <select bind:value={creativity}>
            <option value="strict">엄격</option>
            <option value="conservative">보수적</option>
            <option value="balanced">균형</option>
            <option value="free">자유</option>
          </select>
        </label>
      </div>
      <label>재현용 시드 <input type="number" bind:value={seed} /></label>
    </section>
  </div>

  <section class="card stack" style="margin-top:16px">
    <div class="row wrap">
      <button class="secondary" disabled={busy || !projectId || !recipeId} on:click={() => runAction('context-preview')}>컨텍스트 미리보기</button>
      <button class="secondary" disabled={busy || !projectId || !recipeId} on:click={() => runAction('plan')}>구성안 생성</button>
      <button class="primary" disabled={busy || !projectId || !recipeId} on:click={() => runAction('generate')}>로어 작성</button>
      {#if busy}<span class="small">처리 중…</span>{/if}
    </div>

    {#if preview}
      <h3>컨텍스트 팩</h3>
      {#if preview.warnings?.length}
        {#each preview.warnings as warning}<p class="error">{warning}</p>{/each}
      {/if}
      <pre>{JSON.stringify(preview, null, 2)}</pre>
    {/if}

    {#if plan}
      <h3>Article Plan</h3>
      <pre>{JSON.stringify(plan, null, 2)}</pre>
    {/if}

    {#if document}
      <h3>{document.title}</h3>
      <pre>{document.body_markdown}</pre>
      <a class="primary" href="/documents">문서 편집기로 이동</a>
    {/if}
  </section>
</div>
