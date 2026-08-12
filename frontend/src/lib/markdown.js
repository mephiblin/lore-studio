const EMPTY_DOC = { type: 'doc', content: [] };

export function isSafeMarkdownHref(value) {
  const href = String(value || '').trim();
  return /^(https?:|mailto:)/i.test(href) || /^(\/|\.\/|\.\.\/|#)/.test(href);
}

function textNode(text, marks = []) {
  const node = { type: 'text', text };
  if (marks.length) node.marks = marks;
  return node;
}

function isEscaped(text, index) {
  let slashes = 0;
  for (let cursor = index - 1; cursor >= 0 && text[cursor] === '\\'; cursor -= 1) slashes += 1;
  return slashes % 2 === 1;
}

function unescapeMarkdown(text) {
  return text.replace(/\\([\\`*_[\]~])/g, '$1');
}

function appendPlain(nodes, text) {
  const parts = unescapeMarkdown(text).split('\n');
  parts.forEach((part, index) => {
    if (part) nodes.push(textNode(part));
    if (index < parts.length - 1) nodes.push({ type: 'hardBreak' });
  });
}

function addMark(nodes, mark) {
  return nodes.map((node) => node.type === 'text'
    ? { ...node, marks: [...(node.marks || []), mark] }
    : node);
}

const INLINE_TOKENS = [
  { kind: 'code', expression: /`([^`\n]+)`/g },
  { kind: 'link', expression: /\[([^\]\n]+)\]\(([^)\s]+)\)/g },
  { kind: 'bold', expression: /\*\*([^*\n]+)\*\*/g },
  { kind: 'bold', expression: /__([^_\n]+)__/g },
  { kind: 'strike', expression: /~~([^~\n]+)~~/g },
  { kind: 'italic', expression: /\*([^*\n]+)\*/g },
  { kind: 'italic', expression: /_([^_\n]+)_/g }
];

function nextInlineToken(text) {
  let selected = null;
  INLINE_TOKENS.forEach((spec, priority) => {
    spec.expression.lastIndex = 0;
    let match = spec.expression.exec(text);
    while (match && isEscaped(text, match.index)) match = spec.expression.exec(text);
    if (!match) return;
    if (!selected || match.index < selected.match.index || (
      match.index === selected.match.index && priority < selected.priority
    )) selected = { ...spec, match, priority };
  });
  return selected;
}

export function parseMarkdownInline(text = '') {
  const nodes = [];
  let remaining = String(text);
  while (remaining) {
    const token = nextInlineToken(remaining);
    if (!token) {
      appendPlain(nodes, remaining);
      break;
    }
    appendPlain(nodes, remaining.slice(0, token.match.index));
    const [source, label, href] = token.match;
    if (token.kind === 'code') nodes.push(textNode(label, [{ type: 'code' }]));
    else if (token.kind === 'link') {
      const labelNodes = parseMarkdownInline(label);
      nodes.push(...(isSafeMarkdownHref(href)
        ? addMark(labelNodes, { type: 'link', attrs: { href } })
        : labelNodes));
    } else {
      const mark = {
        bold: { type: 'bold' },
        italic: { type: 'italic' },
        strike: { type: 'strike' }
      }[token.kind];
      nodes.push(...addMark(parseMarkdownInline(label), mark));
    }
    remaining = remaining.slice(token.match.index + source.length);
  }
  return nodes;
}

function startsBlock(line) {
  return /^(#{1,6})\s+/.test(line)
    || /^\s*([-+*])\s+/.test(line)
    || /^\s*\d+[.)]\s+/.test(line)
    || /^\s*>\s?/.test(line)
    || /^\s*(```|~~~)/.test(line)
    || /^\s*((\*\s*){3,}|(-\s*){3,}|(_\s*){3,})\s*$/.test(line);
}

function listItem(content) {
  return {
    type: 'listItem',
    content: [{ type: 'paragraph', content: parseMarkdownInline(content.trim()) }]
  };
}

export function markdownToTiptap(markdown = '') {
  const lines = String(markdown).replace(/\r\n?/g, '\n').split('\n');
  const content = [];
  let index = 0;

  while (index < lines.length) {
    const raw = lines[index];
    const line = raw.trimEnd();
    if (!line.trim()) {
      index += 1;
      continue;
    }

    const fence = line.match(/^\s*(```|~~~)\s*([^\s]*)\s*$/);
    if (fence) {
      const closing = fence[1];
      const code = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith(closing)) {
        code.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      const node = { type: 'codeBlock', content: code.length ? [textNode(code.join('\n'))] : [] };
      if (fence[2]) node.attrs = { language: fence[2] };
      content.push(node);
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      content.push({
        type: 'heading',
        attrs: { level: heading[1].length },
        content: parseMarkdownInline(heading[2].trim())
      });
      index += 1;
      continue;
    }

    if (/^\s*((\*\s*){3,}|(-\s*){3,}|(_\s*){3,})\s*$/.test(line)) {
      content.push({ type: 'horizontalRule' });
      index += 1;
      continue;
    }

    if (/^\s*>\s?/.test(line)) {
      const quote = [];
      while (index < lines.length && /^\s*>\s?/.test(lines[index])) {
        quote.push(lines[index].replace(/^\s*>\s?/, ''));
        index += 1;
      }
      const parsed = markdownToTiptap(quote.join('\n')).content;
      content.push({
        type: 'blockquote',
        content: parsed.length ? parsed : [{ type: 'paragraph' }]
      });
      continue;
    }

    const bullet = line.match(/^\s*[-+*]\s+(.+)$/);
    if (bullet) {
      const items = [];
      while (index < lines.length) {
        const item = lines[index].match(/^\s*[-+*]\s+(.+)$/);
        if (!item) break;
        items.push(listItem(item[1]));
        index += 1;
      }
      content.push({ type: 'bulletList', content: items });
      continue;
    }

    const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
    if (ordered) {
      const items = [];
      while (index < lines.length) {
        const item = lines[index].match(/^\s*\d+[.)]\s+(.+)$/);
        if (!item) break;
        items.push(listItem(item[1]));
        index += 1;
      }
      content.push({ type: 'orderedList', attrs: { start: 1, type: null }, content: items });
      continue;
    }

    const paragraph = [line.trim()];
    index += 1;
    while (index < lines.length && lines[index].trim() && !startsBlock(lines[index])) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    content.push({ type: 'paragraph', content: parseMarkdownInline(paragraph.join('\n')) });
  }

  return content.length ? { type: 'doc', content } : EMPTY_DOC;
}

