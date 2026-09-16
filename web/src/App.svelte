<script lang="ts">
  import {
    createPlan,
    getEvents,
    getMissReasons,
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
    ReasonOption,
    Recall,
  } from './lib/types'
  import Calendar from './components/Calendar.svelte'
  import ChangeLog from './components/ChangeLog.svelte'
  import Insights from './components/Insights.svelte'
  import IntakeForm from './components/IntakeForm.svelte'
  import SessionDetail from './components/SessionDetail.svelte'

  let plan = $state<PlanResponse | null>(null)
  let events = $state<CalendarEvent[]>([])
  let changes = $state<PlanChange[]>([])
  let insights = $state<InsightsData | null>(null)
  let reasons = $state<ReasonOption[]>([])
  let selectedId = $state<string | null>(null)
  let building = $state(false)
  let updating = $state(false)
  let error = $state<string | null>(null)

  // Reason labels come from the backend. A failure here must not block the
  // core flow, so the prompt simply does not appear.
  $effect(() => {
    getMissReasons()
      .then((r) => (reasons = r))
      .catch(() => (reasons = []))
  })

  const selected = $derived(events.find((e) => e.id === selectedId) ?? null)

  const counts = $derived({
    learn: events.filter((e) => !e.is_review).length,
    review: events.filter((e) => e.is_review).length,
    hours:
      events.reduce(
        (total, e) => total + (Date.parse(e.end) - Date.parse(e.start)) / 3.6e6,
        0,
      ),
  })

  async function build(request: PlanRequest) {
    building = true
    error = null
    changes = []
    insights = null
    selectedId = null
    try {
      const created = await createPlan(request)
      plan = created
      events = await getEvents(created.plan_id)
    } catch (e) {
      error = e instanceof ApiError ? e.message : 'Something went wrong building the plan.'
    } finally {
      building = false
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
      events = await getEvents(plan.plan_id)
      selectedId = null
    } catch (e) {
      error = e instanceof ApiError ? e.message : 'Could not save your progress.'
    } finally {
      updating = false
    }
  }

  function startOver() {
    plan = null
    events = []
    changes = []
    insights = null
    selectedId = null
    error = null
  }
</script>

