<script>
  import { onMount } from 'svelte';
  import ProjectCreator from '$lib/components/ProjectCreator.svelte';
  import { api } from '$lib/api';
  import { coverFallbackLabel } from '$lib/labels';
  import { forgetProject, rememberProject } from '$lib/project';

  let projects = [];
  let loading = true;
  let error = '';
  let coverBusy = '';
  let coverError = '';

  const MAX_COVER_FILE_SIZE = 12 * 1024 * 1024;

  onMount(load);

  async function load() {
    try {
      projects = await api.get('/projects');
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function projectCreated(project) {
    projects = [project, ...projects];
  }

  function projectCover(project) {
    return project.settings_json?.cover_image || '';
  }

  function projectInitial(project) {
    return coverFallbackLabel(project.name);
  }

  function loadImage(file) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      const url = URL.createObjectURL(file);
      image.onload = () => {
        URL.revokeObjectURL(url);
        resolve(image);
      };
      image.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error('이미지를 읽을 수 없습니다.'));
      };
      image.src = url;
    });
  }

  async function normalizeCover(file) {
    if (!file?.type.startsWith('image/')) throw new Error('JPEG, PNG, WebP 이미지를 선택해 주세요.');
    if (file.size > MAX_COVER_FILE_SIZE) throw new Error('커버 원본은 12MB 이하로 선택해 주세요.');
    const image = await loadImage(file);
    const canvas = document.createElement('canvas');
    canvas.width = 1200;
    canvas.height = 675;
    const context = canvas.getContext('2d');
    if (!context) throw new Error('이미지를 처리할 수 없습니다.');

    const sourceRatio = image.naturalWidth / image.naturalHeight;
    const targetRatio = canvas.width / canvas.height;
    let sourceWidth = image.naturalWidth;
    let sourceHeight = image.naturalHeight;
    let sourceX = 0;
    let sourceY = 0;
    if (sourceRatio > targetRatio) {
      sourceWidth = image.naturalHeight * targetRatio;
      sourceX = (image.naturalWidth - sourceWidth) / 2;
    } else {
      sourceHeight = image.naturalWidth / targetRatio;
      sourceY = (image.naturalHeight - sourceHeight) / 2;
    }
    context.fillStyle = '#e8edea';
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, sourceX, sourceY, sourceWidth, sourceHeight, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.82);
  }

  async function setProjectCover(event, project) {
    const input = event.currentTarget;
    const file = input.files?.[0];
    if (!file || coverBusy) return;
    coverBusy = project.id;
    coverError = '';
    try {
      const coverImage = await normalizeCover(file);
      const updated = await api.patch(`/projects/${project.id}`, {
        settings_json: {
          ...(project.settings_json || {}),
          cover_image: coverImage,
          cover_image_name: file.name
        }
      });
      projects = projects.map((item) => item.id === updated.id ? updated : item);
    } catch (e) {
      coverError = e.message;
    } finally {
      coverBusy = '';
      input.value = '';
    }
  }

  async function removeProjectCover(project) {
    if (coverBusy) return;
    coverBusy = project.id;
    coverError = '';
    try {
      const settings = { ...(project.settings_json || {}) };
      delete settings.cover_image;
      delete settings.cover_image_name;
      const updated = await api.patch(`/projects/${project.id}`, { settings_json: settings });
      projects = projects.map((item) => item.id === updated.id ? updated : item);
    } catch (e) {
      coverError = e.message;
    } finally {
      coverBusy = '';
    }
  }

  async function deleteProject(project) {
    if (!confirm(`'${project.name}' 프로젝트를 삭제할까요?\n\n이 프로젝트의 세계관 자료, 글 만들기 기록, 원고와 로어북 글이 함께 삭제됩니다. 이 작업은 되돌릴 수 없습니다.`)) return;
    error = '';
    try {
      await api.delete(`/projects/${project.id}`);
      projects = projects.filter((item) => item.id !== project.id);
      forgetProject(project.id);
    } catch (e) {
      error = e.message;
    }
  }
</script>

<div class="page stack" style="gap:18px">
  <section class="home-briefing">
    <div class="home-thesis">
      <div>
        <p class="eyebrow">오늘의 작업</p>
        <h1>세계를 선택하고, 필요한 글을 만드세요.</h1>
      </div>
      <p>프로젝트별로 세계관 자료와 원고가 분리됩니다. 원고에서 나온 새 설정은 승인하기 전까지 세계관을 바꾸지 않습니다.</p>
    </div>
  </section>

  <section class="section-heading row spread wrap">
    <h2>어느 세계에서 작업할까요?</h2>
    <ProjectCreator onCreated={projectCreated} />
  </section>

  {#if error}<p class="notice-error" role="alert">{error}</p>{/if}

  {#if projects.length}
    {#if coverError}<p class="notice-error" role="alert">{coverError}</p>{/if}
    <div class="project-grid" aria-label="프로젝트 목록">
      {#each projects as project}
        <article class="project-card">
          <div class:has-image={!!projectCover(project)} class="project-cover">
            {#if projectCover(project)}
              <img src={projectCover(project)} alt={`${project.name} 프로젝트 커버`} />
            {:else}
              <div class="project-cover-placeholder" aria-hidden="true"><span>{projectInitial(project)}</span></div>
            {/if}
            <div class="project-cover-tools">
              <label class="project-cover-control" class:busy={coverBusy === project.id}>
                <input class="visually-hidden" aria-label={`${project.name} 커버 이미지`} type="file" accept="image/jpeg,image/png,image/webp" disabled={!!coverBusy} on:change={(event) => setProjectCover(event, project)} />
                <span>{coverBusy === project.id ? '처리 중…' : projectCover(project) ? '교체' : '+ 커버'}</span>
              </label>
              {#if projectCover(project)}<button class="project-cover-remove" aria-label={`${project.name} 커버 제거`} disabled={!!coverBusy} on:click={() => removeProjectCover(project)}>제거</button>{/if}
            </div>
          </div>
          <div class="project-card-copy">
            <a href="/editor" on:click={() => rememberProject(project.id)}><h3>{project.name}</h3></a>
            <p>{project.description || '아직 프로젝트 설명이 없습니다.'}</p>
          </div>
          <div class="project-actions">
            <a href="/editor" on:click={() => rememberProject(project.id)}>세계관 자료</a>
            <a href="/playbook" on:click={() => rememberProject(project.id)}>글 만들기 <span aria-hidden="true">→</span></a>
            <button class="project-delete" aria-label={`${project.name} 프로젝트 삭제`} on:click={() => deleteProject(project)}>삭제</button>
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

</div>
