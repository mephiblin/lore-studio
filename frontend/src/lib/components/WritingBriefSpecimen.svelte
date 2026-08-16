<script>
  export let ariaLabel = '선택한 결과물 견본';
  export let mark = '원고';
  export let subject = '선택 필요';
  export let outputTitle = '결과물 형태';
  export let outputCopy = '';
  export let background = '선택 안 함';
  export let elements = '선택 안 함';
  export let conflicts = '선택 안 함';
  export let guidance = '선택 안 함';
  export let recipe = '선택 필요';
  export let voice = '모델 기본 문체';
  export let viewpoint = '';
  export let tense = '';
  export let length = '';
  export let tokenEstimate = 0;
</script>

<aside class="output-specimen playbook-output-specimen" aria-label={ariaLabel}>
  <span class="specimen-mark">{mark}</span>
  <div class="specimen-title-block">
    <p>{subject}</p>
    <h2>{outputTitle}</h2>
    <blockquote>{outputCopy}</blockquote>
  </div>
  <section class="specimen-ledger specimen-input-ledger" aria-labelledby="specimen-input-title">
    <header><h3 id="specimen-input-title">원고 설계</h3><small>앞 단계에서 고른 내용</small></header>
    <dl aria-label="현재 원고 설계">
      <div><dt>주제</dt><dd>{subject}</dd></div>
      <div><dt>배경</dt><dd>{background}</dd></div>
      <div><dt>주요 요소</dt><dd>{elements}</dd></div>
      <div><dt>갈등·변수</dt><dd>{conflicts}</dd></div>
      <div><dt>집필 지침</dt><dd>{guidance}</dd></div>
      <div><dt>전개 방식</dt><dd>{recipe}</dd></div>
      <div><dt>문체·필력</dt><dd>{voice}</dd></div>
    </dl>
  </section>
  <section class="specimen-ledger specimen-output-ledger" aria-labelledby="specimen-output-title">
    <header><h3 id="specimen-output-title">출력 설정</h3><small>완성될 글의 기준</small></header>
    <dl class="specimen-selection-summary" aria-label="현재 결과물 설정">
      <div><dt>형식</dt><dd>{outputTitle}</dd></div>
      <div><dt>시점</dt><dd>{viewpoint}</dd></div>
      <div><dt>시제</dt><dd>{tense}</dd></div>
      <div><dt>분량</dt><dd>{length}</dd></div>
    </dl>
  </section>
  <footer><span>예상 {Number(tokenEstimate || 0).toLocaleString()} tokens</span><span>현재 원고 설계 기준</span></footer>
</aside>
