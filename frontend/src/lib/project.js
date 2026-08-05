import { browser } from '$app/environment';

const PROJECT_KEY = 'lore-studio:active-project';

export function initialProjectId(projects) {
  if (!projects.length) return '';
  if (!browser) return projects[0].id;
  const saved = localStorage.getItem(PROJECT_KEY);
  return projects.some((project) => project.id === saved) ? saved : projects[0].id;
}

export function rememberProject(projectId) {
  if (browser && projectId) localStorage.setItem(PROJECT_KEY, projectId);
}

