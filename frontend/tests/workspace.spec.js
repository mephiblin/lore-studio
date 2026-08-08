import { expect, test } from '@playwright/test';

const routes = ['/', '/editor', '/playbook', '/documents', '/lorebook'];

async function expectStepHelp(page, label, text) {
  await page.getByLabel(label).click();
  await expect(page.getByRole('tooltip').filter({ hasText: text })).toBeVisible();
}

for (const route of routes) {
  test(`${route} renders without browser or API errors`, async ({ page }) => {
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('response', (response) => {
      if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`);
    });
    await page.goto(route);
    if (route === '/') {
      await expect(page.getByRole('heading', { level: 1 })).toContainText(/세계를 선택하고/);
    } else {
      await expect(page.getByLabel('현재 프로젝트')).toBeVisible();
    }
    await expect.poll(() => errors).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(await page.locator('.app-nav').evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    if (await page.locator('.wizard-progress').count()) {
      expect(await page.locator('.wizard-progress').evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    }
  });
}

test('desktop navigation collapses, persists, and gives the workspace more room', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'desktop sidebar check only');
  await page.goto('/editor');
  const shell = page.locator('.app-shell');
  const expandedMainWidth = (await page.locator('.app-main').boundingBox()).width;
  const expandedWidth = (await page.locator('.app-nav').boundingBox()).width;
  await page.getByRole('button', { name: '주요 메뉴 접기' }).click();
  await expect(shell).toHaveClass(/nav-collapsed/);
  await expect(page.getByRole('button', { name: '주요 메뉴 펼치기' })).toBeVisible();
  await expect(page.locator('.app-nav')).toHaveCSS('width', '64px');
  const collapsedWidth = (await page.locator('.app-nav').boundingBox()).width;
  const collapsedMainWidth = (await page.locator('.app-main').boundingBox()).width;
  expect(collapsedWidth).toBeLessThan(expandedWidth);
  expect(collapsedMainWidth).toBeGreaterThan(expandedMainWidth);
  await page.reload();
  await expect(shell).toHaveClass(/nav-collapsed/);
  await page.getByRole('button', { name: '주요 메뉴 펼치기' }).click();
});

test('desktop workspaces keep the browser page fixed and scroll inside their main panels', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'desktop workspace check only');
  await page.goto('/editor');
  await expect(page.locator('.workspace-main')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight)).toBe(true);
  const workspace = await page.locator('.workspace-page').boundingBox();
  expect(workspace.height).toBeLessThanOrEqual(900);

  await page.goto('/lorebook');
  expect(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight)).toBe(true);
  const shelf = await page.locator('.lorebook-shelf').boundingBox();
  const reader = await page.locator('.lorebook-reader').boundingBox();
  expect(shelf.y).toBe(reader.y);
});

test('world material editor keeps writing primary and metadata compact', async ({ page }, testInfo) => {
  test.skip(process.env.E2E_EXPECT_DATA !== 'true', 'requires the curated Diablo project');
  test.skip(testInfo.project.name !== 'desktop', 'desktop editor desk check only');
  await page.goto('/editor');
  await page.getByLabel('현재 프로젝트').selectOption({ label: 'Diablo' });

  const commandbar = page.locator('.editor-commandbar');
  await expect(commandbar.getByRole('navigation', { name: '세계관 자료 관리' })).toBeVisible();
  await expect(commandbar.getByLabel('현재 프로젝트')).toBeVisible();
  await expect(page.getByLabel('자료 제목')).toBeEditable();
  await expect(page.getByLabel('한 줄 요약')).toBeEditable();
  await expect(page.locator('.archive-inspector').getByLabel('시대')).toHaveCount(0);
  await expect(page.locator('.archive-inspector').getByLabel('연속성')).toHaveCount(0);
  await expect(page.locator('.archive-page-list .badge')).toHaveCount(0);

  const bodyScroll = await page.locator('.editor-content').evaluate((element) => ({
    client: element.clientHeight,
    scroll: element.scrollHeight,
    overflow: getComputedStyle(element).overflowY,
  }));
  expect(bodyScroll.scroll).toBeGreaterThan(bodyScroll.client);
  expect(bodyScroll.overflow).toBe('auto');

  const relation = page.locator('.relation-card').first();
  await expect(relation).toBeVisible();
  await expect(relation).not.toContainText('이 자료 —');
  await expect(relation).not.toContainText(/HOME_OF|CULMINATES_IN|CONTAINS|INHABITS|SERVES/);
});

test('small mobile navigation and workflow steps stay inside the viewport', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'small-viewport check only');
  await page.setViewportSize({ width: 360, height: 844 });
  for (const route of ['/editor', '/playbook', '/documents']) {
    await page.goto(route);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(await page.locator('.app-nav').evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    if (await page.locator('.wizard-progress').count()) {
      expect(await page.locator('.wizard-progress').evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    }
  }
});

test('mobile project creator stays above navigation and closes without data loss', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'mobile dialog check only');
  await page.goto('/');
  await expect(page.getByText('연결 상태 확인 중…')).toBeHidden();
  await page.getByRole('button', { name: '+ 새 프로젝트' }).click();
  const dialog = page.getByRole('dialog', { name: '새 프로젝트 만들기' });
  await expect(dialog).toBeVisible();
  const bounds = await dialog.boundingBox();
  expect(bounds.x).toBeGreaterThanOrEqual(0);
  expect(bounds.y).toBeGreaterThanOrEqual(0);
  expect(bounds.x + bounds.width).toBeLessThanOrEqual(390);
  expect(bounds.y + bounds.height).toBeLessThanOrEqual(844 - 61);
  await page.getByLabel('프로젝트 이름').fill('닫기 검증');
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
});

test('dense Diablo materials stay bounded and use its project taxonomy', async ({ page }, testInfo) => {
  test.skip(process.env.E2E_EXPECT_DATA !== 'true', 'requires the curated Diablo project');
  const browserErrors = [];
  page.on('pageerror', (error) => browserErrors.push(error.message));

  await page.goto('/editor');
  await page.getByLabel('현재 프로젝트').selectOption({ label: 'Diablo' });
  await page.getByLabel('종류 필터').selectOption({ label: '일반 몬스터 종족' });
  await expect(page.locator('.archive-page-list button').first()).toBeVisible();
  expect(await page.locator('.archive-page-list button').count()).toBeGreaterThan(10);
  await expect(page.locator('.archive-page-list button').first()).toContainText('일반 몬스터 종족');
  if (testInfo.project.name === 'desktop') {
    const list = await page.locator('.archive-list').boundingBox();
    expect(list.height).toBeLessThanOrEqual(900 - 45);
    expect(await page.locator('.archive-page-list').evaluate((element) => element.scrollHeight > element.clientHeight)).toBe(true);
  }

  await page.goto('/playbook');
  await page.getByLabel('현재 프로젝트').selectOption({ label: 'Diablo' });
  await expect(page.getByText('이 단계의 추천 자료')).toBeVisible();
  expect(await page.locator('.wizard-choice-card').count()).toBeLessThanOrEqual(18);
  if (testInfo.project.name === 'mobile') {
    const grid = await page.locator('.wizard-card-grid').boundingBox();
    expect(grid.height).toBeLessThanOrEqual(461);
    expect(await page.locator('.wizard-card-grid').evaluate((element) => element.scrollHeight > element.clientHeight)).toBe(true);
  }
  await page.getByRole('button', { name: '전체', exact: true }).click();
  await expect(page.getByText('모든 세계관 자료')).toBeVisible();
  await page.getByLabel('자료 종류').selectOption({ label: '일반 몬스터 종족' });
  await expect(page.locator('.wizard-choice-card').first()).toContainText('일반 몬스터 종족');
  await page.locator('.wizard-choice-card').first().click();
  await page.getByRole('button', { name: /배경으로 계속/ }).click();
  await expectStepHelp(page, '배경 단계 설명', '어디서, 어떤 상황에서');
  await expect.poll(() => browserErrors).toEqual([]);
});

test('lorebook defaults to reading and edit mode is reversible', async ({ page }) => {
  test.skip(process.env.E2E_EXPECT_DATA !== 'true', 'requires a Diablo lorebook entry');
  await page.goto('/lorebook');
  await page.getByLabel('현재 프로젝트').selectOption({ label: 'Diablo' });
  await expect(page.locator('.lorebook-body-reader')).toBeVisible();
  await expect(page.getByLabel('로어북 글 제목')).toHaveCount(0);
  await page.getByRole('button', { name: '글 편집' }).click();
  await expect(page.getByLabel('로어북 글 제목')).toBeVisible();
  await expect(page.getByLabel('로어북 글 내용')).toHaveJSProperty('tagName', 'TEXTAREA');
  await page.getByRole('button', { name: '취소' }).click();
  await expect(page.locator('.lorebook-body-reader')).toBeVisible();
  await expect(page.getByLabel('로어북 글 제목')).toHaveCount(0);
});

test('a project can be added after projects already exist', async ({ page }, testInfo) => {
  const projectName = `UX 검증 ${testInfo.project.name} ${Date.now()}`;
  await page.goto('/');
  await expect(page.getByText('연결 상태 확인 중…')).toBeHidden();
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

  await page.goto('/editor');
  await page.getByLabel('현재 프로젝트').selectOption({ label: projectName });
  await page.getByRole('navigation', { name: '세계관 자료 관리' }).getByRole('button', { name: /^자료 종류/ }).click();
  await expect(page.locator('.category-intro')).toHaveCount(0);
  await expect(page.locator('.category-settings-row')).toHaveCount(5);
  await expectStepHelp(page, '자료 종류 설명', '자료 종류는 프로젝트별 분류');
  await page.getByText('새 자료 종류 만들기', { exact: true }).click();
  await expect(page.getByLabel('새 자료 종류 이름')).toBeVisible();
  await page.getByLabel('새 자료 종류 이름').fill('세력');
  await page.getByRole('button', { name: '자료 종류 만들기' }).click();
  await expect(page.getByText("'세력' 자료 종류를 만들었습니다.")).toBeVisible();
  await page.getByRole('button', { name: /세계관 자료/ }).click();
  await page.getByRole('button', { name: '+ 새 자료' }).click();
  await expect(page.getByLabel('자료 종류')).toContainText('세력');

  await page.request.delete(`${new URL(createdRequest.url()).origin}/api/v1/projects/${project.id}`);
});

test('project-first workflow exposes understandable controls', async ({ page }, testInfo) => {
  test.skip(process.env.E2E_EXPECT_DATA !== 'true', 'requires the curated Black Route world project');
  await page.goto('/');
  if (testInfo.project.name === 'mobile') {
    await expect(page.locator('.model-board').getByText('실제 연결')).toBeVisible();
    await expect(page.getByRole('heading', { name: '어느 세계에서 작업할까요?' })).toBeVisible();
  } else {
    await expect(page.getByText('글 작성')).toBeVisible();
    await expect(page.getByText('자료 검색')).toBeVisible();
    await expect(page.getByText('준비됨').first()).toBeVisible();
  }
  await expect(page.getByRole('button', { name: /새 프로젝트/ })).toBeVisible();

  await page.goto('/editor');
  await page.getByLabel('현재 프로젝트').selectOption({ label: '검은 항로 연대기' });
  await expect(page.locator('.archive-page-list strong').filter({ hasText: /^검은 등대$/ })).toBeVisible();
  await expect(page.locator('.archive-page-list strong').filter({ hasText: /^기억세$/ })).toBeVisible();
  const lighthousePage = page.locator('.archive-page-list button').filter({ has: page.getByText('검은 등대', { exact: true }) });
  const memoryTaxPage = page.locator('.archive-page-list button').filter({ has: page.getByText('기억세', { exact: true }) });
  await lighthousePage.click();
  await expect(page.locator('.editor-content')).toContainText('통과에는 대가가 필요하다');
  await memoryTaxPage.click();
  await expect(memoryTaxPage).toHaveClass(/active/);
  await expect(page.locator('.manuscript-toolbar').getByLabel('자료 제목')).toHaveValue('기억세');
  await expect(page.locator('.editor-content')).toContainText('기억세는 돈이 아니라 손실 가능성을 시민에게 배분하는 제도다');
  await expect(page.locator('.editor-content')).not.toContainText('통과에는 대가가 필요하다');
  if (testInfo.project.name === 'mobile') {
    await expect.poll(() => page.locator('.manuscript-panel').evaluate((element) => Math.round(element.getBoundingClientRect().top))).toBeLessThan(120);
  }
  await expect(page.getByText('연결된 자료')).toBeVisible();
  await expect(page.locator('text=/[0-9a-f]{8}-[0-9a-f]{4}-/')).toHaveCount(0);
  await page.getByRole('navigation', { name: '세계관 자료 관리' }).getByRole('button', { name: /^집필 지침/ }).click();
  await expect(page.locator('.direction-intro')).toHaveCount(0);
  await expectStepHelp(page, '집필 지침 설명', '반복해 지킬 강조점');
  await expect(page.getByRole('button', { name: 'AI로 세부 규칙 정리' }).first()).toBeVisible();

  await page.goto('/playbook');
  await expect(page.locator('select[multiple]')).toHaveCount(0);
  await expect(page.locator('.wizard-heading')).toHaveCount(0);
  await expectStepHelp(page, '주제 단계 설명', '무엇에 관한 글인가요?');
  await expect(page.getByRole('button', { name: /배경으로 계속/ })).toBeDisabled();
  const lighthouse = page.locator('.wizard-choice-card').filter({
    has: page.getByText('검은 등대', { exact: true }),
  });
  await lighthouse.click();
  await expect(lighthouse).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: /배경으로 계속/ }).click();

  await expectStepHelp(page, '배경 단계 설명', '어디서, 어떤 상황에서');
  await expect(page.getByRole('button', { name: /주제 검은 등대/ })).toBeVisible();
  await expect(page.getByText('지금까지 선택')).toHaveCount(0);
  await expect(page.locator('.wizard-choice-card').filter({ has: page.getByText('검은 등대', { exact: true }) })).toHaveCount(0);
  const recoveryRoom = page.locator('.wizard-choice-card').filter({ has: page.getByText('회수실', { exact: true }) });
  await recoveryRoom.click();
  await page.getByRole('button', { name: /주요 요소로 계속/ }).click();

  await expectStepHelp(page, '주요 요소 단계 설명', '꼭 함께 다룰 것은');
  await expect(page.getByRole('button', { name: /배경 회수실/ })).toBeVisible();
  await expect(page.locator('.wizard-choice-card').filter({ has: page.getByText('회수실', { exact: true }) })).toHaveCount(0);
  const leah = page.locator('.wizard-choice-card').filter({ has: page.getByText('레아 벨', { exact: true }) });
  await leah.click();
  await page.getByRole('button', { name: /갈등·변수로 계속/ }).click();

  await expectStepHelp(page, '갈등·변수 단계 설명', '무엇이 긴장과 변화를');
  await page.getByRole('button', { name: /선택 없이 집필 지침으로/ }).click();
  await expectStepHelp(page, '집필 지침 단계 설명', '이번 글에서 무엇을 강조하거나 피할까요');
  await page.getByRole('button', { name: /선택 없이 전개 방식으로/ }).click();

  await expectStepHelp(page, '전개 방식 단계 설명', '글을 어떤 방식으로 풀어갈까요');
  const causalPattern = page.locator('.recipe-option').filter({ hasText: '원인에서 파급으로' });
  await causalPattern.click();
  await expect(causalPattern).toHaveAttribute('aria-pressed', 'true');
  await expect(causalPattern).toContainText('시작 원인');
  await expect(causalPattern).toContainText('사회의 파급');
  await page.getByRole('button', { name: /결과물 형태로 계속/ }).click();

  await expectStepHelp(page, '결과물 형태 단계 설명', '어떤 결과물로 만들까요');
  await expect(page.getByLabel('시점')).toHaveValue('omniscient');
  await expect(page.getByLabel('시제')).toHaveValue('present');
  await page.getByLabel('시점').selectOption('third_limited');
  await page.getByLabel('시제').selectOption('past');
  await page.getByRole('button', { name: /확인·작성으로 계속/ }).click();

  await expectStepHelp(page, '확인·작성 단계 설명', '선택을 확인하고 초안을 만드세요');
  await expect(page.locator('.wizard-review-grid')).toContainText('검은 등대');
  await expect(page.locator('.wizard-review-grid')).toContainText('회수실');
  await expect(page.locator('.wizard-review-grid')).toContainText('레아 벨');
  await expect(page.locator('.wizard-review-grid')).toContainText('전개 방식');
  await expect(page.locator('.wizard-review-grid')).toContainText('원인에서 파급으로');
  await expect(page.getByRole('button', { name: '초안 작성', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: '사용할 설정 확인 설명' }).click();
  await expect(page.getByRole('tooltip').filter({ hasText: 'AI가 사실로 쓸 내용' })).toBeVisible();
  const sessionRequestPromise = page.waitForRequest((request) =>
    request.method() === 'POST' && request.url().endsWith('/api/v1/playbook-sessions')
  );
  await page.getByRole('button', { name: '사용할 설정 확인', exact: true }).click();
  const sessionRequest = await sessionRequestPromise;
  expect(sessionRequest.postDataJSON().settings_json).toMatchObject({
    viewpoint: 'third_limited',
    tense: 'past',
  });
  expect(sessionRequest.postDataJSON().writing_recipe_id).toBeTruthy();
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
  await expect(page.locator('.document-wizard-progress .wizard-step-button').filter({ hasText: '초안 편집' })).toBeVisible();
  await expect(page.locator('.document-wizard-progress .wizard-step-button').filter({ hasText: '완성 설정' })).toBeVisible();
  await expect(page.locator('.document-wizard-progress .wizard-step-button').filter({ hasText: '완성본 만들기' })).toBeVisible();
  await expect(page.locator('.wizard-heading')).toHaveCount(0);
  await page.getByRole('button', { name: /완성 설정으로 계속/ }).click();
  await expectStepHelp(page, '완성 설정 단계 설명', '완성본의 결과물 형태를 다시 정하세요.');
  await expect(page.getByLabel('전개 방식')).toBeVisible();
  await expect(page.getByLabel('결과물 종류')).toHaveValue('video_narration');
  await page.getByLabel('시점').selectOption('first_observer');
  await page.getByLabel('시제').selectOption('present');
  await page.getByLabel('완성본의 추가 지시').fill('완성 단계에서 바꾼 지시');
  await page.getByRole('button', { name: /설정 확인으로 계속/ }).click();
  await expect(page.getByText('1인칭 관찰자 · 현재형 중심')).toBeVisible();
  await expect(page.getByText('완성 단계에서 바꾼 지시')).toBeVisible();
  await expect(page.getByText('완성본은 로어북에 별도 저장됩니다.')).toBeVisible();
  await expect(page.getByRole('button', { name: /로어북에 저장/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);

  await page.goto('/lorebook');
  await page.getByLabel('현재 프로젝트').selectOption({ label: '검은 항로 연대기' });
  await expect(page.getByRole('heading', { name: '책장' })).toBeVisible();
});

test('draft edits and a new paragraph are saved before moving to final settings', async ({ page }, testInfo) => {
  test.skip(process.env.E2E_EXPECT_DATA !== 'true', 'requires the curated Black Route draft');
  test.skip(testInfo.project.name !== 'desktop', 'mutates and restores one curated draft');
  test.setTimeout(60_000);
  const apiBase = 'http://localhost:18000/api/v1';
  const marker = `자동 저장 검증 ${Date.now()}`;

  await page.goto('/documents');
  const blackProjectId = await page.getByLabel('현재 프로젝트').locator('option', { hasText: '검은 항로 연대기' }).getAttribute('value');
  const documentsResponsePromise = page.waitForResponse((response) => {
    const url = new URL(response.url());
    return url.pathname.endsWith('/api/v1/documents') && url.searchParams.get('project_id') === blackProjectId;
  });
  await page.getByLabel('현재 프로젝트').selectOption({ label: '검은 항로 연대기' });
  const projectDocuments = await (await documentsResponsePromise).json();
  const documentId = projectDocuments[0].id;
  await expect(page.getByLabel(/작업할 초안/)).toHaveValue(documentId);
  await expect(page.getByLabel('초안 제목')).toHaveValue(projectDocuments[0].title);
  const originalDocument = await (await page.request.get(`${apiBase}/documents/${documentId}`)).json();
  const originalBlocks = await (await page.request.get(`${apiBase}/documents/${documentId}/blocks`)).json();

  try {
    await page.getByLabel('초안 제목').fill(`${originalDocument.title} · ${marker}`);
    await page.getByLabel('1번 문단 내용').fill(`${originalBlocks[0].content_markdown}\n\n${marker}`);
    await page.getByRole('button', { name: '+ 새 문단 추가' }).click();
    await page.getByLabel(`${originalBlocks.length + 1}번 문단 내용`).fill(`${marker} 새 문단`);
    await expect(page.getByText('저장 안 됨')).toBeVisible();

    const saveRequestPromise = page.waitForRequest((request) =>
      request.method() === 'PATCH' && request.url().endsWith(`/documents/${documentId}/draft`)
    );
    await page.getByRole('button', { name: /저장하고 완성 설정으로 계속/ }).click();
    const saveRequest = await saveRequestPromise;
    expect(saveRequest.postDataJSON().blocks).toHaveLength(originalBlocks.length + 1);
    expect((await saveRequest.response()).status()).toBe(200);
    await expectStepHelp(page, '완성 설정 단계 설명', '완성본의 결과물 형태를 다시 정하세요.');

    await page.reload();
    await expect(page.getByLabel('초안 제목')).toHaveValue(`${originalDocument.title} · ${marker}`);
    await expect(page.getByLabel('1번 문단 내용')).toHaveValue(new RegExp(marker));
    await expect(page.getByLabel(`${originalBlocks.length + 1}번 문단 내용`)).toHaveValue(`${marker} 새 문단`);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  } finally {
    await page.request.patch(`${apiBase}/documents/${documentId}/draft`, {
      data: {
        title: originalDocument.title,
        status: originalDocument.status,
        blocks: originalBlocks.map((block) => ({
          id: block.id,
          content_markdown: block.content_markdown,
          rhetorical_move: block.rhetorical_move,
          evidence_ids: block.evidence_ids,
          certainty: block.certainty,
          locked: block.locked,
        })),
      },
    });
  }
});
