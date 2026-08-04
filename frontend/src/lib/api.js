import { browser } from '$app/environment';
import { env } from '$env/dynamic/public';

const apiPort = env.PUBLIC_API_PORT || '18000';

export const API_BASE =
  env.PUBLIC_API_BASE_URL ||
  (browser
    ? `${window.location.protocol}//${window.location.hostname}:${apiPort}/api/v1`
    : `http://localhost:${apiPort}/api/v1`);

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
