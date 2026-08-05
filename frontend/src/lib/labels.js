export const roleLabels = {
  PROJECT_CANON: '정식 설정',
  DRAFT_SETTING: '설정 초안',
  CANON_EVIDENCE: '정사 근거',
  SECONDARY_INTERPRETATION: '해석 자료',
  INSPIRATION: '영감 자료',
  DISCOURSE_REFERENCE: '문체 참고',
  CANDIDATE: '검토 후보',
  REJECTED: '제외됨'
};

export const categoryLabels = {
  artifact: '유물·기술',
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
  writer: '원고 작성',
  utility: '구성·분석',
  vision: '이미지 이해',
  embedding: '자료 검색'
};

export const moveLabels = {
  ORIENT: '맥락 열기',
  NARROW: '대상으로 좁히기',
  ANCHOR: '핵심 사실',
  COMPLICATE: '복잡성 추가',
  COMPARE: '비교',
  EXEMPLIFY: '사례',
  ESCALATE: '긴장 높이기',
  INTERPRET: '의미 해석',
  WITHHOLD: '미스터리 남기기',
  TURN: '전환',
  STING: '여운'
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
export const relationLabel = (value) => relationLabels[value] || value;
