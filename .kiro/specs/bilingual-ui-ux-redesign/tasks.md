# Implementation Plan: StudyGrid Bilingual UI/UX Redesign

## Overview

Incrementally migrate the existing Svelte 5 application without changing FastAPI wire contracts, persistence, or scheduler behavior. The protected 48-hour path is: preserve scheduling authority and fallbacks → generate a plan from analyzed/editable material → render it in calendar/phone agenda views → record a missed or completed session and show the complete backend adaptation. Bilingual accessibility and the `web/src/lib/api.ts` boundary are part of that path, not deferred polish.

Use TypeScript, the existing Playwright runner, and deterministic seeded/bounded generators. Do not add a runtime or test dependency for this feature. Existing Schedule-X packages (`4.8.0`) and `temporal-polyfill` (`0.3.0`) remain exactly pinned; any later dependency exception must have an explicit MIT, Apache-2.0, or BSD license and an exact version before adoption.

## Tasks

- [x] 1. P0 — Lock scheduling and HTTP authority before UI migration
  - [x] 1.1 Remove unauthorized Coach-derived scheduling from the existing calendar
    - In `web/src/components/Calendar.svelte`, remove `AiPreview` timestamp fields, `findSuggestedMove`, `applyAiPreview`, and every prose-driven Apply path while retaining a read-only Coach response and accurate `ai`/`fallback` source.
    - Keep explicit user move/resize and backend `/api/plan`, `/api/progress`, `/api/reschedule`, and health-apply responses as the only paths that can change timestamps; do not create a second allocator or a browser slot finder.
    - _Requirements: 4.1_

  - [x]* 1.2 Write the property test for client scheduling authority
    - **Property 10: No client auto-scheduling**
    - Add a dedicated Playwright/property test that generates Coach replies and event states, proves rendering either provider source cannot change IDs/timestamps, and confirms explicit edits or scheduler-backed responses remain authoritative.
    - Add a source assertion that production frontend files contain no Coach-prose apply action or automatic slot-search helper.
    - **Validates: Requirements 4.1**

  - [x]* 1.3 Add architecture and backend-invariant validation gates
    - Add/extend an automated boundary check proving `fetch` exists only in `web/src/lib/api.ts` and no frontend allocator/automatic-placement implementation exists.
    - If implementation touches `app/`, backend schemas/routes, provider configuration, or scheduler-facing contracts, run all four required unchanged gates: `.venv\Scripts\python.exe scripts\smoke_ai.py`, `.venv\Scripts\python.exe scripts\smoke_coach.py`, `.venv\Scripts\python.exe scripts\smoke_scheduler.py`, and `.venv\Scripts\python.exe scripts\smoke_api.py`.
    - _Requirements: 2.3, 3.3, 4.1, 4.2_

