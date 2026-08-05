<script>
  export let text = '';
  export let label = '쉬운 설명 보기';
  let open = false;
</script>

<span class:open class="help-tip-wrap">
  <button type="button" class="help-tip-button" aria-label={label} aria-expanded={open} on:click={() => open = !open} on:keydown={(event) => { if (event.key === 'Escape') open = false; }}>?</button>
  <span class="help-tip-bubble" role="tooltip">{text}</span>
</span>
