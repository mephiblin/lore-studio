<script>
  import { onDestroy, onMount } from 'svelte';
  import { Editor } from '@tiptap/core';
  import Link from '@tiptap/extension-link';
  import Placeholder from '@tiptap/extension-placeholder';
  import StarterKit from '@tiptap/starter-kit';
  import { api } from '$lib/api';
  import { LoreBlock } from '$lib/extensions/LoreBlock';
  import { isSafeMarkdownHref, markdownToTiptap, tiptapToMarkdown } from '$lib/markdown';

  export let value = { type: 'doc', content: [] };
  export let onChange = () => {};
  export let editable = true;
  export let aiPageId = '';
  export let aiBoundaries = { locked_facts: [], open_questions: [], forbidden_changes: [] };
  export let sourceOptions = [];
  export let linkedSourceIds = [];
  export let onNotice = () => {};

  const operations = [
    ['polish', '문맥에 맞게 다듬기'],
    ['shorter', '더 짧게'],
    ['longer', '더 자세히 (약 2배)'],
    ['clarify', '설명을 명확하게'],
    ['consistency', '설정 충돌 줄이기'],
    ['custom', '직접 지시']
  ];

  let mount;
  let editor;
  let lastExternal = JSON.stringify(value || {});
  let savedSelection = null;
  let rewriteOpen = false;
  let rewriteOperation = 'polish';
  let rewriteInstruction = '';
  let rewriteUsesLinked = true;
  let aiModelKey = 'gemma';
  let draftOpen = false;
  let draftPrompt = '';
  let draftPlacement = 'replace';
  let draftLength = 'normal';
  let draftSourceIds = [];
  let sourceQuery = '';
  let proposal = null;
  let proposalSnapshot = '';
  let busy = '';
  let aiError = '';
  let cursorAtDraftOpen = 1;
  let visibleViewportHeight = 0;
  let visibleViewportTop = 0;
  let markdownMode = false;
  let markdownDraft = '';

  $: filteredSources = sourceOptions.filter((source) => {
    const query = sourceQuery.trim().toLowerCase();
    return !query || `${source.title} ${source.summary || ''} ${source.role_label || ''}`.toLowerCase().includes(query);
  });
  $: selectionReady = !!savedSelection?.text?.trim() && savedSelection.text.length <= 12000;
  $: currentSnapshot = editor ? JSON.stringify(value || editor.getJSON()) : '';
  $: proposalStale = !!proposal && proposalSnapshot !== currentSnapshot;

  function modelLabel(modelKey) {
    return modelKey === 'qwen' ? 'Qwen' : 'Gemma';
  }

  function rememberSelection({ editor: currentEditor }) {
    const { from, to, empty } = currentEditor.state.selection;
    if (empty) return;
    const text = currentEditor.state.doc.textBetween(from, to, '\n').trim();
    if (!text) return;
    savedSelection = {
      from,
      to,
      text,
      inline: currentEditor.state.doc.resolve(from).parent === currentEditor.state.doc.resolve(to).parent
    };
  }

  function editorChanged(currentEditor) {
    const json = currentEditor.getJSON();
    lastExternal = JSON.stringify(json);
    if (markdownMode) markdownDraft = tiptapToMarkdown(json);
    onChange(json);
  }

  onMount(() => {
    editor = new Editor({
      element: mount,
      extensions: [
        StarterKit,
        Link.configure({
          openOnClick: true,
          autolink: false,
          linkOnPaste: true,
          isAllowedUri: isSafeMarkdownHref
        }),
        LoreBlock,
        Placeholder.configure({ placeholder: '설정, 이야기 조각, 인용, 메모를 자유롭게 작성하십시오.' })
      ],
      content: value || { type: 'doc', content: [] },
      editable,
      onSelectionUpdate: rememberSelection,
      onUpdate: ({ editor: currentEditor }) => editorChanged(currentEditor)
    });
    const syncVisibleViewport = () => {
      visibleViewportHeight = Math.round(window.visualViewport?.height || window.innerHeight);
      visibleViewportTop = Math.round(window.visualViewport?.offsetTop || 0);
    };
    syncVisibleViewport();
    window.visualViewport?.addEventListener('resize', syncVisibleViewport);
    window.visualViewport?.addEventListener('scroll', syncVisibleViewport);
    window.addEventListener('resize', syncVisibleViewport);
    return () => {
      window.visualViewport?.removeEventListener('resize', syncVisibleViewport);
      window.visualViewport?.removeEventListener('scroll', syncVisibleViewport);
      window.removeEventListener('resize', syncVisibleViewport);
    };
  });

  $: if (editor) {
    editor.setEditable(editable);
    const incoming = JSON.stringify(value || {});
    if (incoming !== lastExternal) {
      editor.commands.setContent(value || { type: 'doc', content: [] }, false);
      lastExternal = incoming;
      if (markdownMode) markdownDraft = tiptapToMarkdown(value);
      savedSelection = null;
      proposal = null;
    }
  }
  $: if (!editable && markdownMode) markdownMode = false;

  function toggleMarkdownMode() {
    if (!editor) return;
    aiError = '';
    rewriteOpen = false;
    savedSelection = null;
    if (!markdownMode) {
      markdownDraft = tiptapToMarkdown(editor.getJSON());
      markdownMode = true;
      return;
    }
    syncMarkdownDraft();
    markdownMode = false;
    requestAnimationFrame(() => editor?.commands.focus('end'));
  }

  function syncMarkdownDraft() {
    if (!editor) return;
    const body = markdownToTiptap(markdownDraft);
    editor.commands.setContent(body, false);
    lastExternal = JSON.stringify(body);
    onChange(body);
  }

  function keepSelection(event) {
    event.preventDefault();
  }

  function openRewrite() {
    aiError = '';
    if (!selectionReady) {
      aiError = savedSelection?.text?.length > 12000
        ? 'AI 수정은 한 번에 1만 2천 자까지 선택할 수 있습니다.'
        : '본문에서 수정할 문장을 먼저 선택해 주세요.';
      return;
    }
    rewriteOpen = !rewriteOpen;
    draftOpen = false;
  }

  function openDraft() {
    aiError = '';
    cursorAtDraftOpen = editor?.state.selection.from || 1;
    draftSourceIds = [...new Set(linkedSourceIds)].filter((id) => sourceOptions.some((item) => item.id === id)).slice(0, 12);
    sourceQuery = '';
    draftOpen = true;
    rewriteOpen = false;
  }

  function boundaryPayload() {
    const stringList = (values) => (Array.isArray(values)
      ? values.filter((value) => typeof value === 'string').map((value) => value.trim()).filter(Boolean)
      : []);
    return {
      locked_facts: stringList(aiBoundaries?.locked_facts),
      open_questions: stringList(aiBoundaries?.open_questions),
      forbidden_changes: stringList(aiBoundaries?.forbidden_changes)
    };
  }

  async function submitRewrite() {
    if (!editor || !aiPageId || !selectionReady) return;
    aiError = '';
    const instruction = rewriteInstruction.trim();
    if (instruction.length > 2000) {
      aiError = '추가 지시는 2,000자 이하로 줄여 주세요.';
      return;
    }
    const validSourceIds = new Set(sourceOptions.map((source) => source?.id).filter((id) => typeof id === 'string'));
    const sourcePageIds = rewriteUsesLinked
      ? [...new Set(linkedSourceIds.filter((id) => typeof id === 'string' && validSourceIds.has(id)))].slice(0, 12)
      : [];
    busy = 'selection';
    const body = editor.getJSON();
    proposalSnapshot = JSON.stringify(body);
    try {
      proposal = await api.post(`/concept-pages/${aiPageId}/ai/rewrite-selection`, {
        body_json: body,
        model_key: aiModelKey,
        selection_from: savedSelection.from,
        selection_to: savedSelection.to,
        selection_text: savedSelection.text,
        operation: rewriteOperation,
        instruction,
        source_page_ids: sourcePageIds,
        ...boundaryPayload()
      });
      proposal = { ...proposal, placement: 'selection', selection: { ...savedSelection } };
      rewriteOpen = false;
    } catch (error) {
      aiError = error.message;
      proposal = null;
    } finally {
      busy = '';
    }
  }

  async function submitDraft() {
    if (!editor || !aiPageId || !draftPrompt.trim()) return;
    aiError = '';
    busy = 'draft';
    const body = editor.getJSON();
    proposalSnapshot = JSON.stringify(body);
    try {
      const response = await api.post(`/concept-pages/${aiPageId}/ai/draft`, {
        body_json: body,
        model_key: aiModelKey,
        prompt: draftPrompt.trim(),
        source_page_ids: draftSourceIds.slice(0, 12),
        placement: draftPlacement,
        length: draftLength,
        ...boundaryPayload()
      });
      proposal = { ...response, placement: draftPlacement, cursor: cursorAtDraftOpen };
      draftOpen = false;
    } catch (error) {
      aiError = error.message;
      proposal = null;
    } finally {
      busy = '';
    }
  }

  function applyProposal() {
    if (!editor || !proposal || proposalStale) return;
    if (proposal.mode === 'rewrite_selection') {
      const selection = proposal.selection;
      const currentText = editor.state.doc.textBetween(selection.from, selection.to, '\n').trim();
      if (currentText !== proposal.original_text.trim()) {
        aiError = '선택했던 문장이 달라졌습니다. 다시 선택한 뒤 AI 수정을 요청해 주세요.';
        return;
      }
      if (selection.inline) {
        const replacement = proposal.proposed_text.replace(/\s*\n\s*/g, ' ');
        const transaction = editor.state.tr.replaceWith(
          selection.from,
          selection.to,
          editor.schema.text(replacement, editor.state.doc.resolve(selection.from).marks())
        );
        editor.view.dispatch(transaction);
        editor.commands.focus(selection.from + replacement.length);
      } else {
        editor.chain().focus().insertContentAt(
          { from: selection.from, to: selection.to },
          markdownToTiptap(proposal.proposed_text).content
        ).run();
      }
    } else {
      const nodes = markdownToTiptap(proposal.proposed_text).content;
      if (proposal.placement === 'replace') {
        editor.commands.setContent({ type: 'doc', content: nodes }, true);
      } else if (proposal.placement === 'append') {
        editor.chain().focus().insertContentAt(editor.state.doc.content.size, nodes).run();
      } else {
        const position = Math.min(proposal.cursor, editor.state.doc.content.size);
        editor.chain().focus().insertContentAt(position, nodes).run();
      }
    }
    proposal = null;
    savedSelection = null;
    onNotice('AI 제안을 본문에 반영했습니다. 아직 저장되지 않았습니다.');
  }

  function retryProposal() {
    if (!proposal) return;
    if (proposal.mode === 'rewrite_selection') submitRewrite();
    else submitDraft();
  }

  function closeDraftOnEscape(event) {
    if (event.key === 'Escape' && draftOpen) draftOpen = false;
  }

  onDestroy(() => editor?.destroy());
