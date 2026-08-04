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
  let pageFilter = '';
  let relations = [];
  let indexStats = null;
  let cardSuggestion = null;
  let referenceAnalysis = null;
  let busy = '';

  $: visiblePages = pages.filter((page) => !pageFilter || `${page.title} ${(page.tags || []).join(' ')}`.toLowerCase().includes(pageFilter.toLowerCase()));
  $: allTags = [...new Set(pages.flatMap((page) => page.tags || []))].sort();

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
      [pages, cards, indexStats] = await Promise.all([
        api.get(`/concept-pages?project_id=${projectId}`),
        api.get(`/direction-cards?project_id=${projectId}`),
        api.get(`/index/stats?project_id=${projectId}`)
      ]);
      if (pages[0]) await selectPage(pages[0]); else selectedPage = null;
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
        custom_category: selectedPage.custom_category,
        tags: typeof selectedPage.tagsText === 'string'
          ? selectedPage.tagsText.split(',').map((item) => item.trim()).filter(Boolean)
          : selectedPage.tags,
        usage_role: selectedPage.usage_role,
        namespace: selectedPage.namespace,
        era: selectedPage.era,
        continuity: selectedPage.continuity,
        summary: selectedPage.summary,
        body_json: selectedPage.body_json,
        locked_facts: typeof selectedPage.lockedFactsText === 'string'
          ? selectedPage.lockedFactsText.split('\n').map((item) => item.trim()).filter(Boolean)
          : selectedPage.locked_facts,
        open_questions: typeof selectedPage.openQuestionsText === 'string'
          ? selectedPage.openQuestionsText.split('\n').map((item) => item.trim()).filter(Boolean)
          : selectedPage.open_questions,
        forbidden_changes: typeof selectedPage.forbiddenChangesText === 'string'
          ? selectedPage.forbiddenChangesText.split('\n').map((item) => item.trim()).filter(Boolean)
          : selectedPage.forbidden_changes,
        properties_json: selectedPage.properties_json || {},
        attachment_refs: selectedPage.attachment_refs || []
      });
      selectedPage = updated;
      pages = pages.map((item) => item.id === updated.id ? updated : item);
      message = '저장했습니다.';
    } catch (e) {
      error = e.message;
    }
  }

  async function selectPage(page) {
    selectedPage = {
      ...page,
      tagsText: (page.tags || []).join(', '),
      lockedFactsText: (page.locked_facts || []).join('\n'),
      openQuestionsText: (page.open_questions || []).join('\n'),
      forbiddenChangesText: (page.forbidden_changes || []).join('\n')
    };
    try { relations = await api.get(`/concept-pages/${page.id}/relations`); }
    catch (e) { error = e.message; }
    referenceAnalysis = null;
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

  async function suggestCard(card) {
    busy = 'Utility 모델이 카드 원문을 구조화하는 중'; error = '';
    try { cardSuggestion = await api.post(`/direction-cards/${card.id}/suggest-structure`, {}); }
    catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  async function applyCardSuggestion() {
    if (!cardSuggestion) return;
    const suggestion = cardSuggestion.suggestion;
    const updated = await api.patch(`/direction-cards/${cardSuggestion.card_id}`, {
      parsed_rules: suggestion,
      compatible_tags: suggestion.compatible_tags || [],
      incompatible_tags: suggestion.incompatible_tags || []
    });
    cards = cards.map((item) => item.id === updated.id ? updated : item);
    cardSuggestion = null;
    message = '구조화 제안을 카드에 적용했습니다. 원문은 그대로 보존됐습니다.';
  }

  async function analyzeReference() {
    if (!selectedPage) return;
    busy = 'Utility 모델이 수사 이동과 문체 구조를 분석하는 중'; error = '';
    try { referenceAnalysis = await api.post(`/reference-analyzer/${selectedPage.id}`, {}); }
    catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  async function approveReference() {
    const result = await api.post(`/reference-analyses/${referenceAnalysis.id}/approve`, {});
    referenceAnalysis = { ...referenceAnalysis, status: result.status };
    message = '분석에서 집필 레시피와 Voice Profile을 승인했습니다.';
  }

  async function reindexPage() {
    if (!selectedPage) return;
    busy = 'BGE-M3 재색인 중'; error = '';
    try {
      const job = await api.post('/index/jobs', { project_id: projectId, concept_page_id: selectedPage.id });
      await api.post(`/index/jobs/${job.id}/run`, {});
      indexStats = await api.get(`/index/stats?project_id=${projectId}`);
      message = '페이지를 전용 벡터 인덱스에 반영했습니다.';
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }
</script>

<div class="page">
  <div class="page-header">
    <div>
      <p class="eyebrow">CONCEPT ARCHIVE</p>
      <h1>컨셉 아카이브</h1>
      <p>자유 본문을 중심으로 권위, 관계, 근거와 작문 참고를 분리해 축적합니다.</p>
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
  {#if busy}<div class="notice" role="status">{busy}… 원문은 변경하지 않습니다.</div>{/if}

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
          <span class="badge">{visiblePages.length}/{pages.length}</span>
        </div>
        <input aria-label="페이지 검색" bind:value={pageFilter} placeholder="제목·태그 검색" />
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
            <option>CANON_EVIDENCE</option>
            <option>SECONDARY_INTERPRETATION</option>
            <option>INSPIRATION</option>
            <option>DISCOURSE_REFERENCE</option>
            <option>CANDIDATE</option>
          </select>
        </label>
        <button class="secondary" on:click={createPage}>페이지 추가</button>
        <div class="list">
          {#each visiblePages as page}
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
            <div class="card stack" style="padding:10px">
              <strong>{card.title}</strong>
              <div class="small">{card.body.slice(0, 90)}</div>
              <button class="ghost" on:click={() => suggestCard(card)}>Utility 구조화 제안</button>
            </div>
          {/each}
        </div>
        {#if cardSuggestion}<div class="notice"><strong>원문 보존됨</strong><pre>{JSON.stringify(cardSuggestion.suggestion, null, 2)}</pre><button class="primary" on:click={applyCardSuggestion}>제안 적용</button></div>{/if}
      </aside>

      <section class="stack">
        {#if selectedPage}
          <div class="card row" style="justify-content:space-between">
            <div>
              <strong>{selectedPage.title}</strong>
              <div class="small">자유 본문이 원본이며 구조화 필드는 선택 사항입니다.</div>
            </div>
            <div class="row"><button class="ghost" on:click={reindexPage}>BGE-M3 재색인</button><button class="primary" on:click={savePage}>변경 저장</button></div>
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
          <label>사용자 정의 카테고리 <input bind:value={selectedPage.custom_category} placeholder="프리셋에 없을 때만" /></label>
          <label>태그 <input bind:value={selectedPage.tagsText} list="known-tags" placeholder="쉼표로 구분" /></label>
          <datalist id="known-tags">{#each allTags as tag}<option value={tag}></option>{/each}</datalist>
          <label>
            사용 역할
            <select bind:value={selectedPage.usage_role}>
              <option>PROJECT_CANON</option>
              <option>DRAFT_SETTING</option>
              <option>CANON_EVIDENCE</option>
              <option>SECONDARY_INTERPRETATION</option>
              <option>INSPIRATION</option>
              <option>DISCOURSE_REFERENCE</option>
              <option>CANDIDATE</option>
              <option>REJECTED</option>
            </select>
          </label>
          <label>네임스페이스 <input bind:value={selectedPage.namespace} /></label>
          <div class="grid-2"><label>시대 <input bind:value={selectedPage.era} /></label><label>연속성 <input bind:value={selectedPage.continuity} /></label></div>
          <label>짧은 요약 <textarea bind:value={selectedPage.summary}></textarea></label>
          <label>잠긴 사실 · 한 줄에 하나 <textarea bind:value={selectedPage.lockedFactsText}></textarea></label>
          <label>열린 질문 · 한 줄에 하나 <textarea bind:value={selectedPage.openQuestionsText}></textarea></label>
          <label>금지된 변경 · 한 줄에 하나 <textarea bind:value={selectedPage.forbiddenChangesText}></textarea></label>
          <hr />
          <div class="row spread"><strong>관계·백링크</strong><span class="badge">{relations.length}</span></div>
          {#each relations as relation}<div class="evidence-item"><strong>{relation.relation_type}</strong><small>{relation.source_page_id.slice(0,8)} → {relation.target_page_id.slice(0,8)}</small></div>{/each}
          {#if !relations.length}<p class="small">연결된 관계가 없습니다.</p>{/if}
          <div class="notice"><strong>전용 인덱스</strong><div class="small">{indexStats?.indexed_pages || 0}개 페이지 · {indexStats?.chunks || 0}개 청크 · {indexStats?.model || '비활성'}</div></div>
          {#if selectedPage.usage_role === 'DISCOURSE_REFERENCE'}
            <button class="secondary" on:click={analyzeReference}>Reference Analyzer 실행</button>
            {#if referenceAnalysis}<pre>{JSON.stringify(referenceAnalysis.analysis_json, null, 2)}</pre><button class="primary" disabled={referenceAnalysis.status !== 'CANDIDATE'} on:click={approveReference}>{referenceAnalysis.status === 'CANDIDATE' ? '레시피·Voice 승인' : '승인됨'}</button>{/if}
          {/if}
          {#if message}<p class="success">{message}</p>{/if}
        {/if}
      </aside>
    </div>
  {/if}
</div>
