import { expect, test } from '@playwright/test';

const routes = [
  ['/', /세계를 선택하고/],
  ['/editor', /설정을 기록하고 연결합니다/],
  ['/playbook', /쓸 대상과 방향을 고르세요/],
  ['/documents', /원고를 문단별로 다듬습니다/],
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

test('a project can be added after projects already exist', async ({ page }, testInfo) => {
  const projectName = `UX 검증 ${testInfo.project.name} ${Date.now()}`;
  await page.goto('/');
  await page.getByRole('button', { name: '+ 새 프로젝트' }).click();
  await page.getByLabel('프로젝트 이름').fill(projectName);
  await page.getByLabel('한 줄 설명').fill('자동 검증 뒤 삭제되는 프로젝트');

  const createdRequestPromise = page.waitForRequest((request) =>
    request.method() === 'POST' && request.url().endsWith('/api/v1/projects')
  );
  await page.getByRole('button', { name: '프로젝트 만들기' }).click();
  const createdRequest = await createdRequestPromise;
  const response = await createdRequest.response();
  expect(response?.status()).toBe(201);
  const project = await response.json();
  await expect(page.getByRole('heading', { name: projectName })).toBeVisible();
  await page.request.delete(`${new URL(createdRequest.url()).origin}/api/v1/projects/${project.id}`);
});

test('project-first workflow exposes understandable controls', async ({ page }) => {
  test.skip(process.env.E2E_EXPECT_DATA !== 'true', 'requires the curated Black Route world project');
  await page.goto('/');
  await expect(page.getByText('원고 작성')).toBeVisible();
  await expect(page.getByText('자료 검색')).toBeVisible();
  await expect(page.getByText('준비됨').first()).toBeVisible();
  await expect(page.getByRole('button', { name: /새 프로젝트/ })).toBeVisible();

  await page.goto('/editor');
  await expect(page.locator('.archive-page-list strong').filter({ hasText: /^검은 등대$/ })).toBeVisible();
  await expect(page.locator('.archive-page-list strong').filter({ hasText: /^기억세$/ })).toBeVisible();
  await expect(page.getByText('연결된 자료')).toBeVisible();
  await expect(page.locator('text=/[0-9a-f]{8}-[0-9a-f]{4}-/')).toHaveCount(0);
  await page.getByRole('button', { name: /글의 방향 규칙/ }).click();
  await expect(page.getByText(/무엇을 쓸지가 아니라/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'AI로 세부 규칙 정리' }).first()).toBeVisible();

  await page.goto('/playbook');
  await expect(page.locator('select[multiple]')).toHaveCount(0);
  await expect(page.getByRole('button', { name: '1. 선택 근거 확인' })).toBeDisabled();
  const lighthouse = page.locator('.concept-choice-card').filter({
    has: page.getByRole('heading', { name: '검은 등대', exact: true }),
  });
  await lighthouse.getByRole('button', { name: '주제로 쓰기' }).click();
  await expect(page.getByText('주제 · 필수').locator('..')).toContainText('검은 등대');
  await expect(page.getByRole('button', { name: '1. 선택 근거 확인' })).toBeEnabled();
  await expect(page.getByRole('button', { name: '3. 원고 작성' })).toBeDisabled();
  await expect(page.getByLabel('시점')).toHaveValue('omniscient');
  await expect(page.getByLabel('시제')).toHaveValue('present');

  await page.getByLabel('시점').selectOption('third_limited');
  await page.getByLabel('시제').selectOption('past');
  const sessionRequestPromise = page.waitForRequest((request) =>
    request.method() === 'POST' && request.url().endsWith('/api/v1/playbook-sessions')
  );
  await page.getByRole('button', { name: '1. 선택 근거 확인' }).click();
  const sessionRequest = await sessionRequestPromise;
  expect(sessionRequest.postDataJSON().settings_json).toMatchObject({
    viewpoint: 'third_limited',
    tense: 'past',
  });
  const sessionResponse = await sessionRequest.response();
  const session = await sessionResponse.json();
  await expect(page.getByRole('button', { name: '✓ 근거 확인됨' })).toBeEnabled();
  await page.request.delete(`${new URL(sessionRequest.url()).origin}/api/v1/playbook-sessions/${session.id}`);
});