</script>

<svelte:window on:keydown={closeDraftOnEscape} />

<div class="editor-shell">
  {#if editable}<div class="editor-toolbar" aria-label="본문 서식">
    {#if !markdownMode}
      <button type="button" on:click={() => editor?.chain().focus().toggleBold().run()} aria-label="굵게"><strong>B</strong></button>
      <button type="button" on:click={() => editor?.chain().focus().toggleItalic().run()} aria-label="기울임"><em>I</em></button>
      <button type="button" on:click={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}>제목</button>
      <button type="button" on:click={() => editor?.chain().focus().toggleBulletList().run()}>목록</button>
      <button type="button" on:click={() => editor?.chain().focus().toggleBlockquote().run()}>인용</button>
    {/if}
    <span class="toolbar-divider" aria-hidden="true"></span>
    {#if !markdownMode}<button
      type="button"
      class="ai-tool"
      class:active={rewriteOpen}
      disabled={!editable || !aiPageId || !selectionReady || !!busy}
      title={selectionReady ? '선택한 부분만 문맥에 맞게 수정' : '본문에서 수정할 문장을 먼저 선택하세요'}
      on:mousedown={keepSelection}
      on:click={openRewrite}
    >AI 수정</button>{/if}
    <button
      type="button"
      class="ai-tool primary-ai"
      disabled={!editable || !aiPageId || !!busy}
      on:mousedown={keepSelection}
      on:click={openDraft}
    >AI 작성</button>
    <button
      type="button"
      class="markdown-mode-button"
      class:active={markdownMode}
      aria-pressed={markdownMode}
      on:click={toggleMarkdownMode}
    >{markdownMode ? '서식 편집' : 'Markdown 편집'}</button>
  </div>{/if}

  {#if rewriteOpen}
    <form class="ai-inline-panel" aria-label="선택 영역 AI 수정" on:submit|preventDefault={submitRewrite}>
      <div class="selection-preview"><span>선택 영역</span><q>{savedSelection?.text}</q></div>
      <div class="rewrite-controls">
        <label>사용할 모델
          <select bind:value={aiModelKey}><option value="gemma">Gemma</option><option value="qwen">Qwen</option></select>
        </label>
        <label>수정 방식
          <select bind:value={rewriteOperation}>
            {#each operations as [value, label]}<option {value}>{label}</option>{/each}
          </select>
        </label>
        <label class="rewrite-instruction">추가 지시
          <input bind:value={rewriteInstruction} maxlength="2000" placeholder="선택 사항 · 2,000자 이하" />
        </label>
      </div>
      {#if linkedSourceIds.length}
        <label class="reference-toggle"><input type="checkbox" bind:checked={rewriteUsesLinked} /> 연결된 자료 {Math.min(linkedSourceIds.length, 12)}개 참고</label>
      {/if}
      <div class="panel-actions">
        <button type="button" class="ghost-button" on:click={() => rewriteOpen = false}>취소</button>
        <button type="submit" class="identity-button" disabled={!!busy || (rewriteOperation === 'custom' && !rewriteInstruction.trim())}>{busy === 'selection' ? '제안 중…' : '수정 제안'}</button>
      </div>
    </form>
  {/if}

  {#if aiError}<div class="ai-error" role="alert">{aiError}</div>{/if}

  {#if proposal}
    <section class="proposal-panel" aria-label="AI 본문 제안">
      <div class="proposal-heading">
        <div><span class="candidate-label">검토할 제안</span><strong>{modelLabel(proposal.model_key)} · {proposal.mode === 'rewrite_selection' ? '선택 영역 수정' : '본문 초안'}</strong></div>
        <button type="button" class="icon-close" aria-label="AI 제안 닫기" on:click={() => proposal = null}>×</button>
      </div>
      {#if proposal.mode === 'rewrite_selection'}
        <div class="proposal-original"><span>기존</span><p>{proposal.original_text}</p></div>
      {/if}
      <div class="proposal-copy"><span>제안</span><pre>{proposal.proposed_text}</pre></div>
      {#if proposal.warnings?.length}
        <ul class="proposal-warnings">{#each proposal.warnings as warning}<li>{warning}</li>{/each}</ul>
      {/if}
      {#if proposalStale}<p class="stale-warning">제안 뒤에 본문이 바뀌었습니다. 현재 본문에 덮어쓰지 않도록 다시 제안해 주세요.</p>{/if}
      <div class="panel-actions">
        <button type="button" class="ghost-button" on:click={() => proposal = null}>취소</button>
        <button type="button" class="ghost-button" disabled={!!busy} on:click={retryProposal}>{busy ? '제안 중…' : '다시 제안'}</button>
        <button type="button" class="identity-button" disabled={proposalStale || !!busy} on:click={applyProposal}>본문에 반영</button>
      </div>
    </section>
  {/if}

  {#if markdownMode && editable}
    <div class="markdown-editor-pane">
      <textarea
        class="markdown-source-editor"
        aria-label="세계관 자료 Markdown 본문"
        bind:value={markdownDraft}
        on:input={syncMarkdownDraft}
        spellcheck="true"
      ></textarea>
      <small>`#` 제목 · `**굵게**` · `-` 목록 · `>` 인용 · 코드 블록 · 링크를 사용할 수 있습니다.</small>
    </div>
  {/if}
  <div bind:this={mount} class:reader={!editable} class:hidden={markdownMode && editable} class="editor-content" aria-label={editable ? '세계관 자료 본문 편집' : '세계관 자료 본문'}></div>
</div>

{#if draftOpen}
  <div
    class="ai-modal-backdrop"
    role="presentation"
    style={`--ai-visible-height:${visibleViewportHeight ? `${visibleViewportHeight}px` : '100dvh'};--ai-visible-top:${visibleViewportTop}px`}
    on:mousedown={(event) => event.target === event.currentTarget && (draftOpen = false)}
  >
    <div class="ai-draft-modal" role="dialog" aria-modal="true" aria-labelledby="ai-draft-title">
      <form class="ai-draft-form" on:submit|preventDefault={submitDraft}>
      <header>
        <div><span>세계관 자료</span><h2 id="ai-draft-title">AI 작성</h2></div>
        <button type="button" class="icon-close" aria-label="AI 작성 닫기" on:click={() => draftOpen = false}>×</button>
      </header>
      <div class="ai-draft-body">
      <label class="prompt-field">무엇을 작성할까요?
        <textarea bind:value={draftPrompt} placeholder="예: 이 장소의 출입 절차와 주민이 느끼는 긴장을 3개 단락으로 작성해 줘."></textarea>
      </label>

      <fieldset>
        <legend>본문에 넣을 위치</legend>
        <div class="segmented">
          <label class:checked={draftPlacement === 'replace'}><input type="radio" bind:group={draftPlacement} value="replace" />본문 전체 초안</label>
          <label class:checked={draftPlacement === 'cursor'}><input type="radio" bind:group={draftPlacement} value="cursor" />현재 위치에 추가</label>
          <label class:checked={draftPlacement === 'append'}><input type="radio" bind:group={draftPlacement} value="append" />이어쓰기</label>
        </div>
      </fieldset>

      <div class="draft-meta">
        <label>사용할 모델
          <select bind:value={aiModelKey}><option value="gemma">Gemma</option><option value="qwen">Qwen</option></select>
        </label>
        <label>분량
          <select bind:value={draftLength}><option value="short">짧게</option><option value="normal">보통</option><option value="long">길게</option></select>
        </label>
        <div class="reference-count"><strong>참고 자료</strong><span>{draftSourceIds.length}/12 선택</span></div>
      </div>

      <section class="source-picker" aria-label="이번 AI 작성의 참고 자료">
        <input aria-label="참고 자료 검색" bind:value={sourceQuery} placeholder="자료 검색" />
        <p>이 선택은 이번 작성에만 사용하며 자료 사이의 영구 연결을 만들지 않습니다. 연결된 자료는 미리 선택했습니다.</p>
        <div class="source-list">
          {#each filteredSources as source}
            <label class:selected={draftSourceIds.includes(source.id)}>
              <input type="checkbox" bind:group={draftSourceIds} value={source.id} disabled={!draftSourceIds.includes(source.id) && draftSourceIds.length >= 12} />
              <span><strong>{source.title}</strong><small>{source.role_label}{source.linked ? ' · 연결됨' : ''}{source.summary ? ` · ${source.summary}` : ''}</small></span>
            </label>
          {/each}
          {#if !filteredSources.length}<div class="empty-source">조건에 맞는 자료가 없습니다.</div>{/if}
        </div>
      </section>
      </div>

      <footer>
        <small>결과는 저장 전 검토할 제안으로만 생성됩니다.</small>
        <div class="panel-actions">
          <button type="button" class="ghost-button" on:click={() => draftOpen = false}>취소</button>
          <button type="submit" class="identity-button" disabled={!draftPrompt.trim() || !!busy}>{busy === 'draft' ? '초안 작성 중…' : '초안 제안'}</button>
        </div>
      </footer>
      </form>
    </div>
  </div>
{/if}

<style>
  .editor-shell {
    width: 100%; max-width: 100%; min-width: 0; min-height: 460px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border: 1px solid var(--line);
    border-radius: 7px;
    background: var(--paper);
    box-shadow: 0 10px 30px rgba(20, 43, 53, .06);
  }
  .editor-toolbar { flex:0 0 auto; display:flex; align-items:center; gap:4px; padding:8px 10px; border-bottom:1px solid var(--line); background:var(--paper-deep); }
  .editor-toolbar button { min-width:34px; min-height:32px; border:1px solid transparent; background:transparent; border-radius:3px; padding:5px 8px; color:var(--muted-text); font-size:12px; }
  .editor-toolbar button:hover:not(:disabled) { background:#fff; border-color:var(--line); color:var(--ink); }
  .editor-toolbar button:disabled { cursor:not-allowed; opacity:.42; }
  .toolbar-divider { width:1px; height:20px; margin:0 4px; background:var(--line-strong); }
  .editor-toolbar .ai-tool { min-width:58px; font-weight:800; color:var(--nav-deep, #173f38); }
  .editor-toolbar .ai-tool.active { border-color:var(--nav-deep, #173f38); background:#fff; }
  .editor-toolbar .primary-ai { background:var(--nav-deep, #173f38); color:var(--nav-accent, #f2cf5b); }
  .editor-toolbar .primary-ai:hover:not(:disabled) { background:var(--nav-deep, #173f38); color:var(--nav-accent, #f2cf5b); filter:brightness(1.08); }
  .editor-toolbar .markdown-mode-button { min-width:106px; margin-left:auto; color:var(--nav-deep, #173f38); font-weight:800; }
  .editor-toolbar .markdown-mode-button.active { border-color:var(--nav-deep, #173f38); background:#fff; }
  .editor-content.hidden { display:none; }
  .markdown-editor-pane { min-height:0; flex:1 1 auto; display:flex; flex-direction:column; }
  .markdown-source-editor {
    min-height:430px; flex:1 1 auto; resize:none; border:0; border-radius:0; padding:clamp(24px, 4vw, 48px);
    outline:none; background:#fbfcf9; color:var(--ink); font:14px/1.75 ui-monospace, "SFMono-Regular", Consolas, "Noto Sans KR", monospace;
    tab-size:2;
  }
  .markdown-editor-pane > small { flex:0 0 auto; padding:8px 12px; border-top:1px solid var(--line); color:var(--muted); background:var(--paper-deep); font-size:10px; }
  .editor-content { min-height: 0; flex: 1 1 auto; overflow-y: auto; overscroll-behavior: contain; scrollbar-width: thin; scrollbar-color: var(--line-strong) transparent; }
  .editor-content :global(.ProseMirror) {
    min-height: 430px;
    padding: clamp(24px, 4vw, 48px);
    outline: none;
    color: var(--ink);
    font: 16px/1.85 Georgia, "Noto Serif KR", serif;
  }
  .editor-content.reader :global(.ProseMirror) { cursor: default; }
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

  .ai-inline-panel, .proposal-panel { min-width:0; flex:0 0 auto; padding:12px 14px; border-bottom:1px solid var(--line); background:#fffdf8; }
  .selection-preview { display:flex; align-items:baseline; gap:10px; min-width:0; margin-bottom:10px; }
  .selection-preview span, .proposal-copy > span, .proposal-original > span { flex:0 0 auto; color:var(--muted); font-size:11px; font-weight:800; letter-spacing:.06em; }
  .selection-preview q { min-width:0; overflow:hidden; color:var(--ink); font:13px/1.5 Georgia, "Noto Serif KR", serif; text-overflow:ellipsis; white-space:nowrap; }
  .rewrite-controls { display:grid; grid-template-columns:minmax(110px, .65fr) minmax(150px, .85fr) minmax(180px, 1.2fr); gap:10px; }
  .rewrite-controls label, .prompt-field { display:grid; gap:5px; color:var(--muted-text); font-size:12px; font-weight:700; }
  .rewrite-controls select, .rewrite-controls input { width:100%; min-height:34px; }
  .reference-toggle { display:flex; align-items:center; gap:7px; margin-top:9px; color:var(--muted-text); font-size:12px; }
  .reference-toggle input { width:auto; }
  .panel-actions { display:flex; align-items:center; justify-content:flex-end; gap:7px; margin-top:10px; }
  .identity-button, .ghost-button, .icon-close { border-radius:4px; font-weight:800; }
  .identity-button { border:1px solid var(--nav-deep, #173f38); background:var(--nav-deep, #173f38); color:var(--nav-accent, #f2cf5b); padding:8px 13px; }
  .identity-button:disabled { opacity:.48; }
  .ghost-button { border:1px solid var(--line); background:var(--paper); color:var(--muted-text); padding:8px 12px; }
  .ai-error { flex:0 0 auto; padding:9px 14px; border-bottom:1px solid #e5c3bd; background:#fff4f1; color:#923c2f; font-size:12px; }
  .proposal-panel { max-height:45%; overflow:auto; background:#f8faf7; }
  .proposal-heading { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; }
  .proposal-heading > div { display:flex; align-items:center; gap:8px; }
  .candidate-label { border-radius:999px; background:#e8efe8; color:var(--nav-deep, #173f38); padding:3px 7px; font-size:10px; font-weight:900; letter-spacing:.04em; }
  .icon-close { border:0; background:transparent; color:var(--muted); padding:2px 6px; font-size:21px; line-height:1; }
  .proposal-original, .proposal-copy { display:grid; grid-template-columns:42px minmax(0, 1fr); gap:8px; margin-top:10px; }
  .proposal-original p, .proposal-copy pre { max-height:150px; overflow:auto; margin:0; white-space:pre-wrap; }
  .proposal-original p { color:var(--muted-text); font-size:12px; }
  .proposal-copy pre {
    border:1px solid #365f57;
    background:var(--nav-deep, #173f38);
    color:var(--nav-accent, #f2cf5b);
    font:13px/1.65 Georgia, "Noto Serif KR", serif;
  }
  .proposal-warnings { margin:9px 0 0 50px; padding-left:16px; color:#765f25; font-size:11px; }
  .stale-warning { margin:9px 0 0; color:#923c2f; font-size:12px; font-weight:700; }

  .ai-modal-backdrop { position:fixed; top:var(--ai-visible-top, 0); right:0; bottom:auto; left:0; height:var(--ai-visible-height, 100dvh); z-index:1000; display:grid; place-items:center; padding:20px; background:rgba(15, 29, 27, .42); backdrop-filter:blur(2px); }
  .ai-draft-modal { width:min(620px, 100%); max-height:min(760px, calc(100dvh - 40px)); display:flex; flex-direction:column; overflow:hidden; border:1px solid rgba(255,255,255,.5); border-radius:9px; background:var(--paper); box-shadow:0 24px 80px rgba(10,30,27,.28); padding:20px; }
  .ai-draft-form { min-height:0; display:flex; flex:1 1 auto; flex-direction:column; gap:16px; overflow:hidden; }
  .ai-draft-modal header { flex:0 0 auto; display:flex; align-items:flex-start; justify-content:space-between; }
  .ai-draft-modal header span { color:var(--signal); font-size:11px; font-weight:900; letter-spacing:.09em; text-transform:uppercase; }
  .ai-draft-modal h2 { margin:2px 0 0; color:var(--ink); font:700 25px/1.2 Georgia, "Noto Serif KR", serif; }
  .ai-draft-body { min-width:0; min-height:0; display:flex; flex:1 1 auto; flex-direction:column; gap:16px; overflow-x:hidden; overflow-y:auto; padding:1px 3px 4px 1px; scrollbar-width:thin; scrollbar-color:var(--line-strong) transparent; }
  .prompt-field textarea { min-height:100px; resize:vertical; }
  .ai-draft-modal fieldset { min-width:0; margin:0; padding:0; border:0; }
  .ai-draft-modal legend { margin-bottom:7px; color:var(--muted-text); font-size:12px; font-weight:800; }
  .segmented { display:grid; grid-template-columns:repeat(3, 1fr); gap:5px; }
  .segmented label { display:flex; justify-content:center; border:1px solid var(--line); border-radius:4px; padding:8px 6px; color:var(--muted-text); font-size:12px; font-weight:700; }
  .segmented label.checked { border-color:var(--nav-deep, #173f38); background:var(--nav-deep, #173f38); color:var(--nav-accent, #f2cf5b); }
  .segmented input { position:absolute; opacity:0; pointer-events:none; }
  .draft-meta { display:flex; align-items:end; justify-content:space-between; gap:16px; }
  .draft-meta label { display:grid; gap:5px; color:var(--muted-text); font-size:12px; font-weight:800; }
  .draft-meta select { min-width:120px; }
  .reference-count { display:flex; align-items:center; gap:8px; font-size:12px; }
  .reference-count span { color:var(--muted); }
  .source-picker { min-height:0; display:flex; flex:0 0 auto; flex-direction:column; gap:8px; }
  .source-picker > p { margin:0; color:var(--muted); font-size:11px; line-height:1.5; }
  .source-list { min-height:90px; overflow:visible; border:1px solid var(--line); border-radius:5px; background:#fff; }
  .source-list label { display:flex; align-items:flex-start; gap:9px; padding:10px 11px; border-bottom:1px solid var(--line); }
  .source-list label:last-child { border-bottom:0; }
  .source-list label.selected { background:#f1f6ef; }
  .source-list input { width:auto; margin-top:3px; }
  .source-list span { min-width:0; display:grid; gap:2px; }
  .source-list strong { color:var(--ink); font-size:13px; }
  .source-list small { overflow:hidden; color:var(--muted); font-size:11px; text-overflow:ellipsis; white-space:nowrap; }
  .empty-source { padding:20px; color:var(--muted); font-size:12px; text-align:center; }
  .ai-draft-modal footer { flex:0 0 auto; display:flex; align-items:center; justify-content:space-between; gap:14px; padding-top:10px; border-top:1px solid var(--line); background:var(--paper); }
  .ai-draft-modal footer small { color:var(--muted); }

  @media (min-width: 821px) {
    .editor-shell { height: 100%; min-height: 0; }
    .editor-content :global(.ProseMirror) { min-height: 100%; }
  }
  @media (max-width: 820px) {
    .editor-shell { overflow: visible; }
    .editor-content { flex: 0 0 auto; overflow-y: visible; overscroll-behavior-y: auto; }
    .ai-inline-panel, .proposal-panel {
      width: 100%; max-width: 100%; position: sticky; z-index: 12; top: 8px; max-height: calc(100dvh - 92px); overflow-y: auto;
      border: 1px solid var(--line); box-shadow: 0 12px 30px rgba(20,43,53,.13);
    }
  }
  @media (max-width: 540px) {
    .editor-toolbar { flex-wrap:wrap; }
    .editor-toolbar .markdown-mode-button { margin-left:0; }
    .editor-content :global(.ProseMirror) { min-height: 360px; padding:22px 18px; font-size:15px; }
    .markdown-source-editor { min-height:360px; padding:22px 18px; font-size:13px; }
    .rewrite-controls { grid-template-columns:1fr; }
    .ai-modal-backdrop { align-items:end; padding:0; }
    .ai-draft-modal { width:100%; max-height:min(92dvh, calc(100dvh - env(safe-area-inset-bottom))); border-radius:12px 12px 0 0; padding:18px; }
    .segmented { grid-template-columns:1fr; }
    .draft-meta, .ai-draft-modal footer { align-items:stretch; flex-direction:column; }
    .ai-draft-modal footer .panel-actions { width:100%; margin-top:0; }
    .ai-draft-modal footer .identity-button { flex:1; }
  }
</style>
