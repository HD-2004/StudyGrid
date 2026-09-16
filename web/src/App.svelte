<script lang="ts">
  import { onMount, tick } from 'svelte'
  import {
    createPlan,
    deletePlan,
    deleteSessionData,
    getEvents,
    getInsights,
    getLatestPlan,
    getMissReasons,
    getPrivacy,
    submitProgress,
    ApiError,
  } from './lib/api'
  import type {
    CalendarEvent,
    Completion,
    Insights as InsightsData,
    MissReason,
    PlanChange,
    PlanRequest,
    PlanResponse,
    PrivacyResponse,
    ReasonOption,
    Recall,
  } from './lib/types'
  import Calendar from './components/Calendar.svelte'
  import ChangeLog from './components/ChangeLog.svelte'
  import Insights from './components/Insights.svelte'
  import IntakeForm from './components/IntakeForm.svelte'
  import ProgressDashboard from './components/ProgressDashboard.svelte'
  import SessionDetail from './components/SessionDetail.svelte'
  import StudyCoach from './components/StudyCoach.svelte'

  type Theme = 'light' | 'dark'

  let plan = $state<PlanResponse | null>(null)
  let events = $state<CalendarEvent[]>([])
  let changes = $state<PlanChange[]>([])
  let insights = $state<InsightsData | null>(null)
  let reasons = $state<ReasonOption[]>([])
  let selectedId = $state<string | null>(null)
  let building = $state(false)
  let updating = $state(false)
  let resetting = $state(false)
  let restoring = $state(true)
  let deletingData = $state(false)
  let deleteArmed = $state(false)
  let setupOpen = $state(false)
  let progressOpen = $state(false)
  let error = $state<string | null>(null)
  let theme = $state<Theme>('light')
  let themeReady = $state(false)
  let privacy = $state<PrivacyResponse | null>(null)
  let plannerDialog = $state<HTMLDialogElement | null>(null)
  let setupTrigger = $state<HTMLElement | null>(null)

  onMount(() => {
    const stored = localStorage.getItem('studygrid-theme')
    theme =
      stored === 'light' || stored === 'dark'
        ? stored
        : window.matchMedia('(prefers-color-scheme: dark)').matches
          ? 'dark'
          : 'light'
    themeReady = true
    void restoreLatestPlan()
    getPrivacy()
      .then((response) => (privacy = response))
      .catch(() => (privacy = null))
  })

  $effect(() => {
    if (!themeReady) return
    document.documentElement.dataset.theme = theme
    document.documentElement.style.colorScheme = theme
    localStorage.setItem('studygrid-theme', theme)
  })

  $effect(() => {
    if (!plannerDialog) return
    if (setupOpen && !plannerDialog.open) plannerDialog.showModal()
    if (!setupOpen && plannerDialog.open) plannerDialog.close()
  })

  // Reason labels come from the backend. A failure here must not block the
  // core flow, so the prompt simply does not appear.
  $effect(() => {
    getMissReasons()
      .then((response) => (reasons = response))
      .catch(() => (reasons = []))
  })

  const selected = $derived(events.find((event) => event.id === selectedId) ?? null)

  const counts = $derived({
    learn: events.filter((event) => !event.is_review).length,
    review: events.filter((event) => event.is_review).length,
    hours: events.reduce(
      (total, event) => total + (Date.parse(event.end) - Date.parse(event.start)) / 3.6e6,
      0,
    ),
  })

  const guideStep = $derived(!plan ? 0 : progressOpen ? 2 : changes.length ? 3 : selected ? 2 : 1)
  const guideCopy = $derived(
    [
      'Add your subjects, planning date, study windows, and fixed commitments.',
      'Review the calendar. Select any session to record how it went.',
      'Log completion and recall so StudyGrid can adapt the remaining sessions.',
      'Review what moved and use the coach or insights to decide what to do next.',
    ][guideStep],
  )

  function openSetup(trigger?: HTMLElement) {
    setupTrigger = trigger ?? null
    setupOpen = true
  }

  async function closeSetup() {
    setupOpen = false
    await tick()
    setupTrigger?.focus()
  }

  async function build(request: PlanRequest) {
    building = true
    error = null
    changes = []
    insights = null
    selectedId = null
    try {
      const created = await createPlan(request)
      const createdEvents = await getEvents(created.plan_id)
      plan = created
      events = createdEvents
      progressOpen = false
      await closeSetup()
      document.querySelector<HTMLElement>('.calendar-panel')?.focus()
    } catch (reason) {
      error = reason instanceof ApiError ? reason.message : 'Something went wrong building the plan.'
    } finally {
      building = false
    }
  }

  async function restoreLatestPlan() {
    try {
      const latest = await getLatestPlan()
      if (!latest) return
      const [restoredEvents, restoredInsights] = await Promise.all([
        getEvents(latest.plan_id),
        getInsights(latest.plan_id),
      ])
      plan = latest
      events = restoredEvents
      insights = restoredInsights
    } catch (reason) {
      error = reason instanceof ApiError ? reason.message : 'Could not restore your saved plan.'
    } finally {
      restoring = false
    }
  }

  async function record(
    completion: Completion,
    recall: Recall | null,
    missReason: MissReason | null,
  ) {
    if (!plan || !selectedId) return
    updating = true
    error = null
    try {
      const result = await submitProgress(
        plan.plan_id,
        selectedId,
        completion,
        recall,
        missReason,
      )
      changes = result.changes
      insights = result.insights
      plan = { ...plan, sessions: result.sessions, warnings: result.warnings }
      events = await getEvents(plan.plan_id)
      selectedId = null
      progressOpen = true
    } catch (reason) {
      error = reason instanceof ApiError ? reason.message : 'Could not save your progress.'
    } finally {
      updating = false
    }
  }

  async function startOver(event: MouseEvent) {
    if (!plan || resetting) return
    resetting = true
    error = null
    try {
      await deletePlan(plan.plan_id)
      plan = null
      events = []
      changes = []
      insights = null
      selectedId = null
      progressOpen = false
      openSetup(event.currentTarget as HTMLElement)
    } catch (reason) {
      error = reason instanceof ApiError ? reason.message : 'Could not reset this plan.'
    } finally {
      resetting = false
    }
  }

  async function eraseSessionData() {
    if (!deleteArmed) {
      deleteArmed = true
      return
    }
    deletingData = true
    error = null
    try {
      await deleteSessionData()
      plan = null
      events = []
      changes = []
      insights = null
      selectedId = null
      progressOpen = false
      deleteArmed = false
    } catch (reason) {
      error = reason instanceof ApiError ? reason.message : 'Could not delete your session data.'
    } finally {
      deletingData = false
    }
  }
