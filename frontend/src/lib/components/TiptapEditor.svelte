<script>
  import { onDestroy, onMount } from 'svelte';
  import { Editor } from '@tiptap/core';
  import Placeholder from '@tiptap/extension-placeholder';
  import StarterKit from '@tiptap/starter-kit';

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
  <div bind:this={mount} class="editor-content"></div>
</div>

<style>
  .editor-shell {
    min-height: 460px;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--surface);
  }
  .editor-content :global(.ProseMirror) {
    min-height: 430px;
    padding: 28px;
    outline: none;
    line-height: 1.75;
  }
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
    line-height: 1.25;
  }
  .editor-content :global(blockquote) {
    border-left: 3px solid var(--border-strong);
    margin-left: 0;
    padding-left: 18px;
    color: var(--muted-text);
  }
</style>