function escapeMarkdownText(text) {
  return String(text).replace(/([\\`*_[\]~])/g, '\\$1');
}

function inlineNodeToMarkdown(node) {
  if (node.type === 'hardBreak') return '  \n';
  if (node.type !== 'text') return '';
  let value = escapeMarkdownText(node.text || '');
  for (const mark of node.marks || []) {
    if (mark.type === 'code') value = `\`${String(node.text || '').replace(/`/g, '\\`')}\``;
    else if (mark.type === 'bold') value = `**${value}**`;
    else if (mark.type === 'italic') value = `*${value}*`;
    else if (mark.type === 'strike') value = `~~${value}~~`;
    else if (mark.type === 'link' && mark.attrs?.href) value = `[${value}](${mark.attrs.href})`;
  }
  return value;
}

function inlineContentToMarkdown(content = []) {
  return content.map(inlineNodeToMarkdown).join('');
}

function indentContinuation(text, prefix) {
  return text.split('\n').map((line, index) => index === 0 ? `${prefix}${line}` : `  ${line}`).join('\n');
}

function blockToMarkdown(node, index = 0) {
  if (!node) return '';
  if (node.type === 'text' || node.type === 'hardBreak') return inlineNodeToMarkdown(node);
  if (node.type === 'paragraph') return inlineContentToMarkdown(node.content);
  if (node.type === 'heading') return `${'#'.repeat(node.attrs?.level || 2)} ${inlineContentToMarkdown(node.content)}`;
  if (node.type === 'horizontalRule') return '---';
  if (node.type === 'codeBlock') {
    const body = (node.content || []).map((item) => item.text || '').join('');
    const fence = body.includes('```') ? '~~~' : '```';
    return `${fence}${node.attrs?.language || ''}\n${body}\n${fence}`;
  }
  if (node.type === 'blockquote') {
    return (node.content || []).map(blockToMarkdown).join('\n\n').split('\n').map((line) => `> ${line}`).join('\n');
  }
  if (node.type === 'listItem') return (node.content || []).map(blockToMarkdown).join('\n');
  if (node.type === 'bulletList') {
    return (node.content || []).map((item) => indentContinuation(blockToMarkdown(item), '- ')).join('\n');
  }
  if (node.type === 'orderedList') {
    const start = Number(node.attrs?.start) || 1;
    return (node.content || []).map((item, itemIndex) => (
      indentContinuation(blockToMarkdown(item), `${start + itemIndex}. `)
    )).join('\n');
  }
  if (node.type === 'loreBlock' || node.type === 'doc') {
    return (node.content || []).map((item, itemIndex) => blockToMarkdown(item, itemIndex)).filter(Boolean).join('\n\n');
  }
  return (node.content || []).map((item, itemIndex) => blockToMarkdown(item, itemIndex)).join('\n\n');
}

