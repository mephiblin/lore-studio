import { expect, test } from '@playwright/test';

const project = {
  id: 'project-1', name: '성역', slug: 'sanctuary', description: '',
  universe_namespace: 'sanctuary', settings_json: {}, created_at: '', updated_at: ''
};
const category = {
  id: 'category-food', project_id: project.id, key: 'food', name: '음식',
  description: '성역의 음식과 식문화', template_json: {}, is_builtin: false,
  created_at: '', updated_at: ''
};
const source = {
  id: 'source-1', project_id: project.id, title: '성역의 이야기', category_key: 'food',
  custom_category: '', tags: [], usage_role: 'DRAFT_SETTING', authority_state: 'DRAFT_SETTING',
  status: 'active', namespace: 'sanctuary', era: '', continuity: '',
  summary: '악마의 침공 이후에도 이어지는 사람들의 삶',
  body_json: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: '성역의 사람들은 각 지역의 풍습을 지켰다.' }] }] },
  properties_json: {}, locked_facts: [], open_questions: [], forbidden_changes: [],
  attachment_refs: [], created_at: '', updated_at: ''
};

function savedPage(candidate, index) {
  return {
    ...source,
    id: `saved-${index}`,
    title: candidate.title,
    summary: candidate.summary,
    body_json: { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: candidate.content_text }] }] },
    tags: candidate.tags,
    usage_role: 'CANDIDATE',
    authority_state: 'CANDIDATE'
  };
}

async function mockEditor(page) {
  const captured = { seeds: null, generate: null, accept: null, rewrite: null, draft: null };
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace('/api/v1', '');
    let body = [];
    if (path === '/projects') body = [project];
    else if (path === '/presets/direction-cards') body = [];
    else if (path === '/concept-pages' && request.method() === 'GET') body = [source];
    else if (path === '/direction-cards') body = [];
    else if (path === '/index/stats') body = { total: 0 };
    else if (path === '/categories') body = [category];
    else if (path === '/writing-recipes') body = [];
    else if (path === '/voice-profiles') body = [];
    else if (path.endsWith('/relations')) body = [];
    else if (path === '/concept-batches/seeds') {
      captured.seeds = request.postDataJSON();
      body = {
        run_id: 'seed-run-1', source_page_id: source.id, category_key: category.key,
        model_key: captured.seeds.model_key,
        seeds: Array.from({ length: 6 }, (_, index) => ({
          seed_id: `seed-${index + 1}`,
          title: `성역의 음식 ${index + 1}`,
          summary: `지역과 계층을 드러내는 음식 글감 ${index + 1}`,
          distinction: `다른 지역 ${index + 1}의 식재료와 계층을 다룬다.`,
          source_basis: ['성역의 사람들은 각 지역의 풍습을 지켰다.']
        }))
      };
    } else if (path === '/concept-batches/generate') {
      captured.generate = request.postDataJSON();
      body = {
        seed_run_id: 'seed-run-1', requested_count: captured.generate.selected_seeds.length,
        candidates: captured.generate.selected_seeds.map((seed, index) => ({
          run_id: `worker-${index + 1}`, seed_id: seed.seed_id, title: seed.title,
          summary: seed.summary, content_text: `${seed.title}의 유래다.\n\n성역 사람들은 이 음식을 나눈다.`,
          tags: ['음식', '성역'], warnings: [],
          details: [{ label: '사회적 용도', value: '의식 때 공동체가 나누어 먹는다.' }],
          inherited_facts: ['각 지역의 풍습이 이어진다.'],
          candidate_facts: ['의식 때 이 음식을 나눈다.'],
          character_count: 34
        })),
        failures: [], writer_model_key: captured.generate.writer_model_key,
        length_key: captured.generate.length_key, max_concurrency: captured.generate.max_concurrency
      };
    } else if (path === '/concept-batches/accept') {
      captured.accept = request.postDataJSON();
      body = captured.accept.candidates.map(savedPage);
    } else if (path === `/concept-pages/${source.id}/ai/rewrite-selection`) {
      captured.rewrite = request.postDataJSON();
      body = {
        run_id: 'rewrite-1', concept_page_id: source.id, mode: 'rewrite_selection',
        model_key: captured.rewrite.model_key, status: 'CANDIDATE', persisted: false,
        base_body_hash: 'a'.repeat(64), original_text: captured.rewrite.selection_text,
        proposed_text: '안개 항구의 주민들은 공동 화덕에서 붉은 해초를 끓인다.',
        selection_from: captured.rewrite.selection_from, selection_to: captured.rewrite.selection_to,
        source_page_ids: [], warnings: []
      };
    } else if (path === `/concept-pages/${source.id}/ai/draft`) {
      captured.draft = request.postDataJSON();
      body = {
        run_id: 'draft-1', concept_page_id: source.id, mode: 'draft',
        model_key: captured.draft.model_key, status: 'CANDIDATE', persisted: false,
        base_body_hash: 'b'.repeat(64), original_text: '',
        proposed_text: '## 공동 화덕\n\n겨울이면 주민들은 이곳에 모인다.',
        source_page_ids: captured.draft.source_page_ids, warnings: []
      };
    } else {
      throw new Error(`Unhandled mock API: ${request.method()} ${path}`);
    }
    await route.fulfill({ status: path === '/concept-batches/accept' ? 201 : 200, contentType: 'application/json', body: JSON.stringify(body) });
  });
  return captured;
}

