<script lang="ts">
  import { onMount } from 'svelte'
  import '@material/web/progress/linear-progress.js'
  import {
    IconAlertCircle,
    IconBook2,
    IconCalendarMonth,
    IconCheck,
    IconClock,
    IconEdit,
    IconMenu2,
    IconMoon,
    IconPlus,
    IconRefresh,
    IconSun,
    IconX,
  } from '@tabler/icons-svelte'
  import ChangeLog from './components/ChangeLog.svelte'
  import IntakeForm from './components/IntakeForm.svelte'
  import SessionDetail from './components/SessionDetail.svelte'
  import StudyCalendar from './components/StudyCalendar.svelte'
  import { analyzeMaterial, createPlan, getEvents, submitProgress } from './lib/api'
  import { createSample, defaultAvailability, today } from './lib/sample'
  import type {
    Availability,
    CalendarEvent,
    Completion,
    DraftSubject,
    PlanChange,
    PlanResponse,
    Recall,
    Strategy,
    StudySession,
  } from './lib/types'

  let subjects: DraftSubject[] = createSample('fresh')
  let availability: Availability = structuredClone(defaultAvailability)
  let strategy: Strategy = 'fresh'
  let startDate = today()
  let analyzingIndex: number | null = null
  let generating = false
  let savingProgress = false
  let plan: PlanResponse | null = null
  let events: CalendarEvent[] = []
  let changes: PlanChange[] = []
  let selectedSession: StudySession | null = null
  let errorMessage = ''
  let noticeMessage = ''
  let theme: 'light' | 'dark' = 'light'
  let plannerOpen = false

  onMount(() => {
    const savedTheme = localStorage.getItem('studygrid-theme')
    theme =
      savedTheme === 'light' || savedTheme === 'dark'
        ? savedTheme
        : window.matchMedia('(prefers-color-scheme: dark)').matches
          ? 'dark'
          : 'light'
  })

  $: if (typeof document !== 'undefined') {
    document.documentElement.dataset.theme = theme
  }

  $: totalMinutes =
    plan?.sessions.reduce((sum, session) => {
      return sum + (new Date(session.end).getTime() - new Date(session.start).getTime()) / 60_000
    }, 0) || 0
  $: reviewCount = plan?.sessions.filter((session) => session.repetition > 1).length || 0
  $: completedCount =
    plan?.sessions.filter((session) => session.completion === 'completed').length || 0
  $: topicCount = subjects.reduce((count, subject) => count + subject.topics.length, 0)
  $: weeklyHours =
    Object.values(availability.weekday_minutes).reduce((sum, minutes) => sum + minutes, 0) / 60
  $: calendarTitle = new Intl.DateTimeFormat(undefined, {
    month: 'long',
    year: 'numeric',
  }).format(new Date(`${startDate}T12:00:00`))

  function toggleTheme() {
    theme = theme === 'light' ? 'dark' : 'light'
    localStorage.setItem('studygrid-theme', theme)
  }

  function clearMessages() {
    errorMessage = ''
    noticeMessage = ''
  }

  function loadSample(nextStrategy: Strategy) {
    clearMessages()
    strategy = nextStrategy
    subjects = createSample(nextStrategy)
    availability = structuredClone(defaultAvailability)
    startDate = today()
    plan = null
    events = []
    changes = []
    selectedSession = null
  }

  function startOver() {
    loadSample(strategy)
    openPlanner()
  }

  function openPlanner() {
    plannerOpen = true
  }

  function closePlanner() {
    plannerOpen = false
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape' && plannerOpen) closePlanner()
  }

  async function analyzeSubject(index: number) {
    const subject = subjects[index]
    if (!subject.name.trim()) {
      errorMessage = 'Add a subject name before analyzing its material.'
      return
    }
    if (!subject.materialText.trim()) {
      errorMessage = 'Paste course material before running analysis.'
      return
    }

    clearMessages()
    analyzingIndex = index
    try {
      const response = await analyzeMaterial(subject.name, subject.materialText)
      subjects[index] = {
        ...subject,
        topics: response.topics,
        analysisSource: response.source,
      }
      subjects = [...subjects]
      noticeMessage =
        response.source === 'ai'
          ? `${response.topics.length} topics extracted with AI.`
          : `${response.topics.length} topics extracted with the offline fallback.`
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Material analysis failed.'
    } finally {
      analyzingIndex = null
    }
  }

  function validatePlan(): string | null {
    if (!subjects.length) return 'Add at least one subject.'
    if (subjects.some((subject) => !subject.name.trim())) return 'Every subject needs a name.'
    if (subjects.some((subject) => !subject.exam_date)) return 'Every subject needs an exam date.'
    if (subjects.some((subject) => !subject.topics.length)) {
      return 'Every subject needs at least one topic.'
    }
    if (subjects.some((subject) => subject.topics.some((topic) => !topic.name.trim()))) {
      return 'Every topic needs a name.'
    }
    if (!Object.values(availability.weekday_minutes).some((minutes) => minutes > 0)) {
      return 'Add study time to at least one day.'
    }
    return null
  }

  async function generatePlan() {
    const validationError = validatePlan()
    if (validationError) {
      errorMessage = validationError
      return
    }

    clearMessages()
    generating = true
    changes = []
    try {
      const response = await createPlan({
        strategy,
        start_date: startDate,
        availability,
        notes: '',
        subjects: subjects.map(({ materialText: _materialText, analysisSource: _source, ...subject }) =>
          subject,
        ),
      })
      plan = response
      events = await getEvents(response.plan_id)
      closePlanner()
      noticeMessage = 'Your study plan is ready. Select any session to record progress.'
      setTimeout(() => {
        document.querySelector('.workspace-panel')?.scrollIntoView({ behavior: 'smooth' })
      }, 0)
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'The study plan could not be created.'
    } finally {
      generating = false
    }
  }

  function selectSession(eventId: string) {
    selectedSession = plan?.sessions.find((session) => session.id === eventId) || null
  }

  async function saveProgress(completion: Completion, recall: Recall | null) {
    if (!plan || !selectedSession) return

    clearMessages()
    savingProgress = true
    try {
      const response = await submitProgress({
        plan_id: plan.plan_id,
        session_id: selectedSession.id,
        completion,
        recall,
      })
      plan = {
        ...plan,
        sessions: response.sessions,
        warnings: response.warnings,
      }
      changes = response.changes
      events = await getEvents(plan.plan_id)
      selectedSession = null
      noticeMessage = response.changes.length
        ? 'Progress saved and the remaining plan was updated.'
        : 'Progress saved. The current schedule still fits.'
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Progress could not be saved.'
    } finally {
      savingProgress = false
    }
  }
