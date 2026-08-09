import { expect, test } from '@playwright/test';

const routes = ['/', '/editor', '/playbook', '/documents', '/lorebook'];

async function expectStepHelp(page, label, text) {
  await page.getByLabel(label).click();
  const tooltip = page.getByRole('tooltip').filter({ hasText: text });
  await expect(tooltip).toBeVisible();
  await expect(tooltip).toHaveCSS('position', 'fixed');
  const box = await tooltip.boundingBox();
  const viewport = page.viewportSize();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(viewport.width);
  expect(box.y + box.height).toBeLessThanOrEqual(viewport.height);
}

async function expectWorkspaceDialog(page, name) {
  const dialog = page.getByRole('dialog', { name });
  await expect(dialog).toBeVisible();
  const box = await dialog.boundingBox();
  const viewport = page.viewportSize();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(viewport.width);
  expect(box.y + box.height).toBeLessThanOrEqual(viewport.height);
  await expect(dialog.locator('footer')).toBeVisible();
  return dialog;
}

async function removeProjectFixture(request, apiOrigin, projectId) {
  const pagesResponse = await request.get(`${apiOrigin}/api/v1/concept-pages?project_id=${projectId}`);
  if (pagesResponse.ok()) {
    for (const conceptPage of await pagesResponse.json()) {
      await request.delete(`${apiOrigin}/api/v1/concept-pages/${conceptPage.id}`);
    }
  }
  const projectResponse = await request.delete(`${apiOrigin}/api/v1/projects/${projectId}`);
  expect(projectResponse.status()).toBe(204);
}

for (const route of routes) {
  test(`${route} renders without browser or API errors`, async ({ page }, testInfo) => {
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
    if (route === '/playbook') {
      await expect(page.locator('.page-tools > nav[aria-label="글 만들기 선택 단계"]')).toBeVisible();
      await expect(page.locator('.wizard-shell > nav[aria-label="글 만들기 선택 단계"]')).toHaveCount(0);
      await expect(page.locator('.wizard-layout')).toHaveCSS('padding', '0px');
      const navigation = page.locator('.playbook-page > .playbook-navigation');
      await expect(navigation).toBeVisible();
      await expect(page.locator('.playbook-workspace .wizard-actions')).toHaveCount(0);
      expect(parseFloat(await navigation.evaluate((element) => getComputedStyle(element).paddingTop))).toBeLessThanOrEqual(10);
      const navigationBox = await navigation.boundingBox();
      expect(navigationBox.height).toBeLessThanOrEqual(65);
      expect(navigationBox.y + navigationBox.height).toBeLessThanOrEqual(page.viewportSize().height);
      if (testInfo.project.name === 'mobile') {
        const appNavBox = await page.locator('.app-nav').boundingBox();
        expect(navigationBox.y + navigationBox.height).toBeLessThanOrEqual(appNavBox.y + 1);
        await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
      } else {
        await page.locator('.playbook-workspace').evaluate((element) => element.scrollTop = element.scrollHeight);
      }
      const navigationAfterScroll = await navigation.boundingBox();
      expect(Math.abs(navigationAfterScroll.y - navigationBox.y)).toBeLessThanOrEqual(1);
    }
    if (route === '/documents') {
      await expect(page.locator('.page-tools > nav[aria-label="원고 완성 단계"]')).toBeVisible();
      await expect(page.locator('.document-workflow > nav[aria-label="원고 완성 단계"]')).toHaveCount(0);
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
  await expect(page.getByLabel('세계관 자료 본문')).toBeVisible();
  await expect(page.getByLabel('자료 제목')).toHaveCount(0);
  await page.getByRole('button', { name: '글 편집' }).click();
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

test('voice profiles use a local tab and a bounded review modal', async ({ page }) => {
  await page.goto('/editor');
  const voiceTab = page.getByRole('button', { name: /문체·필력/ }).first();
  await voiceTab.click();
  await expect(page.getByRole('heading', { name: '문체·필력' })).toBeVisible();
  const voiceManager = page.locator('.voice-manager');
  const voiceList = page.locator('.voice-profile-list');
  await expect(voiceManager).toHaveCSS('display', 'grid');
  await expect(voiceManager).toHaveCSS('gap', '10px');
  await expect(voiceList).toBeVisible();
  if (page.viewportSize().width > 820) {
    expect((await voiceManager.boundingBox()).height).toBeGreaterThan(500);
    await expect(voiceList).toHaveCSS('overflow-y', 'auto');
  }
  await page.getByRole('button', { name: '+ 새 문체 프로필' }).click();
  const dialog = await expectWorkspaceDialog(page, '새 문체 프로필');
  await expect(dialog.getByLabel('사용 범위')).toHaveValue('PROJECT');
  await expect(dialog.getByRole('button', { name: '검토본 만들기' })).toBeDisabled();
  await dialog.getByRole('button', { name: '취소' }).click();
  await expect(dialog).toBeHidden();
});

test('dense voice profile galleries preserve card height and scroll inside the workspace', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'desktop bounded gallery check only');
  const profiles = Array.from({ length: 100 }, (_, index) => ({
    id: `dense-voice-${index}`,
    project_id: 'dense-audit-project',
    name: `밀도 검증 문체 ${String(index + 1).padStart(3, '0')}`,
    description: '문장 호흡과 묘사 밀도를 검증하는 표시 자료',
    status: 'DRAFT',
    version: 1,
    is_builtin: false,
    profile_json: {
      reader_effect: '절제된 긴장',
      sentence_rhythm: '중간 호흡',
      sensory_balance: '시각보다 촉각',
      dialogue_style: '짧고 간접적',
    },
  }));
  await page.route('**/api/v1/voice-profiles?**', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(profiles),
  }));

  await page.goto('/editor');
  await page.getByRole('button', { name: /문체·필력/ }).first().click();
  const gallery = page.locator('.voice-profile-list');
  const firstCard = gallery.locator('.voice-profile-card').first();
  const fifthCard = gallery.locator('.voice-profile-card').nth(4);
  await expect(gallery.locator('.voice-profile-card')).toHaveCount(100);
  const galleryMetrics = await gallery.evaluate((element) => ({
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight,
    overflow: getComputedStyle(element).overflowY,
  }));
  expect(galleryMetrics.scrollHeight).toBeGreaterThan(galleryMetrics.clientHeight);
  expect(galleryMetrics.overflow).toBe('auto');
  const firstBox = await firstCard.boundingBox();
  const fifthBox = await fifthCard.boundingBox();
  expect(firstBox.height).toBeGreaterThan(180);
  expect(firstBox.width).toBeLessThanOrEqual(305);
  expect(fifthBox.y).toBeGreaterThanOrEqual(firstBox.y + firstBox.height);
});