</script>

<a class="skip-link" href="#main-content">Skip to planner</a>

<div class="app-frame">
  <header class="topbar">
    <a class="brand" href="#main-content" aria-label="StudyGrid home">
      <span class="brand-mark" aria-hidden="true">SG</span>
      <span>StudyGrid</span>
    </a>
    <nav aria-label="Application controls">
      <button
        type="button"
        class="control-button"
        aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
        onclick={() => (theme = theme === 'light' ? 'dark' : 'light')}>
        {theme === 'light' ? 'Dark' : 'Light'} theme
      </button>
      {#if plan}
        <button type="button" class="control-button" disabled={resetting} onclick={startOver}>
          {resetting ? 'Resetting…' : 'Start a new plan'}
        </button>
      {:else}
        <button
          type="button"
          class="primary-action"
          onclick={(event) => openSetup(event.currentTarget)}>
          Create plan
        </button>
      {/if}
    </nav>
  </header>

  <main id="main-content" class="app-shell" inert={setupOpen}>
    <section class="intro" aria-labelledby="page-title">
      <div>
        <p class="product-label">Adaptive study planner</p>
        <h1 id="page-title">Create your study schedule</h1>
      </div>
      <p>
        Turn course material, deadlines, and your real availability into a plan that
        responds to what you remember.
      </p>
    </section>

    {#if error}
      <div class="error-banner" role="alert">
        <span>{error}</span>
        <button type="button" class="text-button" onclick={() => (error = null)}>Dismiss</button>
      </div>
    {/if}

    <section class="guide" aria-labelledby="guide-title" aria-live="polite">
      <div class="guide-copy">
        <span class="guide-count">{guideStep + 1} of 4</span>
        <div>
          <h2 id="guide-title">
            {['Set up your week', 'Review the plan', 'Log a session', 'See the adaptation'][guideStep]}
          </h2>
          <p>{guideCopy}</p>
        </div>
      </div>
      <ol aria-label="Demo progress">
        {#each ['Setup', 'Plan', 'Progress', 'Adapt'] as label, index (label)}
          <li class:active={index === guideStep} class:complete={index < guideStep}>
            <span aria-hidden="true">{index + 1}</span>
            <span>{label}</span>
          </li>
        {/each}
      </ol>
      {#if plan}
        <button
          type="button"
          class="guide-action quiet"
          aria-pressed={progressOpen}
          onclick={() => {
            progressOpen = !progressOpen
            selectedId = null
          }}>
          {progressOpen ? 'Back to planner' : 'Open progress'}
        </button>
      {/if}
    </section>

    {#if plan && (plan.warnings.length || plan.unscheduled.length)}
      <section class="caveats" aria-labelledby="capacity-title">
        <h2 id="capacity-title">Plan limits</h2>
        {#each plan.warnings as warning (warning)}
          <p>{warning}</p>
        {/each}
        {#if plan.unscheduled.length}
          <p>
            No room before the exam for {plan.unscheduled.join(', ')}. Free up more time or
            remove a topic.
          </p>
        {/if}
      </section>
    {/if}

    {#if progressOpen && plan}
      <ProgressDashboard onClose={() => (progressOpen = false)} />
    {:else}
    <div class="workspace">
      <section class="calendar-panel" aria-labelledby="calendar-heading" tabindex="-1">
        <header class="calendar-header">
          <div>
            <h2 id="calendar-heading">Study calendar</h2>
            <p>{plan?.summary ?? 'Your generated sessions will appear here.'}</p>
          </div>
          {#if plan}
            <dl class="summary" aria-label="Plan summary">
              <div>
                <dt>First passes</dt>
                <dd>{counts.learn}</dd>
              </div>
              <div>
                <dt>Reviews</dt>
                <dd>{counts.review}</dd>
              </div>
              <div>
                <dt>Hours booked</dt>
                <dd>{counts.hours.toFixed(1)}</dd>
              </div>
            </dl>
          {/if}
        </header>

        {#if plan}
          <div class="key" aria-label="Calendar legend">
            <span><i class="swatch learn"></i>New material</span>
            <span><i class="swatch review"></i>Review</span>
            <span><i class="swatch flag"></i>Needs another look</span>
          </div>
        {/if}

        <div class="calendar-frame">
          <Calendar {events} {theme} onSelect={(id) => (selectedId = id)} />
          {#if !plan}
            <div class="empty-calendar-overlay">
              <div class="empty-calendar-card">
                <span class="empty-index" aria-hidden="true">01</span>
                {#if restoring}
                  <h3>Restoring your plan</h3>
                  <p role="status">Checking this browser's private study session…</p>
                {:else}
                  <h3>Build around your real week</h3>
                  <p>Add subjects, exam dates, available hours, and fixed commitments.</p>
                  <button
                    type="button"
                    class="primary-action"
                    onclick={(event) => openSetup(event.currentTarget)}>
                    Create study plan
                  </button>
                {/if}
              </div>
            </div>
          {/if}
        </div>
      </section>

      <aside class="rail" aria-label="Plan details and guidance">
        {#if selected}
          {#key selected.id}
            <SessionDetail
              event={selected}
              busy={updating}
              {reasons}
              onSubmit={record}
              onClose={() => (selectedId = null)} />
          {/key}
        {:else if plan}
          <section class="rail-empty">
            <span class="rail-number">{events.length}</span>
            <h2>Choose a session</h2>
            <p>Select a calendar event to record completion and recall. StudyGrid will explain every change.</p>
          </section>
        {:else}
          <section class="rail-empty">
            <span class="rail-number">0</span>
            <h2>No sessions yet</h2>
            <p>Create a plan to see the calendar, coach, and time-use insights working together.</p>
          </section>
        {/if}

        {#if plan}
          <StudyCoach planId={plan.plan_id} focusSessionId={selectedId} />
          <ChangeLog {changes} />
          <Insights {insights} />
        {/if}
      </aside>
    </div>
    {/if}

    {#if privacy}
      <footer class="privacy-note" aria-label="User-test data controls">
        <div>
          <strong>Anonymous user-test session</strong>
          <p>
            {privacy.durable_storage
              ? `This browser's plans are retained for up to ${privacy.retention_days} days.`
              : 'Plans are temporary on this development server.'}
            No account or personal profile is created.
          </p>
        </div>
        <button
          type="button"
          class:danger-action={deleteArmed}
          class="quiet"
          disabled={deletingData}
          onclick={eraseSessionData}
          onblur={() => (deleteArmed = false)}>
          {deletingData ? 'Deleting…' : deleteArmed ? 'Confirm delete all' : 'Delete my data'}
        </button>
      </footer>
    {/if}
  </main>
</div>

{#if setupOpen}
  <dialog
    bind:this={plannerDialog}
    class="planner-dialog"
    aria-labelledby="planner-title"
    oncancel={(event) => {
      event.preventDefault()
      void closeSetup()
    }}>
    <div class="planner-drawer">
      <header>
        <div>
          <p class="product-label">Plan setup</p>
          <h2 id="planner-title">Create study plan</h2>
          <p>Add your course material and set the study time that fits your real week.</p>
        </div>
        <button type="button" class="close-button" aria-label="Close plan setup" onclick={closeSetup}>
          Close
        </button>
      </header>
      <IntakeForm busy={building} onSubmit={build} />
    </div>
  </dialog>
{/if}

<style>
  .app-frame {
    min-height: 100dvh;
    background: var(--page);
  }

  .topbar {
    position: sticky;
    top: 0;
    z-index: var(--z-header);
    min-height: 68px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
    padding: 10px max(24px, calc((100vw - 1440px) / 2));
    border-bottom: 1px solid var(--rule);
    background: color-mix(in srgb, var(--page) 92%, transparent);
    backdrop-filter: blur(18px);
  }

  .brand {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    color: var(--ink);
    font-size: 17px;
    font-weight: 700;
    text-decoration: none;
    letter-spacing: -0.02em;
  }

  .brand-mark {
    width: 34px;
    height: 34px;
    display: grid;
    place-items: center;
    border-radius: var(--radius-small);
    background: var(--accent);
    color: var(--accent-ink);
    font-family: var(--mono);
    font-size: 11px;
    letter-spacing: 0.04em;
  }

  nav {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .app-shell {
    width: min(1440px, calc(100% - 48px));
    margin: 0 auto;
    padding: 54px 0 80px;
  }

  .intro {
    display: grid;
    grid-template-columns: minmax(0, 1.25fr) minmax(280px, 0.75fr);
    align-items: end;
    gap: 64px;
    margin-bottom: 34px;
  }

  .product-label {
    margin: 0 0 8px;
    color: var(--accent-strong);
    font-size: 12px;
    font-weight: 700;
  }

  .intro h1 {
    max-width: 760px;
    text-wrap: balance;
  }

  .intro > p {
    max-width: 48ch;
    margin: 0 0 5px;
    color: var(--ink-soft);
    font-size: 16px;
    line-height: 1.65;
    text-wrap: pretty;
  }

  .error-banner,
  .caveats {
    margin-bottom: 18px;
    border-radius: var(--radius-medium);
    background: var(--danger-surface);
    color: var(--danger-ink);
  }

  .error-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    padding: 12px 16px;
  }

  .guide {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    align-items: center;
    gap: 32px;
    margin-bottom: 22px;
    padding: 18px 20px;
    border: 1px solid var(--rule);
    border-radius: var(--radius-large);
    background: var(--surface);
  }

  .guide-copy {
    display: grid;
    grid-template-columns: 42px minmax(0, 1fr);
    align-items: start;
    gap: 14px;
  }

  .guide-count {
    padding-top: 2px;
    color: var(--accent-strong);
    font-family: var(--mono);
    font-size: 11px;
    font-variant-numeric: tabular-nums;
  }

  .guide h2 {
    margin-bottom: 3px;
    font-size: 15px;
  }

  .guide p {
    max-width: 66ch;
    margin: 0;
    color: var(--ink-soft);
    font-size: 13px;
  }

  .guide ol {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .guide li {
    display: grid;
    grid-template-columns: 24px auto;
    align-items: center;
    gap: 6px;
    color: var(--ink-faint);
    font-size: 11px;
  }

  .guide li > span:first-child {
    width: 24px;
    height: 24px;
    display: grid;
    place-items: center;
    border: 1px solid var(--rule-strong);
    border-radius: 50%;
    font-family: var(--mono);
    font-size: 10px;
  }

  .guide li.active,
  .guide li.complete {
    color: var(--ink);
  }

  .guide li.active > span:first-child,
  .guide li.complete > span:first-child {
    border-color: var(--accent);
    background: var(--accent);
    color: var(--accent-ink);
  }

  .guide-action {
    min-height: 38px;
    padding-block: 7px;
  }

  .caveats {
    padding: 14px 18px;
  }

  .caveats h2 {
    font-size: 14px;
  }

  .caveats p {
    margin: 4px 0 0;
    font-size: 12px;
  }

  .workspace {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(286px, 340px);
    gap: 18px;
    align-items: start;
  }

  .calendar-panel,
  .rail {
    border: 1px solid var(--rule);
    border-radius: var(--radius-large);
    background: var(--surface);
  }

  .calendar-panel {
    min-width: 0;
    padding: 20px;
  }

  .calendar-panel:focus-visible {
    outline: 2px solid var(--focus);
    outline-offset: 3px;
  }

  .calendar-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 24px;
    margin-bottom: 15px;
  }

  .calendar-header h2 {
    font-size: 20px;
  }

  .calendar-header p {
    margin: 4px 0 0;
    color: var(--ink-soft);
    font-size: 12px;
  }

  .summary {
    display: flex;
    gap: 22px;
    margin: 0;
  }

  .summary div {
    display: flex;
    flex-direction: column-reverse;
    align-items: flex-end;
  }

  .summary dt {
    color: var(--ink-faint);
    font-size: 10px;
  }

  .summary dd {
    margin: 0;
    color: var(--ink);
    font-family: var(--mono);
    font-size: 18px;
    font-weight: 650;
    font-variant-numeric: tabular-nums;
  }

  .key {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px 16px;
    margin-bottom: 11px;
    color: var(--ink-soft);
    font-size: 11px;
  }

  .key span {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .swatch {
    width: 9px;
    height: 9px;
    border-radius: 2px;
  }

  .swatch.learn {
    background: var(--learn);
  }

  .swatch.review {
    background: var(--review);
  }

  .swatch.flag {
    background: var(--flag);
  }

  .calendar-frame {
    position: relative;
    min-height: 640px;
  }

  .empty-calendar-overlay {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    padding: 24px;
    border-radius: var(--radius-medium);
    background: color-mix(in srgb, var(--surface) 82%, transparent);
    backdrop-filter: blur(7px);
  }

  .empty-calendar-card {
    width: min(420px, 100%);
    padding: 26px;
    border: 1px solid var(--rule-strong);
    border-radius: var(--radius-large);
    background: var(--surface-elevated);
  }

  .empty-index {
    color: var(--accent-strong);
    font-family: var(--mono);
    font-size: 12px;
  }

  .empty-calendar-card h3 {
    margin-top: 30px;
    font-family: var(--sans);
    font-size: 24px;
    line-height: 1.15;
    letter-spacing: -0.035em;
  }

  .empty-calendar-card p {
    max-width: 36ch;
    margin: 10px 0 20px;
    color: var(--ink-soft);
  }

  .rail {
    padding: 20px;
  }

  .rail-empty {
    min-height: 210px;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    padding-bottom: 4px;
  }

  .rail-number {
    margin-bottom: auto;
    color: var(--accent-strong);
    font-family: var(--mono);
    font-size: 48px;
    font-weight: 650;
    letter-spacing: -0.06em;
  }

  .rail-empty h2 {
    font-size: 19px;
  }

  .rail-empty p {
    margin: 7px 0 0;
    color: var(--ink-soft);
    font-size: 12px;
  }

  .privacy-note {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
    margin-top: 18px;
    padding: 16px 2px 0;
    border-top: 1px solid var(--rule);
    color: var(--ink-soft);
  }

  .privacy-note strong {
    color: var(--ink);
  }

  .privacy-note p {
    max-width: 70ch;
    margin: 3px 0 0;
  }

  .privacy-note button {
    flex: 0 0 auto;
  }

  .privacy-note .danger-action {
    border-color: var(--danger);
    color: var(--danger-ink);
  }

  .planner-dialog {
    width: min(860px, calc(100% - 28px));
    max-height: min(920px, calc(100dvh - 32px));
    margin: auto 16px auto auto;
    padding: 0;
    border: 0;
    border-radius: var(--radius-large);
    background: var(--surface-elevated);
    color: var(--ink);
    box-shadow: var(--shadow-dialog);
  }

  .planner-dialog::backdrop {
    background: var(--scrim);
    backdrop-filter: blur(4px);
  }

  .planner-drawer {
    max-height: calc(100dvh - 34px);
    overflow-y: auto;
    padding: 28px;
  }

  .planner-drawer > header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 24px;
    margin-bottom: 28px;
    padding-bottom: 20px;
    border-bottom: 1px solid var(--rule);
  }

  .planner-drawer > header h2 {
    font-size: 28px;
  }

  .planner-drawer > header p:last-child {
    max-width: 58ch;
    margin: 7px 0 0;
    color: var(--ink-soft);
    font-size: 13px;
  }

  .close-button {
    flex: 0 0 auto;
  }

  @media (max-width: 1120px) {
    .app-shell {
      width: min(100% - 32px, 980px);
      padding-top: 40px;
    }

    .workspace {
      grid-template-columns: minmax(0, 1fr);
    }

    .rail {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 22px;
    }

    .rail > :global(section) {
      min-width: 0;
    }
  }

  @media (max-width: 780px) {
    .topbar {
      padding-inline: 16px;
    }

    .brand > span:last-child {
      display: none;
    }

    .control-button {
      padding-inline: 10px;
    }

    .app-shell {
      width: calc(100% - 24px);
      padding: 28px 0 54px;
    }

    .intro {
      grid-template-columns: 1fr;
      gap: 14px;
      margin-bottom: 24px;
    }

    .intro > p {
      font-size: 14px;
    }

    .guide {
      grid-template-columns: 1fr;
      gap: 16px;
    }

    .guide ol {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }

    .guide li {
      grid-template-columns: 24px;
    }

    .guide li > span:last-child {
      display: none;
    }

    .calendar-header {
      flex-direction: column;
      gap: 14px;
    }

    .summary {
      width: 100%;
      justify-content: space-between;
    }

    .summary div {
      align-items: flex-start;
    }

    .calendar-panel,
    .rail {
      border-radius: var(--radius-medium);
    }

    .privacy-note {
      align-items: flex-start;
      flex-direction: column;
      gap: 12px;
    }

    .calendar-panel {
      padding: 14px;
    }

    .rail {
      display: block;
      padding: 16px;
    }

    .planner-dialog {
      width: 100%;
      max-width: none;
      max-height: calc(100dvh - 12px);
      margin: 12px 0 0;
      border-radius: var(--radius-large) var(--radius-large) 0 0;
    }

    .planner-drawer {
      max-height: calc(100dvh - 12px);
      padding: 20px 16px 34px;
    }
  }

  @media (max-width: 480px) {
    nav {
      gap: 5px;
    }

    .topbar button {
      min-height: 42px;
      font-size: 12px;
    }

    .guide-copy {
      grid-template-columns: 1fr;
      gap: 3px;
    }

    .calendar-frame {
      min-height: 560px;
    }

    .empty-calendar-overlay {
      padding: 10px;
    }

    .empty-calendar-card {
      padding: 20px;
    }
  }
</style>
