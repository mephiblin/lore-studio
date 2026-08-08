export const roleLabels = {
  PROJECT_CANON: '정식 설정',
  DRAFT_SETTING: '설정 초안',
  CANON_EVIDENCE: '정식 설정 근거',
  SECONDARY_INTERPRETATION: '해석 자료',
  INSPIRATION: '영감 자료',
  DISCOURSE_REFERENCE: '문체 참고',
  CANDIDATE: '설정 후보',
  REJECTED: '제외됨'
};

export const categoryLabels = {
  artifact: '유물·기술',
  creature: '종족·생물',
  event: '사건',
  free: '자유 자료',
  person: '인물',
  place: '장소'
};

export const relationLabels = {
  RELATED_TO: '관련됨',
  OPERATED_BY: '운영됨',
  DEPENDS_ON: '의존함',
  ADMINISTERED_BY: '관리됨',
  INVESTIGATES: '조사함',
  POINTS_TO: '가리킴',
  REGULATES: '규율함',
  CONTEXT_FOR: '배경이 됨',
  CONFLICTS_WITH: '충돌함',
  LOCATED_IN: '소재함'
};

export const modelRoleLabels = {
  writer: '글 작성',
  utility: '구성·분석',
  vision: '이미지 이해',
  embedding: '자료 검색'
};

export const moveLabels = {
  ORIENT: '배경 설명',
  NARROW: '주제로 초점 이동',
  ANCHOR: '핵심 사실 제시',
  COMPLICATE: '문제·예외 추가',
  COMPARE: '차이 비교',
  EXEMPLIFY: '사례 제시',
  ESCALATE: '긴장 고조',
  INTERPRET: '의미 해설',
  WITHHOLD: '의문 남기기',
  TURN: '관점 전환',
  STING: '마지막 여운'
};

export const moveDescriptions = {
  ORIENT: '독자가 상황을 이해하도록 장소·시대·배경부터 설명합니다.',
  NARROW: '넓은 배경에서 이 글의 핵심 인물이나 사건으로 초점을 옮깁니다.',
  ANCHOR: '이 글에서 반드시 기억해야 할 설정이나 사실을 분명히 제시합니다.',
  COMPLICATE: '단순한 설명으로 끝나지 않도록 문제, 예외, 대가를 덧붙입니다.',
  COMPARE: '두 대상이나 전후 상황의 차이를 비교해 특징을 드러냅니다.',
  EXEMPLIFY: '추상적인 설정을 실제 사건이나 구체적인 사례로 보여 줍니다.',
  ESCALATE: '위험이나 갈등을 키워 다음 내용을 궁금하게 만듭니다.',
  INTERPRET: '앞서 제시한 사실이 세계나 인물에게 어떤 의미인지 풀이합니다.',
  WITHHOLD: '아직 정하지 않은 답을 단정하지 않고 의문으로 남깁니다.',
  TURN: '새 정보나 다른 관점을 제시해 글의 방향을 바꿉니다.',
  STING: '핵심 이미지나 질문을 남겨 글을 짧고 선명하게 마무리합니다.'
};

export const certaintyLabels = {
  EVIDENCED: '자료 근거 있음',
  INFERENCE: '해석 포함',
  CANDIDATE: '확인 필요'
};

export const auditTypeLabels = {
  CANON: '세계관 사실 점검',
  DISCOURSE: '글의 전개 점검',
  STYLE: '문체 점검'
};

export const documentStatusLabels = {
  draft: '초안',
  review: '검토 중',
  approved: '완료',
  archived: '보관'
};

export const roleLabel = (value) => roleLabels[value] || value;
export const categoryLabel = (value) => categoryLabels[value] || value;
export function pageCategoryKey(page) {
  if (page?.properties_json?.entity_type === 'creature_lineage') return 'creature';
  if (page?.custom_category === '일반 몬스터 종족') return 'creature';
  return page?.category_key || 'free';
}
export const pageCategoryLabel = (page) => categoryLabel(pageCategoryKey(page));
export const relationLabel = (value) => relationLabels[value] || value;