export function tiptapToMarkdown(document = EMPTY_DOC) {
  return blockToMarkdown(document).trim();
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function safeHref(value) {
  const href = String(value || '').trim();
  return isSafeMarkdownHref(href) ? href : '';
}

function inlineNodeToHtml(node) {
  if (node.type === 'hardBreak') return '<br>';
  if (node.type !== 'text') return '';
  let value = escapeHtml(node.text || '');
  for (const mark of node.marks || []) {
    if (mark.type === 'code') value = `<code>${escapeHtml(node.text || '')}</code>`;
    else if (mark.type === 'bold') value = `<strong>${value}</strong>`;
    else if (mark.type === 'italic') value = `<em>${value}</em>`;
    else if (mark.type === 'strike') value = `<s>${value}</s>`;
    else if (mark.type === 'link') {
      const href = safeHref(mark.attrs?.href);
      if (href) value = `<a href="${escapeHtml(href)}" rel="noreferrer">${value}</a>`;
    }
  }
  return value;
}

function nodesToHtml(nodes = []) {
  return nodes.map(nodeToHtml).join('');
}

function nodeToHtml(node) {
  if (!node) return '';
  if (node.type === 'text' || node.type === 'hardBreak') return inlineNodeToHtml(node);
  if (node.type === 'paragraph') return `<p>${nodesToHtml(node.content)}</p>`;
  if (node.type === 'heading') {
    const level = Math.min(6, Math.max(1, Number(node.attrs?.level) || 2));
    return `<h${level}>${nodesToHtml(node.content)}</h${level}>`;
  }
  if (node.type === 'horizontalRule') return '<hr>';
  if (node.type === 'blockquote') return `<blockquote>${nodesToHtml(node.content)}</blockquote>`;
  if (node.type === 'bulletList') return `<ul>${nodesToHtml(node.content)}</ul>`;
  if (node.type === 'orderedList') return `<ol>${nodesToHtml(node.content)}</ol>`;
  if (node.type === 'listItem') return `<li>${nodesToHtml(node.content)}</li>`;
  if (node.type === 'codeBlock') {
    const body = (node.content || []).map((item) => item.text || '').join('');
    return `<pre><code>${escapeHtml(body)}</code></pre>`;
  }
  if (node.type === 'loreBlock') return `<section>${nodesToHtml(node.content)}</section>`;
  return nodesToHtml(node.content);
}

export function markdownToSafeHtml(markdown = '') {
  return nodesToHtml(markdownToTiptap(markdown).content);
}