- [x] 2. P0 — Add typed bilingual and deterministic view foundations
  - [x] 2.1 Implement typed locale state, catalogs, and browser-local formatters
    - Create `web/src/lib/i18n/{keys,en,vi,index}.ts` with exact catalog parity, typed arguments, stable enum-label mappings, locale persistence, `<html lang>`, and `Intl` date/time/number/plural/duration helpers.
    - Resolve valid stored locale → first supported browser base locale → `vi`; display authoritative backend prose as data and remove hard-coded `vi-VN`/`GMT+07` formatting as each protected surface migrates.
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 5.1_
  - [x]* 2.2 Write locale and catalog property tests
    - **Property 1: Locale totality and precedence** — generate stored/browser locale combinations and verify supported precedence. **Validates: Requirements 1.1**
    - **Property 2: Catalog parity** — exercise every key and valid argument shape in both catalogs without missing/raw output. **Validates: Requirements 1.2**
    - **Property 3: Locale round trip** — persist/reload each supported locale and verify `<html lang>`. **Validates: Requirements 1.3**

  - [x]* 2.3 Write the property test for browser-local time consistency
    - **Property 4: Browser-local time consistency**
    - Generate valid instants, including supported DST boundaries, and assert schedule text/accessibility labels use one browser-local contract with no hard-coded `GMT+07`.
    - **Validates: Requirements 1.4**

  - [x] 2.4 Extract pure setup and schedule state modules from existing components
    - Add typed pure modules for `PlanDraft` validation/request conversion and schedule projection/view models; preserve `web/src/lib/types.ts` wire shapes and keep all HTTP calls in `web/src/lib/api.ts`.
    - Convert daily hours to integer `weekday_minutes`, derive display totals, flag/exclude non-zero short days from full-session capacity, project visible events immutably, and order by local start then stable ID.
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.4, 3.6_

  - [~]* 2.5 Write setup and schedule derivation property tests
    - **Property 5: Projection conservation** — visible events occur once and canonical input is unchanged. **Validates: Requirements 3.1**
    - **Property 6: Stable ordering** — all input permutations produce local-start-then-ID order. **Validates: Requirements 3.2**
    - **Property 7: Setup preservation** — arbitrary Back/Continue sequences preserve draft and analysis state until explicit reset/removal. **Validates: Requirements 2.1**
    - **Property 8: Request conversion** — generated hour maps serialize correctly and short days are excluded/flagged. **Validates: Requirements 2.2**

  - [~]* 2.6 Write filter and deterministic-derivation property tests
    - **Property 13: Filter reversibility** — toggling a subject twice restores visible IDs/order without mutating canonical events. **Validates: Requirements 3.4**
    - **Property 18: Deterministic UI derivation** — equal canonical data and complete context yield deeply equal view models/adaptation summaries. **Validates: Requirements 3.6**

- [ ] 3. P0 — Deliver material analysis through plan generation end to end
  - [ ] 3.1 Refactor the existing `IntakeForm.svelte` into a preserving staged setup
    - Build Basics, Materials, Topics, Availability, Commitments, and Review over one parent-owned `PlanDraft`; retain existing text/file/URL analysis, editable topics, session presets/custom duration, breaks, commitments, and strategy/start-date fields.
    - Add localized linked validation, first-invalid focus, short-day warnings, and final conversion to the current `PlanRequest`; submit only through `createPlan` in `lib/api.ts`.
    - _Requirements: 1.2, 2.1, 2.2, 5.2_

  - [ ] 3.2 Preserve deterministic material fallback and expose analysis truth
    - Keep the existing analyze/upload/URL endpoints and backend fallback untouched; display loading, truncation, retryable errors, and the exact returned `source` without calling fallback AI.
    - Preserve input and prior topics on failure, keep every returned topic editable, and render material/topic/error strings as text.
    - _Requirements: 2.1, 2.3, 6.1_

  - [~]* 3.3 Write the property test for analysis transparency
    - **Property 9: Analysis transparency**
    - Generate `ai` and `fallback` results, topic arrays, and truncation states; verify exact source disclosure, editable topics, preserved failure state, and no fallback-as-AI label.
    - **Validates: Requirements 2.3**

  - [ ] 3.4 Wire atomic plan creation and first schedule load in `App.svelte`
    - On submit, call `createPlan`, then load `getEvents` through `lib/api.ts`; atomically commit the returned plan, canonical events, warnings, and unscheduled work before closing setup and announcing/focusing the schedule.
    - Preserve anonymous restoration/deletion, theme/locale, deterministic provider fallback, previous state on failure, and the existing same-origin relative API contract.
    - _Requirements: 1.3, 2.1, 2.3, 3.3, 4.1, 4.2, 5.2_

  - [~]* 3.5 Add the protected analyze → generate → calendar integration test
    - Extend `web/tests/app.spec.ts` with deterministic requests for text/file analysis in both sources, editable topics, valid conversion, generated events, warning/unscheduled visibility, reload restoration, and API failure rollback.
    - Run with the existing Playwright web servers and fallback provider; do not introduce a new mock framework or direct component `fetch`.
    - _Requirements: 1.2, 2.1, 2.2, 2.3, 3.3, 4.1, 4.2, 6.1_

