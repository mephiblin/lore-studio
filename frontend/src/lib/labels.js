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
  LOCATED_IN: '소재함',
  CONTAINS: '포함함',
  CULMINATES_IN: '귀결됨',
  HOME_OF: '거점이 됨',
  INHABITS: '거주함',
  SERVES: '섬김'
};

export const modelRoleLabels = {
  writer: '글 작성',
  utility: '구성·분석',
  vision: '이미지 이해',
  embedding: '자료 검색'
};

export const moveLabels = {
  ORIENT: '맥락 열기',
  NARROW: '초점 좁히기',
  ANCHOR: '핵심 근거·장면',
  COMPLICATE: '문제·예외 검토',
  COMPARE: '비교·대조',
  EXEMPLIFY: '사례·장면',
  ESCALATE: '긴장·중요도 높이기',
  INTERPRET: '의미·분석',
  WITHHOLD: '답을 유보하기',
  TURN: '관점 전환',
  STING: '결론·여운'
};

export const moveDescriptions = {
  ORIENT: '독자가 글의 질문과 상황을 이해하도록 필요한 맥락을 엽니다.',
  NARROW: '넓은 주제에서 이번 글이 다룰 대상이나 쟁점으로 초점을 좁힙니다.',
  ANCHOR: '글의 중심이 되는 근거, 관찰, 장면 또는 주장을 구체적으로 제시합니다.',
  COMPLICATE: '첫 설명만으로 풀리지 않는 문제, 예외, 반론 또는 대가를 검토합니다.',
  COMPARE: '대상, 관점, 전후 상황을 비교해 차이와 기준을 드러냅니다.',
  EXEMPLIFY: '추상적인 생각이나 규칙을 구체적인 사례 또는 장면으로 보여 줍니다.',
  ESCALATE: '갈등, 중요도, 영향 범위를 높여 다음 판단이나 선택으로 이끕니다.',
  INTERPRET: '앞서 제시한 근거나 경험이 무엇을 뜻하는지 분석하고 해석합니다.',
  WITHHOLD: '근거가 부족한 답을 단정하지 않고 질문이나 판단을 유보합니다.',
  TURN: '새 근거, 반론, 깨달음을 제시해 글의 관점이나 방향을 전환합니다.',
  STING: '핵심 결론, 이미지 또는 질문으로 글의 의미와 여운을 남깁니다.'
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
