<script>
  import '../styles.css';
</script>

<svelte:head>
  <title>Lore Studio</title>
  <meta name="description" content="Local-first lore writing studio" />
</svelte:head>

<div class="app-shell">
  <header class="topbar">
    <a class="brand" href="/">Lore Studio</a>
    <nav>
      <a href="/editor">에디터</a>
      <a href="/playbook">플레이북</a>
      <a href="/documents">로어 문서</a>
    </nav>
  </header>
  <main>
    <slot />
  </main>
</div>