test('world material AI edits stay reviewable and use temporary references', async ({ page }) => {
  test.skip(process.env.E2E_EXPECT_DATA !== 'true', 'requires the curated Black Route world project');

  await page.route('**/api/v1/concept-pages/*/ai/rewrite-selection', async (route) => {
    const payload = route.request().postDataJSON();
    expect(payload.operation).toBe('longer');
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: 'rewrite-run',
        concept_page_id: 'page',
        mode: 'rewrite_selection',
        status: 'CANDIDATE',
        persisted: false,
        base_body_hash: 'test',
        original_text: payload.selection_text,
        proposed_text: '기억세는 손실 가능성을 시민에게 나누어 지우는 제도다.',
        selection_from: payload.selection_from,
        selection_to: payload.selection_to,
        source_page_ids: payload.source_page_ids,
        warnings: []
      })
    });
  });
  await page.route('**/api/v1/concept-pages/*/ai/draft', async (route) => {
    const payload = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: 'draft-run',
        concept_page_id: 'page',
        mode: 'draft',
        status: 'CANDIDATE',
        persisted: false,
        base_body_hash: 'test',
        original_text: '',
        proposed_text: '## 징수 뒤의 흔적\n\n시민은 잃을 가능성까지 장부에 남긴다.',
        source_page_ids: payload.source_page_ids,
        warnings: ['저장 전 검토가 필요합니다.']
      })
    });
  });

  await page.goto('/editor');
  await page.getByLabel('현재 프로젝트').selectOption({ label: '검은 항로 연대기' });
  const memoryTaxPage = page.locator('.archive-page-list button').filter({ has: page.getByText('기억세', { exact: true }) });
  await memoryTaxPage.click();
  await expect(page.locator('.relation-card').first()).toBeVisible();
  await page.getByRole('button', { name: '글 편집' }).click();

  const rewriteButton = page.getByRole('button', { name: 'AI 수정' });
  await expect(rewriteButton).toBeDisabled();
  await page.locator('.ProseMirror').click();
  await page.keyboard.press('Control+A');
  await expect(rewriteButton).toBeEnabled();
  await rewriteButton.click();
  const rewritePanel = page.getByRole('form', { name: '선택 영역 AI 수정' });
  await expect(rewritePanel).toBeVisible();
  await expect(rewritePanel).toContainText('연결된 자료');
  await rewritePanel.getByLabel('수정 방식').selectOption('longer');
  await expect(rewritePanel.getByLabel('수정 방식')).toContainText('더 자세히 (약 2배)');
  await rewritePanel.getByRole('button', { name: '수정 제안' }).click();

  const proposal = page.getByRole('region', { name: 'AI 본문 제안' });
  await expect(proposal).toContainText('기억세는 손실 가능성을 시민에게 나누어 지우는 제도다.');
  await expect(proposal.locator('.proposal-copy pre')).toHaveCSS('background-color', 'rgb(20, 50, 46)');
  await expect(proposal.locator('.proposal-copy pre')).toHaveCSS('color', 'rgb(240, 188, 101)');
  await expect(page.locator('.editor-content')).not.toContainText('시민에게 나누어 지우는 제도다');
  await proposal.getByRole('button', { name: '본문에 반영' }).click();
  await expect(page.locator('.editor-content')).toContainText('시민에게 나누어 지우는 제도다');
  await expect(page.getByText('아직 저장되지 않았습니다.')).toBeVisible();

  await page.getByRole('button', { name: 'AI 작성' }).click();
  const dialog = page.getByRole('dialog', { name: 'AI 작성' });
  await expect(dialog).toBeVisible();
  const dialogBounds = await dialog.boundingBox();
  const viewport = page.viewportSize();
  expect(dialogBounds.x).toBeGreaterThanOrEqual(0);
  expect(dialogBounds.y).toBeGreaterThanOrEqual(0);
  expect(dialogBounds.x + dialogBounds.width).toBeLessThanOrEqual(viewport.width);
  expect(dialogBounds.y + dialogBounds.height).toBeLessThanOrEqual(viewport.height);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await expect(dialog).toContainText('이번 작성에만 사용');
  expect(await dialog.locator('.source-list label.selected').count()).toBeGreaterThan(0);
  await dialog.getByLabel('무엇을 작성할까요?').fill('기억세 징수 뒤의 흔적을 설명해 줘.');
  await dialog.getByText('이어쓰기', { exact: true }).click();
  await dialog.getByRole('button', { name: '초안 제안' }).click();
  await expect(proposal).toContainText('징수 뒤의 흔적');
  await proposal.getByRole('button', { name: '본문에 반영' }).click();
  await expect(page.locator('.editor-content')).toContainText('시민은 잃을 가능성까지 장부에 남긴다.');
});

test('small mobile navigation and workflow steps stay inside the viewport', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'small-viewport check only');
  await page.setViewportSize({ width: 360, height: 844 });
  for (const route of ['/editor', '/playbook', '/documents', '/lorebook']) {
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
  await expect(page.locator('.wizard-scope-bar')).toHaveCount(0);
  await expect(page.locator('.scope-switch')).toHaveCount(0);
  expect(await page.locator('.wizard-choice-card').count()).toBeLessThanOrEqual(18);
  if (testInfo.project.name === 'mobile') {
    const grid = await page.locator('.wizard-card-grid').boundingBox();
    expect(grid.height).toBeLessThanOrEqual(461);
    expect(await page.locator('.wizard-card-grid').evaluate((element) => element.scrollHeight > element.clientHeight)).toBe(true);
  } else {
    const firstCard = page.locator('.wizard-choice-card').first();
    const cardBox = await firstCard.boundingBox();
    const coverBox = await firstCard.locator('.wizard-card-cover').boundingBox();
    const copyBox = await firstCard.locator('.wizard-card-copy').boundingBox();
    const metaBox = await firstCard.locator('.wizard-card-meta').boundingBox();
    expect(cardBox.width).toBeLessThanOrEqual(305);
    expect(Math.abs(coverBox.width / coverBox.height - 16 / 9)).toBeLessThan(0.02);
    expect(metaBox.y).toBeGreaterThan(copyBox.y);
    if (await page.getByRole('button', { name: /자료 더 보기/ }).count()) {
      const moreBox = await page.getByRole('button', { name: /자료 더 보기/ }).boundingBox();
      const navigationBox = await page.locator('.playbook-navigation').boundingBox();
      expect(moreBox.y + moreBox.height).toBeLessThanOrEqual(navigationBox.y);
      const fifthCardBox = await page.locator('.wizard-choice-card').nth(4).boundingBox();
      expect(fifthCardBox.y).toBeGreaterThanOrEqual(cardBox.y + cardBox.height);
    }
    const cardTitle = (await firstCard.locator('.wizard-card-copy strong').textContent()).trim();
    const placeholder = firstCard.locator('.project-cover-placeholder > span');
    if (await placeholder.count()) await expect(placeholder).toHaveText(cardTitle.slice(0, 5).toUpperCase());
  }
  await page.getByLabel('자료 종류').selectOption({ label: '일반 몬스터 종족' });
  await expect(page.locator('.wizard-choice-card').first()).toContainText('일반 몬스터 종족');
  await expect(page.locator('.wizard-choice-card').first().locator('.wizard-card-authority small')).toHaveText('사용');
  await expect(page.getByText('정식 설정 근거', { exact: true })).toHaveCount(0);
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
  await expect(page.getByRole('button', { name: '글 삭제' })).toBeVisible();
  await expect(page.getByLabel('로어북 글 제목')).toHaveCount(0);
  await page.getByRole('button', { name: '글 편집' }).click();
  await expect(page.getByLabel('로어북 글 제목')).toBeVisible();
  await expect(page.getByLabel('로어북 글 내용')).toHaveJSProperty('tagName', 'TEXTAREA');
  await page.getByRole('button', { name: '취소' }).click();
  await expect(page.locator('.lorebook-body-reader')).toBeVisible();
  await expect(page.getByLabel('로어북 글 제목')).toHaveCount(0);
});

