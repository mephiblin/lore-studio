<script>
  import { onMount } from 'svelte';
  import TiptapEditor from '$lib/components/TiptapEditor.svelte';
  import { api } from '$lib/api';

  let projects = [];
  let projectId = '';
  let pages = [];
  let cards = [];
  let templates = [];
  let selectedPage = null;
  let error = '';
  let message = '';

  let projectForm = { name: '', slug: '', universe_namespace: 'my-world' };
  let pageForm = { title: '', category_key: 'free', usage_role: 'DRAFT_SETTING' };
  let cardForm = { title: '', body: '', tags: '' };

  onMount(loadInitial);

  async function loadInitial() {
    try {
      templates = await api.get('/presets/page-templates');
      projects = await api.get('/projects');
      if (projects.length) {
        projectId = projects[0].id;
        await loadProjectData();
      }
    } catch (e) {
      error = e.message;
    }
  }

  async function createProject() {
    error = '';
    try {
      const created = await api.post('/projects', {
        ...projectForm,
        description: '',
        settings_json: {}
      });
      projects = [created, ...projects];
      projectId = created.id;
      projectForm = { name: '', slug: '', universe_namespace: 'my-world' };
      await loadProjectData();
    } catch (e) {
      error = e.message;
    }
  }

  async function loadProjectData() {
    if (!projectId) return;
    error = '';
    try {
      [pages, cards] = await Promise.all([
        api.get(`/concept-pages?project_id=${projectId}`),
        api.get(`/direction-cards?project_id=${projectId}`)
      ]);
      selectedPage = pages[0] || null;
    } catch (e) {
      error = e.message;
    }
  }

  async function createPage() {
    if (!projectId || !pageForm.title.trim()) return;
    error = '';
    try {
      const project = projects.find((item) => item.id === projectId);
      const page = await api.post('/concept-pages', {
        project_id: projectId,
        title: pageForm.title,
        category_key: pageForm.category_key,
        tags: [],
        usage_role: pageForm.usage_role,
        status: 'active',
        namespace: project?.universe_namespace || 'default',
        summary: '',
        body_json: { type: 'doc', content: [] },
        properties_json: {},
        locked_facts: [],
        open_questions: []
      });
      pages = [page, ...pages];
      selectedPage = page;
      pageForm.title = '';
    } catch (e) {
      error = e.message;
    }
  }

  async function savePage() {
    if (!selectedPage) return;
    error = '';
    message = '';
    try {
      const updated = await api.patch(`/concept-pages/${selectedPage.id}`, {
        title: selectedPage.title,
        category_key: selectedPage.category_key,
        tags: typeof selectedPage.tagsText === 'string'
          ? selectedPage.tagsText.split(',').map((item) => item.trim()).filter(Boolean)
          : selectedPage.tags,
        usage_role: selectedPage.usage_role,
        namespace: selectedPage.namespace,
        summary: selectedPage.summary,
        body_json: selectedPage.body_json,
        locked_facts: typeof selectedPage.lockedFactsText === 'string'
          ? selectedPage.lockedFactsText.split('\n').map((item) => item.trim()).filter(Boolean)
          : selectedPage.locked_facts,
        open_questions: typeof selectedPage.openQuestionsText === 'string'
          ? selectedPage.openQuestionsText.split('\n').map((item) => item.trim()).filter(Boolean)
          : selectedPage.open_questions
      });
      selectedPage = updated;
      pages = pages.map((item) => item.id === updated.id ? updated : item);
      message = '저장했습니다.';
    } catch (e) {
      error = e.message;
    }
  }

  function selectPage(page) {
    selectedPage = {
      ...page,
      tagsText: (page.tags || []).join(', '),
      lockedFactsText: (page.locked_facts || []).join('\n'),
      openQuestionsText: (page.open_questions || []).join('\n')
    };
    message = '';
  }

  async function createCard() {
    if (!projectId || !cardForm.title.trim() || !cardForm.body.trim()) return;
    error = '';
    try {
      const card = await api.post('/direction-cards', {
        project_id: projectId,
        title: cardForm.title,
        body: cardForm.body,
        tags: cardForm.tags.split(',').map((item) => item.trim()).filter(Boolean),
        parsed_rules: {},
        weight: 1,
        enabled: true
      });
      cards = [card, ...cards];
      cardForm = { title: '', body: '', tags: '' };
    } catch (e) {
      error = e.message;
    }
  }
</script>

