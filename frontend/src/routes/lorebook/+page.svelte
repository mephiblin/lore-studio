<script>
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import ProjectCreator from '$lib/components/ProjectCreator.svelte';
  import { api, API_BASE } from '$lib/api';
  import { initialProjectId, rememberProject } from '$lib/project';

  const LOREBOOK_THEME_KEY = 'lore-studio:lorebook-theme';
  const lorebookThemes = [
    { id: 'normal', name: '노말', number: '1' },
    { id: 'fantasia', name: '판타지아', number: '2' },
    { id: 'mechanical', name: '메카니컬', number: '3' },
    { id: 'urban', name: '어반 판타지', number: '4' }
  ];
  let projects = [], entries = [];
  let projectId = '', selected = null, sourceState = null;
  let busy = '', error = '', message = '';
  let editing = false;
  let lorebookTheme = 'normal';
  $: readingBlocks = readerBlocks(selected?.body_markdown || '');
  $: activeThemeName = lorebookThemes.find((theme) => theme.id === lorebookTheme)?.name || '노말';
  $: requestedEntryId = $page.url.searchParams.get('entry') || '';
  $: mobileReaderOpen = !!selected && requestedEntryId === selected.id;
  $: selectedEntryNumber = Math.max(0, entries.findIndex((entry) => entry.id === selected?.id)) + 1;

  onMount(() => {
    const storedTheme = localStorage.getItem(LOREBOOK_THEME_KEY);
    if (lorebookThemes.some((theme) => theme.id === storedTheme)) lorebookTheme = storedTheme;
    syncWorkspaceTheme();
    loadInitial();
    return () => document.documentElement.removeAttribute('data-lorebook-theme');
  });

  function selectTheme(themeId) {
    if (!lorebookThemes.some((theme) => theme.id === themeId)) return;
    lorebookTheme = themeId;
    localStorage.setItem(LOREBOOK_THEME_KEY, themeId);
    syncWorkspaceTheme();
  }

  function syncWorkspaceTheme() {
    document.documentElement.dataset.lorebookTheme = lorebookTheme;
  }

  async function loadInitial() {
    try {
      projects = await api.get('/projects');
      if (projects.length) {
        projectId = initialProjectId(projects);
        await loadEntries();
      }
    } catch (e) { error = e.message; }
  }

  async function loadEntries() {
    if (!projectId) return;
    rememberProject(projectId); error = '';
    try {
      entries = await api.get(`/lorebook?project_id=${projectId}`);
      const requestedId = $page.url.searchParams.get('entry');
      await selectEntry(entries.find((entry) => entry.id === requestedId) || entries[0] || null);
    } catch (e) { error = e.message; }
  }

  async function projectCreated(project) {
    projects = [project, ...projects]; projectId = project.id; await loadEntries();
  }

  async function selectEntry(entry) {
    selected = entry ? { ...entry } : null; sourceState = null; message = ''; editing = false;
    if (!selected?.source_document_id) return;
    try { sourceState = await api.get(`/documents/${selected.source_document_id}/finalization`); }
    catch { sourceState = null; }
  }

  async function openMobileEntry(entry) {
    await selectEntry(entry);
    await goto(`/lorebook?entry=${entry.id}`, { keepFocus: true, noScroll: true });
    window.scrollTo({ top: 0, behavior: 'auto' });
  }

  async function showMobileIndex() {
    editing = false;
    await goto('/lorebook', { keepFocus: true, noScroll: true });
    window.scrollTo({ top: 0, behavior: 'auto' });
  }

  async function saveEntry() {
    if (!selected?.body_markdown?.trim()) return;
    busy = '로어북 글 저장 중'; error = ''; message = '';
    try {
      selected = await api.patch(`/lorebook/${selected.id}`, {
        title: selected.title,
        body_markdown: selected.body_markdown,
        status: selected.status
      });
      entries = entries.map((item) => item.id === selected.id ? selected : item);
      message = '로어북 글을 저장했습니다.';
      editing = false;
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  function settingLabel(value) {
    return ({
      omniscient: '전지적 설명자', first_observer: '1인칭 관찰자', third_limited: '3인칭 제한',
      present: '현재형 중심', past: '과거형 중심', short: '짧게', normal: '보통', long: '길게', very_long: '매우 길게'
    })[value] || value || '지정 안 함';
  }

  function statusLabel(value) {
    return ({ approved: '완료', review: '검토 중', archived: '보관' })[value] || value;
  }

  function readerBlocks(markdown) {
    return markdown.split(/\n\s*\n/).map((raw) => raw.trim()).filter(Boolean).map((raw) => {
      if (raw.startsWith('### ')) return { type: 'h4', text: raw.slice(4) };
      if (raw.startsWith('## ')) return { type: 'h3', text: raw.slice(3) };
      if (raw.startsWith('# ')) return { type: 'h2', text: raw.slice(2) };
      return { type: 'p', text: raw };
    });
  }

  function cancelEdit() {
    const persisted = entries.find((entry) => entry.id === selected?.id);
    if (persisted) selected = { ...persisted };
    editing = false;
    message = '';
  }

  async function deleteEntry() {
    if (!selected || busy) return;
    if (!confirm(`'${selected.title}' 로어북 글을 삭제할까요?\n\n출처 초안은 보존되지만, 이 완성본과 수정 기록은 되돌릴 수 없습니다.`)) return;
    const deletedId = selected.id;
    busy = '로어북 글 삭제 중'; error = ''; message = '';
    try {
      await api.delete(`/lorebook/${deletedId}`);
      entries = entries.filter((entry) => entry.id !== deletedId);
      await selectEntry(entries[0] || null);
      if (requestedEntryId === deletedId) await goto('/lorebook', { replaceState: true, keepFocus: true, noScroll: true });
      message = '로어북 글을 삭제했습니다.';
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }
</script>

<div class="page lorebook-page workspace-page" class:mobile-reader-view={mobileReaderOpen} data-lorebook-theme={lorebookTheme}>
  <div class="page-tools lorebook-commandbar">
    <div class="lorebook-theme-toolbar">
      <div class="lorebook-theme-heading"><span>열람 테마</span><strong>{activeThemeName}</strong></div>
      <div class="lorebook-theme-options" role="group" aria-label="로어북 열람 테마">
        {#each lorebookThemes as theme}
          <button
            type="button"
            class="lorebook-theme-button theme-{theme.id}"
            class:active={lorebookTheme === theme.id}
            aria-label={`로어북 테마: ${theme.name}`}
            aria-pressed={lorebookTheme === theme.id}
            title={theme.name}
            on:click={() => selectTheme(theme.id)}
          ><span aria-hidden="true">{theme.number}</span></button>
        {/each}
      </div>
    </div>
    <div class="project-tools"><label>현재 프로젝트<select bind:value={projectId} on:change={loadEntries}>{#each projects as project}<option value={project.id}>{project.name}</option>{/each}</select></label><ProjectCreator onCreated={projectCreated} /></div>
  </div>

  {#if error}<p class="notice-error">{error}</p>{/if}
  {#if busy}<div class="notice" role="status">{busy}…</div>{/if}

  <section class="lorebook-mobile-index" aria-label="로어북 목차">
    <header class="lorebook-index-heading">
      <div><h1>책장</h1><p>제목을 고르면 읽기 화면으로 이동합니다.</p></div>
      <span class="lorebook-index-count"><b>{entries.length}</b><small>ARTICLES</small></span>
    </header>
    {#if entries.length}
      <nav class="lorebook-mobile-toc" aria-label="로어북 글 목록">
        {#each entries as entry, index}
          <a href={`/lorebook?entry=${entry.id}`} on:click|preventDefault={() => openMobileEntry(entry)}>
            <span class="lorebook-toc-number">{String(index + 1).padStart(2, '0')}</span>
            <span class="lorebook-toc-copy"><strong>{entry.title}</strong><small>{entry.body_markdown.length.toLocaleString()}자 · {new Date(entry.published_at || entry.updated_at).toLocaleDateString('ko-KR')}</small></span>
            <span class="lorebook-toc-arrow" aria-hidden="true">→</span>
          </a>
        {/each}
      </nav>
    {:else}
      <section class="empty-state lorebook-mobile-empty"><strong>아직 로어북에 완성된 글이 없습니다.</strong><p>원고 작업에서 초안을 다듬어 로어북에 저장하세요.</p><a class="primary" href="/documents">원고 작업으로 이동</a></section>
    {/if}
  </section>

  <div class="lorebook-layout" class:mobile-reader-open={mobileReaderOpen}>
    <aside class="card stack lorebook-shelf">
      <div class="row spread"><h3 class="lorebook-shelf-title">책장</h3><span class="badge">{entries.length}</span></div>
      <div class="list lorebook-list">
        {#each entries as entry}
          <button class:active={selected?.id === entry.id} on:click={() => selectEntry(entry)}><strong>{entry.title}</strong><small>{entry.body_markdown.length.toLocaleString()}자 · {new Date(entry.published_at || entry.updated_at).toLocaleDateString('ko-KR')}</small></button>
        {/each}
      </div>
      {#if !entries.length}<div class="empty-mini">원고 작업에서 완성본을 만들면 이 책장에 저장됩니다.</div>{/if}
    </aside>

    <main class="stack lorebook-reader">
      {#if selected}
        <nav class="lorebook-mobile-readerbar" aria-label="로어북 읽기 이동">
          <a href="/lorebook" on:click|preventDefault={showMobileIndex}>← 목차로</a>
          <span>{String(selectedEntryNumber).padStart(2, '0')} / {String(entries.length).padStart(2, '0')}</span>
        </nav>
        {#if sourceState?.status === 'stale'}<div class="notice-error"><strong>연결된 초안이 바뀌었습니다.</strong> 이 글은 이전 초안을 바탕으로 만든 버전입니다. <a href={`/documents?document=${selected.source_document_id}`}>원고 작업에서 다시 만들기 →</a></div>{/if}
        <article class="card lorebook-sheet" class:editing>
          <header class="lorebook-sheet-heading">
            <div class="lorebook-title-block">
              {#if editing}<input aria-label="로어북 글 제목" bind:value={selected.title} />{:else}<h2>{selected.title}</h2>{/if}
              <span>{statusLabel(selected.status)} · {selected.body_markdown.length.toLocaleString()}자 · {new Date(selected.published_at || selected.updated_at).toLocaleString('ko-KR')}</span>
            </div>
            <div class="lorebook-heading-actions"><span class="lorebook-mark">LORE<br />BOOK</span>{#if !editing}<button class="secondary lorebook-edit-button" on:click={() => editing = true}>글 편집</button>{/if}</div>
          </header>
          {#if editing}
            <textarea class="lorebook-body lorebook-body-editor" aria-label="로어북 글 내용" bind:value={selected.body_markdown}></textarea>
          {:else}
            <div class="lorebook-body lorebook-body-reader" aria-label="로어북 글 내용">
              {#each readingBlocks as block}
                {#if block.type === 'h2'}<h2>{block.text}</h2>
                {:else if block.type === 'h3'}<h3>{block.text}</h3>
                {:else if block.type === 'h4'}<h4>{block.text}</h4>
                {:else}<p>{block.text}</p>{/if}
              {/each}
            </div>
          {/if}
          <footer class="lorebook-actions">
            {#if editing}<label>보관 상태<select bind:value={selected.status}><option value="approved">완료</option><option value="review">검토 중</option><option value="archived">보관</option></select></label>{:else}<span class="lorebook-read-note">읽기 모드 · 편집할 때만 입력란이 열립니다.</span>{/if}
            <div>
              {#if !editing}<button class="danger-button" on:click={deleteEntry}>글 삭제</button><a class="ghost" href={`${API_BASE}/lorebook/${selected.id}/export?format=markdown`} target="_blank">Markdown</a><a class="ghost" href={`${API_BASE}/lorebook/${selected.id}/export?format=html`} target="_blank">HTML</a><a class="ghost" href={`${API_BASE}/lorebook/${selected.id}/export?format=json`} target="_blank">JSON</a>
              {:else}<button class="ghost" on:click={cancelEdit}>취소</button><button class="primary" on:click={saveEntry}>변경 저장</button>{/if}
            </div>
          </footer>
        </article>
        <section class="card lorebook-source-link" aria-label="로어북 글 출처">
          <div class="row spread lorebook-source-row"><span>출처 초안은 로어북 글과 별도로 보존됩니다.</span><a class="secondary" href={`/documents?document=${selected.source_document_id}`}>출처 초안 열기</a></div>
          <details class="lorebook-provenance"><summary>이 글을 만든 설정</summary><div class="details-body"><div><small>결과물 형태</small><strong>{selected.generation_inputs_json?.output_profile?.name || '기록 없음'}</strong></div><div><small>전개 방식</small><strong>{selected.generation_inputs_json?.writing_recipe?.name || '기록 없음'}</strong></div><div><small>시점·시제·분량</small><strong>{settingLabel(selected.generation_inputs_json?.generation_settings?.viewpoint)} · {settingLabel(selected.generation_inputs_json?.generation_settings?.tense)} · {settingLabel(selected.generation_inputs_json?.generation_settings?.length)}</strong></div><div><small>추가 지시</small><p>{selected.generation_inputs_json?.user_direction || '추가 지시 없음'}</p></div></div></details>
        </section>
        {#if message}<p class="success">{message}</p>{/if}
      {:else}
        <section class="empty-state lorebook-empty"><strong>아직 로어북에 완성된 글이 없습니다.</strong><p>원고 작업에서 초안을 편집하고 완성 다듬기 방향을 정한 뒤 로어북에 저장하세요.</p><a class="primary" href="/documents">원고 작업으로 이동</a></section>
      {/if}
    </main>
  </div>
</div>