- [ ] 4. Checkpoint — Ensure the protected generation flow passes
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. P0 — Render the generated plan in desktop calendar and phone agenda
  - [ ] 5.1 Migrate `Calendar.svelte` incrementally to shared schedule projections
    - Keep the existing calendar operational while extracting schedule workspace/toolbar, event rendering, filters, and unscheduled presentation; use one canonical event array and the pure projection module.
    - Retain week and month, make month overflow controls open the date agenda, remove dead search/account controls, and localize dates, timezone, accessible event names, warnings, and status labels.
    - _Requirements: 1.4, 3.1, 3.2, 3.4, 3.6, 5.1_

  - [ ] 5.2 Add a first-class phone agenda with command parity
    - Make agenda primary below 768px, grouped by browser-local date, while preserving month overview and desktop week behavior.
    - Expose select/create/edit/reschedule/delete/filter/navigation through keyboard/touch controls with the same semantic command and `lib/api.ts` intent as desktop; empty-time creation must not depend on double-click.
    - _Requirements: 3.7, 5.2_

  - [ ] 5.3 Implement explicit edit drafts, target isolation, and rollback
    - Route pointer move/resize and session-form date/time edits through the existing `updateSession` API wrapper; draft only the target event and commit canonical data only after success.
    - On validation/network/conflict failure restore canonical/rendered values, leave unrelated events untouched, and announce a localized actionable error; never find an alternate slot in the browser.
    - _Requirements: 3.3, 3.5, 3.7, 4.1_

  - [~]* 5.4 Write schedule interaction property tests
    - **Property 12: Failed edit rollback** — inject failures across move/resize/layout/conflict operations and compare pre/post canonical and rendered values. **Validates: Requirements 3.3**
    - **Property 17: Optimistic isolation** — generate pending edits and verify only the target may receive a draft transform before success. **Validates: Requirements 3.5**
    - **Property 19: Responsive functional parity** — generate core command matrices and verify desktop and phone paths produce the same API intent/outcome. **Validates: Requirements 3.7**

  - [~]* 5.5 Write the property test for state meaning without color
    - **Property 14: State meaning without color**
    - Generate every completion/review/readiness/warning state in both locales/themes and verify visible text or a non-color marker plus equivalent accessible text.
    - **Validates: Requirements 5.1**

- [ ] 6. P0 — Complete backend-authoritative adaptive rescheduling
  - [ ] 6.1 Reconcile progress and reschedule responses atomically in `App.svelte`
    - Unify completion/partial/missed submission and subsequent `rescheduleCancelledSession` actions so sessions/events, `changes[]`, warnings, unscheduled entries, and proposals come from one backend response cycle before announcement.
    - Keep the prior canonical schedule on failure, reject stale/mismatched results, and preserve the backend's existing single-`TimeAllocator` placement and explicit capacity-approval flow.
    - _Requirements: 3.3, 3.6, 4.1, 4.2_

  - [ ] 6.2 Render complete adaptations and unscheduled work
    - Replace fragmented change output with one adaptation summary that renders every returned change in order, authoritative `why`, localized before/after times, warnings, unscheduled entries, and an explicit no-change outcome.
    - Keep blocked/unscheduled work visible until superseded; return focus to a stable schedule target without forced smooth scrolling under reduced motion.
    - _Requirements: 4.2, 5.3, 6.1_

  - [~]* 6.3 Write the property test for adaptation completeness
    - **Property 11: Adaptation completeness**
    - Generate empty and populated adaptation payloads, duplicate-looking rows, warnings, blocked/cancelled changes, and unscheduled entries; assert exact exposure with no omission or invention.
    - **Validates: Requirements 4.2**

  - [~]* 6.4 Add the protected generate → miss → reschedule integration test
    - Extend Playwright to generate a plan, mark a session missed/partial with reason, exercise full-slot/split/approval/backlog outcomes, and verify calendar replacement plus complete adaptation explanation in both locales.
    - Assert Coach responses cannot mutate timestamps, fallback mode remains usable, all network intents route through `/api`, and failed rescheduling restores the prior schedule.
    - _Requirements: 1.2, 3.3, 3.7, 4.1, 4.2, 6.1_

