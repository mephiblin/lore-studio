<script>
  import { onMount } from 'svelte';
  import { api } from '$lib/api';

  let projects = [];
  let projectId = '';
  let documents = [];
  let selected = null;
  let error = '';
  let message = '';

  onMount(loadInitial);

  async function loadInitial() {
    try {
      projects = await api.get('/projects');
      if (projects.length) {
        projectId = projects[0].id;
        await loadDocuments();
      }
    } catch (e) {
      error = e.message;
    }
  }

  async function loadDocuments() {
    if (!projectId) return;
    try {
      documents = await api.get(`/documents?project_id=${projectId}`);
      selected = documents[0] || null;
    } catch (e) {
      error = e.message;
    }
  }

  async function saveDocument() {
    if (!selected) return;
    error = '';
    message = '';
    try {
      selected = await api.patch(`/documents/${selected.id}`, {
        title: selected.title,
        body_markdown: selected.body_markdown,
        status: selected.status
      });
      documents = documents.map((item) => item.id === selected.id ? selected : item);
      message = '문서를 저장했습니다.';
    } catch (e) {
      error = e.message;
    }
  }
</script>

<div class="page">
  <div class="page-header">
    <div>
      <h1>로어 문서</h1>
      <p>생성 결과를 채팅 메시지가 아닌 편집 가능한 문서로 관리합니다.</p>
    </div>
    <label style="min-width:260px">
      프로젝트
      <select bind:value={projectId} on:change={loadDocuments}>
        {#each projects as project}<option value={project.id}>{project.name}</option>{/each}
      </select>
    </label>
  </div>

  {#if error}<p class="error">{error}</p>{/if}

  <div class="grid-3" style="grid-template-columns:260px minmax(0,1fr) 240px">
    <aside class="card stack">
      <div class="row" style="justify-content:space-between">
        <h3>문서</h3><span class="badge">{documents.length}</span>
      </div>
      <div class="list">
        {#each documents as document}
          <button class:active={selected?.id === document.id} on:click={() => selected = { ...document }}>
            <strong>{document.title}</strong>
            <div class="small">{document.status}</div>
          </button>
        {/each}
      </div>
    </aside>

    <section class="card stack">
      {#if selected}
        <input bind:value={selected.title} style="font-size:22px;font-weight:700" />
        <textarea bind:value={selected.body_markdown} style="min-height:640px;line-height:1.7"></textarea>
      {:else}
        <p>플레이북에서 생성한 문서가 여기에 나타납니다.</p>
      {/if}
    </section>

    <aside class="card stack">
      {#if selected}
        <label>
          상태
          <select bind:value={selected.status}>
            <option value="draft">초안</option>
            <option value="review">검토</option>
            <option value="approved">승인</option>
            <option value="archived">보관</option>
          </select>
        </label>
        <div class="small">생성 실행 ID와 문단별 근거·Move는 다음 구현 단계에서 이 패널에 표시됩니다.</div>
        <button class="primary" on:click={saveDocument}>저장</button>
        {#if message}<p class="success">{message}</p>{/if}
      {/if}
    </aside>
  </div>
</div>
