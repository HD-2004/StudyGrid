# Requirements Document

## Introduction

These requirements are derived from the approved design-first artifact for the StudyGrid `bilingual-ui-ux-redesign` feature. They define the stable acceptance criteria needed to trace the design's correctness properties without changing the existing scheduling authority, persistence model, or backend wire boundaries.

## Glossary

- **StudyGrid UI**: The Svelte browser interface covered by this redesign.
- **Canonical Events**: The event data most recently accepted from the backend, before any temporary interaction draft.
- **Scheduler-backed Response**: A backend response whose time placement was produced and validated through the plan's single `TimeAllocator`.
- **Deterministic Fallback**: Non-model behavior that keeps material analysis or coaching usable when the configured AI provider fails.
- **Active Locale**: The currently resolved supported locale, either Vietnamese (`vi`) or English (`en`).

## Requirements

### Requirement 1: Bilingual Locale and Formatting

**User Story:** As a Vietnamese- or English-speaking student, I want the interface and local formatting to follow my persisted language preference so that I can understand and trust the schedule.

#### Acceptance Criteria

1. WHEN locale resolution receives stored and browser language values, THE StudyGrid UI SHALL return a supported locale, prefer a valid stored locale, then the first supported browser locale, then Vietnamese.
2. THE StudyGrid UI SHALL provide complete, type-compatible Vietnamese and English catalog entries for every translation key and SHALL produce rendered messages without missing-key output.
3. WHEN a student selects a supported locale, THE StudyGrid UI SHALL persist that locale and restore the same locale and matching document language after reload.
4. WHILE the StudyGrid UI is operational and presents schedule or progress data, THE StudyGrid UI SHALL actively render applicable dates, times, numbers, durations, and accessible event labels using the active locale and browser-local timezone consistently and SHALL NOT hard-code `GMT+07`.

### Requirement 2: Preserved and Transparent Plan Setup

**User Story:** As a student creating a plan, I want staged setup to preserve my work and explain analysis outcomes so that I can safely review inputs before generating a schedule.

#### Acceptance Criteria

1. WHEN a student navigates forward or backward through setup stages, THE StudyGrid UI SHALL preserve all entered values and material-analysis results until explicit removal or reset.
2. WHEN the StudyGrid UI converts a valid setup draft into a plan request, THE StudyGrid UI SHALL convert daily hours to the defined weekday-minute values, derive the weekly display total from those values, and exclude non-zero days shorter than one session from usable full-session capacity.
3. WHEN material analysis succeeds, THE StudyGrid UI SHALL display the response's actual source, keep every returned topic editable, and SHALL NOT represent deterministic fallback output as AI output.

### Requirement 3: Deterministic Schedule Projection and Explicit Editing

**User Story:** As a student using calendar or agenda views, I want every view and edit to remain consistent with canonical schedule data so that filtering and failed interactions cannot corrupt my plan.

#### Acceptance Criteria

1. WHEN events are projected into week, month, or agenda views, THE StudyGrid UI SHALL include every visible-subject event exactly once, exclude hidden-subject events, and leave canonical event data unchanged.
2. WHEN the same event set is supplied in any input order, THE StudyGrid UI SHALL produce the same local-start-then-stable-ID projection order.
3. IF any operation modifies event presentation or state and then fails, including explicit move/resize or implicit layout/conflict operations, THEN THE StudyGrid UI SHALL restore canonical and rendered events to their pre-command values.
4. WHEN a subject filter is toggled twice, THE StudyGrid UI SHALL restore the same visible event identities and order without changing canonical events.
5. WHILE an explicit event edit awaits confirmation, THE StudyGrid UI SHALL apply draft presentation to at most the target event and SHALL leave unrelated events and persisted state unchanged.
6. WHEN canonical API data, locale, timezone, theme, filters, and anchor date are equal, THE StudyGrid UI SHALL derive deeply equal schedule view models and adaptation summaries.
7. WHERE a core command is available in desktop week view, THE StudyGrid UI SHALL provide a keyboard- and touch-operable command with the same API intent and outcome in phone agenda or session surfaces.

### Requirement 4: Backend Scheduling Authority and Complete Adaptation

**User Story:** As a student relying on an adaptive plan, I want schedule changes to come only from explicit edits or the backend scheduler and to be fully explained so that AI prose cannot silently alter my calendar.

#### Acceptance Criteria

1. WHEN the Study Coach response is received or rendered, THE StudyGrid UI SHALL leave all event timestamps and identities unchanged; concurrently completed explicit manual update commands or scheduler-backed API responses take priority and may change them.
2. WHEN an adaptation command succeeds, THE StudyGrid UI SHALL expose every returned change, warning, and unscheduled entry without omission or invention, including an explicit no-change outcome.

### Requirement 5: Accessible State, Focus, and Motion

**User Story:** As a student using assistive technology, a keyboard, touch, zoom, or reduced motion, I want equivalent and understandable interactions so that I can complete every core workflow.

#### Acceptance Criteria

1. WHEN session status is rendered, THE StudyGrid UI SHALL identify it in both locales with visible text or a non-color marker and equivalent accessible text.
2. WHEN a modal overlay opens or closes by Escape, Cancel, Success, or Close, THE StudyGrid UI SHALL contain focus while open, mark background content inert only while open, and restore focus to the invoking control or documented fallback after close.
3. WHEN reduced motion is requested, THE StudyGrid UI SHALL reach the same final data, focus, and announcement state as default motion without continuous animation or smooth scrolling.

### Requirement 6: Safe Untrusted-Text Rendering

**User Story:** As a student viewing imported material and backend explanations, I want untrusted strings rendered safely so that content cannot execute in the interface.

#### Acceptance Criteria

1. WHEN the StudyGrid UI renders user-provided or backend-provided strings containing HTML- or script-like content, THE StudyGrid UI SHALL both render that value as text and prevent creation of executable DOM or event handlers; violation of either condition SHALL fail this criterion.
