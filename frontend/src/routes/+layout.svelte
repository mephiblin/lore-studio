<script>
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import '../styles.css';

  let navCollapsed = false;

  const navigation = [
    { href: '/', label: '프로젝트', mark: '01' },
    { href: '/editor', label: '세계관 자료', mark: '02' },
    { href: '/playbook', label: '글 만들기', mark: '03' },
    { href: '/documents', label: '원고 작업', mark: '04' },
    { href: '/lorebook', label: '로어북', mark: '05' }
  ];

  onMount(() => {
    navCollapsed = window.localStorage.getItem('lore-studio:nav-collapsed') === 'true';
  });

  function toggleNavigation() {
    navCollapsed = !navCollapsed;
    window.localStorage.setItem('lore-studio:nav-collapsed', String(navCollapsed));
  }
</script>

<svelte:head>
  <title>Lore Studio</title>
  <meta name="description" content="DGX Spark를 위한 세계관 집필 작업실" />
</svelte:head>

<div class="app-shell" class:nav-collapsed={navCollapsed}>
  <aside class="app-nav" aria-label="주요 메뉴">
    <a class="brand" href="/" aria-label="Lore Studio 프로젝트">
      <span class="brand-seal">LS</span>
      <span class="brand-copy"><strong>Lore Studio</strong><small>LOCAL WRITING ROOM</small></span>
    </a>

    <button
      class="nav-toggle"
      type="button"
      aria-label={navCollapsed ? '주요 메뉴 펼치기' : '주요 메뉴 접기'}
      aria-expanded={!navCollapsed}
      aria-controls="primary-navigation"
      on:click={toggleNavigation}
    >
      <span aria-hidden="true">{navCollapsed ? '›' : '‹'}</span>
    </button>

    <nav class="nav-list" id="primary-navigation">
      {#each navigation as item}
        <a href={item.href} class:active={$page.url.pathname === item.href} aria-current={$page.url.pathname === item.href ? 'page' : undefined} title={navCollapsed ? item.label : undefined}>
          <span class="nav-mark" aria-hidden="true">{item.mark}</span><span class="nav-label">{item.label}</span>
        </a>
      {/each}
    </nav>

    <a
      class="model-settings-link"
      class:active={$page.url.pathname === '/settings'}
      aria-current={$page.url.pathname === '/settings' ? 'page' : undefined}
      href="/settings"
      aria-label="모델 연결 설정"
      title="모델 연결"
    >
      <span aria-hidden="true">⚙</span><span class="nav-label">모델 연결</span>
    </a>

  </aside>
  <main class="app-main" class:workspace-main={$page.url.pathname !== '/'}><slot /></main>
</div>
