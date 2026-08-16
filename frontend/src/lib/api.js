import { browser } from '$app/environment';
import { env } from '$env/dynamic/public';

const apiPort = env.PUBLIC_API_PORT || '18000';

const API_FIELD_LABELS = {
  body_json: '본문',
  selection_from: '선택 시작 위치',
  selection_to: '선택 끝 위치',
  selection_text: '선택 영역',
  operation: '수정 방식',
  instruction: '추가 지시',
  source_page_ids: '연결 자료'
};

export const API_BASE =
  env.PUBLIC_API_BASE_URL ||
  (browser
    ? `${window.location.protocol}//${window.location.hostname}:${apiPort}/api/v1`
    : `http://localhost:${apiPort}/api/v1`);

function validationMessage(issues) {
  if (!Array.isArray(issues) || !issues.length) return '';
  return issues.slice(0, 3).map((issue) => {
    const field = issue?.loc?.at(-1);
    const label = API_FIELD_LABELS[field] || field || '요청 값';
    const limit = issue?.ctx?.max_length;
    if (limit && ['string_too_long', 'too_long'].includes(issue?.type)) {
      const unit = field === 'source_page_ids' ? '개' : '자';
      return `${label}은(는) ${Number(limit).toLocaleString('ko-KR')}${unit} 이하여야 합니다.`;
    }
    if (issue?.type === 'greater_than_equal' && Number.isFinite(issue?.ctx?.ge)) {
      return `${label}은(는) ${issue.ctx.ge} 이상이어야 합니다.`;
    }
    return `${label}: ${issue?.msg || '요청 값을 확인해 주세요.'}`;
  }).join(' ');
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    },
    ...options
  });

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const data = await response.json();
      if (typeof data.detail === 'string') detail = data.detail;
      else if (data.detail?.message) detail = `${data.detail.message} (${data.detail.code || 'API_ERROR'})`;
      else if (Array.isArray(data.detail)) detail = validationMessage(data.detail) || detail;
    } catch {
      // Keep the HTTP status text.
    }
    throw new Error(detail);
  }

  if (response.status === 204) return null;
  return response.json();
}

async function postEvents(path, body, onEvent) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(body)
  });
  if (!response.ok || !response.body) throw new Error(`${response.status} ${response.statusText}`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const records = buffer.split('\n\n');
    buffer = records.pop() || '';
    for (const record of records) {
      const event = record.match(/^event: (.+)$/m)?.[1] || 'message';
      const raw = record.match(/^data: (.+)$/m)?.[1];
      if (raw) onEvent(event, JSON.parse(raw));
    }
    if (done) break;
  }
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body: JSON.stringify(body) }),
  postEvents,
  patch: (path, body) => request(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: (path) => request(path, { method: 'DELETE' })
};
