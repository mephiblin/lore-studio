<script>
  import { onMount, tick } from 'svelte';

  export let text = '';
  export let label = '쉬운 설명 보기';

  let open = false;
  let hovered = false;
  let keyboardFocus = false;
  let button;
  let bubble;

  $: visible = open || hovered || keyboardFocus;
  $: if (visible) {
    tick().then(positionBubble);
  }

  function portal(node) {
    if (typeof document === 'undefined') return {};
    document.body.appendChild(node);
    return {
      destroy() {
        node.remove();
      }
    };
  }

  function positionBubble() {
    if (!visible || !button || !bubble || typeof window === 'undefined') return;

    const buttonRect = button.getBoundingClientRect();
    const viewportPadding = 12;
    const gap = 8;
    const width = Math.min(260, window.innerWidth - viewportPadding * 2);

    bubble.style.width = `${width}px`;
    const bubbleHeight = bubble.offsetHeight;
    const placeBelow = buttonRect.top < bubbleHeight + gap + viewportPadding;
    const left = Math.min(
      window.innerWidth - width - viewportPadding,
      Math.max(viewportPadding, buttonRect.left + buttonRect.width / 2 - width / 2)
    );
    const top = placeBelow
      ? buttonRect.bottom + gap
      : buttonRect.top - bubbleHeight - gap;
    const arrowLeft = Math.min(
      width - 12,
      Math.max(12, buttonRect.left + buttonRect.width / 2 - left)
    );

    bubble.style.left = `${left}px`;
    bubble.style.top = `${Math.max(viewportPadding, top)}px`;
    bubble.style.setProperty('--tip-arrow-left', `${arrowLeft}px`);
    bubble.classList.toggle('below', placeBelow);
  }

  function handleKeydown(event) {
    if (event.key !== 'Escape') return;
    open = false;
    keyboardFocus = false;
    button?.blur();
  }

  onMount(() => {
    const reposition = () => {
      if (visible) positionBubble();
    };
    const closeOutside = (event) => {
      if (open && !button?.contains(event.target)) open = false;
    };

    window.addEventListener('resize', reposition);
    window.addEventListener('scroll', reposition, true);
    document.addEventListener('pointerdown', closeOutside, true);
    return () => {
      window.removeEventListener('resize', reposition);
      window.removeEventListener('scroll', reposition, true);
      document.removeEventListener('pointerdown', closeOutside, true);
    };
  });
</script>

<span class="help-tip-wrap">
  <button
    bind:this={button}
    type="button"
    class="help-tip-button"
    aria-label={label}
    aria-expanded={visible}
    on:click={() => open = !open}
    on:mouseenter={() => hovered = true}
    on:mouseleave={() => hovered = false}
    on:focus={() => keyboardFocus = true}
    on:blur={() => keyboardFocus = false}
    on:keydown={handleKeydown}
  >?</button>
  <span
    bind:this={bubble}
    use:portal
    class:visible
    class="help-tip-bubble"
    role="tooltip"
    aria-hidden={!visible}
  >{text}</span>
</span>