test('lorebook reading themes switch, persist, and leave content actions unchanged', async ({ page }) => {
  test.skip(process.env.E2E_EXPECT_DATA !== 'true', 'requires a Diablo lorebook entry');
  await page.goto('/lorebook');
  await page.getByLabel('현재 프로젝트').selectOption({ label: 'Diablo' });

  const lorebookPage = page.locator('.lorebook-page');
  const reader = page.getByLabel('로어북 글 내용');
  const originalBody = await reader.textContent();
  const originalMarkdownHref = await page.getByRole('link', { name: 'Markdown' }).getAttribute('href');
  const themes = [
    ['노말', 'normal', null],
    ['판타지아', 'fantasia', 'lorebook-fantasia.webp'],
    ['메카니컬', 'mechanical', 'lorebook-mechanical.webp'],
    ['어반 판타지', 'urban', 'lorebook-urban.webp']
  ];
  const workspaceColors = {
    fantasia: 'rgb(60, 41, 34)',
    mechanical: 'rgb(1, 8, 6)',
    urban: 'rgb(8, 14, 32)'
  };
  const shelfTitleColors = {
    normal: 'rgb(24, 48, 44)',
    fantasia: 'rgb(123, 45, 37)',
    mechanical: 'rgb(125, 255, 164)',
    urban: 'rgb(238, 242, 255)'
  };

  const themeGroup = page.getByRole('group', { name: '로어북 열람 테마' });
  await expect(page.locator('.lorebook-commandbar').getByRole('group', { name: '로어북 열람 테마' })).toBeVisible();
  await expect(page.locator('.lorebook-shelf .lorebook-theme-toolbar')).toHaveCount(0);
  await expect(themeGroup).toBeVisible();
  await expect(page.getByRole('button', { name: '로어북 테마: 노말' })).toHaveAttribute('aria-pressed', 'true');
  for (const [name, id, asset] of themes) {
    await page.getByRole('button', { name: `로어북 테마: ${name}` }).click();
    await expect(lorebookPage).toHaveAttribute('data-lorebook-theme', id);
    await expect(page.getByRole('button', { name: `로어북 테마: ${name}` })).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByRole('heading', { name: '책장' })).toHaveCSS('color', shelfTitleColors[id]);
    await expect(page.getByRole('button', { name: '글 편집' })).toHaveCSS('background-color', 'rgb(20, 50, 46)');
    await expect(page.getByRole('button', { name: '글 편집' })).toHaveCSS('color', 'rgb(240, 188, 101)');
    if (asset) {
      const backgroundImage = await page.locator('.lorebook-sheet').evaluate((node) => getComputedStyle(node).backgroundImage);
      expect(backgroundImage).toContain(asset);
      await expect(page.locator('.workspace-main')).toHaveCSS('background-color', workspaceColors[id]);
    }
    if (id === 'mechanical') {
      const glitchAnimation = await page.locator('.lorebook-sheet').evaluate((node) => getComputedStyle(node, '::after').animationName);
      expect(glitchAnimation).toBe('lorebook-crt-glitch');
    }
  }

  expect(await reader.textContent()).toBe(originalBody);
  await expect(page.getByRole('link', { name: 'Markdown' })).toHaveAttribute('href', originalMarkdownHref);
  await page.reload();
  await expect(lorebookPage).toHaveAttribute('data-lorebook-theme', 'urban');
  await expect(page.getByRole('button', { name: '로어북 테마: 어반 판타지' })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: '글 편집' }).click();
  await expect(page.getByLabel('로어북 글 내용')).toHaveJSProperty('tagName', 'TEXTAREA');
  await expect(page.getByLabel('로어북 글 내용')).toHaveCSS('color', 'rgb(230, 237, 255)');
  await page.getByRole('button', { name: '취소' }).click();
  await page.goto('/documents');
  await expect(page.locator('html')).not.toHaveAttribute('data-lorebook-theme');
});

