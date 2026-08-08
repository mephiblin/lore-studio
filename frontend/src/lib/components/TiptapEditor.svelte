<script>
  import { onDestroy, onMount } from 'svelte';
  import { Editor } from '@tiptap/core';
  import Placeholder from '@tiptap/extension-placeholder';
  import StarterKit from '@tiptap/starter-kit';
  import { LoreBlock } from '$lib/extensions/LoreBlock';

  export let value = { type: 'doc', content: [] };
  export let onChange = () => {};
  export let editable = true;

  let mount;
  let editor;
  let lastExternal = JSON.stringify(value || {});

  onMount(() => {
    editor = new Editor({
      element: mount,
      extensions: [
        StarterKit,
        LoreBlock,
        Placeholder.configure({ placeholder: '설정, 이야기 조각, 인용, 메모를 자유롭게 작성하십시오.' })
      ],
      content: value || { type: 'doc', content: [] },
      editable,
      onUpdate: ({ editor }) => {
        const json = editor.getJSON();
        lastExternal = JSON.stringify(json);
        onChange(json);
      }
    });
  });

  $: if (editor) {
    editor.setEditable(editable);
    const incoming = JSON.stringify(value || {});
    if (incoming !== lastExternal) {
      editor.commands.setContent(value || { type: 'doc', content: [] }, false);
      lastExternal = incoming;
    }
  }

  onDestroy(() => editor?.destroy());
</script>

<div class="editor-shell">
  <div class="editor-toolbar" aria-label="본문 서식">
    <button type="button" on:click={() => editor?.chain().focus().toggleBold().run()} aria-label="굵게"><strong>B</strong></button>
    <button type="button" on:click={() => editor?.chain().focus().toggleItalic().run()} aria-label="기울임"><em>I</em></button>
    <button type="button" on:click={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}>제목</button>
    <button type="button" on:click={() => editor?.chain().focus().toggleBulletList().run()}>목록</button>
    <button type="button" on:click={() => editor?.chain().focus().toggleBlockquote().run()}>인용</button>
  </div>
  <div bind:this={mount} class="editor-content"></div>
</div>

<style>
  .editor-shell {
    min-height: 460px;
    overflow: hidden;
    border: 1px solid var(--line);
    border-radius: 7px;
    background: var(--paper);
    box-shadow: 0 10px 30px rgba(20, 43, 53, .06);
  }
  .editor-toolbar { display:flex; gap:4px; padding:8px 10px; border-bottom:1px solid var(--line); background:var(--paper-deep); }
  .editor-toolbar button { min-width:34px; min-height:32px; border:1px solid transparent; background:transparent; border-radius:3px; padding:5px 8px; color:var(--muted-text); font-size:12px; }
  .editor-toolbar button:hover { background:#fff; border-color:var(--line); color:var(--ink); }
  .editor-content :global(.ProseMirror) {
    min-height: 430px;
    padding: clamp(24px, 4vw, 48px);
    outline: none;
    color: var(--ink);
    font: 16px/1.85 Georgia, "Noto Serif KR", serif;
  }
  .editor-content :global(.ProseMirror > :first-child) { margin-top: 0; }
  .editor-content :global(.ProseMirror p.is-editor-empty:first-child::before) {
    color: var(--muted);
    content: attr(data-placeholder);
    float: left;
    height: 0;
    pointer-events: none;
  }
  .editor-content :global(h1),
  .editor-content :global(h2),
  .editor-content :global(h3) {
    color: var(--ink);
    font-family: Georgia, "Noto Serif KR", serif;
    line-height: 1.3;
  }
  .editor-content :global(blockquote) {
    border-left: 3px solid var(--signal);
    margin-left: 0;
    padding-left: 18px;
    color: var(--muted-text);
  }
  .editor-content :global(section[data-lore-block]) { position:relative; margin:14px 0; padding:10px 18px; border-left:3px solid var(--signal); background:#f6f8f6; }
  .editor-content :global(section[data-lore-block][locked="true"]) { border-left-color:var(--lichen); }
  @media (max-width: 540px) {
    .editor-content :global(.ProseMirror) { min-height: 360px; padding: 22px 18px; font-size: 15px; }
  }
</style>
