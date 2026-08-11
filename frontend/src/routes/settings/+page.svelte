<script>
  import { onMount } from 'svelte';
  import { api } from '$lib/api';

  const roleLabels = {
    writer: { name: 'Writer', description: '글의 흐름·초안·완성 다듬기' },
    utility: { name: 'Utility', description: '구조화 분석·감사·설정 후보 추출' },
    vision: { name: 'Vision', description: '이미지 캡션·시각 자료 분석' },
    embedding: { name: 'Embedding', description: '세계관 자료 검색 벡터 생성' }
  };

  let profiles = [];
  let loading = true;
  let pageError = '';
  let state = {};

  function editable(profile) {
    return { ...profile, api_key: '', clear_api_key: false };
  }

  function payload(profile) {
    return {
      base_url: profile.base_url,
      model: profile.model,
      api_key: profile.api_key || null,
      clear_api_key: Boolean(profile.clear_api_key),
      timeout_seconds: Number(profile.timeout_seconds),
      context_budget: Number(profile.context_budget),
      disable_thinking: Boolean(profile.disable_thinking)
    };
  }

  function setState(role, values) {
    state = { ...state, [role]: { ...(state[role] || {}), ...values } };
  }

  async function loadProfiles() {
    loading = true;
    pageError = '';
    try {
      profiles = (await api.get('/model-connections')).map(editable);
    } catch (error) {
      pageError = error.message;
    } finally {
      loading = false;
    }
  }

  function applyLocalQwen() {
    profiles = profiles.map((profile) => profile.role === 'embedding' ? profile : {
      ...profile,
      base_url: 'http://host.docker.internal:18091/v1',
      model: 'qwen36-heretic-mtp',
      api_key: 'EMPTY',
      clear_api_key: false,
      disable_thinking: true
    });
    for (const role of ['writer', 'utility', 'vision']) {
      setState(role, { kind: 'notice', message: '로컬 Qwen 값을 채웠습니다. 연결 시험 후 저장하세요.' });
    }
  }

  async function testConnection(profile) {
    setState(profile.role, { busy: true, kind: '', message: '' });
    try {
      const result = await api.post('/model-connections/test', { role: profile.role, ...payload(profile) });
      if (!result.available) throw new Error(result.error?.message || '모델 연결을 확인하지 못했습니다.');
      setState(profile.role, {
        busy: false,
        kind: 'success',
        message: `연결 성공 · ${result.model} · 모델 ${result.models.length}개 확인`
      });
    } catch (error) {
      setState(profile.role, { busy: false, kind: 'error', message: error.message });
    }
  }

  async function saveConnection(profile) {
    setState(profile.role, { busy: true, kind: '', message: '' });
    try {
      const saved = await api.patch(`/model-connections/${profile.role}`, payload(profile));
      profiles = profiles.map((item) => item.role === profile.role ? editable(saved) : item);
      setState(profile.role, { busy: false, kind: 'success', message: '연결을 시험하고 서버에 저장했습니다.' });
    } catch (error) {
      setState(profile.role, { busy: false, kind: 'error', message: error.message });
    }
  }

  async function resetConnection(profile) {
    if (!confirm(`${roleLabels[profile.role].name} 연결을 .env 기본값으로 되돌릴까요?`)) return;
    setState(profile.role, { busy: true, kind: '', message: '' });
    try {
      const reset = await api.delete(`/model-connections/${profile.role}`);
      profiles = profiles.map((item) => item.role === profile.role ? editable(reset) : item);
      setState(profile.role, { busy: false, kind: 'success', message: '.env 기본값으로 되돌렸습니다.' });
    } catch (error) {
      setState(profile.role, { busy: false, kind: 'error', message: error.message });
    }
  }

  onMount(loadProfiles);
</script>

<svelte:head><title>모델 연결 · Lore Studio</title></svelte:head>