test('a project can be added after projects already exist', async ({ page }, testInfo) => {
  const projectName = `UX 검증 ${testInfo.project.name} ${Date.now()}`;
  let project = null;
  let apiOrigin = '';
  await page.goto('/');
  try {
    await expect(page.getByText('연결 상태 확인 중…')).toBeHidden();
    await expect(page.getByLabel('작업 흐름')).toHaveCount(0);
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
    project = await response.json();
    apiOrigin = new URL(createdRequest.url()).origin;
    const projectCard = page.locator('.project-card').filter({ has: page.getByRole('heading', { name: projectName }) });
    await expect(projectCard).toBeVisible();
    await expect(projectCard.locator('.project-cover-placeholder > span')).toHaveText(projectName.trim().slice(0, 5).toUpperCase());
    if (testInfo.project.name === 'desktop') {
      expect((await projectCard.boundingBox()).width).toBeLessThanOrEqual(305);
    }

    const coverResponsePromise = page.waitForResponse((response) =>
      response.request().method() === 'PATCH' && response.url().endsWith(`/api/v1/projects/${project.id}`)
    );
    await projectCard.getByLabel(`${projectName} 커버 이미지`).setInputFiles({
      name: 'cover.png',
      mimeType: 'image/png',
      buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl7NqQAAAAASUVORK5CYII=', 'base64'),
    });
    const coverResponse = await coverResponsePromise;
    expect(coverResponse.status()).toBe(200);
    await expect(projectCard.getByRole('img', { name: `${projectName} 프로젝트 커버` })).toBeVisible();
    expect((await coverResponse.json()).settings_json.cover_image).toMatch(/^data:image\/jpeg;base64,/);

    const removeResponsePromise = page.waitForResponse((response) =>
      response.request().method() === 'PATCH' && response.url().endsWith(`/api/v1/projects/${project.id}`)
    );
    await projectCard.getByRole('button', { name: `${projectName} 커버 제거` }).click();
    expect((await removeResponsePromise).status()).toBe(200);
    await expect(projectCard.getByRole('img')).toHaveCount(0);

    await page.goto('/editor');
    await page.getByLabel('현재 프로젝트').selectOption({ label: projectName });
    await page.getByRole('navigation', { name: '세계관 자료 관리' }).getByRole('button', { name: /^자료 종류/ }).click();
    await expect(page.locator('.category-intro')).toHaveCount(0);
    await expect(page.locator('.category-settings-card')).toHaveCount(5);
    await expect(page.getByText('분류 기준', { exact: true })).toHaveCount(0);
    if (testInfo.project.name === 'desktop') {
      expect((await page.locator('.category-settings-card').first().boundingBox()).width).toBeLessThanOrEqual(305);
    }
    await expect(page.getByText('글 만들기 추천')).toHaveCount(0);
    await expect(page.locator('.category-recommendations')).toHaveCount(0);
    await expectStepHelp(page, '자료 종류 설명', '이 프로젝트의 세계관 자료를 묶는 이름');
    await page.getByRole('button', { name: '+ 새 자료 종류', exact: true }).click();
    const categoryCreateDialog = await expectWorkspaceDialog(page, '새 자료 종류');
    await expect(page.getByLabel('새 자료 종류 이름')).toBeVisible();
    await page.getByLabel('새 자료 종류 이름').fill('세력');
    await page.getByRole('button', { name: '자료 종류 만들기' }).click();
    await expect(page.getByText("'세력' 자료 종류를 만들었습니다.")).toBeVisible();
    await expect(categoryCreateDialog).toBeHidden();
    const createdCategoryCard = page.locator('.category-settings-card').filter({ hasText: '세력' });
    await createdCategoryCard.getByRole('button', { name: '수정', exact: true }).click();
    const categoryEditDialog = await expectWorkspaceDialog(page, '자료 종류 수정');
    await expect(categoryEditDialog.getByLabel('세력 자료 종류 이름')).toHaveValue('세력');
    await categoryEditDialog.getByRole('button', { name: '취소' }).click();
    await page.getByRole('button', { name: /세계관 자료/ }).click();
    await page.getByRole('button', { name: '+ 새 자료' }).click();
    await expect(page.getByLabel('자료 종류')).toContainText('세력');
    await expect(page.getByText('용도', { exact: true })).toHaveCount(0);
    await page.getByLabel('자료 이름').fill('경계 관측소');
    await page.getByLabel('자료 종류').selectOption({ label: '세력' });
    const conceptResponsePromise = page.waitForResponse((response) =>
      response.request().method() === 'POST' && response.url().endsWith('/api/v1/concept-pages')
    );
    await page.getByRole('button', { name: '자료 만들기' }).click();
    const conceptResponse = await conceptResponsePromise;
    expect(conceptResponse.status()).toBe(201);
    expect((await conceptResponse.json()).usage_role).toBe('DRAFT_SETTING');
    const writingBoundaries = page.locator('.writing-boundaries');
    await expect(writingBoundaries).toContainText('원고 작성 경계');
    await expect(writingBoundaries).toContainText('유지할 사실');
    await expect(writingBoundaries).toContainText('공개 유보');
    await expect(writingBoundaries).toContainText('금지된 변경·전개');
    await expect(writingBoundaries.getByRole('button', { name: '유지할 사실 설명' })).toBeVisible();
    await expect(writingBoundaries.getByRole('button', { name: '공개 유보 설명' })).toBeVisible();
    await expect(writingBoundaries.getByRole('button', { name: '금지된 변경 설명' })).toBeVisible();
    const boundaryAiButton = writingBoundaries.getByRole('button', { name: 'AI 제안', exact: true });
    await expect(boundaryAiButton).toBeVisible();
    await expect.poll(() => boundaryAiButton.evaluate((element) => element.getBoundingClientRect().width === element.parentElement.getBoundingClientRect().width)).toBe(true);
    await page.getByRole('button', { name: '변경 저장' }).click();
    await expect(page.getByLabel('세계관 자료 본문')).toBeVisible();
    await expect(page.getByLabel('자료 제목')).toHaveCount(0);
    await page.getByRole('button', { name: '글 편집' }).click();
    await expect(page.getByLabel('자료 제목')).toBeEditable();
    await page.getByRole('button', { name: '취소', exact: true }).click();

    await page.getByRole('navigation', { name: '세계관 자료 관리' }).getByRole('button', { name: /^집필 지침/ }).click();
    await expectStepHelp(page, '집필 지침 설명', '이 프로젝트의 글에서 반복해 지킬');
    await page.getByRole('button', { name: '+ 새 집필 지침', exact: true }).click();
    const directionCreateDialog = await expectWorkspaceDialog(page, '새 집필 지침');
    const directionScroll = page.locator('.direction-workspace-scroll');
    if (testInfo.project.name === 'desktop') {
      await expect(directionScroll).toHaveCSS('overflow-y', 'auto');
      expect(await directionScroll.evaluate((element) => element.clientHeight > 0)).toBe(true);
    }
    await page.getByLabel('지침 이름').fill('유용한 기술의 대가');
    await page.getByLabel('이 프로젝트의 글에서 무엇을 지킬까요?').fill('효능은 유지하고 대가가 누적되는 과정을 보여 준다.');
    await expect(directionCreateDialog.locator('.direction-rule-editor')).toBeVisible();
    await page.getByLabel('새 집필 지침 목표').fill('기술의 실제 효능을 보여 준다');
    await page.getByLabel('새 집필 지침 전개 순서').fill('도입\n성공\n의존\n대가');
    await page.getByLabel('새 집필 지침 반드시 포함').fill('대체재가 없는 이유');
    await page.getByLabel('새 집필 지침 피할 전개').fill('처음부터 모두 거짓이었다는 반전');
    await page.getByLabel('새 집필 지침 선호 결말').fill('해결보다 선택의 비용을 남긴다');
    const directionResponsePromise = page.waitForResponse((response) =>
      response.request().method() === 'POST' && response.url().endsWith('/api/v1/direction-cards')
    );
    await page.getByRole('button', { name: '지침 추가', exact: true }).click();
    const directionResponse = await directionResponsePromise;
    expect(directionResponse.status()).toBe(201);
    const directionPayload = await directionResponse.json();
    expect(directionPayload.parsed_rules.sequence).toEqual(['도입', '성공', '의존', '대가']);
    expect(directionPayload.parsed_rules.must_include).toEqual(['대체재가 없는 이유']);
    const directionCard = page.locator('.direction-card').filter({ hasText: '유용한 기술의 대가' });
    await expect(directionCard).toContainText('도입 → 성공 → 의존 → 대가');
    await expect(directionCard).toContainText('해결보다 선택의 비용을 남긴다');
    await directionCard.getByRole('button', { name: '내용 수정' }).click();
    const directionEditDialog = await expectWorkspaceDialog(page, '집필 지침 수정');
    await expect(directionEditDialog.locator('.direction-rule-editor')).toBeVisible();
    await expect(directionEditDialog.getByLabel('유용한 기술의 대가 지침 목표')).toBeVisible();
    await directionEditDialog.getByRole('button', { name: '취소' }).click();

    await page.getByRole('navigation', { name: '세계관 자료 관리' }).getByRole('button', { name: /^전개 방식/ }).click();
    await expectStepHelp(page, '전개 방식 설명', '공용 기본 방식은 프로젝트와 관계없이');
    await expect(page.locator('.recipe-settings-card').filter({ hasText: '모든 프로젝트에서 사용' }).first()).toBeVisible();
    await page.getByRole('button', { name: '+ 새 전개 방식', exact: true }).click();
    await expectWorkspaceDialog(page, '새 전개 방식');
    await expect(page.getByText('카드 표시', { exact: true })).toHaveCount(0);
    await expect(page.locator('.recipe-create .recipe-step-row input')).toHaveCount(0);
    await expect(page.locator('.recipe-create .recipe-derived-purpose')).toHaveCount(3);
    await page.getByLabel('새 전개 방식 이름').fill('징후에서 결론으로');
    await page.getByRole('button', { name: '전개 방식 만들기', exact: true }).click();
    await expect(page.getByText("'징후에서 결론으로' 전개 방식을 만들었습니다.")).toBeVisible();
    const recipeCard = page.locator('.recipe-settings-card').filter({ hasText: '징후에서 결론으로' });
    await expect(recipeCard).toContainText('맥락 열기');
    await expect(recipeCard).toContainText('핵심 근거·장면');
    await expect(recipeCard).toContainText('의미·분석');
    await expect(recipeCard.locator('.recipe-card-route li')).toHaveCount(3);
    if (testInfo.project.name === 'desktop') {
      expect((await recipeCard.boundingBox()).width).toBeLessThanOrEqual(305);
    }
    await recipeCard.getByRole('button', { name: '수정', exact: true }).click();
    const recipeEditDialog = await expectWorkspaceDialog(page, '전개 방식 수정');
    await recipeEditDialog.getByLabel('이름').fill('징후에서 결론으로 개정');
    await recipeEditDialog.getByRole('button', { name: '변경 저장', exact: true }).click();
    await expect(page.locator('.recipe-settings-card').filter({ hasText: '징후에서 결론으로 개정' })).toBeVisible();

    await page.goto('/playbook');
    await page.getByLabel('현재 프로젝트').selectOption({ label: projectName });
    await page.locator('.wizard-choice-card').filter({ hasText: '경계 관측소' }).click();
    await page.getByRole('button', { name: /배경으로 계속/ }).click();
    await page.getByRole('button', { name: /주요 요소로 계속/ }).click();
    await page.getByRole('button', { name: /갈등·변수로 계속/ }).click();
    await page.getByRole('button', { name: /집필 지침으로 계속/ }).click();
    await page.getByRole('button', { name: /전개 방식으로 계속/ }).click();
    const projectRecipe = page.locator('.recipe-option').filter({ hasText: '징후에서 결론으로 개정' });
    await expect(projectRecipe).toContainText('이 프로젝트에서 사용');
    await projectRecipe.click();
    await expect(projectRecipe).toHaveAttribute('aria-pressed', 'true');

    await page.goto('/editor');
    await page.getByLabel('현재 프로젝트').selectOption({ label: projectName });
    await page.getByRole('navigation', { name: '세계관 자료 관리' }).getByRole('button', { name: /^전개 방식/ }).click();
    page.once('dialog', (dialog) => dialog.accept());
    await page.locator('.recipe-settings-card').filter({ hasText: '징후에서 결론으로 개정' }).getByRole('button', { name: '삭제' }).click();
    await expect(page.getByText("'징후에서 결론으로 개정' 전개 방식을 삭제했습니다.")).toBeVisible();

    await page.getByRole('navigation', { name: '세계관 자료 관리' }).getByRole('button', { name: /^세계관 자료/ }).click();
    await page.locator('.archive-page-list button').filter({ hasText: '경계 관측소' }).click();
    page.once('dialog', (dialog) => dialog.accept());
    await page.getByRole('button', { name: '자료 삭제' }).click();
    await expect(page.locator('.archive-page-list')).not.toContainText('경계 관측소');

    await page.goto('/');
    const disposableCard = page.locator('.project-card').filter({ has: page.getByRole('heading', { name: projectName }) });
    page.once('dialog', (dialog) => dialog.accept());
    const deleteProjectResponse = page.waitForResponse((response) => response.request().method() === 'DELETE' && response.url().endsWith(`/api/v1/projects/${project.id}`));
    await disposableCard.getByRole('button', { name: `${projectName} 프로젝트 삭제` }).click();
    expect((await deleteProjectResponse).status()).toBe(204);
    await expect(disposableCard).toHaveCount(0);
    project = null;
  } finally {
    if (project && apiOrigin) await removeProjectFixture(page.request, apiOrigin, project.id);
  }
});

