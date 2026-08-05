import { expect, test } from '@playwright/test';

const routes = [
  ['/', /세계를 선택하고/],
  ['/editor', /설정을 기록하고 연결합니다/],
  ['/playbook', /쓸 대상과 방향을 고르세요/],
  ['/documents', /초안을 검토한 뒤 완성 설정을 따로 정합니다/],
  ['/lorebook', /완성된 글만 모아 읽고 보관합니다/],
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
  await page.getByLabel('현재 프로젝트').selectOption({ label: '검은 항로 연대기' });
  await expect(page.locator('.archive-page-list strong').filter({ hasText: /^검은 등대$/ })).toBeVisible();
  await expect(page.locator('.archive-page-list strong').filter({ hasText: /^기억세$/ })).toBeVisible();
  await expect(page.getByText('연결된 자료')).toBeVisible();
  await expect(page.locator('text=/[0-9a-f]{8}-[0-9a-f]{4}-/')).toHaveCount(0);
  await page.getByRole('button', { name: /글의 방향 규칙/ }).click();
  await expect(page.getByText(/무엇을 쓸지가 아니라/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'AI로 세부 규칙 정리' }).first()).toBeVisible();

  await page.goto('/playbook');
  await expect(page.locator('select[multiple]')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: '무엇에 관한 글인가요?' })).toBeVisible();
  await expect(page.getByRole('button', { name: /배경으로 계속/ })).toBeDisabled();
  const lighthouse = page.locator('.wizard-choice-card').filter({
    has: page.getByText('검은 등대', { exact: true }),
  });
  await lighthouse.click();
  await expect(lighthouse).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: /배경으로 계속/ }).click();

  await expect(page.getByRole('heading', { name: /어디서, 어떤 상황에서/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /주제 검은 등대/ })).toBeVisible();
  await expect(page.getByText('지금까지 선택')).toHaveCount(0);
  await expect(page.locator('.wizard-choice-card').filter({ has: page.getByText('검은 등대', { exact: true }) })).toHaveCount(0);
  const recoveryRoom = page.locator('.wizard-choice-card').filter({ has: page.getByText('회수실', { exact: true }) });
  await recoveryRoom.click();
  await page.getByRole('button', { name: /주요 요소로 계속/ }).click();

  await expect(page.getByRole('heading', { name: /꼭 함께 다룰 것은/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /배경 회수실/ })).toBeVisible();
  await expect(page.locator('.wizard-choice-card').filter({ has: page.getByText('회수실', { exact: true }) })).toHaveCount(0);
  const leah = page.locator('.wizard-choice-card').filter({ has: page.getByText('레아 벨', { exact: true }) });
  await leah.click();
  await page.getByRole('button', { name: /갈등·변수로 계속/ }).click();

  await expect(page.getByRole('heading', { name: /긴장과 변화를/ })).toBeVisible();
  await page.getByRole('button', { name: /선택 없이 전개 방향으로/ }).click();
  await expect(page.getByRole('heading', { name: /어떤 방식으로 전개할까요/ })).toBeVisible();
  await page.getByRole('button', { name: /선택 없이 글 형태로/ }).click();

  await expect(page.getByRole('heading', { name: /어떤 형태의 글로/ })).toBeVisible();
  await expect(page.getByLabel('시점')).toHaveValue('omniscient');
  await expect(page.getByLabel('시제')).toHaveValue('present');
  await page.getByLabel('시점').selectOption('third_limited');
  await page.getByLabel('시제').selectOption('past');
  await page.getByRole('button', { name: /확인·작성으로 계속/ }).click();

  await expect(page.getByRole('heading', { name: /선택을 확인하고 원고를/ })).toBeVisible();
  await expect(page.locator('.wizard-review-grid')).toContainText('검은 등대');
  await expect(page.locator('.wizard-review-grid')).toContainText('회수실');
  await expect(page.locator('.wizard-review-grid')).toContainText('레아 벨');
  await expect(page.getByRole('button', { name: '초안 작성', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: '사용할 설정 확인 설명' }).click();
  await expect(page.getByRole('tooltip').first()).toBeVisible();
  await expect(page.getByRole('tooltip').first()).toContainText('AI가 사실로 쓸 내용');
  const sessionRequestPromise = page.waitForRequest((request) =>
    request.method() === 'POST' && request.url().endsWith('/api/v1/playbook-sessions')
  );
  await page.getByRole('button', { name: '사용할 설정 확인', exact: true }).click();
  const sessionRequest = await sessionRequestPromise;
  expect(sessionRequest.postDataJSON().settings_json).toMatchObject({
    viewpoint: 'third_limited',
    tense: 'past',
  });
  const sessionResponse = await sessionRequest.response();
  const session = await sessionResponse.json();
  await expect(page.getByRole('button', { name: '✓ 사용할 설정 확인됨' })).toBeEnabled();
  await expect(page.getByRole('heading', { name: '이 글이 참고할 세계관' })).toBeVisible();
  await page.request.delete(`${new URL(sessionRequest.url()).origin}/api/v1/playbook-sessions/${session.id}`);
});

test('document workflow separates draft editing, editable final settings, and lorebook', async ({ page }) => {
  test.skip(process.env.E2E_EXPECT_DATA !== 'true', 'requires the curated Black Route draft');
  await page.goto('/documents');
  await page.getByLabel('현재 프로젝트').selectOption({ label: '검은 항로 연대기' });
  await expect(page.locator('.document-wizard-progress').getByRole('button', { name: /초안 편집/ })).toBeVisible();
  await expect(page.locator('.document-wizard-progress').getByRole('button', { name: /완성 설정/ })).toBeVisible();
  await expect(page.locator('.document-wizard-progress').getByRole('button', { name: /완성본 만들기/ })).toBeVisible();
  await page.getByRole('button', { name: /완성 설정으로 계속/ }).click();
  await expect(page.getByRole('heading', { name: '완성본의 글 형태를 다시 정하세요.' })).toBeVisible();
  await expect(page.getByLabel('결과물')).toHaveValue('video_narration');
  await page.getByLabel('시점').selectOption('first_observer');
  await page.getByLabel('시제').selectOption('present');
  await page.getByLabel('이번 완성본의 집필 지시').fill('완성 단계에서 바꾼 지시');
  await page.getByRole('button', { name: /설정 확인으로 계속/ }).click();
  await expect(page.getByText('1인칭 관찰자 · 현재형 중심')).toBeVisible();
  await expect(page.getByText('완성 단계에서 바꾼 지시')).toBeVisible();
  await expect(page.getByText('완성본은 로어북에 별도 저장됩니다.')).toBeVisible();
  await expect(page.getByRole('button', { name: /로어북에 저장/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);

  await page.goto('/lorebook');
  await page.getByLabel('현재 프로젝트').selectOption({ label: '검은 항로 연대기' });
  await expect(page.getByRole('heading', { name: '완성된 글만 모아 읽고 보관합니다.' })).toBeVisible();
});
