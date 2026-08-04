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

test('live-model readiness and curated concept archive are visible', async ({ page }) => {
  test.skip(process.env.E2E_EXPECT_DATA !== 'true', 'requires the curated Black Route world project');
  await page.goto('/');
  await expect(page.getByText('writer')).toBeVisible();
  await expect(page.getByText('embedding')).toBeVisible();
  await expect(page.getByText('READY').first()).toBeVisible();

  await page.goto('/editor');
  await expect(page.getByText('검은 등대', { exact: true })).toBeVisible();
  await expect(page.getByText('기억세', { exact: true })).toBeVisible();

  await page.goto('/playbook');
  await expect(page.getByRole('button', { name: '풀에서 추첨' })).toBeVisible();
  await expect(page.getByRole('button', { name: /실제 Writer로 원고 작성/ })).toBeVisible();
});