test('project-first workflow exposes understandable controls', async ({ page }, testInfo) => {
  test.skip(process.env.E2E_EXPECT_DATA !== 'true', 'requires the curated Black Route world project');
  await page.goto('/');
  await expect(page.locator('.model-board')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: '어느 세계에서 작업할까요?' })).toBeVisible();
  expect((await page.locator('.home-briefing').boundingBox()).height).toBeLessThanOrEqual(180);
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
  await expect(page.locator('.manuscript-read-title')).toHaveText('기억세');
  await expect(page.locator('.editor-content')).toContainText('기억세는 돈이 아니라 손실 가능성을 시민에게 배분하는 제도다');
  await expect(page.locator('.editor-content')).not.toContainText('통과에는 대가가 필요하다');
  if (testInfo.project.name === 'mobile') {
    await expect.poll(() => page.locator('.manuscript-panel').evaluate((element) => Math.round(element.getBoundingClientRect().top))).toBeLessThan(120);
  }
  await expect(page.getByText('연결된 자료')).toBeVisible();
  await expect(page.getByText('원고 작성 경계', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'AI 제안', exact: true })).toBeVisible();
  await expect(page.locator('text=/[0-9a-f]{8}-[0-9a-f]{4}-/')).toHaveCount(0);
  await page.getByRole('navigation', { name: '세계관 자료 관리' }).getByRole('button', { name: /^집필 지침/ }).click();
  await expect(page.locator('.direction-intro')).toHaveCount(0);
  await expectStepHelp(page, '집필 지침 설명', '반복해 지킬 강조점');
  await expect(page.getByRole('button', { name: 'AI로 세부 규칙 정리' }).first()).toBeVisible();
  await page.getByRole('button', { name: '+ 새 집필 지침' }).click();
  const directionDialog = await expectWorkspaceDialog(page, '새 집필 지침');
  await expect(directionDialog.getByRole('button', { name: '인물의 욕망과 선택을 장면으로 보여 준다' })).toBeVisible();
  await expect(directionDialog.getByRole('button', { name: '구체적 경험에서 생각을 확장한다' })).toBeVisible();
  await expect(directionDialog.getByRole('button', { name: '근거와 한계를 분리해 판단한다' })).toBeVisible();
  await directionDialog.getByRole('button', { name: '구체적 경험에서 생각을 확장한다' }).click();
  await expect(directionDialog.getByLabel('새 집필 지침 목표')).toHaveValue(/경험과 성찰/);
  await directionDialog.getByRole('button', { name: '취소' }).click();

  await page.goto('/playbook');
  await expect(page.locator('select[multiple]')).toHaveCount(0);
  await expect(page.locator('.wizard-heading')).toHaveCount(0);
  await expect(page.locator('.selection-action')).toHaveCount(0);
  await expect(page.getByText('이 자료를 주제로 선택')).toHaveCount(0);
  await expectStepHelp(page, '주제 단계 설명', '무엇에 관한 글인가요?');
  await expect(page.getByRole('button', { name: /배경으로 계속/ })).toBeDisabled();
  const lighthouse = page.locator('.wizard-choice-card').filter({
    has: page.locator('.wizard-card-copy strong', { hasText: /^검은 등대$/ }),
  });
  await lighthouse.click();
  await expect(lighthouse).toHaveAttribute('aria-pressed', 'true');
  await expect.poll(() => lighthouse.evaluate((element) => getComputedStyle(element).backgroundColor)).toBe('rgb(32, 66, 62)');
  await expect.poll(() => lighthouse.locator('.wizard-card-copy strong').evaluate((element) => getComputedStyle(element).color)).toBe('rgb(240, 188, 101)');
  const lighthouseCopy = await lighthouse.locator('.wizard-card-copy').boundingBox();
  const lighthouseMeta = await lighthouse.locator('.wizard-card-meta').boundingBox();
  expect(lighthouseMeta.y).toBeGreaterThan(lighthouseCopy.y);
  await page.getByRole('button', { name: /배경으로 계속/ }).click();

  await expectStepHelp(page, '배경 단계 설명', '어디서, 어떤 상황에서');
  await expect(page.getByRole('button', { name: /주제 검은 등대/ })).toBeVisible();
  await expect(page.getByText('지금까지 선택')).toHaveCount(0);
  await expect(page.locator('.wizard-choice-card').filter({ has: page.locator('.wizard-card-copy strong', { hasText: /^검은 등대$/ }) })).toHaveCount(0);
  const recoveryRoom = page.locator('.wizard-choice-card').filter({ has: page.locator('.wizard-card-copy strong', { hasText: /^회수실$/ }) });
  await recoveryRoom.click();
  await page.getByRole('button', { name: /주요 요소로 계속/ }).click();

  await expectStepHelp(page, '주요 요소 단계 설명', '꼭 함께 다룰 것은');
  await expect(page.getByRole('button', { name: /배경 회수실/ })).toBeVisible();
  await expect(page.locator('.wizard-choice-card').filter({ has: page.locator('.wizard-card-copy strong', { hasText: /^회수실$/ }) })).toHaveCount(0);
  const leah = page.locator('.wizard-choice-card').filter({ has: page.locator('.wizard-card-copy strong', { hasText: /^레아 벨$/ }) });
  await leah.click();
  await page.getByRole('button', { name: /갈등·변수로 계속/ }).click();

  await expectStepHelp(page, '갈등·변수 단계 설명', '무엇이 긴장과 변화를');
  await page.getByRole('button', { name: /선택 없이 집필 지침으로/ }).click();
  await expectStepHelp(page, '집필 지침 단계 설명', '이번 글에서 무엇을 강조하거나 피할까요');
  if (testInfo.project.name === 'desktop' && await page.locator('.direction-option').count()) {
    expect((await page.locator('.direction-option').first().boundingBox()).width).toBeLessThanOrEqual(305);
  }
  await page.getByRole('button', { name: /선택 없이 전개 방식으로/ }).click();

  await expectStepHelp(page, '전개 방식 단계 설명', '글을 어떤 방식으로 풀어갈까요');
  if (testInfo.project.name === 'desktop') {
    expect((await page.locator('.recipe-option').first().boundingBox()).width).toBeLessThanOrEqual(305);
  }
  const causalPattern = page.locator('.recipe-option').filter({ hasText: '원인에서 파급으로' });
  await expect(page.locator('.recipe-option').filter({ hasText: '경험에서 통찰로' })).toBeVisible();
  await expect(page.locator('.recipe-option').filter({ hasText: '질문에서 결론으로' })).toBeVisible();
  await causalPattern.click();
  await expect(causalPattern).toHaveAttribute('aria-pressed', 'true');
  await expect(causalPattern).toContainText('맥락 열기');
  await expect(causalPattern).toContainText('핵심 근거·장면');
  await expect(causalPattern).toContainText('사례·장면');
  await expect(causalPattern).toContainText('긴장·중요도 높이기');
  await expect(causalPattern).toContainText('의미·분석');
  await expect(causalPattern).not.toContainText('시작 원인');
  await page.getByRole('button', { name: /문체·필력으로 계속/ }).click();

  await expectStepHelp(page, '문체·필력 단계 설명', '어떤 문장 감각으로 전달할까요');
  const modelDefaultVoice = page.locator('.voice-option.model-default');
  await expect(modelDefaultVoice).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('.voice-option').filter({ hasText: '장면 중심 소설 문체' })).toBeVisible();
  await expect(page.locator('.voice-option').filter({ hasText: '구체적 성찰 문체' })).toBeVisible();
  await expect(page.locator('.voice-option').filter({ hasText: '근거 중심 보고서 문체' })).toBeVisible();
  await page.getByRole('button', { name: /결과물 형태로 계속/ }).click();

  await expectStepHelp(page, '결과물 형태 단계 설명', '어떤 결과물로 만들까요');
  const outputSpecimen = page.getByLabel('선택한 결과물 견본');
  await expect(outputSpecimen).toContainText('세계관 설명 글');
  const inputLedger = outputSpecimen.getByLabel('현재 원고 설계');
  await expect(inputLedger).toContainText('주제검은 등대');
  await expect(inputLedger).toContainText('배경회수실');
  await expect(inputLedger).toContainText('주요 요소레아 벨');
  await expect(inputLedger).toContainText('갈등·변수선택 안 함');
  await expect(inputLedger).toContainText('집필 지침선택 안 함');
  await expect(inputLedger).toContainText('전개 방식원인에서 파급으로');
  await expect(inputLedger).toContainText('문체·필력모델 기본 문체');
  await expect(page.getByRole('group', { name: '결과물 종류' }).getByRole('button', { name: /수필·에세이/ })).toBeVisible();
  await expect(page.getByRole('group', { name: '결과물 종류' }).getByRole('button', { name: /분석 보고서/ })).toBeVisible();
  const viewpointGroup = page.getByRole('group', { name: '시점' });
  const tenseGroup = page.getByRole('group', { name: '시제' });
  await expect(viewpointGroup.getByRole('button', { name: /전지적 설명자/ })).toHaveAttribute('aria-pressed', 'true');
  await expect(tenseGroup.getByRole('button', { name: /현재형 중심/ })).toHaveAttribute('aria-pressed', 'true');
  await viewpointGroup.getByRole('button', { name: /3인칭 제한/ }).click();
  await tenseGroup.getByRole('button', { name: /과거형 중심/ }).click();
  await page.getByRole('group', { name: '분량' }).getByRole('button', { name: /^길게/ }).click();
  await expect(outputSpecimen).toContainText('3인칭 제한');
  await expect(outputSpecimen).toContainText('과거형 중심');
  await expect(page.locator('.specimen-selection-summary')).toContainText('형식');
  await expect(page.locator('.specimen-selection-summary')).toContainText('분량');
  await expect(page.locator('.specimen-selection-summary')).toContainText('길게 · 약 6,500자');
  await expect(page.getByLabel('선택 자료 본문 반영')).toHaveValue('balanced');
  await expect(page.locator('.output-tuning-card')).toContainText('주제를 포함해 선택한 3개 자료에 적용됩니다.');
  await page.getByRole('button', { name: /확인·작성으로 계속/ }).click();

  await expectStepHelp(page, '확인·작성 단계 설명', '선택을 확인하고 초안을 만드세요');
  const reviewWorkbench = page.locator('.review-workbench');
  const reviewSpecimen = page.getByLabel('선택한 결과물 견본');
  await expect(reviewSpecimen).toContainText('검은 등대');
  await expect(reviewSpecimen).toContainText('회수실');
  await expect(reviewSpecimen).toContainText('레아 벨');
  await expect(reviewSpecimen).toContainText('원인에서 파급으로');
  await expect(reviewWorkbench.getByLabel('확인에서 초안까지')).toBeVisible();
  await expect(reviewWorkbench).toContainText('글의 흐름 설계');
  await expect(reviewWorkbench).not.toContainText('설정 경계 정리');
  await expect(page.locator('.review-stage-cards > button')).toHaveCount(2);
  const reviewSpecimenBox = await reviewSpecimen.boundingBox();
  const reviewResultBox = await page.locator('.review-result-slot').boundingBox();
  if (testInfo.project.name === 'desktop') expect(reviewResultBox.x).toBeGreaterThan(reviewSpecimenBox.x + reviewSpecimenBox.width);
  else expect(reviewResultBox.y).toBeGreaterThan(reviewSpecimenBox.y + reviewSpecimenBox.height);
  await expect(page.getByRole('heading', { name: '이 글이 참고할 세계관' })).toHaveCount(0);
  await expect(page.locator('.playbook-page > .playbook-navigation')).toBeVisible();
  await expect(page.locator('.review-stage-cards > button.complete')).toHaveCount(0);
  const originalBackground = (await reviewSpecimen.getByLabel('현재 원고 설계').locator('div').filter({ has: page.locator('dt', { hasText: '배경' }) }).locator('dd').textContent()).trim();
  await reviewWorkbench.getByRole('button', { name: '주제·소재 수정' }).click();
  await expect(page.locator('.playbook-page > .playbook-navigation').getByRole('button', { name: /확인·작성으로 돌아가기/ })).toBeVisible();
  const candidateTitles = await page.locator('.wizard-choice-card .wizard-card-copy strong').allTextContents();
  const alternativeIndex = candidateTitles.findIndex((title) => !originalBackground.includes(title.trim()));
  if (alternativeIndex >= 0) await page.locator('.wizard-choice-card').nth(alternativeIndex).click();
  await page.locator('.playbook-page > .playbook-navigation').getByRole('button', { name: '수정 취소' }).click();
  await expect(reviewSpecimen.getByLabel('현재 원고 설계')).toContainText(originalBackground);
  await reviewWorkbench.getByRole('button', { name: '주제·소재 수정' }).click();
  await page.locator('.playbook-page > .playbook-navigation').getByRole('button', { name: /확인·작성으로 돌아가기/ }).click();
  await expect(reviewWorkbench).toBeVisible();
  await page.route('**/api/v1/playbook-sessions/*/plan', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session: { id: 'e2e-plan-session' },
        plan: {
          title: '검은 등대 흐름', angle: '대가가 항로를 유지하는 방식을 설명한다.',
          target_length: 6500, planned_length: 6500, warnings: [],
          blocks: [
            { move: 'ORIENT', purpose: '맥락', evidence_ids: [], word_budget: 1300, must_include: [], avoid: [], scene_mode: '설명', expression_focus: '', locked: false },
            { move: 'ANCHOR', purpose: '근거', evidence_ids: [], word_budget: 1300, must_include: [], avoid: [], scene_mode: '설명', expression_focus: '', locked: false },
            { move: 'EXEMPLIFY', purpose: '사례', evidence_ids: [], word_budget: 1300, must_include: [], avoid: [], scene_mode: '설명', expression_focus: '', locked: false },
            { move: 'ESCALATE', purpose: '파급', evidence_ids: [], word_budget: 1300, must_include: [], avoid: [], scene_mode: '설명', expression_focus: '', locked: false },
            { move: 'INTERPRET', purpose: '의미', evidence_ids: [], word_budget: 1300, must_include: [], avoid: [], scene_mode: '설명', expression_focus: '', locked: false }
          ]
        }
      })
    });
  });
  const sessionRequestPromise = page.waitForRequest((request) =>
    request.method() === 'POST' && request.url().endsWith('/api/v1/playbook-sessions')
  );
  const playbookNavigation = page.locator('.playbook-page > .playbook-navigation');
  await page.locator('.review-stage-cards > button').first().click();
  const sessionRequest = await sessionRequestPromise;
  expect(sessionRequest.postDataJSON().settings_json).toMatchObject({
    length: 'long',
    viewpoint: 'third_limited',
    tense: 'past',
    context_depth: 'balanced',
  });
  expect(sessionRequest.postDataJSON().writing_recipe_id).toBeTruthy();
  expect(sessionRequest.postDataJSON()).toMatchObject({
    voice_profile_id: null,
    voice_selection_mode: 'model_default',
    voice_example_ids: [],
  });
  const sessionResponse = await sessionRequest.response();
  const session = await sessionResponse.json();
  await expect(page.locator('.review-stage-cards > button').first()).toHaveClass(/complete/);
  await expect(page.locator('.review-stage-cards > button').first()).toContainText('5개 문단 · 6,500자');
  await expect(page.locator('.plan-heading')).toContainText('총 6,500자 / 목표 6,500자');
  await expect(playbookNavigation.getByRole('button', { name: /초안 작성/ })).toBeEnabled();
  await page.route('**/api/v1/playbook-sessions/*/generate/stream', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: `event: complete\ndata: ${JSON.stringify({ session: { id: session.id }, plan: { title: '검은 등대 흐름', angle: '대가가 항로를 유지하는 방식을 설명한다.', target_length: 6500, planned_length: 6500, warnings: [], blocks: Array.from({ length: 5 }, (_, index) => ({ move: 'ORIENT', purpose: `${index + 1}번 흐름`, evidence_ids: [], word_budget: 1300, must_include: [], avoid: [], scene_mode: '설명', expression_focus: '', locked: false })) }, document: { id: 'e2e-draft', title: '검은 등대 초안', body_markdown: '첫 문단의 초안입니다.\n\n둘째 문단의 초안입니다.' } })}\n\n`
    });
  });
  await page.locator('.review-stage-cards > button').nth(1).click();
  await expect(page.locator('.review-result-slot')).toContainText('검은 등대 초안');
  await expect(page.locator('.review-result-slot')).toContainText('첫 문단의 초안입니다.');
  await expect(page.locator('.review-result-slot')).not.toContainText('총 6,500자 / 목표 6,500자');
  await expect(page.locator('.review-stage-cards > button').nth(1)).toHaveClass(/complete/);
  await page.locator('.review-stage-cards > button').first().click();
  await expect(page.locator('.review-result-slot')).toContainText('총 6,500자 / 목표 6,500자');
  await expect(page.locator('.review-result-slot')).not.toContainText('첫 문단의 초안입니다.');
  await page.locator('.review-stage-cards > button').nth(1).click();
  await expect(page.locator('.review-result-slot')).toContainText('첫 문단의 초안입니다.');
  await expect(page).toHaveURL(/\/playbook/);
  await expect(page.getByRole('heading', { name: '이 글이 참고할 세계관' })).toHaveCount(0);
  await page.request.delete(`${new URL(sessionRequest.url()).origin}/api/v1/playbook-sessions/${session.id}`);
});