</script>

<svelte:head>
  <title>StudyGrid | Adaptive study calendar</title>
  <meta
    name="description"
    content="Build an adaptive study schedule from course material, exam dates, and real availability."
  />
</svelte:head>

<svelte:window on:keydown={handleKeydown} />

<div class="app-root">
  <header class="topbar">
    <div class="topbar-main">
      <button
        class="material-icon-button menu-button"
        type="button"
        aria-label="Open plan setup"
        title="Open plan setup"
        aria-expanded={plannerOpen}
        on:click={openPlanner}
      >
        <IconMenu2 size={22} stroke={1.8} aria-hidden="true" />
      </button>
      <a class="brand" href="#top" aria-label="StudyGrid home">
        <span class="brand-mark" aria-hidden="true">
          <IconCalendarMonth size={22} stroke={1.8} />
        </span>
        <span>StudyGrid</span>
      </a>
      <span class="header-context">Study calendar</span>
    </div>
    <div class="topbar-meta">
      <span class="service-state"><IconCheck size={16} stroke={2} /> Planner ready</span>
      <button
        class="material-icon-button theme-toggle"
        type="button"
        aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
        title={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}
        on:click={toggleTheme}
      >
        {#if theme === 'light'}
          <IconMoon size={20} stroke={1.8} aria-hidden="true" />
        {:else}
          <IconSun size={20} stroke={1.8} aria-hidden="true" />
        {/if}
      </button>
    </div>
  </header>

  <main id="top" class="app-shell" inert={plannerOpen}>
    <aside class="navigation-rail" aria-label="Plan summary">
      <button
        class="material-tonal-button create-plan-button"
        type="button"
        aria-expanded={plannerOpen}
        on:click={openPlanner}
      >
        <IconPlus size={20} stroke={1.9} aria-hidden="true" />
        {plan ? 'Edit plan' : 'Create plan'}
      </button>

      <div class="rail-current">
        <IconCalendarMonth size={19} stroke={1.8} aria-hidden="true" />
        <span>Study calendar</span>
      </div>

      <section class="rail-section">
        <h2>{plan ? 'Plan summary' : 'Ready to schedule'}</h2>
        <dl class="rail-stats">
          <div>
            <dt>Subjects</dt>
            <dd>{subjects.length}</dd>
          </div>
          <div>
            <dt>Topics</dt>
            <dd>{topicCount}</dd>
          </div>
          <div>
            <dt>Weekly capacity</dt>
            <dd>{weeklyHours.toFixed(1)}h</dd>
          </div>
          {#if plan}
            <div>
              <dt>Completed</dt>
              <dd>{completedCount}/{plan.sessions.length}</dd>
            </div>
          {/if}
        </dl>
      </section>

      <section class="rail-section">
        <h2>Subjects</h2>
        <div class="rail-subjects">
          {#each subjects.slice(0, 4) as subject}
            <div>
              <IconBook2 size={17} stroke={1.7} aria-hidden="true" />
              <span>{subject.name || 'Untitled subject'}</span>
              {#if subject.exam_date}
                <time datetime={subject.exam_date}>{new Date(`${subject.exam_date}T12:00:00`).toLocaleDateString([], { month: 'short', day: 'numeric' })}</time>
              {:else}
                <span class="rail-date">Set date</span>
              {/if}
            </div>
          {/each}
        </div>
      </section>

      <section class="rail-section calendar-key">
        <h2>Calendar key</h2>
        <p><span class="key-swatch key-study"></span>First pass</p>
        <p><span class="key-swatch key-review"></span>Review</p>
        <p><span class="key-swatch key-completed"></span>Completed</p>
      </section>
    </aside>

    <section class="workspace-panel" aria-label="Study plan workspace">
      {#if !plannerOpen && errorMessage}
        <div class="message-banner error-banner" role="alert">
          <IconAlertCircle size={19} stroke={1.8} aria-hidden="true" />
          <span>{errorMessage}</span>
          <button type="button" on:click={() => (errorMessage = '')}>Dismiss</button>
        </div>
      {/if}
      {#if !plannerOpen && noticeMessage}
        <div class="message-banner notice-banner" role="status">
          <IconCheck size={19} stroke={1.8} aria-hidden="true" />
          <span>{noticeMessage}</span>
          <button type="button" on:click={() => (noticeMessage = '')}>Dismiss</button>
        </div>
      {/if}

      <div class="workspace-toolbar">
        <div>
          <h1>{calendarTitle}</h1>
          <p>
            {#if plan}
              {plan.sessions.length} sessions, {(totalMinutes / 60).toFixed(1)} study hours, {reviewCount} reviews
            {:else}
              Build a plan to add focused study sessions to your week.
            {/if}
          </p>
        </div>
        <div class="toolbar-actions">
          {#if plan}
            <button class="button button-secondary" type="button" on:click={openPlanner}>
              <IconEdit size={17} stroke={1.8} aria-hidden="true" />
              Edit plan
            </button>
            <button class="button button-quiet" type="button" on:click={startOver}>
              <IconRefresh size={17} stroke={1.8} aria-hidden="true" />
              Start over
            </button>
          {/if}
        </div>
      </div>

      {#if plan?.warnings.length || plan?.unscheduled.length}
        <section class="capacity-panel" aria-label="Scheduling notices">
          <IconAlertCircle size={20} stroke={1.8} aria-hidden="true" />
          <div>
            <h2>Check plan capacity</h2>
            {#each plan?.warnings || [] as warning}<p>{warning}</p>{/each}
            {#if plan?.unscheduled.length}
              <p>Could not schedule: {plan.unscheduled.join(', ')}</p>
            {/if}
          </div>
        </section>
      {/if}

      <ChangeLog {changes} />

      <section class="calendar-section" aria-label="Study calendar">
        <div class="calendar-canvas">
          {#key plan?.plan_id || 'empty-calendar'}
            <StudyCalendar events={plan ? events : []} {theme} onSelect={selectSession} />
          {/key}

          {#if generating}
            <div class="calendar-overlay loading-overlay" aria-live="polite">
              <div class="overlay-card">
                <md-linear-progress indeterminate aria-label="Building study plan"></md-linear-progress>
                <h2>Building your study plan</h2>
                <p>Balancing deadlines, priorities, and review intervals.</p>
              </div>
            </div>
          {:else if !plan}
            <div class="calendar-overlay empty-calendar-overlay">
              <div class="overlay-card">
                <span class="overlay-icon" aria-hidden="true">
                  <IconCalendarMonth size={25} stroke={1.7} />
                </span>
                <h2>Create your study schedule</h2>
                <p>Add subjects, exam dates, and your weekly availability.</p>
                <button class="material-tonal-button" type="button" on:click={openPlanner}>
                  <IconPlus size={19} stroke={1.9} aria-hidden="true" />
                  Create plan
                </button>
              </div>
            </div>
          {/if}
        </div>
      </section>
    </section>
  </main>

  {#if plannerOpen}
    <button
      class="planner-scrim"
      type="button"
      aria-label="Close plan setup"
      on:click={closePlanner}
    ></button>
    <div class="planner-drawer" role="dialog" aria-modal="true" aria-labelledby="planner-title">
      <header class="planner-drawer-header">
        <div>
          <p>Study plan</p>
          <h1 id="planner-title">Create study plan</h1>
        </div>
        <button
          class="material-icon-button"
          type="button"
          aria-label="Close plan setup"
          title="Close plan setup"
          on:click={closePlanner}
        >
          <IconX size={22} stroke={1.8} aria-hidden="true" />
        </button>
      </header>
      <div class="planner-drawer-scroll">
        {#if errorMessage || noticeMessage}
          <div class="drawer-message-stack">
            {#if errorMessage}
              <div class="message-banner error-banner" role="alert">
                <IconAlertCircle size={19} stroke={1.8} aria-hidden="true" />
                <span>{errorMessage}</span>
                <button type="button" on:click={() => (errorMessage = '')}>Dismiss</button>
              </div>
            {/if}
            {#if noticeMessage}
              <div class="message-banner notice-banner" role="status">
                <IconCheck size={19} stroke={1.8} aria-hidden="true" />
                <span>{noticeMessage}</span>
                <button type="button" on:click={() => (noticeMessage = '')}>Dismiss</button>
              </div>
            {/if}
          </div>
        {/if}
        <IntakeForm
          bind:subjects
          bind:availability
          bind:strategy
          bind:startDate
          {analyzingIndex}
          {generating}
          onAnalyze={analyzeSubject}
          onGenerate={generatePlan}
          onLoadSample={loadSample}
        />
      </div>
    </div>
  {/if}

  <SessionDetail
    session={selectedSession}
    open={selectedSession !== null}
    saving={savingProgress}
    onClose={() => (selectedSession = null)}
    onSave={saveProgress}
  />
</div>
