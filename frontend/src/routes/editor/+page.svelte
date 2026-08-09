<script>
  import { onMount } from 'svelte';
  import TiptapEditor from '$lib/components/TiptapEditor.svelte';
  import ProjectCreator from '$lib/components/ProjectCreator.svelte';
  import HelpTip from '$lib/components/HelpTip.svelte';
  import { api } from '$lib/api';
  import { moveDescriptions, moveLabels, relationLabel, relationLabels, roleLabel } from '$lib/labels';
  import { initialProjectId, rememberProject } from '$lib/project';

  let projects = [];
  let projectId = '';
  let pages = [];
  let cards = [];
  let recipes = [];
  let voiceProfiles = [];
  let voiceExamples = [];
  let categories = [];
  let selectedPage = null;
  let pageEditing = false;
  let activeTab = 'pages';
  let error = '';
  let message = '';
  let pageFilter = '';
  let categoryFilter = 'all';
  let relations = [];
  let indexStats = null;
  let cardSuggestion = null;
  let boundarySuggestion = null;
  let referenceAnalysis = null;
  let busy = '';
  let newPageOpen = false;
  let settingsModal = '';
  let editingCategoryId = '';
  let editingCardId = '';
  let editingRecipeId = '';
  let editingVoiceId = '';
  let cardDraft = null;
  let categoryForm = { name: '' };
  let categoryDraft = { name: '' };
  let aiSourceOptions = [];
  let linkedSourceIds = [];

  const starterRecipeSteps = () => [
    { move: 'ORIENT' },
    { move: 'ANCHOR' },
    { move: 'INTERPRET' }
  ];

  const emptyCardForm = () => ({
    title: '', body: '', tags: '', goals: '', sequence: '', mustInclude: '', avoid: '', endingPreference: ''
  });

  const emptyRecipeForm = () => ({
    name: '', description: '', bestFor: '', steps: starterRecipeSteps(),
    plannerRules: '', auditRules: ''
  });

  const emptyVoiceForm = () => ({
    name: '', scope: 'PROJECT', readerEffect: '', sentenceRhythm: '', descriptionRules: '',
    dialogueRules: '', figurativeLanguage: '', paragraphRules: '', avoidPatterns: '',
    bestFor: '', auditRules: '', viewpoints: '', tenses: ''
  });

  const emptyVoiceExampleForm = () => ({
    label: '', excerpt: '', teaches: '', sceneTags: '', rightsBasis: 'SELF_AUTHORED', useInGeneration: true
  });

  $: visiblePages = pages.filter((page) => {
    const matchesText = !pageFilter || `${page.title} ${page.summary} ${(page.tags || []).join(' ')}`.toLowerCase().includes(pageFilter.toLowerCase());
    return matchesText && (categoryFilter === 'all' || page.category_key === categoryFilter);
  });
  $: allTags = [...new Set(pages.flatMap((page) => page.tags || []))].sort();

  let pageForm = { title: '', category_key: '' };
  let cardForm = emptyCardForm();
  let recipeForm = emptyRecipeForm();
  let recipeDraft = emptyRecipeForm();
  let voiceForm = emptyVoiceForm();
  let voiceDraft = emptyVoiceForm();
  let voiceExampleForm = emptyVoiceExampleForm();
  let relationForm = { target_page_id: '', relation_type: 'RELATED_TO', notes: '' };

  $: projectRecipes = recipes.filter((recipe) => recipe.project_id === projectId);
  $: sharedRecipes = recipes.filter((recipe) => !recipe.project_id);
  $: editingCategory = categories.find((category) => category.id === editingCategoryId);
  $: editingCard = cards.find((card) => card.id === editingCardId);
  $: editingRecipe = recipes.find((recipe) => recipe.id === editingRecipeId);
  $: editingVoice = voiceProfiles.find((profile) => profile.id === editingVoiceId);
  $: settingsModalTitle = ({
    'category-create': '새 자료 종류',
    'category-edit': '자료 종류 수정',
    'direction-create': '새 집필 지침',
    'direction-edit': '집필 지침 수정',
    'recipe-create': '새 전개 방식',
    'recipe-edit': '전개 방식 수정',
    'voice-create': '새 문체 프로필',
    'voice-edit': '문체 프로필 수정'
  })[settingsModal] || '';
  $: linkedSourceIds = selectedPage
    ? [...new Set(relations.map((relation) => otherPage(relation)))]
    : [];
  $: aiSourceOptions = pages
    .filter((page) => page.id !== selectedPage?.id && page.status !== 'rejected' && page.usage_role !== 'REJECTED')
    .map((page) => ({
      id: page.id,
      title: page.title,
      summary: page.summary,
      usage_role: page.usage_role,
      role_label: roleLabel(page.usage_role),
      linked: linkedSourceIds.includes(page.id)
    }));

  onMount(loadInitial);

  async function loadInitial() {
    try {
      projects = await api.get('/projects');
      projectId = initialProjectId(projects);
      if (projectId) await loadProjectData();
    } catch (e) { error = e.message; }
  }

  async function projectCreated(project) {
    projects = [project, ...projects];
    projectId = project.id;
    rememberProject(projectId);
    await loadProjectData();
  }

  async function changeProject() {
    rememberProject(projectId);
    await loadProjectData();
  }

  async function loadProjectData() {
    if (!projectId) return;
    error = '';
    message = '';
    closeSettingsModal();
    categoryFilter = 'all';
    try {
      [pages, cards, indexStats, categories, recipes, voiceProfiles] = await Promise.all([
        api.get(`/concept-pages?project_id=${projectId}`),
        api.get(`/direction-cards?project_id=${projectId}`),
        api.get(`/index/stats?project_id=${projectId}`),
        api.get(`/categories?project_id=${projectId}`),
        api.get(`/writing-recipes?project_id=${projectId}`),
        api.get(`/voice-profiles?project_id=${projectId}`)
      ]);
      pageForm = {
        ...pageForm,
        category_key: categories.some((item) => item.key === pageForm.category_key)
          ? pageForm.category_key
          : categories[0]?.key || ''
      };
      if (pages[0]) await selectPage(pages[0]);
      else { selectedPage = null; relations = []; }
    } catch (e) { error = e.message; }
  }

  async function createPage() {
    if (!projectId || !pageForm.title.trim()) return;
    error = '';
    try {
      const project = projects.find((item) => item.id === projectId);
      const page = await api.post('/concept-pages', {
        project_id: projectId,
        title: pageForm.title.trim(),
        category_key: pageForm.category_key,
        tags: [],
        status: 'active',
        namespace: project?.universe_namespace || 'default',
        summary: '',
        body_json: { type: 'doc', content: [] },
        properties_json: {},
        locked_facts: [],
        open_questions: [],
        forbidden_changes: []
      });
      pages = [page, ...pages];
      pageForm = { title: '', category_key: categories[0]?.key || '' };
      newPageOpen = false;
      await selectPage(page, { reveal: true, edit: true });
      message = '새 자료를 만들었습니다. 본문과 핵심 사실을 채워 보세요.';
    } catch (e) { error = e.message; }
  }

  async function savePage() {
    if (!selectedPage) return;
    error = ''; message = ''; busy = '변경 저장 중';
    try {
      const updated = await api.patch(`/concept-pages/${selectedPage.id}`, {
        title: selectedPage.title,
        category_key: selectedPage.category_key,
        tags: typeof selectedPage.tagsText === 'string' ? selectedPage.tagsText.split(',').map((item) => item.trim()).filter(Boolean) : selectedPage.tags,
        namespace: selectedPage.namespace,
        summary: selectedPage.summary,
        body_json: selectedPage.body_json,
        locked_facts: lines(selectedPage.lockedFactsText, selectedPage.locked_facts),
        open_questions: lines(selectedPage.openQuestionsText, selectedPage.open_questions),
        forbidden_changes: lines(selectedPage.forbiddenChangesText, selectedPage.forbidden_changes),
        properties_json: selectedPage.properties_json || {},
        attachment_refs: selectedPage.attachment_refs || []
      });
      selectedPage = decoratePage(updated);
      pages = pages.map((item) => item.id === updated.id ? updated : item);
      pageEditing = false;
      message = '변경 내용을 저장했습니다.';
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  function selectableBoundarySuggestion(suggestion) {
    return Object.fromEntries(
      ['locked_facts', 'open_questions', 'forbidden_changes'].map((key) => [
        key,
        (suggestion?.[key] || []).map((item) => ({ ...item, selected: true }))
      ])
    );
  }

  async function suggestWritingBoundaries() {
    if (!selectedPage) return;
    error = ''; message = ''; busy = 'AI가 본문에서 작성 경계를 찾는 중';
    try {
      const result = await api.post(`/concept-pages/${selectedPage.id}/suggest-writing-boundaries`, {
        body_json: selectedPage.body_json,
        locked_facts: lines(selectedPage.lockedFactsText, selectedPage.locked_facts),
        open_questions: lines(selectedPage.openQuestionsText, selectedPage.open_questions),
        forbidden_changes: lines(selectedPage.forbiddenChangesText, selectedPage.forbidden_changes)
      });
      boundarySuggestion = selectableBoundarySuggestion(result.suggestion);
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  function mergeBoundaryText(currentText, items) {
    const current = lines(currentText, []);
    const additions = items.filter((item) => item.selected).map((item) => item.text.trim()).filter(Boolean);
    return [...new Set([...current, ...additions])].join('\n');
  }

  function applyBoundarySuggestion() {
    if (!selectedPage || !boundarySuggestion) return;
    selectedPage = {
      ...selectedPage,
      lockedFactsText: mergeBoundaryText(selectedPage.lockedFactsText, boundarySuggestion.locked_facts),
      openQuestionsText: mergeBoundaryText(selectedPage.openQuestionsText, boundarySuggestion.open_questions),
      forbiddenChangesText: mergeBoundaryText(selectedPage.forbiddenChangesText, boundarySuggestion.forbidden_changes)
    };
    boundarySuggestion = null;
    message = 'AI 제안을 입력했습니다. 확인한 뒤 변경 저장을 눌러 주세요.';
  }

  function lines(text, fallback) {
    return typeof text === 'string' ? text.split('\n').map((item) => item.trim()).filter(Boolean) : fallback;
  }

  function cardRulesToForm(card) {
    const rules = card?.parsed_rules || {};
    return {
      goals: (rules.goals || []).join('\n'),
      sequence: (rules.sequence || []).join('\n'),
      mustInclude: (rules.must_include || []).join('\n'),
      avoid: (rules.avoid || []).join('\n'),
      endingPreference: rules.ending_preference || ''
    };
  }

  function cardRulesFromForm(form, existing = {}) {
    return {
      ...existing,
      goals: lines(form.goals, []),
      sequence: lines(form.sequence, []),
      must_include: lines(form.mustInclude, []),
      avoid: lines(form.avoid, []),
      ending_preference: form.endingPreference.trim()
    };
  }

  function hasCardRules(card) {
    const rules = card?.parsed_rules || {};
    return ['goals', 'sequence', 'must_include', 'avoid'].some((key) => rules[key]?.length)
      || !!rules.ending_preference;
  }

  function recipeToForm(recipe) {
    const data = recipe.recipe_json || {};
    const requiredMoves = (data.required_moves || []).length >= 3
      ? data.required_moves
      : starterRecipeSteps().map((step) => step.move);
    return {
      name: recipe.name,
      description: recipe.description || '',
      bestFor: data.best_for || '',
      steps: requiredMoves.map((move) => ({ move })),
      plannerRules: (data.planner_rules || []).join('\n'),
      auditRules: (data.audit_rules || []).join('\n')
    };
  }

  function recipePayload(form) {
    const steps = form.steps.filter((step) => step.move);
    return {
      name: form.name.trim(),
      description: form.description.trim(),
      recipe_json: {
        name: form.name.trim(),
        description: form.description.trim(),
        best_for: form.bestFor.trim(),
        required_moves: steps.map((step) => step.move),
        optional_moves: [],
        planner_rules: lines(form.plannerRules, []),
        style_defaults: {},
        audit_rules: lines(form.auditRules, [])
      }
    };
  }

  function updateRecipeStep(target, index, field, value) {
    target.steps[index] = { ...target.steps[index], [field]: value };
    if (target === recipeDraft) recipeDraft = { ...target, steps: [...target.steps] };
    else recipeForm = { ...target, steps: [...target.steps] };
  }

  function addRecipeStep(target) {
    target.steps = [...target.steps, { move: 'COMPLICATE' }];
    if (target === recipeDraft) recipeDraft = { ...target };
    else recipeForm = { ...target };
  }

  function removeRecipeStep(target, index) {
    if (target.steps.length <= 3) return;
    target.steps = target.steps.filter((_, stepIndex) => stepIndex !== index);
    if (target === recipeDraft) recipeDraft = { ...target };
    else recipeForm = { ...target };
  }

  async function createRecipe() {
    if (!projectId || !recipeForm.name.trim() || recipeForm.steps.length < 3) return;
    error = ''; message = '';
    try {
      const recipe = await api.post('/writing-recipes', {
        project_id: projectId,
        ...recipePayload(recipeForm)
      });
      recipes = [...recipes, recipe].sort((a, b) => a.name.localeCompare(b.name, 'ko'));
      recipeForm = emptyRecipeForm();
      closeSettingsModal();
      message = `'${recipe.name}' 전개 방식을 만들었습니다.`;
    } catch (e) { error = e.message; }
  }

  function editRecipe(recipe) {
    editingRecipeId = recipe.id;
    recipeDraft = recipeToForm(recipe);
    settingsModal = 'recipe-edit';
  }

  async function saveRecipe(recipe) {
    if (!recipeDraft.name.trim() || recipeDraft.steps.length < 3) return;
    error = ''; message = '';
    try {
      const updated = await api.patch(`/writing-recipes/${recipe.id}`, recipePayload(recipeDraft));
      recipes = recipes.map((item) => item.id === recipe.id ? updated : item)
        .sort((a, b) => a.name.localeCompare(b.name, 'ko'));
      closeSettingsModal();
      message = `'${updated.name}' 전개 방식을 저장했습니다.`;
    } catch (e) { error = e.message; }
  }

  async function deleteRecipe(recipe) {
    if (!confirm(`'${recipe.name}' 전개 방식을 삭제할까요? 사용한 글 만들기 기록이 있으면 삭제할 수 없습니다.`)) return;
    error = ''; message = '';
    try {
      await api.delete(`/writing-recipes/${recipe.id}`);
      recipes = recipes.filter((item) => item.id !== recipe.id);
      message = `'${recipe.name}' 전개 방식을 삭제했습니다.`;
    } catch (e) { error = e.message; }
  }

  function voiceToForm(profile) {
    const data = profile.profile_json || {};
    return {
      name: profile.name,
      scope: profile.project_id ? 'PROJECT' : 'SHARED',
      readerEffect: data.reader_effect || profile.description || '',
      sentenceRhythm: (data.sentence_rhythm || []).join('\n'),
      descriptionRules: (data.description_rules || []).join('\n'),
      dialogueRules: (data.dialogue_rules || []).join('\n'),
      figurativeLanguage: (data.figurative_language || []).join('\n'),
      paragraphRules: (data.paragraph_rules || []).join('\n'),
      avoidPatterns: (data.avoid_patterns || []).join('\n'),
      bestFor: (data.best_for || []).join(', '),
      auditRules: (data.audit_rules || []).join('\n'),
      viewpoints: (data.compatibility?.viewpoints || []).join(', '),
      tenses: (data.compatibility?.tenses || []).join(', ')
    };
  }

  function commaItems(text) {
    return text.split(',').map((item) => item.trim()).filter(Boolean);
  }

  function voicePayload(form, { includeScope = false } = {}) {
    const payload = {
      name: form.name.trim(),
      description: form.readerEffect.trim(),
      profile_json: {
        reader_effect: form.readerEffect.trim(),
        sentence_rhythm: lines(form.sentenceRhythm, []),
        description_rules: lines(form.descriptionRules, []),
        dialogue_rules: lines(form.dialogueRules, []),
        figurative_language: lines(form.figurativeLanguage, []),
        paragraph_rules: lines(form.paragraphRules, []),
        avoid_patterns: lines(form.avoidPatterns, []),
        best_for: commaItems(form.bestFor),
        audit_rules: lines(form.auditRules, []),
        compatibility: { viewpoints: commaItems(form.viewpoints), tenses: commaItems(form.tenses) }
      }
    };
    return includeScope ? { ...payload, project_id: form.scope === 'PROJECT' ? projectId : null } : payload;
  }

  function voiceStatusLabel(status) {
    return ({ DRAFT: '검토 중', APPROVED: '사용 가능', DEPRECATED: '사용 중지' })[status] || status;
  }

  function voiceRuleTags(profile) {
    const data = profile.profile_json || {};
    return [...(data.best_for || []), ...(data.sentence_rhythm || []).slice(0, 1), ...(data.dialogue_rules || []).slice(0, 1)].slice(0, 3);
  }

  async function openVoiceCreate() {
    voiceForm = emptyVoiceForm();
    voiceExamples = [];
    settingsModal = 'voice-create';
  }

  async function editVoice(profile) {
    editingVoiceId = profile.id;
    voiceDraft = voiceToForm(profile);
    voiceExampleForm = emptyVoiceExampleForm();
    settingsModal = 'voice-edit';
    try { voiceExamples = await api.get(`/voice-profiles/${profile.id}/examples`); }
    catch (e) { error = e.message; }
  }

  async function createVoiceProfile() {
    if (!voiceForm.name.trim() || !voiceForm.readerEffect.trim()) return;
    error = ''; message = '';
    try {
      const profile = await api.post('/voice-profiles', voicePayload(voiceForm, { includeScope: true }));
      voiceProfiles = [profile, ...voiceProfiles];
      await editVoice(profile);
      message = `'${profile.name}' 검토본을 만들었습니다. 예시를 더한 뒤 사용 가능으로 승인하세요.`;
    } catch (e) { error = e.message; }
  }

  async function saveVoiceProfile(profile) {
    if (!voiceDraft.name.trim() || !voiceDraft.readerEffect.trim()) return;
    error = ''; message = '';
    try {
      const updated = await api.patch(`/voice-profiles/${profile.id}`, voicePayload(voiceDraft));
      voiceProfiles = updated.id === profile.id
        ? voiceProfiles.map((item) => item.id === profile.id ? updated : item)
        : [updated, ...voiceProfiles];
      editingVoiceId = updated.id;
      voiceDraft = voiceToForm(updated);
      voiceExamples = await api.get(`/voice-profiles/${updated.id}/examples`);
      message = updated.id === profile.id
        ? `'${updated.name}' 검토본을 저장했습니다.`
        : `사용 이력을 보존하고 '${updated.name}' 새 버전을 만들었습니다.`;
    } catch (e) { error = e.message; }
  }

  async function approveVoiceProfile(profile) {
    error = ''; message = '';
    try {
      const updated = await api.post(`/voice-profiles/${profile.id}/approve`, {});
      voiceProfiles = voiceProfiles.map((item) => item.id === updated.id ? updated : item);
      editingVoiceId = updated.id;
      message = `'${updated.name}'을 다음 글 만들기부터 사용할 수 있습니다.`;
    } catch (e) { error = e.message; }
  }

  async function deprecateVoiceProfile(profile) {
    if (!confirm(`'${profile.name}'을 새 글에서 더 이상 선택하지 않게 할까요? 기존 원고 기록은 유지됩니다.`)) return;
    try {
      const updated = await api.post(`/voice-profiles/${profile.id}/deprecate`, {});
      voiceProfiles = voiceProfiles.map((item) => item.id === updated.id ? updated : item);
      message = `'${updated.name}'을 사용 중지했습니다.`;
    } catch (e) { error = e.message; }
  }

  async function duplicateVoiceProfile(profile) {
    try {
      const duplicate = await api.post(`/voice-profiles/${profile.id}/duplicate`, { project_id: projectId });
      voiceProfiles = [duplicate, ...voiceProfiles];
      await editVoice(duplicate);
      message = `'${duplicate.name}' 검토본을 만들었습니다.`;
    } catch (e) { error = e.message; }
  }

  async function deleteVoiceProfile(profile) {
    if (!confirm(`'${profile.name}' 문체 프로필을 삭제할까요? 사용 기록이 있으면 삭제할 수 없습니다.`)) return;
    try {
      await api.delete(`/voice-profiles/${profile.id}`);
      voiceProfiles = voiceProfiles.filter((item) => item.id !== profile.id);
      closeSettingsModal();
      message = `'${profile.name}'을 삭제했습니다.`;
    } catch (e) { error = e.message; }
  }

  async function addVoiceExample(profile) {
    if (!voiceExampleForm.label.trim() || !voiceExampleForm.excerpt.trim()) return;
    try {
      const example = await api.post(`/voice-profiles/${profile.id}/examples`, {
        label: voiceExampleForm.label.trim(),
        excerpt: voiceExampleForm.excerpt.trim(),
        teaches_json: lines(voiceExampleForm.teaches, []),
        scene_tags: commaItems(voiceExampleForm.sceneTags),
        rights_basis: voiceExampleForm.rightsBasis,
        use_in_generation: voiceExampleForm.useInGeneration
      });
      voiceExamples = [...voiceExamples, example];
      voiceExampleForm = emptyVoiceExampleForm();
      message = '짧은 문체 예시를 추가했습니다.';
    } catch (e) { error = e.message; }
  }

  async function toggleVoiceExample(example) {
    try {
      const updated = await api.post(`/voice-profile-examples/${example.id}/toggle`, {});
      voiceExamples = voiceExamples.map((item) => item.id === updated.id ? updated : item);
    } catch (e) { error = e.message; }
  }

  async function deleteVoiceExample(example) {
    if (!confirm(`'${example.label}' 예시를 삭제할까요?`)) return;
    try {
      await api.delete(`/voice-profile-examples/${example.id}`);
      voiceExamples = voiceExamples.filter((item) => item.id !== example.id);
    } catch (e) { error = e.message; }
  }

  function decoratePage(page) {
    return {
      ...page,
      tagsText: (page.tags || []).join(', '),
      lockedFactsText: (page.locked_facts || []).join('\n'),
      openQuestionsText: (page.open_questions || []).join('\n'),
      forbiddenChangesText: (page.forbidden_changes || []).join('\n')
    };
  }

  async function selectPage(page, { reveal = false, edit = false } = {}) {
    selectedPage = decoratePage(page);
    pageEditing = edit;
    boundarySuggestion = null;
    relations = [];
    relationForm = { target_page_id: '', relation_type: 'RELATED_TO', notes: '' };
    if (reveal && typeof window !== 'undefined' && window.matchMedia('(max-width: 820px)').matches) {
      setTimeout(() => document.querySelector('.manuscript-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0);
    }
    try {
      const loadedRelations = await api.get(`/concept-pages/${page.id}/relations`);
      if (selectedPage?.id === page.id) relations = loadedRelations;
    }
    catch (e) { error = e.message; }
    referenceAnalysis = null;
    message = '';
  }

  function cancelPageEdit() {
    const persisted = pages.find((page) => page.id === selectedPage?.id);
    if (persisted) selectedPage = decoratePage(persisted);
    pageEditing = false;
    boundarySuggestion = null;
    message = '';
  }

  async function deletePage(page) {
    if (!page || busy) return;
    if (!confirm(`'${page.title}' 세계관 자료를 삭제할까요?\n\n이 자료의 연결·검색 인덱스·수정 기록도 함께 삭제되며 되돌릴 수 없습니다.`)) return;
    const deletedId = page.id;
    error = ''; message = ''; busy = '세계관 자료 삭제 중';
    try {
      await api.delete(`/concept-pages/${deletedId}`);
      pages = pages.filter((item) => item.id !== deletedId);
      if (pages[0]) await selectPage(pages[0]);
      else { selectedPage = null; relations = []; pageEditing = false; }
      message = `'${page.title}' 자료를 삭제했습니다.`;
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  function pageName(pageId) {
    return pages.find((page) => page.id === pageId)?.title || '삭제된 자료';
  }

  function categoryName(page) {
    return categories.find((item) => item.key === page?.category_key)?.name || page?.custom_category || page?.category_key || '종류 없음';
  }

  function categoryUsedCount(category) {
    return pages.filter((page) => page.category_key === category.key).length;
  }

  function recipeSequence(recipe) {
    return (recipe.recipe_json?.required_moves || []).map((move) => ({
      move,
      label: moveLabels[move] || move,
      purpose: moveDescriptions[move] || ''
    }));
  }

  function categoryInitial(category) {
    return category.name.trim().slice(0, 5).toUpperCase() || '종류';
  }

  async function createCategory() {
    if (!projectId || !categoryForm.name.trim()) return;
    error = ''; message = '';
    try {
      const category = await api.post('/categories', {
        project_id: projectId,
        name: categoryForm.name.trim(),
        description: '',
        template_json: {}
      });
      categories = [...categories, category].sort((a, b) => a.name.localeCompare(b.name, 'ko'));
      pageForm = { ...pageForm, category_key: category.key };
      categoryForm = { name: '' };
      closeSettingsModal();
      message = `'${category.name}' 자료 종류를 만들었습니다.`;
    } catch (e) { error = e.message; }
  }

  function editCategory(category) {
    editingCategoryId = category.id;
    categoryDraft = { name: category.name };
    settingsModal = 'category-edit';
  }

  async function saveCategory(category) {
    if (!categoryDraft.name.trim()) return;
    error = ''; message = '';
    try {
      const updated = await api.patch(`/categories/${category.id}`, {
        name: categoryDraft.name.trim(),
        description: '',
        template_json: category.template_json || {}
      });
      categories = categories.map((item) => item.id === updated.id ? updated : item)
        .sort((a, b) => a.name.localeCompare(b.name, 'ko'));
      closeSettingsModal();
      message = `'${updated.name}' 자료 종류를 저장했습니다.`;
    } catch (e) { error = e.message; }
  }

  async function deleteCategory(category) {
    if (!confirm(`'${category.name}' 자료 종류를 삭제할까요? 사용 중인 종류는 삭제할 수 없습니다.`)) return;
    error = ''; message = '';
    try {
      await api.delete(`/categories/${category.id}`);
      categories = categories.filter((item) => item.id !== category.id);
      if (pageForm.category_key === category.key) pageForm = { ...pageForm, category_key: categories[0]?.key || '' };
      message = `'${category.name}' 자료 종류를 삭제했습니다.`;
    } catch (e) { error = e.message; }
  }

  function otherPage(relation) {
    return relation.source_page_id === selectedPage?.id ? relation.target_page_id : relation.source_page_id;
  }

  async function createRelation() {
    if (!selectedPage || !relationForm.target_page_id) return;
    try {
      const relation = await api.post('/concept-relations', {
        project_id: projectId,
        source_page_id: selectedPage.id,
        ...relationForm
      });
      relations = [...relations, relation];
      relationForm = { target_page_id: '', relation_type: 'RELATED_TO', notes: '' };
      message = '자료 연결을 추가했습니다.';
    } catch (e) { error = e.message; }
  }

  async function removeRelation(relation) {
    if (!confirm(`'${pageName(otherPage(relation))}'과의 연결을 삭제할까요?`)) return;
    try {
      await api.delete(`/concept-relations/${relation.id}`);
      relations = relations.filter((item) => item.id !== relation.id);
    } catch (e) { error = e.message; }
  }

  async function createCard() {
    if (!projectId || !cardForm.title.trim() || !cardForm.body.trim()) return;
    try {
      const card = await api.post('/direction-cards', {
        project_id: projectId,
        title: cardForm.title.trim(),
        body: cardForm.body.trim(),
        tags: cardForm.tags.split(',').map((item) => item.trim()).filter(Boolean),
        parsed_rules: cardRulesFromForm(cardForm), weight: 1, enabled: true
      });
      cards = [card, ...cards];
      cardForm = emptyCardForm();
      closeSettingsModal();
      message = '집필 지침을 추가했습니다.';
    } catch (e) { error = e.message; }
  }

  function editCard(card) {
    editingCardId = card.id;
    cardDraft = {
      title: card.title,
      body: card.body,
      tags: (card.tags || []).join(', '),
      ...cardRulesToForm(card)
    };
    settingsModal = 'direction-edit';
  }

  async function saveCard(card) {
    try {
      const updated = await api.patch(`/direction-cards/${card.id}`, {
        title: cardDraft.title.trim(), body: cardDraft.body.trim(),
        tags: cardDraft.tags.split(',').map((item) => item.trim()).filter(Boolean),
        parsed_rules: cardRulesFromForm(cardDraft, card.parsed_rules)
      });
      cards = cards.map((item) => item.id === updated.id ? updated : item);
      closeSettingsModal();
      message = '집필 지침을 저장했습니다.';
    } catch (e) { error = e.message; }
  }

  async function deleteCard(card) {
    if (!confirm(`'${card.title}' 규칙을 삭제할까요?`)) return;
    try { await api.delete(`/direction-cards/${card.id}`); cards = cards.filter((item) => item.id !== card.id); }
    catch (e) { error = e.message; }
  }

  async function suggestCard(card) {
    busy = 'AI가 원문에서 세부 규칙을 정리하는 중'; error = '';
    try { cardSuggestion = await api.post(`/direction-cards/${card.id}/suggest-structure`, {}); }
    catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  async function applyCardSuggestion() {
    if (!cardSuggestion) return;
    const suggestion = cardSuggestion.suggestion;
    const updated = await api.patch(`/direction-cards/${cardSuggestion.card_id}`, {
      parsed_rules: suggestion,
      compatible_tags: suggestion.compatible_tags || [],
      incompatible_tags: suggestion.incompatible_tags || []
    });
    cards = cards.map((item) => item.id === updated.id ? updated : item);
    cardSuggestion = null;
    message = '세부 규칙을 저장했습니다. 원문은 바뀌지 않았습니다.';
  }

  function openCategoryCreate() {
    categoryForm = { name: '' };
    settingsModal = 'category-create';
  }

  function openDirectionCreate() {
    cardForm = emptyCardForm();
    settingsModal = 'direction-create';
  }

  function openRecipeCreate() {
    recipeForm = emptyRecipeForm();
    settingsModal = 'recipe-create';
  }

  function closeSettingsModal() {
    settingsModal = '';
    editingCategoryId = '';
    editingCardId = '';
    editingRecipeId = '';
    editingVoiceId = '';
    voiceExamples = [];
  }

  function handleModalKeydown(event) {
    if (settingsModal && event.key === 'Escape') closeSettingsModal();
  }

  async function analyzeReference() {
    if (!selectedPage) return;
    busy = 'AI가 문단 구조와 문체를 분석하는 중'; error = '';
    try { referenceAnalysis = await api.post(`/reference-analyzer/${selectedPage.id}`, {}); }
    catch (e) { error = e.message; }
    finally { busy = ''; }
  }

  async function approveReference(mode = 'both') {
    try {
      const result = await api.post(`/reference-analyses/${referenceAnalysis.id}/approve`, {
        approve_recipe: mode === 'both' || mode === 'recipe',
        approve_voice_profile: mode === 'both' || mode === 'voice',
        voice_scope: 'PROJECT',
        selected_voice_fields: [],
        selected_example_ranges: [],
        rights_basis: 'ANALYSIS_ONLY'
      });
      referenceAnalysis = { ...referenceAnalysis, status: result.status };
      [recipes, voiceProfiles] = await Promise.all([
        api.get(`/writing-recipes?project_id=${projectId}`),
        api.get(`/voice-profiles?project_id=${projectId}`)
      ]);
      message = mode === 'voice' ? '문체 분석을 승인했습니다. 문체·필력에서 확인하세요.' : mode === 'recipe' ? '구성 분석을 승인했습니다. 전개 방식에서 확인하세요.' : '구성과 문체 분석을 각각 승인했습니다.';
    } catch (e) { error = e.message; }
  }

  async function reindexPage() {
    if (!selectedPage) return;
    busy = '검색 인덱스에 반영하는 중'; error = '';
    try {
      const job = await api.post('/index/jobs', { project_id: projectId, concept_page_id: selectedPage.id });
      await api.post(`/index/jobs/${job.id}/run`, {});
      indexStats = await api.get(`/index/stats?project_id=${projectId}`);
      message = '최신 내용을 자료 검색에 반영했습니다.';
    } catch (e) { error = e.message; }
    finally { busy = ''; }
  }
</script>

<svelte:window on:keydown={handleModalKeydown} />

<div class="page workspace-page editor-page">
  <div class="page-tools editor-commandbar">
    {#if projects.length}
      <nav class="section-tabs" aria-label="세계관 자료 관리">
        <button class:active={activeTab === 'pages'} on:click={() => activeTab = 'pages'}>세계관 자료 <span>{pages.length}</span></button>
        <button class:active={activeTab === 'categories'} on:click={() => activeTab = 'categories'}>자료 종류 <span>{categories.length}</span></button>
        <button class:active={activeTab === 'directions'} on:click={() => activeTab = 'directions'}>집필 지침 <span>{cards.length}</span></button>
        <button class:active={activeTab === 'recipes'} on:click={() => activeTab = 'recipes'}>전개 방식 <span>{recipes.length}</span></button>
        <button class:active={activeTab === 'voices'} on:click={() => activeTab = 'voices'}>문체·필력 <span>{voiceProfiles.length}</span></button>
      </nav>
    {/if}
    <div class="project-tools">
      <label>현재 프로젝트<select bind:value={projectId} on:change={changeProject}><option value="">프로젝트 선택</option>{#each projects as project}<option value={project.id}>{project.name}</option>{/each}</select></label>
      <ProjectCreator onCreated={projectCreated} />
    </div>
  </div>

  {#if error}<p class="notice-error">{error}</p>{/if}
  {#if busy}<div class="notice" role="status">{busy}…</div>{/if}
  {#if message}<div class="success-banner">{message}</div>{/if}

  {#if !projects.length}
    <section class="empty-state"><strong>먼저 프로젝트를 만들어 주세요.</strong><p>프로젝트는 하나의 세계관과 그 원고를 서로 섞이지 않게 보관합니다.</p></section>
  {:else}
    {#if activeTab === 'pages'}
      <div class="archive-layout">
        <aside class="card archive-list stack">
          <div class="row spread"><div><h2>자료</h2><p class="small">원고가 참고할 세계의 사실과 아이디어</p></div><button class="primary compact" on:click={() => newPageOpen = !newPageOpen}>+ 새 자료</button></div>
          {#if newPageOpen}
            <div class="inline-create stack">
              <label>자료 이름 <input bind:value={pageForm.title} placeholder="예: 황혼 시장" /></label>
              <label>자료 종류<select bind:value={pageForm.category_key}>{#each categories as category}<option value={category.key}>{category.name}</option>{/each}</select></label>
              <button class="primary" disabled={!pageForm.title.trim() || !pageForm.category_key} on:click={createPage}>자료 만들기</button>
            </div>
          {/if}
          <div class="filter-row"><input aria-label="자료 검색" bind:value={pageFilter} placeholder="제목·태그·요약 검색" /><select aria-label="종류 필터" bind:value={categoryFilter}><option value="all">모든 종류</option>{#each categories as category}<option value={category.key}>{category.name}</option>{/each}</select></div>
          <div class="archive-page-list">
            {#each visiblePages as page}
              <button class:active={selectedPage?.id === page.id} on:click={() => selectPage(page, { reveal: true })}>
                <strong>{page.title}</strong>
                <small>{categoryName(page)}{page.summary ? ` · ${page.summary.slice(0, 48)}` : ''}</small>
              </button>
            {/each}
            {#if !visiblePages.length}<div class="empty-mini">조건에 맞는 자료가 없습니다.</div>{/if}
          </div>
        </aside>

        <section class="stack manuscript-panel">
          {#if selectedPage}
            <div class="card manuscript-toolbar">
              <div class="manuscript-heading-fields">
                <span class="badge">{categoryName(selectedPage)}</span>
                {#if pageEditing}
                  <input class="manuscript-title-input" aria-label="자료 제목" bind:value={selectedPage.title} />
                  <input class="manuscript-summary-input" aria-label="한 줄 요약" bind:value={selectedPage.summary} placeholder="이 자료를 한 문장으로 설명해 보세요." />
                {:else}
                  <h1 class="manuscript-read-title">{selectedPage.title}</h1>
                  <p class="manuscript-read-summary">{selectedPage.summary || '한 줄 요약이 없습니다.'}</p>
                {/if}
              </div>
              <div class="manuscript-toolbar-actions">
                <button class="danger-button" on:click={() => deletePage(selectedPage)}>자료 삭제</button>
                {#if pageEditing}<button class="ghost" on:click={cancelPageEdit}>취소</button><button class="primary" on:click={savePage}>변경 저장</button>{:else}<button class="primary" on:click={() => pageEditing = true}>글 편집</button>{/if}
              </div>
            </div>
            {#key selectedPage.id}
              <TiptapEditor
                value={selectedPage.body_json}
                editable={pageEditing}
                onChange={(body) => selectedPage = { ...selectedPage, body_json: body }}
                aiPageId={selectedPage.id}
                aiBoundaries={{
                  locked_facts: lines(selectedPage.lockedFactsText, selectedPage.locked_facts),
                  open_questions: lines(selectedPage.openQuestionsText, selectedPage.open_questions),
                  forbidden_changes: lines(selectedPage.forbiddenChangesText, selectedPage.forbidden_changes)
                }}
                sourceOptions={aiSourceOptions}
                {linkedSourceIds}
                onNotice={(notice) => { message = notice; error = ''; }}
              />
            {/key}
          {:else}<div class="empty-state">왼쪽에서 자료를 만들거나 선택하세요.</div>{/if}
        </section>

        <aside class="card archive-inspector stack">
          {#if selectedPage}
            <h2>핵심 정보</h2>
            <label>자료 종류<select disabled={!pageEditing} bind:value={selectedPage.category_key}>{#each categories as category}<option value={category.key}>{category.name}</option>{/each}</select></label>
            <label>태그 <input disabled={!pageEditing} bind:value={selectedPage.tagsText} list="known-tags" placeholder="쉼표로 구분" /></label>
            <datalist id="known-tags">{#each allTags as tag}<option value={tag}></option>{/each}</datalist>

            <details open class="writing-boundaries">
              <summary>원고 작성 경계</summary>
              <div class="stack details-body">
                <button class="primary boundary-ai-button" disabled={!pageEditing || !!busy} on:click={suggestWritingBoundaries}>AI 제안</button>

                {#if boundarySuggestion}
                  <section class="boundary-review" aria-label="AI 작성 경계 제안">
                    <div class="boundary-review-heading"><strong>저장 전 검토</strong><small>체크한 항목만 기존 내용에 추가됩니다.</small></div>
                    {#each [
                      ['locked_facts', '유지할 사실', '원고에서 반드시 참으로 유지할 설정입니다.'],
                      ['open_questions', '공개 유보', '아직 정답이나 정체를 만들거나 독자에게 공개하지 않을 정보입니다.'],
                      ['forbidden_changes', '금지된 변경·전개', '흥미를 위해서도 발생시키거나 뒤집으면 안 되는 변경입니다.']
                    ] as [key, label, helpText]}
                      <div class="boundary-review-group">
                        <div class="heading-with-help"><strong>{label}</strong><HelpTip label={`AI 제안 ${label} 설명`} text={helpText} /></div>
                        {#each boundarySuggestion[key] as item}
                          <label class="boundary-suggestion-item">
                            <input type="checkbox" bind:checked={item.selected} />
                            <span><b>{item.text}</b><small>근거: {item.source_excerpt}</small></span>
                          </label>
                        {/each}
                        {#if !boundarySuggestion[key].length}<small class="empty-mini">제안 없음</small>{/if}
                      </div>
                    {/each}
                    <div class="row"><button class="primary" on:click={applyBoundarySuggestion}>선택 항목 입력</button><button class="ghost" on:click={() => boundarySuggestion = null}>닫기</button></div>
                  </section>
                {/if}

                <label>
                  <span class="heading-with-help">유지할 사실 <HelpTip label="유지할 사실 설명" text="원고에서 반드시 참으로 유지할 설정입니다." /></span>
                  <textarea disabled={!pageEditing} bind:value={selectedPage.lockedFactsText} placeholder="예: 왕은 이미 죽었다. 한 줄에 하나씩"></textarea>
                </label>
                <label>
                  <span class="heading-with-help">공개 유보 <HelpTip label="공개 유보 설명" text="아직 정답이나 정체를 만들거나 독자에게 공개하지 않을 정보입니다." /></span>
                  <textarea disabled={!pageEditing} bind:value={selectedPage.openQuestionsText} placeholder="예: 범인의 정체는 아직 밝히지 않는다. 한 줄에 하나씩"></textarea>
                </label>
                <label>
                  <span class="heading-with-help">금지된 변경·전개 <HelpTip label="금지된 변경 설명" text="흥미를 위해서도 발생시키거나 뒤집으면 안 되는 변경입니다." /></span>
                  <textarea disabled={!pageEditing} bind:value={selectedPage.forbiddenChangesText} placeholder="예: 왕을 다시 살리지 않는다. 한 줄에 하나씩"></textarea>
                </label>
              </div>
            </details>

            <section class="relation-section stack">
              <div class="row spread"><div><h3>연결된 자료</h3><p class="small">이 자료가 세계의 다른 요소와 어떻게 연결되는지 표시합니다.</p></div><span class="badge">{relations.length}</span></div>
              {#each relations as relation}
                <div class="relation-card">
                  <button class="relation-link" on:click={() => selectPage(pages.find((page) => page.id === otherPage(relation)), { reveal: true })}>
                    <small>{relation.source_page_id === selectedPage.id ? '나가는 연결' : '들어오는 연결'} · {relationLabel(relation.relation_type)}</small>
                    <strong>{pageName(otherPage(relation))}</strong>
                    {#if relation.notes}<span>{relation.notes}</span>{/if}
                  </button>
                  <button class="icon-button" aria-label="연결 삭제" disabled={!pageEditing} on:click={() => removeRelation(relation)}>×</button>
                </div>
              {/each}
              {#if !relations.length}<p class="empty-mini">아직 연결된 자료가 없습니다.</p>{/if}
              <div class="inline-create stack">
                <strong>연결 추가</strong>
                <label>대상 자료<select disabled={!pageEditing} bind:value={relationForm.target_page_id}><option value="">선택하세요</option>{#each pages.filter((page) => page.id !== selectedPage.id) as page}<option value={page.id}>{page.title}</option>{/each}</select></label>
                <label>관계<select disabled={!pageEditing} bind:value={relationForm.relation_type}>{#each Object.entries(relationLabels) as [value, label]}<option {value}>{label}</option>{/each}</select></label>
                <label>메모 <input disabled={!pageEditing} bind:value={relationForm.notes} placeholder="연결 이유" /></label>
                <button class="secondary" disabled={!pageEditing || !relationForm.target_page_id} on:click={createRelation}>연결하기</button>
              </div>
            </section>

            <details>
              <summary>고급 정보</summary>
              <div class="stack details-body">
                <label>자료 범위 <input disabled={!pageEditing} bind:value={selectedPage.namespace} /></label>
                <div class="notice"><strong>검색 상태</strong><div class="small">{indexStats?.indexed_pages || 0}개 자료 · {indexStats?.chunks || 0}개 조각</div></div>
                <button class="secondary" disabled={!pageEditing} on:click={reindexPage}>최신 내용을 검색에 반영</button>
              </div>
            </details>
            {#if selectedPage.usage_role === 'DISCOURSE_REFERENCE'}
              <button class="secondary" disabled={!pageEditing} on:click={analyzeReference}>이 글의 구성·문체 분석</button>
              {#if referenceAnalysis}
                <div class="rule-preview stack">
                  <strong>문단 구성 분석</strong>
                  {#each referenceAnalysis.analysis_json?.paragraphs || [] as paragraph}
                    <div class="evidence-item"><strong>{paragraph.index + 1}번째 문단 · {paragraph.primary_move}</strong><small>보조 역할 {paragraph.secondary_move} · 범위 {paragraph.scale} · 맺음 {paragraph.ending}</small></div>
                  {/each}
                  {#if !referenceAnalysis.analysis_json?.paragraphs?.length}<p class="empty-mini">분석된 문단이 없습니다.</p>{/if}
                  <div class="reference-approval-actions">
                    <button class="secondary" disabled={referenceAnalysis.status !== 'CANDIDATE'} on:click={() => approveReference('recipe')}>전개 방식만 승인</button>
                    <button class="secondary" disabled={referenceAnalysis.status !== 'CANDIDATE'} on:click={() => approveReference('voice')}>문체만 승인</button>
                    <button class="primary" disabled={referenceAnalysis.status !== 'CANDIDATE'} on:click={() => approveReference('both')}>{referenceAnalysis.status === 'CANDIDATE' ? '둘 다 승인' : '승인됨'}</button>
                  </div>
                </div>
              {/if}
            {/if}
          {/if}
        </aside>
      </div>
    {:else if activeTab === 'directions'}
      <section class="directions-layout">
        <header class="local-surface-header">
          <div class="heading-with-help"><h2>집필 지침</h2><HelpTip label="집필 지침 설명" text="세계관 사실이나 전개 순서가 아니라, 이 프로젝트의 글에서 반복해 지킬 강조점·금지 사항·결말 원칙입니다. 글 만들기에서 원고별로 선택합니다." /></div>
          <div class="local-surface-actions"><span>{cards.length}개</span><button class="primary" on:click={openDirectionCreate}>+ 새 집필 지침</button></div>
        </header>
        <div class="direction-workspace-scroll">
          <div class="direction-list">
            {#each cards as card}
              <article class="direction-card">
                <div class="row spread"><div><div class="tag-row">{#each card.tags || [] as tag}<span class="badge">{tag}</span>{/each}</div><h3>{card.title}</h3></div><span class="badge canon">선택 가능</span></div>
                <p>{card.body}</p>
                {#if hasCardRules(card)}
                  <div class="rule-grid direction-rule-grid">
                    {#if card.parsed_rules.goals?.length}<div><strong>지침 목표</strong><span>{card.parsed_rules.goals.join(' · ')}</span></div>{/if}
                    {#if card.parsed_rules.sequence?.length}<div><strong>전개 순서</strong><span>{card.parsed_rules.sequence.join(' → ')}</span></div>{/if}
                    {#if card.parsed_rules.must_include?.length}<div><strong>반드시 포함</strong><span>{card.parsed_rules.must_include.join(' · ')}</span></div>{/if}
                    {#if card.parsed_rules.avoid?.length}<div><strong>피할 전개</strong><span>{card.parsed_rules.avoid.join(' · ')}</span></div>{/if}
                    {#if card.parsed_rules.ending_preference}<div><strong>선호 결말</strong><span>{card.parsed_rules.ending_preference}</span></div>{/if}
                  </div>
                {/if}
                <div class="row wrap"><button class="secondary" on:click={() => editCard(card)}>내용 수정</button><button class="ghost" on:click={() => suggestCard(card)}>AI로 세부 규칙 정리</button><button class="danger-button" on:click={() => deleteCard(card)}>삭제</button></div>
              </article>
            {/each}
            {#if !cards.length}<div class="empty-state direction-empty"><strong>아직 집필 지침이 없습니다.</strong><p>새 집필 지침을 눌러 이 프로젝트의 글이 반복해서 지킬 원칙을 추가하세요.</p></div>{/if}
          </div>
          {#if cardSuggestion}
            <section class="card suggestion-review stack">
              <div><p class="eyebrow">AI 정리 결과</p><h3>원문은 그대로 두고, 생성에 쓸 세부 규칙만 추가합니다.</h3></div>
              <div class="rule-grid">
                <div><strong>목표</strong><span>{(cardSuggestion.suggestion.goals || []).join(' · ')}</span></div>
                <div><strong>전개 순서</strong><span>{(cardSuggestion.suggestion.sequence || []).join(' → ')}</span></div>
                <div><strong>반드시 포함</strong><span>{(cardSuggestion.suggestion.must_include || []).join(' · ')}</span></div>
                <div><strong>피할 전개</strong><span>{(cardSuggestion.suggestion.avoid || []).join(' · ')}</span></div>
                <div><strong>선호 결말</strong><span>{cardSuggestion.suggestion.ending_preference}</span></div>
              </div>
              <div class="row"><button class="primary" on:click={applyCardSuggestion}>세부 규칙 저장</button><button class="ghost" on:click={() => cardSuggestion = null}>취소</button></div>
            </section>
          {/if}
        </div>
      </section>
    {:else if activeTab === 'recipes'}
      <section class="recipe-manager">
        <header class="local-surface-header">
          <div class="heading-with-help"><h2>전개 방식</h2><HelpTip label="전개 방식 설명" text="정보를 어떤 순서로 공개할지 정합니다. 공용 기본 방식은 프로젝트와 관계없이 항상 보이고, 현재 프로젝트에서 만든 방식은 같은 목록에 함께 보입니다." /></div>
          <div class="local-surface-actions"><span>공용 {sharedRecipes.length}개 · 프로젝트 {projectRecipes.length}개</span><button class="primary" on:click={openRecipeCreate}>+ 새 전개 방식</button></div>
        </header>
        <div class="recipe-settings-list">
          {#each recipes as recipe}
            <article class="recipe-settings-card">
              <div class="recipe-card-route" aria-label={`${recipe.name} 필수 전개 순서`}>
                <ol>
                  {#each recipeSequence(recipe) as step, index}
                    <li><span>{String(index + 1).padStart(2, '0')}</span><strong>{step.label}</strong></li>
                  {/each}
                </ol>
              </div>
              <div class="recipe-card-copy">
                <span class="recipe-origin">{recipe.project_id ? '이 프로젝트에서 사용' : '모든 프로젝트에서 사용'}</span>
                <h3>{recipe.name}</h3>
                <p>{recipe.description || '정보를 공개할 필수 문단 순서입니다.'}</p>
                {#if recipe.recipe_json?.best_for}<small><b>잘 맞는 글</b> {recipe.recipe_json.best_for}</small>{/if}
              </div>
              <footer class="recipe-card-footer">
                <span>{recipeSequence(recipe).length}개 필수 단계</span>
                {#if recipe.project_id}<div><button class="secondary" on:click={() => editRecipe(recipe)}>수정</button><button class="danger-button" on:click={() => deleteRecipe(recipe)}>삭제</button></div>{:else}<span>읽기 전용</span>{/if}
              </footer>
            </article>
          {/each}
          {#if !recipes.length}<div class="empty-state direction-empty"><strong>사용할 수 있는 전개 방식이 없습니다.</strong></div>{/if}
        </div>
      </section>
    {:else if activeTab === 'voices'}
      <section class="voice-manager">
        <header class="local-surface-header">
          <div class="heading-with-help"><h2>문체·필력</h2><HelpTip label="문체·필력 설명" text="문장이 어떤 호흡과 밀도로 독자에게 전달될지 정합니다. 세계관 사실이나 전개 순서를 바꾸지 않습니다." /></div>
          <div class="local-surface-actions"><span>{voiceProfiles.length}개</span><button class="primary" on:click={openVoiceCreate}>+ 새 문체 프로필</button></div>
        </header>
        <div class="voice-profile-list">
          {#each voiceProfiles as profile}
            <article class="voice-profile-card" class:deprecated={profile.status === 'DEPRECATED'}>
              <div class="voice-rhythm-cover" aria-hidden="true">
                <span style={`width:${46 + (profile.name.length % 5) * 8}%`}></span>
                <span style={`width:${82 - (Number(profile.version) % 4) * 7}%`}></span>
                <span style={`width:${58 + ((profile.description || '').length % 4) * 7}%`}></span>
                <span style="width:38%"></span>
              </div>
              <div class="voice-card-copy">
                <div class="row spread"><span class="voice-scope">{profile.project_id ? '이 프로젝트' : '모든 프로젝트'}</span><span class:canon={profile.status === 'APPROVED'} class:candidate={profile.status === 'DRAFT'} class="badge">{voiceStatusLabel(profile.status)}</span></div>
                <h3>{profile.name}</h3>
                <p>{profile.description || profile.profile_json?.reader_effect}</p>
                <div class="tag-row">{#each voiceRuleTags(profile) as tag}<span class="badge">{tag}</span>{/each}</div>
              </div>
              <footer class="voice-card-footer">
                <span>v{profile.version}{profile.source_analysis_id ? ' · 예시 분석' : ' · 직접 작성'}</span>
                <div>
                  <button class="secondary" on:click={() => editVoice(profile)}>내용 보기</button>
                  <button class="ghost" on:click={() => duplicateVoiceProfile(profile)}>복제</button>
                  {#if profile.status === 'DRAFT'}<button class="primary" on:click={() => approveVoiceProfile(profile)}>사용 가능으로 승인</button>{/if}
                  {#if profile.status === 'APPROVED' && !profile.is_builtin}<button class="ghost" on:click={() => deprecateVoiceProfile(profile)}>사용 중지</button>{/if}
                </div>
              </footer>
            </article>
          {/each}
          {#if !voiceProfiles.length}<div class="empty-state"><strong>아직 문체 프로필이 없습니다.</strong><p>직접 표현 원칙을 적거나 문체 참고 자료에서 분석해 시작하세요.</p></div>{/if}
        </div>
      </section>
    {:else}
      <section class="category-manager">
        <header class="local-surface-header">
          <div class="heading-with-help"><h2>자료 종류</h2><HelpTip label="자료 종류 설명" text="이 프로젝트의 세계관 자료를 묶는 이름입니다. 이름을 바꿔도 기존 자료 본문과 연결은 유지됩니다." /></div>
          <div class="local-surface-actions"><span>{categories.length}개</span><button class="primary" on:click={openCategoryCreate}>+ 새 자료 종류</button></div>
        </header>
        <div class="category-settings-list">
          {#each categories as category}
            <article class="category-settings-card">
              <div class="category-card-mark" aria-hidden="true"><span>{categoryInitial(category)}</span></div>
              <div class="category-card-copy"><h3>{category.name}</h3></div>
              <footer class="category-card-footer"><span>{categoryUsedCount(category)}개 자료</span><div><button class="secondary" on:click={() => editCategory(category)}>수정</button><button class="ghost danger" on:click={() => deleteCategory(category)}>삭제</button></div></footer>
            </article>
          {/each}
          {#if !categories.length}<div class="empty-state">아직 자료 종류가 없습니다. 새 자료 종류를 눌러 이 세계의 분류를 만드세요.</div>{/if}
          </div>
      </section>
    {/if}
  {/if}
</div>

{#if settingsModal}
  <div class="settings-modal-backdrop" role="presentation" on:mousedown={(event) => event.target === event.currentTarget && closeSettingsModal()}>
    <div class:wide={settingsModal.startsWith('direction') || settingsModal.startsWith('recipe') || settingsModal.startsWith('voice')} class="settings-modal" role="dialog" aria-modal="true" aria-label={settingsModalTitle}>
      <header>
        <div><span>세계관 자료 설정</span><h2>{settingsModalTitle}</h2></div>
        <button type="button" class="settings-modal-close" aria-label={`${settingsModalTitle} 닫기`} on:click={closeSettingsModal}>×</button>
      </header>

      {#if settingsModal === 'category-create'}
        <form class="settings-modal-form category-create" on:submit|preventDefault={createCategory}>
          <div class="settings-modal-body stack">
            <label>이름 <input aria-label="새 자료 종류 이름" bind:value={categoryForm.name} placeholder="예: 세력, 마법 체계, 생물종" /></label>
            <p class="modal-field-note">이름을 바꿔도 이 종류에 연결된 자료 본문은 유지됩니다.</p>
          </div>
          <footer><small>현재 프로젝트에만 추가됩니다.</small><div><button type="button" class="ghost" on:click={closeSettingsModal}>취소</button><button type="submit" class="primary" disabled={!categoryForm.name.trim()}>자료 종류 만들기</button></div></footer>
        </form>
      {:else if settingsModal === 'category-edit' && editingCategory}
        <form class="settings-modal-form category-edit" on:submit|preventDefault={() => saveCategory(editingCategory)}>
          <div class="settings-modal-body stack">
            <label>자료 종류 이름 <input aria-label={`${editingCategory.name} 자료 종류 이름`} bind:value={categoryDraft.name} /></label>
            <p class="modal-field-note">현재 {categoryUsedCount(editingCategory)}개 자료가 이 종류를 사용합니다. 이름만 변경되며 자료와 연결은 유지됩니다.</p>
          </div>
          <footer><small>내부 식별자는 변경되지 않습니다.</small><div><button type="button" class="ghost" on:click={closeSettingsModal}>취소</button><button type="submit" class="primary" disabled={!categoryDraft.name.trim()}>변경 저장</button></div></footer>
        </form>
      {:else if settingsModal === 'direction-create'}
        <form class="settings-modal-form direction-create" on:submit|preventDefault={createCard}>
          <div class="settings-modal-body stack">
            <label>지침 이름 <input bind:value={cardForm.title} placeholder="예: 제도의 효능과 대가를 함께 보여 준다" /></label>
            <label>이 프로젝트의 글에서 무엇을 지킬까요? <textarea bind:value={cardForm.body} placeholder="강조할 내용, 반드시 보여 줄 과정, 피할 해석을 자연스럽게 적어 주세요."></textarea></label>
            <label>찾기용 태그 <input bind:value={cardForm.tags} placeholder="제도, 의존, 대가" /></label>
            <fieldset class="direction-rule-editor modal-rule-editor">
              <legend>세부 규칙 직접 작성</legend>
              <div class="direction-rule-fields">
                <label>지침 목표 <textarea aria-label="새 집필 지침 목표" bind:value={cardForm.goals} placeholder="한 줄에 하나씩"></textarea></label>
                <label>전개 순서 <textarea aria-label="새 집필 지침 전개 순서" bind:value={cardForm.sequence} placeholder="도입→성공→의존 순서를 한 줄에 하나씩"></textarea></label>
                <label>반드시 포함 <textarea aria-label="새 집필 지침 반드시 포함" bind:value={cardForm.mustInclude} placeholder="한 줄에 하나씩"></textarea></label>
                <label>피할 전개 <textarea aria-label="새 집필 지침 피할 전개" bind:value={cardForm.avoid} placeholder="한 줄에 하나씩"></textarea></label>
                <label class="direction-ending-field">선호 결말 <input aria-label="새 집필 지침 선호 결말" bind:value={cardForm.endingPreference} placeholder="예: 해결보다 선택의 비용을 남긴다" /></label>
              </div>
            </fieldset>
          </div>
          <footer><small>글 만들기에서 원고별로 선택할 수 있습니다.</small><div><button type="button" class="ghost" on:click={closeSettingsModal}>취소</button><button type="submit" class="primary" disabled={!cardForm.title.trim() || !cardForm.body.trim()}>지침 추가</button></div></footer>
        </form>
      {:else if settingsModal === 'direction-edit' && editingCard}
        <form class="settings-modal-form direction-edit" on:submit|preventDefault={() => saveCard(editingCard)}>
          <div class="settings-modal-body stack">
            <label>지침 이름 <input bind:value={cardDraft.title} /></label>
            <label>지침 설명 <textarea bind:value={cardDraft.body}></textarea></label>
            <label>태그 <input bind:value={cardDraft.tags} /></label>
            <fieldset class="direction-rule-editor modal-rule-editor">
              <legend>세부 규칙 직접 작성</legend>
              <div class="direction-rule-fields">
                <label>지침 목표 <textarea aria-label={`${editingCard.title} 지침 목표`} bind:value={cardDraft.goals}></textarea></label>
                <label>전개 순서 <textarea aria-label={`${editingCard.title} 전개 순서`} bind:value={cardDraft.sequence}></textarea></label>
                <label>반드시 포함 <textarea aria-label={`${editingCard.title} 반드시 포함`} bind:value={cardDraft.mustInclude}></textarea></label>
                <label>피할 전개 <textarea aria-label={`${editingCard.title} 피할 전개`} bind:value={cardDraft.avoid}></textarea></label>
                <label class="direction-ending-field">선호 결말 <input aria-label={`${editingCard.title} 선호 결말`} bind:value={cardDraft.endingPreference} /></label>
              </div>
            </fieldset>
          </div>
          <footer><small>저장한 변경은 다음 글 만들기부터 사용됩니다.</small><div><button type="button" class="ghost" on:click={closeSettingsModal}>취소</button><button type="submit" class="primary" disabled={!cardDraft.title.trim() || !cardDraft.body.trim()}>변경 저장</button></div></footer>
        </form>
      {:else if settingsModal === 'recipe-create'}
        <form class="settings-modal-form recipe-create" on:submit|preventDefault={createRecipe}>
          <div class="settings-modal-body stack">
            <div class="grid-2">
              <label>이름 <input aria-label="새 전개 방식 이름" bind:value={recipeForm.name} placeholder="예: 징후에서 진실로" /></label>
              <label>잘 맞는 글 <input bind:value={recipeForm.bestFor} placeholder="예: 미스터리, 폐허, 조사 기록" /></label>
            </div>
            <label>설명 <textarea bind:value={recipeForm.description} placeholder="이 순서가 독자에게 어떤 경험을 만드는지 적어 주세요."></textarea></label>
            <fieldset class="recipe-step-editor">
              <legend>전개 순서 <HelpTip label="새 전개 방식 순서 설명" text="각 줄이 원고의 필수 문단 방식이 됩니다. 위에서 아래 순서로 글의 흐름을 만듭니다." /></legend>
              {#each recipeForm.steps as step, index}
                <div class="recipe-step-row">
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <label>문단 방식<select aria-label={`${index + 1}번 새 전개 문단 방식`} value={step.move} on:change={(event) => updateRecipeStep(recipeForm, index, 'move', event.currentTarget.value)}>{#each Object.entries(moveLabels) as [value, label]}<option {value}>{label}</option>{/each}</select></label>
                  <p class="recipe-derived-purpose"><span>이 단계의 목적</span>{moveDescriptions[step.move]}</p>
                  <button type="button" class="icon-button" aria-label={`${index + 1}번 전개 단계 삭제`} disabled={recipeForm.steps.length <= 3} on:click={() => removeRecipeStep(recipeForm, index)}>×</button>
                </div>
              {/each}
              <button type="button" class="ghost recipe-add-step" on:click={() => addRecipeStep(recipeForm)}>+ 단계 추가</button>
            </fieldset>
            <div class="grid-2 recipe-rule-fields">
              <label>구성할 때 지킬 규칙 <textarea bind:value={recipeForm.plannerRules} placeholder="한 줄에 하나씩 입력"></textarea></label>
              <label>완성 후 확인할 기준 <textarea bind:value={recipeForm.auditRules} placeholder="한 줄에 하나씩 입력"></textarea></label>
            </div>
          </div>
          <footer><small>현재 프로젝트에만 추가되며 공용 방식은 바꾸지 않습니다.</small><div><button type="button" class="ghost" on:click={closeSettingsModal}>취소</button><button type="submit" class="primary" disabled={!recipeForm.name.trim() || recipeForm.steps.length < 3}>전개 방식 만들기</button></div></footer>
        </form>
      {:else if settingsModal === 'recipe-edit' && editingRecipe}
        <form class="settings-modal-form recipe-edit-form" on:submit|preventDefault={() => saveRecipe(editingRecipe)}>
          <div class="settings-modal-body stack">
            <div class="grid-2"><label>이름 <input bind:value={recipeDraft.name} /></label><label>잘 맞는 글 <input bind:value={recipeDraft.bestFor} /></label></div>
            <label>설명 <textarea bind:value={recipeDraft.description}></textarea></label>
            <fieldset class="recipe-step-editor">
              <legend>전개 순서</legend>
              {#each recipeDraft.steps as step, index}
                <div class="recipe-step-row">
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <label>문단 방식<select aria-label={`${index + 1}번 ${editingRecipe.name} 문단 방식`} value={step.move} on:change={(event) => updateRecipeStep(recipeDraft, index, 'move', event.currentTarget.value)}>{#each Object.entries(moveLabels) as [value, label]}<option {value}>{label}</option>{/each}</select></label>
                  <p class="recipe-derived-purpose"><span>이 단계의 목적</span>{moveDescriptions[step.move]}</p>
                  <button type="button" class="icon-button" aria-label={`${index + 1}번 ${editingRecipe.name} 단계 삭제`} disabled={recipeDraft.steps.length <= 3} on:click={() => removeRecipeStep(recipeDraft, index)}>×</button>
                </div>
              {/each}
              <button type="button" class="ghost recipe-add-step" on:click={() => addRecipeStep(recipeDraft)}>+ 단계 추가</button>
            </fieldset>
            <div class="grid-2 recipe-rule-fields"><label>구성할 때 지킬 규칙 <textarea bind:value={recipeDraft.plannerRules}></textarea></label><label>완성 후 확인할 기준 <textarea bind:value={recipeDraft.auditRules}></textarea></label></div>
          </div>
          <footer><small>기존 글 만들기 기록은 이전 버전을 유지합니다.</small><div><button type="button" class="ghost" on:click={closeSettingsModal}>취소</button><button type="submit" class="primary" disabled={!recipeDraft.name.trim() || recipeDraft.steps.length < 3}>변경 저장</button></div></footer>
        </form>
      {:else if settingsModal === 'voice-create'}
        <form class="settings-modal-form voice-form" on:submit|preventDefault={createVoiceProfile}>
          <div class="settings-modal-body stack">
            <p class="modal-field-note">먼저 독자에게 남길 인상과 문장 호흡을 적으세요. 세계관 사실과 정보 공개 순서는 각각 자료와 전개 방식이 담당합니다.</p>
            <div class="grid-2">
              <label>이름 <input bind:value={voiceForm.name} placeholder="예: 건조한 항해 기록" /></label>
              <label>사용 범위 <select bind:value={voiceForm.scope}><option value="PROJECT">이 프로젝트</option><option value="SHARED">모든 프로젝트</option></select></label>
            </div>
            <label>독자에게 남길 인상 <textarea bind:value={voiceForm.readerEffect} placeholder="예: 담담한 보고를 읽다가 뒤늦게 인물의 소진을 깨닫게 한다."></textarea></label>
            <div class="voice-rule-grid">
              <label>문장 호흡 <textarea bind:value={voiceForm.sentenceRhythm} placeholder="한 줄에 하나씩&#10;짧은 관찰 뒤에 긴 인과 문장을 둔다"></textarea></label>
              <label>묘사 원칙 <textarea bind:value={voiceForm.descriptionRules} placeholder="감각과 사물의 변화를 중심으로 묘사"></textarea></label>
              <label>대화 원칙 <textarea bind:value={voiceForm.dialogueRules} placeholder="감정을 직접 말하기보다 회피와 생략으로 드러낸다"></textarea></label>
              <label>비유 원칙 <textarea bind:value={voiceForm.figurativeLanguage} placeholder="세계 내부의 노동·도구에서 비유를 가져온다"></textarea></label>
              <label>문단 원칙 <textarea bind:value={voiceForm.paragraphRules} placeholder="문단마다 하나의 관찰이나 변화만 다룬다"></textarea></label>
              <label>피할 표현 <textarea bind:value={voiceForm.avoidPatterns} placeholder="과도한 감탄, 같은 문장 시작의 반복"></textarea></label>
            </div>
            <div class="grid-2"><label>잘 맞는 글 <input bind:value={voiceForm.bestFor} placeholder="소설 장면, 기록문" /></label><label>점검 기준 <input bind:value={voiceForm.auditRules} placeholder="문장 시작이 세 번 연속 반복되지 않는다" /></label></div>
            <div class="grid-2"><label>호환 시점 <input bind:value={voiceForm.viewpoints} placeholder="third_limited, omniscient" /></label><label>호환 시제 <input bind:value={voiceForm.tenses} placeholder="past, present" /></label></div>
          </div>
          <footer><small>검토본으로 저장되며, 승인 전에는 글 생성에 사용되지 않습니다.</small><div><button type="button" class="ghost" on:click={closeSettingsModal}>취소</button><button type="submit" class="primary" disabled={!voiceForm.name.trim() || !voiceForm.readerEffect.trim()}>검토본 만들기</button></div></footer>
        </form>
      {:else if settingsModal === 'voice-edit' && editingVoice}
        <form class="settings-modal-form voice-form" on:submit|preventDefault={() => saveVoiceProfile(editingVoice)}>
          <div class="settings-modal-body stack">
            <div class="row spread"><span class="badge" class:canon={editingVoice.status === 'APPROVED'}>{voiceStatusLabel(editingVoice.status)} · v{editingVoice.version}</span><small>{editingVoice.project_id ? '이 프로젝트' : '모든 프로젝트'}</small></div>
            <div class="grid-2"><label>이름 <input bind:value={voiceDraft.name} /></label><label>독자에게 남길 인상 <input bind:value={voiceDraft.readerEffect} /></label></div>
            <div class="voice-rule-grid">
              <label>문장 호흡 <textarea bind:value={voiceDraft.sentenceRhythm}></textarea></label>
              <label>묘사 원칙 <textarea bind:value={voiceDraft.descriptionRules}></textarea></label>
              <label>대화 원칙 <textarea bind:value={voiceDraft.dialogueRules}></textarea></label>
              <label>비유 원칙 <textarea bind:value={voiceDraft.figurativeLanguage}></textarea></label>
              <label>문단 원칙 <textarea bind:value={voiceDraft.paragraphRules}></textarea></label>
              <label>피할 표현 <textarea bind:value={voiceDraft.avoidPatterns}></textarea></label>
            </div>
            <div class="grid-2"><label>잘 맞는 글 <input bind:value={voiceDraft.bestFor} /></label><label>점검 기준 <textarea bind:value={voiceDraft.auditRules}></textarea></label></div>
            <div class="grid-2"><label>호환 시점 <input bind:value={voiceDraft.viewpoints} /></label><label>호환 시제 <input bind:value={voiceDraft.tenses} /></label></div>

            <section class="voice-example-section stack">
              <div><h3>짧은 문체 예시</h3><p>사실 참고가 아닌 표현 참고로만 전달됩니다. 직접 쓴 글이 아니면 권리와 사용 범위를 확인하세요.</p></div>
              {#each voiceExamples as example}
                <article class="voice-example-row">
                  <div><strong>{example.label}</strong><p>{example.excerpt}</p><small>{example.rights_basis} · {(example.scene_tags || []).join(' · ') || '태그 없음'}</small></div>
                  {#if editingVoice.status === 'DRAFT'}<div><button type="button" class:active={example.use_in_generation} class="secondary" disabled={example.rights_basis === 'ANALYSIS_ONLY'} on:click={() => toggleVoiceExample(example)}>{example.use_in_generation ? '생성에 사용' : '분석만'}</button><button type="button" class="danger-button" on:click={() => deleteVoiceExample(example)}>삭제</button></div>{/if}
                </article>
              {/each}
              {#if editingVoice.status === 'DRAFT'}
                <div class="voice-example-create">
                  <div class="grid-2"><label>예시 이름 <input bind:value={voiceExampleForm.label} placeholder="예: 폭풍 전 갑판" /></label><label>권리 근거 <select bind:value={voiceExampleForm.rightsBasis}><option value="SELF_AUTHORED">직접 작성</option><option value="LICENSED">사용 허가됨</option><option value="PUBLIC_DOMAIN">퍼블릭 도메인</option><option value="ANALYSIS_ONLY">분석만 허용</option></select></label></div>
                  <label>짧은 예시 <textarea bind:value={voiceExampleForm.excerpt} placeholder="표현 호흡을 보여 주는 짧은 문단"></textarea></label>
                  <div class="grid-2"><label>이 예시가 가르칠 것 <input bind:value={voiceExampleForm.teaches} placeholder="한 줄에 하나씩" /></label><label>장면 태그 <input bind:value={voiceExampleForm.sceneTags} placeholder="대화, 추격, 내면" /></label></div>
                  <button type="button" class="secondary" disabled={!voiceExampleForm.label.trim() || !voiceExampleForm.excerpt.trim()} on:click={() => addVoiceExample(editingVoice)}>예시 추가</button>
                </div>
              {/if}
            </section>
          </div>
          <footer><small>{editingVoice.status === 'DRAFT' ? '승인하면 다음 글 만들기부터 선택할 수 있습니다.' : '수정 시 사용 기록을 보존한 새 검토 버전을 만듭니다.'}</small><div>{#if editingVoice.status === 'DRAFT' && !editingVoice.is_builtin}<button type="button" class="danger-button" on:click={() => deleteVoiceProfile(editingVoice)}>삭제</button>{/if}<button type="button" class="ghost" on:click={closeSettingsModal}>닫기</button><button type="submit" class="secondary" disabled={!voiceDraft.name.trim() || !voiceDraft.readerEffect.trim()}>변경 저장</button>{#if editingVoice.status === 'DRAFT'}<button type="button" class="primary" on:click={() => approveVoiceProfile(editingVoice)}>사용 가능으로 승인</button>{/if}</div></footer>
        </form>
      {/if}
    </div>
  </div>
{/if}
