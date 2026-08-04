import { Node, mergeAttributes } from '@tiptap/core';

export const LoreBlock = Node.create({
  name: 'loreBlock',
  group: 'block',
  content: 'block+',
  defining: true,
  addAttributes() {
    return {
      rhetoricalMove: { default: 'ANCHOR' },
      playbookStep: { default: 'DRAFT_BLOCKS' },
      evidenceIds: { default: [] },
      certainty: { default: 'CANDIDATE' },
      sourceRole: { default: 'CANDIDATE' },
      generationRun: { default: null },
      locked: { default: false },
      candidateClaims: { default: [] },
      auditWarnings: { default: [] }
    };
  },
  parseHTML() { return [{ tag: 'section[data-lore-block]' }]; },
  renderHTML({ HTMLAttributes }) {
    return ['section', mergeAttributes(HTMLAttributes, { 'data-lore-block': '' }), 0];
  }
});
