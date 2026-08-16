---
name: lore-studio-ui-safety
description: Audit and maintain Lore Studio's page UI contracts, interaction-state safety, responsive layout, scroll ownership, fixed bars, card density, orphan controls, and documentation/test synchronization. Use for requests to inspect or verify the Lore Studio UI, check for regressions or tangled states, apply UI or user-facing feature changes, add or remove pages and workflows, or review changes against UI_PAGE_CONTRACT.md and CHANGE_SAFETY_CHECKLIST.md. Also use when a change may require those contracts, this skill, Playwright coverage, or verification records to evolve together.
---

# Lore Studio UI Safety

Treat the repository documents as executable product contracts. Inspect first, preserve user data, fix only when authorized by the request, and leave durable evidence.

## Load the contracts

From the skill directory, read these files completely before acting:

1. [`AGENTS.md`](../../../AGENTS.md)
2. [`UI_PAGE_CONTRACT.md`](../../../docs/UI_PAGE_CONTRACT.md)
3. [`CHANGE_SAFETY_CHECKLIST.md`](../../../docs/CHANGE_SAFETY_CHECKLIST.md)
4. For an explicit full audit, also read [`recursive-audit.md`](../../../docs/product-audit/recursive-audit.md) and use its finding/status conventions.

Inspect the current routes, CSS, tests, worktree, and running app. Do not rely on an earlier audit result after code has changed.

## Classify the request

- **Inspection/report only:** reproduce and document findings. Do not change product code unless the user also requests correction.
- **UI or user-facing feature change:** establish the affected page contract, implement the change, update affected contracts/tests, and run targeted then broad verification.
- **Audit and fix:** record observed findings before implementation, assign severity and acceptance criteria, fix `FIX_NOW` items, then re-audit fresh evidence until none remain.
- **Documentation/contract change:** confirm the current product actually follows the new contract or label it explicitly as future work.

## Run the preflight

Run the deterministic static check from the repository root:

```bash
python3 .codex/skills/lore-studio-ui-safety/scripts/check_contract_sync.py
```

Resolve failures before signoff. A preflight pass does not replace browser QA.
The manifest check compares files that still exist in the worktree; intentional tracked deletions do not need stale manifest entries during the removal change.

## Build a coverage inventory

Map each requested or changed behavior to:

- route and page state;
- user control and resulting state transition;
- desktop and mobile visual state;
- persistence, cancel, reload, project-switch, or deletion consequence;
- expected automated test and durable evidence.

Always include the five lifecycle routes `/`, `/editor`, `/playbook`, `/documents`, and `/lorebook` in a full audit. Include the `/settings` utility route whenever model connection configuration or the global shell changes. Include empty, reading, editing, selected, loading/error, and dense states when applicable.

## Inspect UI safety

Use real browser interaction where available. At minimum check `1600×900`, `390×844`, and `360×844`.

Verify:

- page hierarchy and main-content priority;
- scroll ownership and `min-height: 0` constraints;
- fixed navigation/footer non-overlap;
- cards at empty, one-item, boundary, and dense counts;
- tooltips/modal clipping and z-index;
- read→edit→cancel→edit→save→reload cycles;
- review→edit→cancel/complete return behavior;
- project switching and stale async state;
- visible controls with accessible names and keyboard focus;
- horizontal overflow, page/console errors, empty command bars, dead buttons, orphan panels;
- AI proposals remaining reviewable and unsaved until explicit apply;
- deletion scope, selection cleanup, preserved source documents, and audit logs.

Prefer route interception or disposable fixtures for dense/error states. Never alter real user content merely to stage visual evidence. Clean up disposable records and confirm the remaining project list.

## Keep the skill and contracts synchronized

Apply this matrix in the same change:

| Change | Required synchronization |
|---|---|
| New/removed route, page role, local tab, major layout, card form, scroll owner, fixed region, breakpoint, or state presentation | Update `docs/UI_PAGE_CONTRACT.md` and Playwright coverage |
| New defect class, safety boundary, validation method, destructive action, or recurring regression | Update `docs/CHANGE_SAFETY_CHECKLIST.md` and the relevant test |
| New project invariant | Update `AGENTS.md`, code boundary, tests, and affected docs |
| New audit route, command, source-of-truth path, trigger phrase, or reusable checker | Update this `SKILL.md`, its script, and `agents/openai.yaml` if UI metadata changed |
| New stable repository file | Update `PROJECT_MANIFEST.txt` |
| Test count, migration head, or verified behavior changed | Update `VERIFICATION.md`, `docs/DEVELOPMENT.md`, `docs/IMPLEMENTATION_STATUS.md`, and `docs/ACCEPTANCE_TESTS.md` as applicable |

Do not edit the skill or contracts for an implementation-only class rename when page behavior and audit procedure are unchanged. Do update them when a future agent would otherwise inspect the wrong states or miss a new failure mode.

## Verify proportionally

Run focused tests first. For completed UI changes or a full audit, use:

```bash
git diff --check
make lint
make test
make validate
npm --prefix frontend run build
npm --prefix frontend run test:e2e
# With curated acceptance data available:
make e2e
docker compose exec -T backend alembic current
```

Use actual Chromium screenshots and numeric geometry when spacing, clipping, scroll, or overlap is disputed. If `js_repl` is unavailable, record the limitation and use the repository Playwright runner rather than claiming interactive-session evidence.

## Record and report

For an explicit audit, update `docs/product-audit/recursive-audit.md` with finding ID, severity, evidence, disposition, acceptance criterion, status, verification, and re-audit conclusion. Mark `VERIFIED` only after the acceptance criterion passes.

Before completion:

1. Re-run the static checker.
2. Confirm every in-scope `FIX_NOW` item is verified.
3. Confirm no disposable project or record remains.
4. Validate the audit report when used.
5. Report fixed findings, negative checks, test counts, unverified limits, changed contracts, and commit/push state.

Do not claim “no defects” globally. State that no additional defect was found **within the inspected routes, states, viewports, and checks**.