<div class="page">
  <div class="page-header">
    <div>
      <h1>에디터</h1>
      <p>컨셉 페이지와 방향성 카드를 축적합니다.</p>
    </div>
    <label style="min-width:260px">
      프로젝트
      <select bind:value={projectId} on:change={loadProjectData}>
        <option value="">프로젝트 선택</option>
        {#each projects as project}
          <option value={project.id}>{project.name}</option>
        {/each}
      </select>
    </label>
  </div>

  {#if error}<p class="error">{error}</p>{/if}

  {#if !projects.length}
    <section class="card stack" style="max-width:560px">
      <h2>첫 프로젝트 만들기</h2>
      <label>이름 <input bind:value={projectForm.name} /></label>
      <label>slug <input bind:value={projectForm.slug} placeholder="my-world" /></label>
      <label>네임스페이스 <input bind:value={projectForm.universe_namespace} /></label>
      <button class="primary" on:click={createProject}>프로젝트 생성</button>
    </section>
  {:else}
    <div class="grid-3">
      <aside class="card stack">
        <div class="row" style="justify-content:space-between">
          <h3>컨셉 페이지</h3>
          <span class="badge">{pages.length}</span>
        </div>
        <label>새 페이지 제목 <input bind:value={pageForm.title} /></label>
        <label>
          카테고리
          <select bind:value={pageForm.category_key}>
            {#each templates as template}<option value={template.key}>{template.name}</option>{/each}
          </select>
        </label>
        <label>
          사용 역할
          <select bind:value={pageForm.usage_role}>
            <option>PROJECT_CANON</option>
            <option>DRAFT_SETTING</option>
            <option>SOURCE_EVIDENCE</option>
            <option>SECONDARY_INTERPRETATION</option>
            <option>INSPIRATION_ONLY</option>
            <option>DISCOURSE_REFERENCE</option>
            <option>CANDIDATE</option>
          </select>
        </label>
        <button class="secondary" on:click={createPage}>페이지 추가</button>
        <div class="list">
          {#each pages as page}
            <button class:active={selectedPage?.id === page.id} on:click={() => selectPage(page)}>
              <strong>{page.title}</strong>
              <div class="small">{page.category_key} · {page.usage_role}</div>
            </button>
          {/each}
        </div>

        <hr />
        <h3>방향성 카드</h3>
        <label>제목 <input bind:value={cardForm.title} /></label>
        <label>내용 <textarea bind:value={cardForm.body}></textarea></label>
        <label>태그 <input bind:value={cardForm.tags} placeholder="비극, 기관, 미스터리" /></label>
        <button class="secondary" on:click={createCard}>카드 추가</button>
        <div class="list">
          {#each cards as card}
            <div class="card" style="padding:10px">
              <strong>{card.title}</strong>
              <div class="small">{card.body.slice(0, 90)}</div>
            </div>
          {/each}
        </div>
      </aside>

      <section class="stack">
        {#if selectedPage}
          <div class="card row" style="justify-content:space-between">
            <div>
              <strong>{selectedPage.title}</strong>
              <div class="small">자유 본문이 원본이며 구조화 필드는 선택 사항입니다.</div>
            </div>
            <button class="primary" on:click={savePage}>저장</button>
          </div>
          <TiptapEditor
            value={selectedPage.body_json}
            onChange={(body) => selectedPage = { ...selectedPage, body_json: body }}
          />
        {:else}
          <div class="card">왼쪽에서 컨셉 페이지를 만들거나 선택하십시오.</div>
        {/if}
      </section>

      <aside class="card stack">
        {#if selectedPage}
          <h3>페이지 속성</h3>
          <label>제목 <input bind:value={selectedPage.title} /></label>
          <label>
            카테고리
            <select bind:value={selectedPage.category_key}>
              {#each templates as template}<option value={template.key}>{template.name}</option>{/each}
            </select>
          </label>
          <label>태그 <input bind:value={selectedPage.tagsText} placeholder="쉼표로 구분" /></label>
          <label>
            사용 역할
            <select bind:value={selectedPage.usage_role}>
              <option>PROJECT_CANON</option>
              <option>DRAFT_SETTING</option>
              <option>SOURCE_EVIDENCE</option>
              <option>SECONDARY_INTERPRETATION</option>
              <option>INSPIRATION_ONLY</option>
              <option>DISCOURSE_REFERENCE</option>
              <option>CANDIDATE</option>
              <option>REJECTED</option>
            </select>
          </label>
          <label>네임스페이스 <input bind:value={selectedPage.namespace} /></label>
          <label>짧은 요약 <textarea bind:value={selectedPage.summary}></textarea></label>
          <label>잠긴 사실 · 한 줄에 하나 <textarea bind:value={selectedPage.lockedFactsText}></textarea></label>
          <label>열린 질문 · 한 줄에 하나 <textarea bind:value={selectedPage.openQuestionsText}></textarea></label>
          {#if message}<p class="success">{message}</p>{/if}
        {/if}
      </aside>
    </div>
  {/if}
</div>
