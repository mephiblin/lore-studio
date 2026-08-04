<script>
  import { page } from '$app/stores';
  import '../styles.css';

  const navigation = [
    { href: '/', label: '작업대', mark: '⌂' },
    { href: '/editor', label: '컨셉 아카이브', mark: '◇' },
    { href: '/playbook', label: '플레이북', mark: '▶' },
    { href: '/documents', label: '로어 문서', mark: '▤' }
  ];
</script>

<svelte:head>
  <title>Lore Studio</title>
  <meta name="description" content="DGX Spark를 위한 로컬 우선 세계관 집필 작업실" />
</svelte:head>

<div class="app-shell">
  <aside class="app-nav" aria-label="주요 메뉴">
    <a class="brand" href="/" aria-label="Lore Studio 작업대">
      <span class="brand-seal">LS</span>
      <span><strong>Lore Studio</strong><small>LOCAL WRITING ROOM</small></span>
    </a>

    <nav class="nav-list">
      {#each navigation as item}
        <a href={item.href} class:active={$page.url.pathname === item.href}>
          <span aria-hidden="true">{item.mark}</span>{item.label}
        </a>
      {/each}
    </nav>

    <div class="local-note">
      <span class="status-dot"></span>
      <div><strong>로컬 우선</strong><small>자료와 모델 키는 브라우저에 노출되지 않습니다.</small></div>
    </div>
  </aside>
  <main class="app-main"><slot /></main>
</div>
