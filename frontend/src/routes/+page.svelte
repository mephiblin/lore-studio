<script>
  import { onMount } from 'svelte';
  import { api } from '$lib/api';

  let projects = [];
  let profiles = [];
  let loading = true;
  let error = '';

  onMount(async () => {
    try {
      [projects, { profiles }] = await Promise.all([api.get('/projects'), api.get('/models/status')]);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  });
</script>

<div class="page stack" style="gap:18px">
  <section class="hero-workbench">
    <div class="hero-copy">
      <p class="eyebrow" style="color:#e3b867">DGX SPARK · LOCAL FIRST</p>
      <h1>설정은 쌓고,<br />정사는 직접 결정합니다.</h1>
      <p>자료, 방향, 작문 방식을 분리해 조합하고 실제 로컬 모델로 근거가 남는 로어 문서를 만듭니다.</p>
    </div>
    <div class="hero-gauge" aria-label="로컬 모델 상태">
      <p class="eyebrow" style="color:#9fb4ae">MODEL ROUTING</p>
      {#if loading}<span class="small">프로필 확인 중…</span>{/if}
      {#each profiles as profile}
        <div class="gauge-row">
          <strong>{profile.role}</strong>
          <div class="gauge-track"><span style={`width:${profile.available ? 100 : 8}%`}></span></div>
          <span>{profile.available ? 'READY' : 'OFFLINE'}</span>
        </div>
      {/each}
      {#if error}<p class="notice-error">{error}</p>{/if}
    </div>
  </section>

  <div class="grid-2">
    <section class="card stack">
      <p class="eyebrow">01 · ARCHIVE</p>
      <h2 style="margin:0">컨셉 아카이브</h2>
      <p class="small">자유 본문을 중심으로 세계관 자료, 외부 근거, 작문 참고를 서로 다른 권위로 보관합니다.</p>
      <div class="row spread"><span class="badge">프로젝트 {projects.length}</span><a class="secondary" href="/editor">자료 정리하기 →</a></div>
    </section>
    <section class="card stack">
      <p class="eyebrow">02 · COMPOSE</p>
      <h2 style="margin:0">플레이북 조립</h2>
      <p class="small">소재·방향성 카드·집필 레시피·출력 프로필을 조합하고 구성안을 검토한 뒤 원고를 씁니다.</p>
      <div class="row spread"><span class="badge candidate">승인 경계 유지</span><a class="primary" href="/playbook">새 로어 만들기 →</a></div>
    </section>
  </div>

  <section class="card">
    <div class="page-header" style="margin:0 0 16px">
      <div><p class="eyebrow">AUTHORITY CURRENT</p><h2 style="margin:0">세계관으로 들어가는 흐름</h2></div>
      <span class="small">모델 출력은 정사가 아닙니다.</span>
    </div>
    <div class="evidence-flow">
      <div class="evidence-item"><strong>CANDIDATE</strong><small>원고에서 발견된 새 설정. 생성 근거와 충돌 가능성을 함께 보관합니다.</small></div>
      <div class="evidence-item"><strong>DRAFT_SETTING</strong><small>사용자가 초안 설정으로 승인했습니다. 다음 작업에서 선택적으로 사용할 수 있습니다.</small></div>
      <div class="evidence-item"><strong>PROJECT_CANON</strong><small>사용자가 프로젝트 정사로 다시 승인했습니다. 잠긴 사실과 함께 우선 근거가 됩니다.</small></div>
    </div>
  </section>
</div>