- [ ] 7. Checkpoint — Ensure generation, calendar, and adaptation tests pass
  - Ensure all tests pass, ask the user if questions arise.
- [ ] 8. P1 — Harden dialogs, safe rendering, and reduced motion on core flows
  - [ ] 8.1 Add shared Dialog/Sheet, status, and focus contracts
    - Create small Svelte primitives/helpers for native modal behavior, trigger capture, initial focus, Tab containment fallback, Escape/Cancel/Close/Success, exact inert lifetime, status announcements, and stable focus restoration.
    - Migrate setup, create, session, and reschedule overlays incrementally; prohibit nested modals and make reduced motion instant while preserving state/focus/announcements.
    - _Requirements: 5.2, 5.3_

  - [ ] 8.2 Centralize plain-text rendering and bilingual status semantics
    - Audit material names/topics, event labels, adaptation prose, Coach content, warnings/unscheduled entries, and API errors; use Svelte text interpolation/text content only and reject executable URL/HTML/event-handler creation.
    - Finish localized labels and non-color state cues across protected surfaces without pretending authoritative backend prose was translated.
    - _Requirements: 1.2, 5.1, 6.1_

  - [~]* 8.3 Write accessibility and safe-rendering property tests
    - **Property 15: Modal focus safety** — generate overlay kinds, close paths, and trigger survival; verify containment, inert lifetime, and focus restoration. **Validates: Requirements 5.2**
    - **Property 16: Reduced-motion equivalence** — replay generated workflows and compare final data/focus/announcement state. **Validates: Requirements 5.3**
    - **Property 20: Unsafe content rendering** — inject HTML/script-like English/Vietnamese strings into each untrusted surface and verify text output with no executable DOM/handlers. **Validates: Requirements 6.1**

- [ ] 9. P2 — Consolidate the read-only Coach and core shell
  - [ ] 9.1 Replace duplicate calendar AI UI and `StudyCoach.svelte` usage with one Coach panel
    - Use only `sendCoachMessage` from `lib/api.ts`, current plan, optional selected session, bounded transcript, active locale, and accurate provider source.
    - Expose advice and suggested explicit next actions only; no prose Apply control, timestamp fields, or mutation claim. Preserve deterministic provider fallback.
    - _Requirements: 2.3, 4.1, 6.1_

  - [ ] 9.2 Finish shell integration and remove obsolete code after parity
    - Reduce `App.svelte` to restoration, identity, canonical state, surfaces/overlays, API command orchestration, and reconciliation; wire setup, schedule, session, adaptation, Coach, privacy, locale, and theme end to end.
    - Remove replaced mixed-language strings, duplicate Coach/AI state, dead controls, and obsolete styles only after protected Playwright coverage passes; retain compatibility wrappers until callers migrate.
    - _Requirements: 1.2, 1.3, 2.1, 3.3, 3.6, 4.1, 4.2, 5.2_

- [ ] 10. P3 — Optional post-demo Progress/readiness localization
  - [~]* 10.1 Migrate Progress and readiness presentation without changing backend truth
    - Localize UI chrome and stable enum values in existing `ProgressDashboard.svelte` and `HealthReadiness.svelte`; retain authoritative backend prose, `plan.history` aggregation, and existing confidence thresholds.
    - Add textual chart equivalents, localized durations, accessible loading/empty/error states, predictable focus, and complete scheduler-backed health adaptation output with explicit confirmation.
    - This is below the 48-hour cut line; do not start it until Task 7 passes.
    - _Requirements: 1.2, 1.4, 3.7, 4.1, 4.2, 5.1, 5.2_