<section class="page model-settings-page">
  <header class="model-settings-header">
    <div>
      <p class="eyebrow">LOCAL MODEL GATEWAY</p>
      <h1>모델 연결</h1>
      <p>작업 역할별 OpenAI 호환 API를 연결합니다. 빈 API 키는 기존 값을 유지하며 저장된 키는 브라우저로 다시 보내지 않습니다.</p>
    </div>
    <button class="secondary" type="button" on:click={applyLocalQwen} disabled={loading}>이 PC의 Qwen 값 채우기</button>
  </header>

  {#if loading}
    <div class="empty-state" aria-live="polite"><strong>모델 연결을 불러오는 중</strong></div>
  {:else if pageError}
    <div class="empty-state"><strong>설정을 불러오지 못했습니다.</strong><p class="error">{pageError}</p><button class="secondary" type="button" on:click={loadProfiles}>다시 시도</button></div>
  {:else}
    <div class="model-profile-grid">
      {#each profiles as profile (profile.role)}
        <article class="card model-profile-card">
          <header>
            <div><p class="eyebrow">{profile.role}</p><h2>{roleLabels[profile.role].name}</h2><p>{roleLabels[profile.role].description}</p></div>
            <span class="badge" class:canon={profile.source === 'database'}>{profile.source === 'database' ? '앱 저장값' : '.env 기본값'}</span>
          </header>

          <div class="model-profile-fields">
            <label for={`${profile.role}-base-url`}>Base URL<input id={`${profile.role}-base-url`} bind:value={profile.base_url} autocomplete="url" spellcheck="false" /></label>
            <label for={`${profile.role}-model`}>모델 alias<input id={`${profile.role}-model`} bind:value={profile.model} placeholder="비워 두면 로드된 모델 자동 선택" spellcheck="false" /></label>
            <label for={`${profile.role}-api-key`}>API 키 <span class="small">{profile.api_key_configured ? '저장됨 · 변경할 때만 입력' : '없음'}</span><input id={`${profile.role}-api-key`} type="password" bind:value={profile.api_key} placeholder={profile.api_key_configured ? '기존 키 유지' : '로컬은 EMPTY 또는 빈 값'} autocomplete="new-password" /></label>
            <div class="model-number-fields">
              <label for={`${profile.role}-timeout`}>타임아웃(초)<input id={`${profile.role}-timeout`} type="number" min="1" max="3600" bind:value={profile.timeout_seconds} /></label>
              <label for={`${profile.role}-budget`}>컨텍스트 예산<input id={`${profile.role}-budget`} type="number" min="1024" max="1000000" step="1024" bind:value={profile.context_budget} /></label>
            </div>
            <label class="model-thinking-toggle"><input type="checkbox" bind:checked={profile.disable_thinking} />Thinking 끄기 <span class="small">Qwen의 숨은 추론 토큰·지연을 줄이며 MTP 가속은 유지</span></label>
          </div>

          <div class="model-profile-actions">
            <button class="ghost" type="button" on:click={() => resetConnection(profile)} disabled={state[profile.role]?.busy || profile.source !== 'database'}>.env로 되돌리기</button>
            <button class="secondary" type="button" on:click={() => testConnection(profile)} disabled={state[profile.role]?.busy}>연결 시험</button>
            <button class="primary" type="button" on:click={() => saveConnection(profile)} disabled={state[profile.role]?.busy}>{state[profile.role]?.busy ? '확인 중…' : '시험하고 저장'}</button>
          </div>
          {#if state[profile.role]?.message}<p class={`model-profile-status ${state[profile.role].kind}`} aria-live="polite">{state[profile.role].message}</p>{/if}
        </article>
      {/each}
    </div>
  {/if}

  <aside class="notice model-settings-security">이 앱은 인증 없는 신뢰 LAN용이며 API 키는 서버 DB에 평문 저장됩니다. 외부 API 키를 저장한 상태로 인터넷에 직접 공개하지 마세요.</aside>
</section>
