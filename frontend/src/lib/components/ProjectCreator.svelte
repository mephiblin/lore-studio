<script>
  import { api } from '$lib/api';
  import { rememberProject } from '$lib/project';

  export let onCreated = () => {};
  export let buttonLabel = '새 프로젝트';

  let open = false;
  let name = '';
  let description = '';
  let busy = false;
  let error = '';

  async function createProject() {
    if (!name.trim() || busy) return;
    busy = true;
    error = '';
    const token = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
    try {
      const project = await api.post('/projects', {
        name: name.trim(),
        slug: `world-${token}`,
        description: description.trim(),
        universe_namespace: `world-${token}`,
        settings_json: { canon_policy: 'user_approved_only' }
      });
      rememberProject(project.id);
      name = '';
      description = '';
      open = false;
      await onCreated(project);
    } catch (e) {
      error = e.message;
    } finally {
      busy = false;
    }
  }
</script>

<button class="secondary" on:click={() => open = !open} aria-expanded={open}>{open ? '닫기' : `+ ${buttonLabel}`}</button>
{#if open}
  <section class="project-create-panel stack" aria-label="새 프로젝트 만들기">
    <div>
      <strong>새 프로젝트 만들기</strong>
      <p class="small">하나의 세계관과 그 자료·원고를 독립적으로 보관합니다.</p>
    </div>
    <label>프로젝트 이름 <input bind:value={name} placeholder="예: 수면 도시 연대기" /></label>
    <label>한 줄 설명 <textarea bind:value={description} placeholder="이 세계의 핵심 전제를 적어 두세요."></textarea></label>
    {#if error}<p class="notice-error">{error}</p>{/if}
    <button class="primary" disabled={!name.trim() || busy} on:click={createProject}>{busy ? '만드는 중…' : '프로젝트 만들기'}</button>
  </section>
{/if}
