import { expect, test } from '@playwright/test';

const profiles = ['writer', 'utility', 'vision'].map((role) => ({
  role,
  base_url: '',
  model: '',
  timeout_seconds: 300,
  context_budget: 32768,
  disable_thinking: false,
  api_key_configured: false,
  source: 'environment',
}));

async function mockModelConnections(page) {
  await page.route('**/api/v1/model-connections', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(profiles),
  }));
}

test('model settings assigns both local vLLMs and never echoes a saved key', async ({ page }) => {
  await mockModelConnections(page);
  let testPayload;
  let savePayload;
  await page.route('**/api/v1/model-connections/test', async (route) => {
    testPayload = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        role: testPayload.role,
        available: true,
        model: testPayload.model,
        models: [testPayload.model],
        capabilities: { chat: true, vision: true },
        error: null,
      }),
    });
  });
  await page.route('**/api/v1/model-connections/writer', async (route) => {
    savePayload = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ...profiles[0],
        base_url: savePayload.base_url,
        model: savePayload.model,
        api_key_configured: true,
        source: 'database',
      }),
    });
  });

  await page.goto('/settings');
  await expect(page.getByRole('heading', { name: '모델 연결', level: 1 })).toBeVisible();
  await expect(page.locator('.model-profile-card')).toHaveCount(3);
  await expect(page.locator('#primary-navigation a')).toHaveCount(5);
  await expect(page.getByRole('link', { name: '모델 연결 설정' })).toHaveAttribute('aria-current', 'page');

  await page.getByRole('button', { name: '이 PC 권장 분담 적용' }).click();
  await expect(page.getByLabel('Writer 로컬 모델')).toHaveValue('gemma');
  await expect(page.getByLabel('Utility 로컬 모델')).toHaveValue('qwen');
  await expect(page.getByLabel('Vision 로컬 모델')).toHaveValue('qwen');
  await expect(page.getByLabel('Base URL').first()).toHaveValue('http://host.docker.internal:18093/v1');
  await expect(page.getByLabel('모델 alias').first()).toHaveValue('gemma4-26b-heretic-mtp');
  await page.locator('.model-profile-card').first().getByRole('button', { name: '연결 시험' }).click();
  await expect(page.getByText(/연결 성공 · gemma4-26b-heretic-mtp/)).toBeVisible();
  expect(testPayload.api_key).toBe('EMPTY');
  expect(testPayload.disable_thinking).toBe(true);

  await page.getByLabel('Writer 로컬 모델').selectOption('qwen');
  await expect(page.getByLabel('Base URL').first()).toHaveValue('http://host.docker.internal:18091/v1');
  await expect(page.getByLabel('모델 alias').first()).toHaveValue('qwen36-heretic-mtp');
  await page.getByLabel('Writer 로컬 모델').selectOption('gemma');

  await page.locator('.model-profile-card').first().getByRole('button', { name: '시험하고 저장' }).click();
  await expect(page.getByText('연결을 시험하고 서버에 저장했습니다.')).toBeVisible();
  await expect(page.getByLabel('API 키 저장됨 · 변경할 때만 입력').first()).toHaveValue('');
  expect(savePayload.api_key).toBe('EMPTY');
  expect(savePayload.model).toBe('gemma4-26b-heretic-mtp');
  expect(JSON.stringify(profiles[0])).not.toContain('EMPTY');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('model settings remains usable at the narrow 360px contract width', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'one deterministic 360px contract check');
  await page.setViewportSize({ width: 360, height: 844 });
  await mockModelConnections(page);
  await page.goto('/settings');
  await expect(page.getByRole('heading', { name: '모델 연결', level: 1 })).toBeVisible();
  await expect(page.locator('.model-profile-card')).toHaveCount(3);
  await expect(page.locator('#primary-navigation a')).toHaveCount(5);
  await expect(page.getByRole('link', { name: '모델 연결 설정' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const finalButton = page.locator('.model-profile-card').last().getByRole('button', { name: '시험하고 저장' });
  await finalButton.scrollIntoViewIfNeeded();
  await expect(finalButton).toBeVisible();
});
