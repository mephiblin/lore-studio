<script>
  import { onMount } from 'svelte';
  import TiptapEditor from '$lib/components/TiptapEditor.svelte';
  import ProjectCreator from '$lib/components/ProjectCreator.svelte';
  import { api } from '$lib/api';
  import { relationLabel, relationLabels } from '$lib/labels';
  import { initialProjectId, rememberProject } from '$lib/project';

  let projects = [];
  let projectId = '';
  let pages = [];
  let cards = [];
  let categories = [];
  let selectedPage = null;
  let activeTab = 'pages';
  let error = '';
  let message = '';
  let pageFilter = '';
  let categoryFilter = 'all';
  let relations = [];
  let indexStats = null;
  let cardSuggestion = null;
  let referenceAnalysis = null;
  let busy = '';
  let newPageOpen = false;
  let editingCardId = '';
  let cardDraft = { title: '', body: '', tags: '' };
  let categoryForm = { name: '', description: '' };

  const categorySlotOptions = [
    { key: 'subject', label: '주제' },
    { key: 'background', label: '배경' },
    { key: 'elements', label: '주요 요소' },
    { key: 'conflicts', label: '갈등·변수' }
  ];

  $: visiblePages = pages.filter((page) => {
    const matchesText = !pageFilter || `${page.title} ${page.summary} ${(page.tags || []).join(' ')}`.toLowerCase().includes(pageFilter.toLowerCase());
    return matchesText && (categoryFilter === 'all' || page.category_key === categoryFilter);
  });
  $: allTags = [...new Set(pages.flatMap((page) => page.tags || []))].sort();

  let pageForm = { title: '', category_key: '', purpose: 'setting' };
  let cardForm = { title: '', body: '', tags: '' };
  let relationForm = { target_page_id: '', relation_type: 'RELATED_TO', notes: '' };

  const purposeRoles = {
    setting: 'DRAFT_SETTING',
    evidence: 'CANON_EVIDENCE',
    inspiration: 'INSPIRATION',
    style: 'DISCOURSE_REFERENCE'
  };

  onMount(loadInitial);

  async function loadInitial() {
    try {
      projects = await api.get('/projects');
      projectId = initialProjectId(projects);
      if (projectId) await loadProjectData();
    } catch (e) { error = e.message; }
  }

  async function projectCreated(project) {
    projects = [project, ...projects];
    projectId = project.id;
    rememberProject(projectId);
    await loadProjectData();
  }

  async function changeProject() {
    rememberProject(projectId);
    await loadProjectData();
  }

  async function loadProjectData() {
    if (!projectId) return;
    error = '';
    message = '';
    categoryFilter = 'all';
    try {
      [pages, cards, indexStats, categories] = await Promise.all([
        api.get(`/concept-pages?project_id=${projectId}`),
        api.get(`/direction-cards?project_id=${projectId}`),
        api.get(`/index/stats?project_id=${projectId}`),
        api.get(`/categories?project_id=${projectId}`)
      ]);
      pageForm = {
        ...pageForm,
        category_key: categories.some((item) => item.key === pageForm.category_key)
          ? pageForm.category_key
          : categories[0]?.key || ''
      };
      if (pages[0]) await selectPage(pages[0]);
      else { selectedPage = null; relations = []; }
    } catch (e) { error = e.message; }
  }

  async function createPage() {
    if (!projectId || !pageForm.title.trim()) return;
    error = '';
    try {
      const project = projects.find((item) => item.id === projectId);
      const page = await api.post('/concept-pages', {
        project_id: projectId,
        title: pageForm.title.trim(),
        category_key: pageForm.category_key,
        tags: [],
        usage_role: purposeRoles[pageForm.purpose],
        status: 'active',
        namespace: project?.universe_namespace || 'default',
        summary: '',
        body_json: { type: 'doc', content: [] },
        properties_json: {},
        locked_facts: [],
        open_questions: [],
        forbidden_changes: []
      });
      pages = [page, ...pages];
      pageForm = { title: '', category_key: categories[0]?.key || '', purpose: 'setting' };
      newPageOpen = false;
      await selectPage(page, { reveal: true });
      message = '새 자료를 만들었습니다. 본문과 핵심 사실을 채워 보세요.';
    } catch (e) { error = e.message; }
  }

  async function savePage() {
    if (!selectedPage) return;
    error = ''; message = ''; busy = '변경 저장 중';
    try {
      const updated = await api.patch(`/concept-pages/${selectedPage.id}`, {
        title: selectedPage.title,
        category_key: selectedPage.category_key,
        tags: typeof selectedPage.tagsText === 'string' ? selectedPage.tagsText.split(',').map((item) => item.trim()).filter(Boolean) : selectedPage.tags,
        namespace: selectedPage.namespace,
        summary: selectedPage.summary,
        body_json: selectedPage.body_json,
        locked_facts: lines(selectedPage.lockedFactsText, selectedPage.locked_facts),
        open_questions: lines(selectedPage.openQuestionsText, selectedPage.open_questions),
        forbidden_changes: lines(selectedPage.forbiddenChangesText, selectedPage.forbidden_changes),
        properties_json: selectedPage.properties_json || {},
        attachment_refs: selectedPage.attachment_refs || []
      });
      selectedPage = decoratePage(updated);
      pages = pages.map((item) => item.id === updated.id ? updated : item);
      message = '변경 내용을 저장했습니다.';
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  function lines(text, fallback) {
    return typeof text === 'string' ? text.split('\n').map((item) => item.trim()).filter(Boolean) : fallback;
  }

  function decoratePage(page) {
    return {
      ...page,
      tagsText: (page.tags || []).join(', '),
      lockedFactsText: (page.locked_facts || []).join('\n'),
      openQuestionsText: (page.open_questions || []).join('\n'),
      forbiddenChangesText: (page.forbidden_changes || []).join('\n')
    };
  }

  async function selectPage(page, { reveal = false } = {}) {
    selectedPage = decoratePage(page);
    relations = [];
    relationForm = { target_page_id: '', relation_type: 'RELATED_TO', notes: '' };
    if (reveal && typeof window !== 'undefined' && window.matchMedia('(max-width: 820px)').matches) {
      setTimeout(() => document.querySelector('.manuscript-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0);
    }
    try {
      const loadedRelations = await api.get(`/concept-pages/${page.id}/relations`);
      if (selectedPage?.id === page.id) relations = loadedRelations;
    }
    catch (e) { error = e.message; }
    referenceAnalysis = null;
    message = '';
  }

  function pageName(pageId) {
    return pages.find((page) => page.id === pageId)?.title || '삭제된 자료';
  }

  function categoryName(page) {
    return categories.find((item) => item.key === page?.category_key)?.name || page?.custom_category || page?.category_key || '종류 없음';
  }

  function categoryUsedCount(category) {
    return pages.filter((page) => page.category_key === category.key).length;
  }

  function categorySlots(category) {
    return category.template_json?.recommended_slots || [];
  }

  function toggleCategorySlot(category, slot) {
    const current = categorySlots(category);
    const recommended_slots = current.includes(slot)
      ? current.filter((item) => item !== slot)
      : [...current, slot];
    category.template_json = { ...(category.template_json || {}), recommended_slots };
    categories = [...categories];
  }

  async function createCategory() {
    if (!projectId || !categoryForm.name.trim()) return;
    error = ''; message = '';
    try {
      const category = await api.post('/categories', {
        project_id: projectId,
        name: categoryForm.name.trim(),
        description: categoryForm.description.trim(),
        template_json: { recommended_slots: categorySlotOptions.map((item) => item.key) }
      });
      categories = [...categories, category].sort((a, b) => a.name.localeCompare(b.name, 'ko'));
      pageForm = { ...pageForm, category_key: category.key };
      categoryForm = { name: '', description: '' };
      message = `'${category.name}' 자료 종류를 만들었습니다.`;
    } catch (e) { error = e.message; }
  }

  async function saveCategory(category) {
    if (!category.name.trim()) return;
    error = ''; message = '';
    try {
      const updated = await api.patch(`/categories/${category.id}`, {
        name: category.name.trim(),
        description: category.description.trim(),
        template_json: category.template_json || {}
      });
      categories = categories.map((item) => item.id === updated.id ? updated : item)
        .sort((a, b) => a.name.localeCompare(b.name, 'ko'));
      message = `'${updated.name}' 자료 종류를 저장했습니다.`;
    } catch (e) { error = e.message; }
  }

  async function deleteCategory(category) {
    if (!confirm(`'${category.name}' 자료 종류를 삭제할까요? 사용 중인 종류는 삭제할 수 없습니다.`)) return;
    error = ''; message = '';
    try {
      await api.delete(`/categories/${category.id}`);
      categories = categories.filter((item) => item.id !== category.id);
      if (pageForm.category_key === category.key) pageForm = { ...pageForm, category_key: categories[0]?.key || '' };
      message = `'${category.name}' 자료 종류를 삭제했습니다.`;
    } catch (e) { error = e.message; }
  }

  function otherPage(relation) {
    return relation.source_page_id === selectedPage?.id ? relation.target_page_id : relation.source_page_id;
  }

  async function createRelation() {
    if (!selectedPage || !relationForm.target_page_id) return;
    try {
      const relation = await api.post('/concept-relations', {
        project_id: projectId,
        source_page_id: selectedPage.id,
        ...relationForm
      });
      relations = [...relations, relation];
      relationForm = { target_page_id: '', relation_type: 'RELATED_TO', notes: '' };
      message = '자료 연결을 추가했습니다.';
    } catch (e) { error = e.message; }
  }

  async function removeRelation(relation) {
    if (!confirm(`'${pageName(otherPage(relation))}'과의 연결을 삭제할까요?`)) return;
    try {
      await api.delete(`/concept-relations/${relation.id}`);
      relations = relations.filter((item) => item.id !== relation.id);
    } catch (e) { error = e.message; }
  }

  async function createCard() {
    if (!projectId || !cardForm.title.trim() || !cardForm.body.trim()) return;
    try {
      const card = await api.post('/direction-cards', {
        project_id: projectId,
        title: cardForm.title.trim(),
        body: cardForm.body.trim(),
        tags: cardForm.tags.split(',').map((item) => item.trim()).filter(Boolean),
        parsed_rules: {}, weight: 1, enabled: true
      });
      cards = [card, ...cards];
      cardForm = { title: '', body: '', tags: '' };
      message = '집필 지침을 추가했습니다.';
    } catch (e) { error = e.message; }
  }

  function editCard(card) {
    editingCardId = card.id;
    cardDraft = { title: card.title, body: card.body, tags: (card.tags || []).join(', ') };
  }

  async function saveCard(card) {
    try {
      const updated = await api.patch(`/direction-cards/${card.id}`, {
        title: cardDraft.title.trim(), body: cardDraft.body.trim(),
        tags: cardDraft.tags.split(',').map((item) => item.trim()).filter(Boolean)
      });
      cards = cards.map((item) => item.id === updated.id ? updated : item);
      editingCardId = '';
      message = '집필 지침을 저장했습니다.';
    } catch (e) { error = e.message; }
  }

  async function deleteCard(card) {
    if (!confirm(`'${card.title}' 규칙을 삭제할까요?`)) return;
    try { await api.delete(`/direction-cards/${card.id}`); cards = cards.filter((item) => item.id !== card.id); }
    catch (e) { error = e.message; }
  }

  async function suggestCard(card) {
    busy = 'AI가 원문에서 세부 규칙을 정리하는 중'; error = '';
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
    message = '세부 규칙을 저장했습니다. 원문은 바뀌지 않았습니다.';
  }

  async function analyzeReference() {
    if (!selectedPage) return;
    busy = 'AI가 문단 구조와 문체를 분석하는 중'; error = '';
    try { referenceAnalysis = await api.post(`/reference-analyzer/${selectedPage.id}`, {}); }
    catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  async function approveReference() {
    const result = await api.post(`/reference-analyses/${referenceAnalysis.id}/approve`, {});
    referenceAnalysis = { ...referenceAnalysis, status: result.status };
    message = '구성·문체 분석 결과를 승인했습니다.';
  }

  async function reindexPage() {
    if (!selectedPage) return;
    busy = '검색 인덱스에 반영하는 중'; error = '';
    try {
      const job = await api.post('/index/jobs', { project_id: projectId, concept_page_id: selectedPage.id });
      await api.post(`/index/jobs/${job.id}/run`, {});
      indexStats = await api.get(`/index/stats?project_id=${projectId}`);
      message = '최신 내용을 자료 검색에 반영했습니다.';
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }
</script>

<div class="page workspace-page editor-page">
  <div class="page-tools editor-commandbar">
    {#if projects.length}
      <nav class="section-tabs" aria-label="세계관 자료 관리">
        <button class:active={activeTab === 'pages'} on:click={() => activeTab = 'pages'}>세계관 자료 <span>{pages.length}</span></button>
        <button class:active={activeTab === 'categories'} on:click={() => activeTab = 'categories'}>자료 종류 <span>{categories.length}</span></button>
        <button class:active={activeTab === 'directions'} on:click={() => activeTab = 'directions'}>집필 지침 <span>{cards.length}</span></button>
      </nav>
    {/if}
    <div class="project-tools">
      <label>현재 프로젝트<select bind:value={projectId} on:change={changeProject}><option value="">프로젝트 선택</option>{#each projects as project}<option value={project.id}>{project.name}</option>{/each}</select></label>
      <ProjectCreator onCreated={projectCreated} />
    </div>
  </div>

  {#if error}<p class="notice-error">{error}</p>{/if}
  {#if busy}<div class="notice" role="status">{busy}…</div>{/if}
  {#if message}<div class="success-banner">{message}</div>{/if}

  {#if !projects.length}
    <section class="empty-state"><strong>먼저 프로젝트를 만들어 주세요.</strong><p>프로젝트는 하나의 세계관과 그 원고를 서로 섞이지 않게 보관합니다.</p></section>
  {:else}
    {#if activeTab === 'pages'}
      <div class="archive-layout">
        <aside class="card archive-list stack">
          <div class="row spread"><div><h2>자료</h2><p class="small">원고가 참고할 세계의 사실과 아이디어</p></div><button class="primary compact" on:click={() => newPageOpen = !newPageOpen}>+ 새 자료</button></div>
          {#if newPageOpen}
            <div class="inline-create stack">
              <label>자료 이름 <input bind:value={pageForm.title} placeholder="예: 황혼 시장" /></label>
              <div class="grid-2">
                <label>자료 종류<select bind:value={pageForm.category_key}>{#each categories as category}<option value={category.key}>{category.name}</option>{/each}</select></label>
                <label>용도<select bind:value={pageForm.purpose}><option value="setting">세계관 설정</option><option value="evidence">정식 설정 근거</option><option value="inspiration">영감 자료</option><option value="style">문체 참고</option></select></label>
              </div>
              <button class="primary" disabled={!pageForm.title.trim() || !pageForm.category_key} on:click={createPage}>자료 만들기</button>
            </div>
          {/if}
          <div class="filter-row"><input aria-label="자료 검색" bind:value={pageFilter} placeholder="제목·태그·요약 검색" /><select aria-label="종류 필터" bind:value={categoryFilter}><option value="all">모든 종류</option>{#each categories as category}<option value={category.key}>{category.name}</option>{/each}</select></div>
          <div class="archive-page-list">
            {#each visiblePages as page}
              <button class:active={selectedPage?.id === page.id} on:click={() => selectPage(page, { reveal: true })}>
                <strong>{page.title}</strong>
                <small>{categoryName(page)}{page.summary ? ` · ${page.summary.slice(0, 48)}` : ''}</small>
              </button>
            {/each}
            {#if !visiblePages.length}<div class="empty-mini">조건에 맞는 자료가 없습니다.</div>{/if}
          </div>
        </aside>

        <section class="stack manuscript-panel">
          {#if selectedPage}
            <div class="card manuscript-toolbar">
              <div class="manuscript-heading-fields">
                <span class="badge">{categoryName(selectedPage)}</span>
                <input class="manuscript-title-input" aria-label="자료 제목" bind:value={selectedPage.title} />
                <input class="manuscript-summary-input" aria-label="한 줄 요약" bind:value={selectedPage.summary} placeholder="이 자료를 한 문장으로 설명해 보세요." />
              </div>
              <button class="primary" on:click={savePage}>변경 저장</button>
            </div>
            {#key selectedPage.id}
              <TiptapEditor value={selectedPage.body_json} onChange={(body) => selectedPage = { ...selectedPage, body_json: body }} />
            {/key}
          {:else}<div class="empty-state">왼쪽에서 자료를 만들거나 선택하세요.</div>{/if}
        </section>

        <aside class="card archive-inspector stack">
          {#if selectedPage}
            <h2>핵심 정보</h2>
            <label>자료 종류<select bind:value={selectedPage.category_key}>{#each categories as category}<option value={category.key}>{category.name}</option>{/each}</select></label>
            <label>태그 <input bind:value={selectedPage.tagsText} list="known-tags" placeholder="쉼표로 구분" /></label>
            <datalist id="known-tags">{#each allTags as tag}<option value={tag}></option>{/each}</datalist>

            <details open>
              <summary>원고에서 지킬 것</summary>
              <div class="stack details-body">
                <label>확정된 사실 <textarea bind:value={selectedPage.lockedFactsText} placeholder="한 줄에 하나씩"></textarea></label>
                <label>아직 답하지 않을 질문 <textarea bind:value={selectedPage.openQuestionsText} placeholder="한 줄에 하나씩"></textarea></label>
                <label>바꾸면 안 되는 것 <textarea bind:value={selectedPage.forbiddenChangesText} placeholder="한 줄에 하나씩"></textarea></label>
              </div>
            </details>

            <section class="relation-section stack">
              <div class="row spread"><div><h3>연결된 자료</h3><p class="small">이 자료가 세계의 다른 요소와 어떻게 연결되는지 표시합니다.</p></div><span class="badge">{relations.length}</span></div>
              {#each relations as relation}
                <div class="relation-card">
                  <button class="relation-link" on:click={() => selectPage(pages.find((page) => page.id === otherPage(relation)), { reveal: true })}>
                    <small>{relation.source_page_id === selectedPage.id ? '나가는 연결' : '들어오는 연결'} · {relationLabel(relation.relation_type)}</small>
                    <strong>{pageName(otherPage(relation))}</strong>
                    {#if relation.notes}<span>{relation.notes}</span>{/if}
                  </button>
                  <button class="icon-button" aria-label="연결 삭제" on:click={() => removeRelation(relation)}>×</button>
                </div>
              {/each}
              {#if !relations.length}<p class="empty-mini">아직 연결된 자료가 없습니다.</p>{/if}
              <div class="inline-create stack">
                <strong>연결 추가</strong>
                <label>대상 자료<select bind:value={relationForm.target_page_id}><option value="">선택하세요</option>{#each pages.filter((page) => page.id !== selectedPage.id) as page}<option value={page.id}>{page.title}</option>{/each}</select></label>
                <label>관계<select bind:value={relationForm.relation_type}>{#each Object.entries(relationLabels) as [value, label]}<option {value}>{label}</option>{/each}</select></label>
                <label>메모 <input bind:value={relationForm.notes} placeholder="연결 이유" /></label>
                <button class="secondary" disabled={!relationForm.target_page_id} on:click={createRelation}>연결하기</button>
              </div>
            </section>

            <details>
              <summary>고급 정보</summary>
              <div class="stack details-body">
                <label>자료 범위 <input bind:value={selectedPage.namespace} /></label>
                <div class="notice"><strong>검색 상태</strong><div class="small">{indexStats?.indexed_pages || 0}개 자료 · {indexStats?.chunks || 0}개 조각</div></div>
                <button class="secondary" on:click={reindexPage}>최신 내용을 검색에 반영</button>
              </div>
            </details>
            {#if selectedPage.usage_role === 'DISCOURSE_REFERENCE'}
              <button class="secondary" on:click={analyzeReference}>이 글의 구성·문체 분석</button>
              {#if referenceAnalysis}
                <div class="rule-preview stack">
                  <strong>문단 구성 분석</strong>
                  {#each referenceAnalysis.analysis_json?.paragraphs || [] as paragraph}
                    <div class="evidence-item"><strong>{paragraph.index + 1}번째 문단 · {paragraph.primary_move}</strong><small>보조 역할 {paragraph.secondary_move} · 범위 {paragraph.scale} · 맺음 {paragraph.ending}</small></div>
                  {/each}
                  {#if !referenceAnalysis.analysis_json?.paragraphs?.length}<p class="empty-mini">분석된 문단이 없습니다.</p>{/if}
                  <button class="primary" disabled={referenceAnalysis.status !== 'CANDIDATE'} on:click={approveReference}>{referenceAnalysis.status === 'CANDIDATE' ? '분석 결과 승인' : '승인됨'}</button>
                </div>
              {/if}
            {/if}
          {/if}
        </aside>
      </div>
    {:else if activeTab === 'directions'}
      <section class="directions-layout">
        <div class="direction-intro">
          <p class="eyebrow">프로젝트 집필 지침</p>
          <h2>이 프로젝트의 글에서<br />강조할 것과 피할 것을 정합니다.</h2>
          <p>세계관 사실도, 글의 전개 순서도 아닙니다. 글 만들기에서 선택하면 이번 원고가 지킬 강조점·금지 사항·결말 원칙을 Writer에게 전달합니다.</p>
        </div>
        <div class="card stack direction-create">
          <h3>새 집필 지침</h3>
          <label>지침 이름 <input bind:value={cardForm.title} placeholder="예: 제도의 효능과 대가를 함께 보여 준다" /></label>
          <label>이 프로젝트의 글에서 무엇을 지킬까요? <textarea bind:value={cardForm.body} placeholder="강조할 내용, 반드시 보여 줄 과정, 피할 해석을 자연스럽게 적어 주세요."></textarea></label>
          <label>찾기용 태그 <input bind:value={cardForm.tags} placeholder="제도, 의존, 대가" /></label>
          <button class="primary" disabled={!cardForm.title.trim() || !cardForm.body.trim()} on:click={createCard}>지침 추가</button>
        </div>
        <div class="direction-list">
          {#each cards as card}
            <article class="direction-card">
              {#if editingCardId === card.id}
                <div class="stack"><label>지침 이름 <input bind:value={cardDraft.title} /></label><label>지침 설명 <textarea bind:value={cardDraft.body}></textarea></label><label>태그 <input bind:value={cardDraft.tags} /></label><div class="row"><button class="primary" on:click={() => saveCard(card)}>저장</button><button class="ghost" on:click={() => editingCardId = ''}>취소</button></div></div>
              {:else}
                <div class="row spread"><div><div class="tag-row">{#each card.tags || [] as tag}<span class="badge">{tag}</span>{/each}</div><h3>{card.title}</h3></div><span class="badge canon">선택 가능</span></div>
                <p>{card.body}</p>
                {#if Object.keys(card.parsed_rules || {}).length}
                  <div class="rule-grid">
                    <div><strong>반드시 포함</strong><span>{(card.parsed_rules.must_include || []).join(' · ') || '없음'}</span></div>
                    <div><strong>피할 전개</strong><span>{(card.parsed_rules.avoid || []).join(' · ') || '없음'}</span></div>
                    <div><strong>선호 결말</strong><span>{card.parsed_rules.ending_preference || '지정 안 함'}</span></div>
                  </div>
                {/if}
                <div class="row wrap"><button class="secondary" on:click={() => editCard(card)}>내용 수정</button><button class="ghost" on:click={() => suggestCard(card)}>AI로 세부 규칙 정리</button><button class="danger-button" on:click={() => deleteCard(card)}>삭제</button></div>
              {/if}
            </article>
          {/each}
          {#if !cards.length}<div class="empty-state direction-empty"><strong>아직 집필 지침이 없습니다.</strong><p>위에서 이 프로젝트의 글이 반복해서 지킬 원칙을 추가하세요.</p></div>{/if}
        </div>
        {#if cardSuggestion}
          <section class="card suggestion-review stack">
            <div><p class="eyebrow">AI 정리 결과</p><h3>원문은 그대로 두고, 생성에 쓸 세부 규칙만 추가합니다.</h3></div>
            <div class="rule-grid">
              <div><strong>목표</strong><span>{(cardSuggestion.suggestion.goals || []).join(' · ')}</span></div>
              <div><strong>전개 순서</strong><span>{(cardSuggestion.suggestion.sequence || []).join(' → ')}</span></div>
              <div><strong>반드시 포함</strong><span>{(cardSuggestion.suggestion.must_include || []).join(' · ')}</span></div>
              <div><strong>피할 전개</strong><span>{(cardSuggestion.suggestion.avoid || []).join(' · ')}</span></div>
              <div><strong>선호 결말</strong><span>{cardSuggestion.suggestion.ending_preference}</span></div>
            </div>
            <div class="row"><button class="primary" on:click={applyCardSuggestion}>세부 규칙 저장</button><button class="ghost" on:click={() => cardSuggestion = null}>취소</button></div>
          </section>
        {/if}
      </section>
    {:else}
      <section class="category-manager">
        <div class="category-intro">
          <p class="eyebrow">프로젝트 자료 종류</p>
          <h2>이 세계에 맞는 분류를<br />직접 정합니다.</h2>
          <p>시작용 종류도 이 프로젝트의 소유입니다. 이름과 설명을 바꾸거나 새 종류를 더할 수 있습니다. 종류를 바꿔도 자료 본문은 그대로 유지됩니다.</p>
        </div>
        <div class="stack">
          <div class="card stack category-create">
            <h3>새 자료 종류</h3>
            <label>이름 <input aria-label="새 자료 종류 이름" bind:value={categoryForm.name} placeholder="예: 세력, 마법 체계, 생물종" /></label>
            <label>설명 <textarea bind:value={categoryForm.description} placeholder="어떤 자료를 이 종류로 묶을지 짧게 적어 주세요."></textarea></label>
            <p class="small">새 종류는 처음에 글 만들기의 모든 선택 단계에 추천됩니다. 만든 뒤 아래에서 추천 위치를 조정할 수 있습니다.</p>
            <button class="primary" disabled={!categoryForm.name.trim()} on:click={createCategory}>자료 종류 만들기</button>
          </div>
          <div class="category-list">
            {#each categories as category}
              <article class="card stack category-card">
                <div class="row spread"><strong>{categoryUsedCount(category)}개 자료 사용 중</strong><button class="ghost danger" on:click={() => deleteCategory(category)}>삭제</button></div>
                <label>이름 <input bind:value={category.name} /></label>
                <label>설명 <textarea bind:value={category.description} placeholder="이 종류에 들어갈 자료의 기준"></textarea></label>
                <fieldset>
                  <legend>글 만들기에서 먼저 추천할 위치</legend>
                  <div class="category-slot-list">
                    {#each categorySlotOptions as slot}
                      <label><input type="checkbox" checked={categorySlots(category).includes(slot.key)} on:change={() => toggleCategorySlot(category, slot.key)} /> {slot.label}</label>
                    {/each}
                  </div>
                </fieldset>
                <button class="secondary" disabled={!category.name.trim()} on:click={() => saveCategory(category)}>이 종류 저장</button>
              </article>
            {/each}
          </div>
        </div>
      </section>
    {/if}
  {/if}
</div>
