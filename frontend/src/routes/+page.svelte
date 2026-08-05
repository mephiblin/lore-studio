<script>
  import { onMount } from 'svelte';
  import ProjectCreator from '$lib/components/ProjectCreator.svelte';
  import { api } from '$lib/api';
  import { modelRoleLabels } from '$lib/labels';
  import { rememberProject } from '$lib/project';

  let projects = [];
  let profiles = [];
  let loading = true;
  let error = '';

  onMount(load);

  async function load() {
    try {
      [projects, { profiles }] = await Promise.all([api.get('/projects'), api.get('/models/status')]);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function projectCreated(project) {
    projects = [project, ...projects];
  }
</script>

<div class="page stack" style="gap:18px">
  <section class="home-briefing">
    <div class="home-thesis">
      <p class="eyebrow">오늘의 작업</p>
      <h1>세계를 선택하고,<br />필요한 글을 만드세요.</h1>
      <p>프로젝트별로 세계관 자료와 원고가 분리됩니다. 원고에서 나온 새 설정은 승인하기 전까지 세계관을 바꾸지 않습니다.</p>
    </div>
    <div class="model-board" aria-label="로컬 모델 상태">
      <div class="row spread"><strong>로컬 모델</strong><span class="badge canon">실제 연결</span></div>
      {#if loading}<span class="small">연결 상태 확인 중…</span>{/if}
      {#each profiles as profile}
        <div class="model-row">
          <span>{modelRoleLabels[profile.role] || profile.role}</span>
          <span class:online={profile.available} class="model-state">{profile.available ? '준비됨' : '연결 필요'}</span>
        </div>
      {/each}
      {#if error}<p class="notice-error">{error}</p>{/if}
    </div>
  </section>

  <section class="section-heading row spread wrap">
    <div><p class="eyebrow">프로젝트</p><h2>어느 세계에서 작업할까요?</h2></div>
    <ProjectCreator onCreated={projectCreated} />
  </section>

  {#if projects.length}
    <div class="project-grid">
      {#each projects as project}
        <article class="project-card">
          <div>
            <span class="project-mark" aria-hidden="true"></span>
            <h3>{project.name}</h3>
            <p>{project.description || '아직 프로젝트 설명이 없습니다.'}</p>
          </div>
          <div class="project-actions">
            <a class="secondary" href="/editor" on:click={() => rememberProject(project.id)}>자료 정리</a>
            <a class="primary" href="/playbook" on:click={() => rememberProject(project.id)}>글 만들기</a>
          </div>
        </article>
      {/each}
    </div>
  {:else if !loading}
    <section class="empty-state">
      <strong>첫 프로젝트를 만들어 보세요.</strong>
      <p>이름과 한 줄 설명만 있으면 시작할 수 있습니다.</p>
    </section>
  {/if}

  <section class="flow-strip" aria-label="작업 흐름">
    <div><span>1</span><strong>세계관 자료</strong><small>인물·장소·사건을 기록합니다.</small></div>
    <div><span>2</span><strong>글 만들기</strong><small>쓸 대상과 전개 방식을 선택합니다.</small></div>
    <div><span>3</span><strong>원고 작업</strong><small>초안을 편집하고 완성 설정을 정합니다.</small></div>
    <div><span>4</span><strong>로어북</strong><small>완성된 글을 읽고 보관합니다.</small></div>
  </section>
</div>