test('document workflow preserves draft design and applies explicit final refinement', async ({ page }) => {
  test.skip(process.env.E2E_EXPECT_DATA !== 'true', 'requires the curated Black Route draft');
  await page.goto('/documents');
  await page.getByLabel('현재 프로젝트').selectOption({ label: '검은 항로 연대기' });
  await expect(page.locator('.document-wizard-progress .wizard-step-button').filter({ hasText: '초안 편집' })).toBeVisible();
  await expect(page.locator('.document-wizard-progress .wizard-step-button').filter({ hasText: '완성 다듬기' })).toBeVisible();
  await expect(page.locator('.document-wizard-progress .wizard-step-button').filter({ hasText: '완성본 만들기' })).toBeVisible();
  await expect(page.locator('.wizard-heading')).toHaveCount(0);
  await expect(page.locator('.document-inspector-tabs')).toBeVisible();
  await expect(page.locator('.document-tool-panel')).toHaveCount(1);
  await page.getByRole('tab', { name: '문장 점검' }).click();
  await expect(page.getByRole('tabpanel')).toContainText('원문은 자동으로 바뀌지 않습니다.');
  await page.getByRole('tab', { name: '재작성' }).click();
  expect(parseFloat(await page.locator('.document-toolbar').evaluate((element) => getComputedStyle(element).paddingTop))).toBeLessThanOrEqual(4);
  expect(parseFloat(await page.locator('.document-main').evaluate((element) => getComputedStyle(element).rowGap))).toBeLessThanOrEqual(8);
  await page.getByRole('button', { name: /완성 다듬기로 계속/ }).click();
  await expectStepHelp(page, '완성 다듬기 단계 설명', '초안에서 무엇을 보강할까요?');
  await expect(page.getByLabel('초안에서 이어받은 원고 기준')).toBeVisible();
  const finalSourceBox = await page.getByLabel('초안에서 이어받은 원고 기준').boundingBox();
  const finalDeckBox = await page.locator('.final-polish-deck').boundingBox();
  expect(finalSourceBox.y).toBeGreaterThanOrEqual(0);
  if (page.viewportSize().width > 820) expect(finalDeckBox.x).toBeGreaterThan(finalSourceBox.x + finalSourceBox.width);
  else expect(finalDeckBox.y).toBeGreaterThan(finalSourceBox.y + finalSourceBox.height);
  await expect(page.getByRole('group', { name: '결과물 종류' })).toHaveCount(0);
  await expect(page.getByLabel('이어받은 원고 설정')).toContainText('전개 방식');
  await page.getByRole('group', { name: '보강 목표' }).getByRole('button', { name: /장면·감각/ }).click();
  await page.getByRole('group', { name: '다듬기 강도' }).getByRole('button', { name: /적극적으로/ }).click();
  await page.getByRole('group', { name: '분량 방향' }).getByRole('button', { name: /필요한 곳 보강/ }).click();
  await page.getByLabel('이번 다듬기에만 추가할 요청').fill('마지막 장면의 여운을 강화해 주세요.');
  await page.getByRole('button', { name: /다듬기 확인으로 계속/ }).click();
  await expect(page.locator('.final-review-sheet')).toContainText('장면·감각');
  await expect(page.locator('.final-review-sheet')).toContainText('적극적으로 · 필요한 곳 보강');
  await expect(page.locator('.final-review-sheet')).toContainText('마지막 장면의 여운을 강화해 주세요.');
  await expect(page.locator('.final-review-sheet')).toBeVisible();
  expect((await page.locator('.final-review-sheet').boundingBox()).y).toBeGreaterThanOrEqual(0);
  await expect(page.locator('.finalization-review').getByRole('button', { name: '수정' })).toHaveCount(0);
  await expect(page.getByText('완성본은 로어북에 별도 저장됩니다.')).toBeVisible();
  await expect(page.getByRole('button', { name: /초안 다듬어 로어북에 저장|완성본 다시 다듬기/ })).toBeVisible();
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
    await page.getByRole('button', { name: /저장하고 완성 다듬기로 계속/ }).click();
    const saveRequest = await saveRequestPromise;
    expect(saveRequest.postDataJSON().blocks).toHaveLength(originalBlocks.length + 1);
    expect((await saveRequest.response()).status()).toBe(200);
    await expectStepHelp(page, '완성 다듬기 단계 설명', '초안에서 무엇을 보강할까요?');

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
