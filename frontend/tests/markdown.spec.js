import { expect, test } from '@playwright/test';

const project = {
  id: 'markdown-project', name: 'Markdown 세계', slug: 'markdown-world', description: '',
  universe_namespace: 'markdown-world', settings_json: {}, created_at: '', updated_at: ''
};

const markdown = [
  '# 밤의 기록',
  '',
  '**강조된 사실**과 *낮은 추측*을 분리한다.',
  '',
  '- 첫 번째 표식',
  '- 두 번째 표식',
  '',
  '> 해가 지면 종을 울린다.',
  '',
  '`watch()`를 실행한다.',
  '',
  '```txt',
  '<script>alert("safe")</script>',
  '```',
  '',
  '[성문 문서](https://example.com/gate)',
  '',
  '[위험한 링크](javascript:alert(1))',
  '',
  '---',
  '',
  '<script>globalThis.compromised = true</script>'
].join('\n');

const entry = {
  id: 'markdown-entry', project_id: project.id, document_kind: 'lorebook',
  title: '밤의 기록', status: 'approved', body_markdown: markdown, body_json: {},
  source_document_id: null, source_revision_hash: '', generation_inputs_json: {},
  published_at: '2026-08-12T00:00:00Z', created_at: '2026-08-12T00:00:00Z',
  updated_at: '2026-08-12T00:00:00Z'
};

async function mockLorebook(page) {
  const captured = { update: null };
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace('/api/v1', '');
    let body;
    if (path === '/projects') body = [project];
    else if (path === '/lorebook' && request.method() === 'GET') body = [entry];
    else if (path === `/lorebook/${entry.id}` && request.method() === 'PATCH') {
      captured.update = request.postDataJSON();
      body = { ...entry, ...captured.update, updated_at: '2026-08-12T01:00:00Z' };
    } else throw new Error(`Unhandled mock API: ${request.method()} ${path}`);
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  return captured;
}

test('lorebook safely renders and edits markdown', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'one deterministic Markdown rendering contract');
  const captured = await mockLorebook(page);
  await page.goto('/lorebook');

  const reader = page.getByLabel('로어북 글 내용');
  await expect(reader.getByRole('heading', { name: '밤의 기록', level: 1 })).toBeVisible();
  await expect(reader.locator('strong')).toHaveText('강조된 사실');
  await expect(reader.locator('em')).toHaveText('낮은 추측');
  await expect(reader.locator('li')).toHaveCount(2);
  await expect(reader.locator('blockquote')).toContainText('해가 지면');
  await expect(reader.locator('pre code')).toContainText('<script>alert("safe")</script>');
  await expect(reader.getByRole('link', { name: '성문 문서' })).toHaveAttribute('href', 'https://example.com/gate');
  await expect(reader.getByRole('link', { name: '위험한 링크' })).toHaveCount(0);
  await expect(reader).toContainText('위험한 링크');
  await expect(reader.locator('hr')).toHaveCount(1);
  await expect(reader.locator('script')).toHaveCount(0);
  expect(await page.evaluate(() => globalThis.compromised)).toBeUndefined();

  await page.getByRole('button', { name: '글 편집' }).click();
  const editor = page.getByLabel('로어북 글 내용');
  await expect(editor).toHaveJSProperty('tagName', 'TEXTAREA');
  await expect(editor).toHaveValue(/# 밤의 기록/);
  await editor.fill(`${markdown}\n\n## 추가 기록\n\n새 문단.`);
  await page.getByRole('button', { name: '변경 저장' }).click();

  expect(captured.update.body_markdown).toContain('## 추가 기록');
  await expect(page.getByLabel('로어북 글 내용').getByRole('heading', { name: '추가 기록', level: 2 })).toBeVisible();
});