<div class="shell">
  <header class="masthead">
    <h1>StudyGrid</h1>
    <p>
      Turn what you have to learn, and the hours you actually have, into a review
      schedule that adjusts when your week does.
    </p>
  </header>

  {#if error}
    <p class="error" role="alert">{error}</p>
  {/if}

  {#if !plan}
    <div class="intake">
      <IntakeForm busy={building} onSubmit={build} />
    </div>
  {:else}
    <div class="summary">
      <div class="tally">
        <span class="figure">{counts.learn}</span>
        <span class="unit">first passes</span>
      </div>
      <div class="tally">
        <span class="figure">{counts.review}</span>
        <span class="unit">reviews</span>
      </div>
      <div class="tally">
        <span class="figure">{counts.hours.toFixed(1)}</span>
        <span class="unit">hours booked</span>
      </div>
      <button class="quiet" onclick={startOver}>Start a new plan</button>
    </div>

    {#if plan.warnings.length || plan.unscheduled.length}
      <div class="caveats">
        {#each plan.warnings as w (w)}
          <p>{w}</p>
        {/each}
        {#if plan.unscheduled.length}
          <p>
            No room before the exam for {plan.unscheduled.join(', ')}. Free up more
            time or drop a topic.
          </p>
        {/if}
      </div>
    {/if}

    <div class="workspace">
      <div class="grid">
        <div class="key">
          <span><i class="swatch learn"></i>New material</span>
          <span><i class="swatch review"></i>Review</span>
          <span><i class="swatch flag"></i>Needs another look</span>
          <span class="key-hint">Click any session to log how it went.</span>
        </div>
        <Calendar {events} onSelect={(id) => (selectedId = id)} />
      </div>

      <div class="sidebar">
        {#if selected}
          <SessionDetail
            event={selected}
            busy={updating}
            {reasons}
            onSubmit={record}
            onClose={() => (selectedId = null)} />
        {:else}
          <div class="placeholder">
            <h2>Log a session</h2>
            <p>
              Pick a session in the calendar to record whether you studied it and
              how much you remembered. The rest of the plan shifts to match.
            </p>
          </div>
        {/if}
        <ChangeLog {changes} />
        <Insights {insights} />
      </div>
    </div>
  {/if}
</div>

<style>
  .shell {
    width: min(1240px, calc(100% - 40px));
    margin: 0 auto;
    padding: 44px 0 80px;
  }

  .masthead {
    border-bottom: 2px solid var(--ink);
    padding-bottom: 16px;
    margin-bottom: 28px;
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 60px;
  }

  .masthead p {
    margin: 0;
    max-width: 46ch;
    color: var(--ink-soft);
    text-align: right;
  }

  .intake {
    width: min(780px, 100%);
  }

  .error {
    border-left: 3px solid var(--flag);
    background: #fdf6ee;
    padding: 10px 14px;
    margin: 0 0 22px;
    color: #7d4715;
  }

  .summary {
    display: flex;
    align-items: baseline;
    gap: 40px;
    padding-bottom: 18px;
    margin-bottom: 18px;
    border-bottom: 1px solid var(--rule);
  }

  .summary button {
    margin-left: auto;
  }

  .tally {
    display: flex;
    align-items: baseline;
    gap: 7px;
  }

  .figure {
    font-family: var(--serif);
    font-size: 27px;
    font-variant-numeric: tabular-nums;
  }

  .unit {
    color: var(--ink-soft);
    font-size: 12px;
  }

  .caveats {
    border-left: 3px solid var(--flag);
    padding: 8px 14px;
    margin-bottom: 22px;
    background: #fdf9f3;
  }

  .caveats p {
    margin: 3px 0;
    font-size: 12px;
    color: #7d4715;
  }

  .workspace {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 316px;
    gap: var(--gutter);
    align-items: start;
  }

  .grid {
    min-width: 0;
  }

  .key {
    display: flex;
    align-items: center;
    gap: 18px;
    font-size: 11px;
    color: var(--ink-soft);
    margin-bottom: 10px;
  }

  .key span {
    display: flex;
    align-items: center;
    gap: 5px;
  }

  .key-hint {
    margin-left: auto;
    color: var(--ink-faint);
  }

  .swatch {
    width: 9px;
    height: 9px;
    border-radius: 1px;
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

  .placeholder h2 {
    margin-bottom: 6px;
  }

  .placeholder {
    border-left: 1px solid var(--rule);
    padding-left: var(--gutter);
    color: var(--ink-soft);
  }

  .placeholder p {
    margin: 0;
    font-size: 12px;
  }

  @media (max-width: 900px) {
    .shell {
      padding-top: 28px;
    }

    .masthead {
      display: block;
      margin-bottom: 24px;
    }

    .masthead p {
      margin-top: 10px;
      max-width: 58ch;
      text-align: left;
    }

    .workspace {
      grid-template-columns: minmax(0, 1fr);
    }

    .sidebar {
      border-top: 1px solid var(--rule);
      padding-top: 20px;
    }

    .placeholder {
      border-left: 0;
      padding-left: 0;
    }
  }

  @media (max-width: 600px) {
    .shell {
      width: calc(100% - 24px);
      padding: 20px 0 48px;
    }

    .summary {
      align-items: center;
      flex-wrap: wrap;
      gap: 12px 20px;
    }

    .summary button {
      width: 100%;
      margin-left: 0;
    }

    .figure {
      font-size: 24px;
    }

    .key {
      flex-wrap: wrap;
      gap: 7px 14px;
    }

    .key-hint {
      flex-basis: 100%;
      margin-left: 0;
    }
  }
</style>