test('world material batch keeps the default path short and saves only reviewed candidates', async ({ page }) => {
  const captured = await mockEditor(page);
  await page.goto('/editor');
  await page.getByRole('button', { name: '자료 양산' }).click();
  const dialog = page.getByRole('dialog', { name: '세계관 자료 양산' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText('한 번 정하면, 씨앗을 고르는 일만 남습니다.')).toBeVisible();
  await expect(dialog.getByLabel('자동 실행 계획')).toContainText('씨앗 기획 · Qwen');
  await expect(dialog.getByLabel('자동 실행 계획')).toContainText('본문 집필 · Gemma');
  await expect(dialog.getByLabel('씨앗 기획 모델')).toBeHidden();
  await dialog.getByLabel('제안받을 씨앗 수').fill('6');
  await dialog.getByLabel('추가 지시').fill('지역별 재료 차이를 드러내 줘.');
  await dialog.getByRole('button', { name: '씨앗 제안받기' }).click();

  await expect(dialog.getByRole('heading', { name: '본문으로 키울 씨앗 선택' })).toBeVisible();
  await expect(dialog.getByText('차별점').first()).toBeVisible();
  expect(captured.seeds).toMatchObject({
    model_key: 'qwen', source_page_id: source.id, category_key: category.key,
    seed_count: 6, additional_instruction: '지역별 재료 차이를 드러내 줘.'
  });
  await dialog.getByRole('button', { name: '성역의 음식 1 선택' }).click();
  await dialog.getByRole('button', { name: '성역의 음식 2 선택' }).click();
  await dialog.getByRole('button', { name: '성역의 음식 3 선택' }).click();
  await dialog.getByLabel('1번 씨앗 간단 내용').fill('사용자가 다듬은 첫 번째 음식 씨앗');
  await dialog.getByRole('button', { name: '선택한 3개 본문 만들기' }).click();

  await expect(dialog.getByRole('heading', { name: '완성 결과 검토' })).toBeVisible();
  expect(captured.generate.selected_seeds).toHaveLength(3);
  expect(captured.generate.selected_seeds[0].summary).toBe('사용자가 다듬은 첫 번째 음식 씨앗');
  expect(captured.generate).toMatchObject({
    writer_model_key: 'gemma', length_key: 'standard', max_concurrency: 4
  });
  await dialog.getByLabel('1번 생성 결과 제목').fill('핏빛 밀로 구운 순례빵');
  await dialog.locator('.batch-result-select input').nth(2).uncheck();
  await dialog.getByText('설정 근거와 핵심 항목').first().click();
  await expect(dialog.getByText('참고 자료에서 계승').first()).toBeVisible();
  await dialog.getByRole('button', { name: '선택한 2개 후보 저장' }).click();

  await expect(dialog).toBeHidden();
  await expect(page.getByText('2개 결과를 검토 후보 자료로 저장했습니다.')).toBeVisible();
  expect(captured.accept.candidates).toHaveLength(2);
  expect(captured.accept.candidates[0].title).toBe('핏빛 밀로 구운 순례빵');
  expect(captured.accept.candidates[0].candidate_facts).toBeUndefined();
  expect(captured.accept.seed_run_id).toBe('seed-run-1');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('batch dialog obeys the 360px workspace contract', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'one deterministic 360px check');
  await page.setViewportSize({ width: 360, height: 844 });
  await mockEditor(page);
  await page.goto('/editor');
  await page.getByRole('button', { name: '자료 양산' }).click();
  const dialog = page.getByRole('dialog', { name: '세계관 자료 양산' });
  await expect(dialog).toBeVisible();
  const box = await dialog.boundingBox();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(360);
  await expect(dialog.locator('footer')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('existing material AI rewrite and draft dialogs select Qwen or Gemma per request', async ({ page }) => {
  const captured = await mockEditor(page);
  await page.goto('/editor');
  await page.getByRole('button', { name: '글 편집' }).click();
  await page.locator('.ProseMirror').click();
  await page.keyboard.press('Control+A');

  await page.getByRole('button', { name: 'AI 수정' }).click();
  const rewritePanel = page.getByRole('form', { name: '선택 영역 AI 수정' });
  await expect(rewritePanel.getByLabel('사용할 모델')).toHaveValue('gemma');
  await rewritePanel.getByLabel('사용할 모델').selectOption('qwen');
  await rewritePanel.getByRole('button', { name: '수정 제안' }).click();
  const proposal = page.getByRole('region', { name: 'AI 본문 제안' });
  await expect(proposal).toContainText('Qwen · 선택 영역 수정');
  expect(captured.rewrite.model_key).toBe('qwen');

  await page.getByRole('button', { name: 'AI 작성' }).click();
  const dialog = page.getByRole('dialog', { name: 'AI 작성' });
  await expect(dialog.getByLabel('사용할 모델')).toHaveValue('qwen');
  await dialog.getByLabel('사용할 모델').selectOption('gemma');
  await dialog.getByLabel('무엇을 작성할까요?').fill('공동 화덕의 겨울 풍경을 작성해 줘.');
  await dialog.getByRole('button', { name: '초안 제안' }).click();
  await expect(proposal).toContainText('Gemma · 본문 초안');
  expect(captured.draft.model_key).toBe('gemma');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