- [ ] 11. P3 — Optional post-demo breadth and release hardening
  - [~]* 11.1 Expand bilingual accessibility integration coverage
    - Run critical first-run/setup/schedule/session/adaptation/Coach flows in `vi` and `en`; run Axe on migrated surfaces and add explicit focus, live-region, 44px touch target, drag alternative, non-color, 200% zoom, text-spacing, and 320/390px overflow checks.
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 3.7, 5.1, 5.2, 5.3_

  - [~]* 11.2 Add bounded visual and performance regression checks
    - Capture deterministic light/dark, English/Vietnamese, loading/error/warning/unscheduled/long-text/reduced-motion screenshots only for protected surfaces and compare production gzip output to a recorded baseline.
    - Verify bounded projection/filter work with 200 events and no translation-only network calls; decorative grid/connection motifs are first to cut and must remain static, low contrast, `aria-hidden`, and removable on small screens if implemented.
    - _Requirements: 1.2, 1.4, 3.1, 3.5, 3.6, 5.3_

  - [~]* 11.3 Run the final validation matrix
    - Run `npm run check`, `npm run build`, and `npx playwright test` from `web/` using non-watch execution.
    - Because any accidental backend-affecting diff must be caught, run all four required smoke scripts from the repository root: `.venv\Scripts\python.exe scripts\smoke_ai.py`, `.venv\Scripts\python.exe scripts\smoke_coach.py`, `.venv\Scripts\python.exe scripts\smoke_scheduler.py`, and `.venv\Scripts\python.exe scripts\smoke_api.py`.
    - Re-run the HTTP/scheduling boundary assertion and fail release if `fetch` appears outside `web/src/lib/api.ts`, client automatic placement exists, provider fallback fails, or more than one allocator is used for a plan build.
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.3, 3.3, 3.6, 4.1, 4.2, 5.1, 5.2, 5.3, 6.1_

- [ ] 12. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- **48-hour protected path:** Tasks 1–7. The demo must work end to end in fallback mode: analyze/edit topics → generate through `POST /api/plan` → render canonical events → record progress/miss → apply a backend reschedule choice → expose all changes/warnings/unscheduled work.
- **Cut line:** Tasks 8–9 are hardening/consolidation after the protected path. Tasks 10–11 are optional post-demo breadth and are cut first. Within any task, cut decorative motifs and broad screenshot matrices before functionality, scheduling correctness, fallback disclosure, bilingual core copy, keyboard/touch parity, or focus safety.
- Tasks marked `*` are optional implementation/test work for a faster MVP and are still represented in the dependency graph. Every approved correctness property remains explicit and executable.
- No application code is changed by this plan. No dependency is proposed. Existing runtime pins remain unchanged. Any future package must be exactly pinned and verified as MIT, Apache-2.0, or BSD before it enters the task plan or lockfile.
- Frontend code must never calculate automatic slots, instantiate `TimeAllocator`, call `fetch` outside `web/src/lib/api.ts`, hide backend warnings/unscheduled work, or represent deterministic fallback as AI.
- If a task changes backend behavior or scheduler-facing contracts despite the presentation-only scope, the four mandatory smoke scripts in Tasks 1.3 and 11.3 are required; additional domain smokes may supplement but never replace them.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "2.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "2.2", "2.3", "2.4"] },
    { "id": 2, "tasks": ["2.5", "2.6", "3.1"] },
    { "id": 3, "tasks": ["3.2"] },
    { "id": 4, "tasks": ["3.3", "3.4"] },
    { "id": 5, "tasks": ["3.5", "5.1"] },
    { "id": 6, "tasks": ["5.2", "5.5"] },
    { "id": 7, "tasks": ["5.3"] },
    { "id": 8, "tasks": ["5.4", "6.1"] },
    { "id": 9, "tasks": ["6.2"] },
    { "id": 10, "tasks": ["6.3", "6.4", "8.1"] },
    { "id": 11, "tasks": ["8.2"] },
    { "id": 12, "tasks": ["8.3", "9.1"] },
    { "id": 13, "tasks": ["9.2"] },
    { "id": 14, "tasks": ["10.1", "11.1", "11.2"] },
    { "id": 15, "tasks": ["11.3"] }
  ]
}
```
