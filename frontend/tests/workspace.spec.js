import { expect, test } from '@playwright/test';

const routes = [
  ['/', /설정은 쌓고/],
  ['/editor', /컨셉 아카이브/],
  ['/playbook', /플레이북 조립/],
  ['/documents', /문단 단위 집필실/],
];

for (const [route, heading] of routes) {
  test(`${route} renders without browser or API errors`, async ({ page }) => {
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('response', (response) => {
      if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`);
    });
    await page.goto(route);
    await expect(page.getByRole('heading', { level: 1 })).toContainText(heading);
    await expect.poll(() => errors).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}

test('real-model readiness and primary authoring controls are visible', async ({ page }) => {
  test.skip(process.env.E2E_EXPECT_DATA !== 'true', 'requires the seeded real-model acceptance project');
  await page.goto('/');
  await expect(page.getByText('writer')).toBeVisible();
  await expect(page.getByText('embedding')).toBeVisible();
  await expect(page.getByText('READY').first()).toBeVisible();

  await page.goto('/playbook');
  await expect(page.getByRole('button', { name: '풀에서 추첨' })).toBeVisible();
  await expect(page.getByRole('button', { name: /실제 Writer로 원고 작성/ })).toBeVisible();

  await page.goto('/documents');
  await expect(page.getByRole('button', { name: '부분 재작성' }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Markdown' })).toBeVisible();
});

test('mock API completes the authoring loop without external models', async ({ request }) => {
  test.skip(process.env.E2E_API_FLOW !== 'true', 'enabled by the isolated Mock Compose CI job');
  const api = process.env.E2E_API_URL || 'http://localhost:18000/api/v1';
  const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const post = async (path, data) => {
    const response = await request.post(`${api}${path}`, { data });
    expect(response.ok(), `${path}: ${await response.text()}`).toBe(true);
    return response.json();
  };

  const project = await post('/projects', {
    name: 'Mock E2E',
    slug: `mock-e2e-${suffix}`,
    universe_namespace: `mock-${suffix}`,
  });
  const page = await post('/concept-pages', {
    project_id: project.id,
    title: '검은 등대',
    usage_role: 'DRAFT_SETTING',
    namespace: project.universe_namespace,
    body_json: {
      type: 'doc',
      content: [{ type: 'paragraph', content: [{ type: 'text', text: '등대는 기억을 대가로 항로를 비춘다.' }] }],
    },
    locked_facts: ['등대의 대가는 기억이다.'],
  });
  const recipesResponse = await request.get(`${api}/writing-recipes`);
  const recipes = await recipesResponse.json();
  const session = await post('/playbook-sessions', {
    project_id: project.id,
    name: 'Mock 전체 흐름',
    concept_slots: { subject: [page.id] },
    writing_recipe_id: recipes[0].id,
    settings_json: { length: 'short', context_depth: 'focused' },
    seed: 42,
  });
  const plan = await post(`/playbook-sessions/${session.id}/plan`, {});
  expect(plan.plan.blocks.length).toBeGreaterThan(0);
  const generated = await post(`/playbook-sessions/${session.id}/generate`, {});
  const documentId = generated.document.id;
  const blocksResponse = await request.get(`${api}/documents/${documentId}/blocks`);
  const blocks = await blocksResponse.json();
  expect(blocks.length).toBeGreaterThan(0);
  const rewrite = await post(`/blocks/${blocks[0].id}/rewrite`, { operation: 'shorter' });
  expect(rewrite.status).toBe('PENDING');
  const applied = await post(`/audits/${rewrite.id}/apply`, {});
  expect(applied.status).toBe('APPLIED');
  const candidates = await post(`/documents/${documentId}/extract-candidates`, {});
  expect(candidates.length).toBeGreaterThan(0);
  const decided = await post(`/candidates/${candidates[0].id}/decide`, {
    decision: 'save_draft',
    reason: 'E2E 사용자 승인',
  });
  expect(decided.status).toBe('ACCEPTED_AS_DRAFT');
  for (const format of ['markdown', 'html', 'json']) {
    const exported = await request.get(`${api}/documents/${documentId}/export`, { params: { format } });
    expect(exported.ok()).toBe(true);
    expect((await exported.body()).length).toBeGreaterThan(20);
  }
});
