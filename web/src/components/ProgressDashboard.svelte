<script lang="ts">
  import { onMount, tick } from 'svelte'
  import {
    ApiError,
    createActivity,
    deleteActivity,
    getActivityCategories,
    getActivityDashboard,
    updateActivity,
  } from '../lib/api'
  import type {
    ActivityCategory,
    ActivityCategoryOption,
    ActivityDashboard,
    ActivityInput,
    ActivityLog,
  } from '../lib/types'

  let { onClose }: { onClose: () => void } = $props()

  const COLOR: Record<ActivityCategory, string> = {
    study: 'var(--activity-study)',
    work: 'var(--activity-work)',
    entertainment: 'var(--activity-entertainment)',
    illness: 'var(--activity-illness)',
    unexpected: 'var(--activity-unexpected)',
    rest: 'var(--activity-rest)',
    other: 'var(--activity-other)',
  }

  let days = $state<7 | 30>(7)
  let dashboard = $state<ActivityDashboard | null>(null)
  let categories = $state<ActivityCategoryOption[]>([])
  let loading = $state(true)
  let saving = $state(false)
  let deletingId = $state<string | null>(null)
  let editingId = $state<string | null>(null)
  let error = $state<string | null>(null)
  let status = $state<string | null>(null)
  let formElement = $state<HTMLFormElement | null>(null)
  let input = $state<ActivityInput>(emptyInput())

  const peakMinutes = $derived(
    Math.max(
      60,
      ...(dashboard?.daily.map((day) =>
        Object.values(day.minutes).reduce((sum, minutes) => sum + minutes, 0),
      ) ?? []),
    ),
  )
  const totalMinutes = $derived(
    dashboard?.totals.reduce((sum, item) => sum + item.minutes, 0) ?? 0,
  )

  onMount(() => {
    void loadInitial()
  })

  function today(): string {
    const now = new Date()
    const offset = now.getTimezoneOffset() * 60_000
    return new Date(now.getTime() - offset).toISOString().slice(0, 10)
  }

  function emptyInput(): ActivityInput {
    return {
      occurred_on: today(),
      category: 'work',
      label: '',
      minutes: 60,
      note: '',
    }
  }

  async function loadInitial() {
    loading = true
    error = null
    try {
      const [categoryOptions, activityData] = await Promise.all([
        getActivityCategories(),
        getActivityDashboard(days, today()),
      ])
      categories = categoryOptions
      dashboard = activityData
    } catch (reason) {
      error = reason instanceof ApiError ? reason.message : 'Progress data could not be loaded.'
    } finally {
      loading = false
    }
  }

  async function refresh(nextDays = days) {
    loading = true
    error = null
    try {
      dashboard = await getActivityDashboard(nextDays, today())
    } catch (reason) {
      error = reason instanceof ApiError ? reason.message : 'Progress data could not be loaded.'
    } finally {
      loading = false
    }
  }

  async function setRange(value: 7 | 30) {
    if (value === days) return
    days = value
    await refresh(value)
  }

  function categoryLabel(category: ActivityCategory): string {
    return categories.find((item) => item.value === category)?.label ?? category
  }

  function formatDuration(minutes: number): string {
    const hours = Math.floor(minutes / 60)
    const remainder = minutes % 60
    if (!hours) return `${remainder}m`
    return remainder ? `${hours}h ${remainder}m` : `${hours}h`
  }

  function formatDay(value: string, compact = false): string {
    const parsed = new Date(`${value}T12:00:00`)
    return new Intl.DateTimeFormat(undefined, compact ? { day: 'numeric' } : {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
    }).format(parsed)
  }

  function barLabel(day: ActivityDashboard['daily'][number]): string {
    const parts = Object.entries(day.minutes)
      .filter(([, minutes]) => minutes > 0)
      .map(([category, minutes]) => `${categoryLabel(category as ActivityCategory)} ${formatDuration(minutes)}`)
    return `${formatDay(day.date)}: ${parts.length ? parts.join(', ') : 'no time logged'}`
  }

  function startEdit(activity: ActivityLog) {
    if (activity.source !== 'manual') return
    editingId = activity.id
    input = {
      occurred_on: activity.occurred_on,
      category: activity.category,
      label: activity.label,
      minutes: activity.minutes,
      note: activity.note,
    }
    status = null
    void tick().then(() => formElement?.scrollIntoView({ behavior: 'smooth', block: 'center' }))
  }

  function cancelEdit() {
    editingId = null
    input = emptyInput()
  }

  async function saveActivity() {
    saving = true
    error = null
    status = null
    try {
      const payload = {
        ...$state.snapshot(input),
        label: input.label.trim() || categoryLabel(input.category),
      }
      if (editingId) {
        await updateActivity(editingId, payload)
        status = 'Activity updated.'
      } else {
        await createActivity(payload)
        status = 'Activity logged.'
      }
      editingId = null
      input = emptyInput()
      await refresh()
    } catch (reason) {
      error = reason instanceof ApiError ? reason.message : 'The activity could not be saved.'
    } finally {
      saving = false
    }
  }

  async function removeActivity(activity: ActivityLog) {
    if (activity.source !== 'manual') return
    deletingId = activity.id
    error = null
    status = null
    try {
      await deleteActivity(activity.id)
      if (editingId === activity.id) cancelEdit()
      status = 'Activity deleted.'
      await refresh()
    } catch (reason) {
      error = reason instanceof ApiError ? reason.message : 'The activity could not be deleted.'
    } finally {
      deletingId = null
    }
  }
</script>

<section class="progress-dashboard" aria-labelledby="progress-heading">
  <header class="progress-heading">
    <div>
      <p class="section-label">Progress</p>
      <h2 id="progress-heading">Where your week went</h2>
      <p>Study sessions appear automatically after completion. Log the rest of your time when it helps.</p>
    </div>
    <button type="button" class="quiet" onclick={onClose}>Return to calendar</button>
  </header>

  {#if error}
    <div class="progress-error" role="alert">
      <span>{error}</span>
      <button type="button" class="text-button" onclick={() => (error = null)}>Dismiss</button>
    </div>
  {/if}
  {#if status}
    <p class="progress-status" role="status">{status}</p>
  {/if}

  <div class="range-control" aria-label="Analytics date range">
    <button type="button" class:active={days === 7} aria-pressed={days === 7} onclick={() => setRange(7)}>
      7 days
    </button>
    <button type="button" class:active={days === 30} aria-pressed={days === 30} onclick={() => setRange(30)}>
      30 days
    </button>
  </div>

  {#if loading && !dashboard}
    <div class="analytics-skeleton" aria-label="Loading progress analytics" aria-busy="true">
      <span></span><span></span><span></span>
    </div>
  {:else if dashboard}
    <div class="analytics-layout" class:loading>
      <section class="chart-panel" aria-labelledby="chart-heading">
        <div class="panel-heading">
          <div>
            <h3 id="chart-heading">Time by category</h3>
            <p>Total time per day, grouped by activity.</p>
          </div>
          <span>{formatDay(dashboard.period_start)} – {formatDay(dashboard.period_end)}</span>
        </div>

        {#if totalMinutes === 0}
          <div class="chart-empty">
            <h3>No time logged in this range</h3>
            <p>Complete a study session or use the form below to add work, rest, and interruptions.</p>
          </div>
        {:else}
          <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
          <div class="chart-scroll" role="region" tabindex="0" aria-label={`${days}-day stacked time chart`}>
            <div class:month={days === 30} class="chart">
              <div class="axis" aria-hidden="true">
                <span>{formatDuration(peakMinutes)}</span>
                <span>{formatDuration(Math.round(peakMinutes / 2))}</span>
                <span>0</span>
              </div>
              <div class="plot" style={`--columns: ${dashboard.daily.length}`}>
                {#each dashboard.daily as day (day.date)}
                  <div class="day-column" aria-label={barLabel(day)}>
                    <div class="bar-stack">
                      {#each Object.entries(day.minutes) as [category, minutes] (category)}
                        {#if minutes > 0}
                          <span
                            title={`${categoryLabel(category as ActivityCategory)}: ${formatDuration(minutes)}`}
                            style={`height: ${(minutes / peakMinutes) * 100}%; background: ${COLOR[category as ActivityCategory]}`}></span>
                        {/if}
                      {/each}
                    </div>
                    <span class="day-label">{days === 7 ? formatDay(day.date) : formatDay(day.date, true)}</span>
                  </div>
                {/each}
              </div>
            </div>
          </div>
        {/if}
      </section>

      <section class="totals-panel" aria-labelledby="totals-heading">
        <h3 id="totals-heading">Category totals ({days} days)</h3>
        <ul>
          {#each dashboard.totals as total (total.category)}
            <li>
              <i style={`background: ${COLOR[total.category]}`} aria-hidden="true"></i>
              <span>{total.label}</span>
              <strong>{formatDuration(total.minutes)}</strong>
              <small>{totalMinutes ? Math.round((total.minutes / totalMinutes) * 100) : 0}%</small>
            </li>
          {/each}
        </ul>
        <div class="total-row"><span>Total logged</span><strong>{formatDuration(totalMinutes)}</strong></div>
      </section>
    </div>

    <div class="activity-layout">
      <form
        bind:this={formElement}
        class="activity-form"
        onsubmit={(event) => {
          event.preventDefault()
          void saveActivity()
        }}>
        <header>
          <div>
            <h3>{editingId ? 'Edit activity' : 'Log activity'}</h3>
            <p>Use a broad category and your own label for useful patterns later.</p>
          </div>
          {#if editingId}
            <button type="button" class="text-button" onclick={cancelEdit}>Cancel edit</button>
          {/if}
        </header>
        <div class="form-grid">
          <div>
            <label for="activity-date">Date</label>
            <input id="activity-date" type="date" max={today()} required bind:value={input.occurred_on} />
          </div>
          <div>
            <label for="activity-category">Category</label>
            <select id="activity-category" required bind:value={input.category}>
              {#each categories as category (category.value)}
                <option value={category.value}>{category.label}</option>
              {/each}
            </select>
          </div>
          <div class="wide">
            <label for="activity-label">Custom label</label>
            <input id="activity-label" type="text" maxlength="120" bind:value={input.label} placeholder="e.g. Project planning" />
          </div>
          <div>
            <label for="activity-duration">Duration (minutes)</label>
            <input id="activity-duration" type="number" min="5" max="1440" step="5" required bind:value={input.minutes} />
          </div>
          <div class="full">
            <label for="activity-note">Note (optional)</label>
            <textarea id="activity-note" rows="2" maxlength="1000" bind:value={input.note} placeholder="What affected this block of time?"></textarea>
          </div>
        </div>
        <button type="submit" disabled={saving}>
          {saving ? 'Saving…' : editingId ? 'Save changes' : 'Log activity'}
        </button>
      </form>

      <section class="recent" aria-labelledby="recent-heading">
        <header>
          <h3 id="recent-heading">Recent activity</h3>
          <span>{dashboard.activities.length} in range</span>
        </header>
        {#if dashboard.activities.length}
          <ul>
            {#each dashboard.activities.slice(0, 12) as activity (activity.id)}
              <li>
                <i style={`background: ${COLOR[activity.category]}`} aria-hidden="true"></i>
                <div>
                  <strong>{activity.label}</strong>
                  <span>{formatDay(activity.occurred_on)} · {formatDuration(activity.minutes)}</span>
                  {#if activity.source === 'study_session'}<small>Synced from study progress</small>{/if}
                </div>
                {#if activity.source === 'manual'}
                  <div class="row-actions">
                    <button type="button" class="text-button" onclick={() => startEdit(activity)}>Edit</button>
                    <button
                      type="button"
                      class="text-button delete"
                      disabled={deletingId === activity.id}
                      onclick={() => removeActivity(activity)}>
                      {deletingId === activity.id ? 'Deleting…' : 'Delete'}
                    </button>
                  </div>
                {/if}
              </li>
            {/each}
          </ul>
        {:else}
          <div class="recent-empty">
            <p>No activity yet. Your first log will appear here.</p>
          </div>
        {/if}
      </section>
    </div>
  {/if}
</section>

<style>
  .progress-dashboard {
    min-width: 0;
  }

  .progress-heading,
  .panel-heading,
  .activity-form > header,
  .recent > header,
  .progress-error,
  .total-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 20px;
  }

  .progress-heading {
    margin-bottom: 18px;
  }

  .progress-heading h2 {
    font-size: 24px;
  }

  .progress-heading p:last-child,
  .panel-heading p,
  .activity-form header p {
    margin: 4px 0 0;
    color: var(--ink-soft);
    font-size: 12px;
  }

  .section-label {
    margin: 0 0 3px;
    color: var(--accent-strong);
    font-size: 12px;
    font-weight: 700;
  }

  .range-control {
    width: fit-content;
    display: flex;
    gap: 3px;
    margin: 0 0 12px auto;
    padding: 3px;
    border: 1px solid var(--rule);
    border-radius: var(--radius-small);
    background: var(--surface-subtle);
  }

  .range-control button {
    min-height: 36px;
    border: 0;
    background: transparent;
    color: var(--ink-soft);
    padding: 7px 16px;
  }

  .range-control button.active {
    background: var(--accent);
    color: var(--accent-ink);
  }

  .progress-error,
  .progress-status {
    margin: 0 0 14px;
    padding: 10px 12px;
    border-radius: var(--radius-small);
  }

  .progress-error {
    background: var(--danger-surface);
    color: var(--danger-ink);
  }

  .progress-status {
    border: 1px solid color-mix(in srgb, var(--success) 36%, var(--rule));
    background: color-mix(in srgb, var(--success) 8%, var(--surface));
    color: var(--success);
  }

  .analytics-layout,
  .activity-layout {
    display: grid;
    gap: 16px;
  }

  .analytics-layout {
    grid-template-columns: minmax(0, 1fr) minmax(250px, 0.34fr);
    transition: opacity 160ms ease;
  }

  .analytics-layout.loading {
    opacity: 0.58;
  }

  .activity-layout {
    grid-template-columns: minmax(0, 1.15fr) minmax(300px, 0.85fr);
    margin-top: 16px;
  }

  .chart-panel,
  .totals-panel,
  .activity-form,
  .recent {
    min-width: 0;
    border: 1px solid var(--rule);
    border-radius: var(--radius-medium);
    background: var(--surface);
    padding: 20px;
  }

  .panel-heading {
    align-items: flex-end;
    margin-bottom: 18px;
  }

  .panel-heading > span,
  .recent > header span {
    color: var(--ink-faint);
    font-size: 11px;
  }

  .chart-scroll {
    overflow-x: auto;
    padding-bottom: 4px;
  }

  .chart {
    min-width: 560px;
    height: 272px;
    display: grid;
    grid-template-columns: 46px minmax(0, 1fr);
    gap: 8px;
  }

  .chart.month {
    min-width: 960px;
  }

  .axis {
    height: 230px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    align-items: flex-end;
    padding: 0 4px 15px 0;
    color: var(--ink-faint);
    font-size: 10px;
    font-variant-numeric: tabular-nums;
  }

  .plot {
    height: 250px;
    display: grid;
    grid-template-columns: repeat(var(--columns), minmax(24px, 1fr));
    gap: 8px;
    align-items: end;
    padding: 0 6px;
    border-bottom: 1px solid var(--rule-strong);
    background:
      linear-gradient(var(--rule), var(--rule)) 0 25% / 100% 1px no-repeat,
      linear-gradient(var(--rule), var(--rule)) 0 50% / 100% 1px no-repeat,
      linear-gradient(var(--rule), var(--rule)) 0 75% / 100% 1px no-repeat;
  }

  .day-column {
    min-width: 0;
    height: 250px;
    display: grid;
    grid-template-rows: 220px 30px;
    align-items: end;
  }

  .bar-stack {
    height: 220px;
    display: flex;
    flex-direction: column-reverse;
    justify-content: flex-start;
    border-radius: 4px 4px 0 0;
    overflow: hidden;
  }

  .bar-stack span {
    display: block;
    min-height: 1px;
  }

  .day-label {
    overflow: hidden;
    padding-top: 7px;
    color: var(--ink-soft);
    font-size: 10px;
    text-align: center;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .chart-empty,
  .recent-empty {
    display: grid;
    place-content: center;
    min-height: 230px;
    color: var(--ink-soft);
    text-align: center;
  }

  .chart-empty p,
  .recent-empty p {
    max-width: 48ch;
    margin: 7px auto 0;
  }

  .totals-panel h3,
  .activity-form h3,
  .recent h3,
  .chart-panel h3 {
    font-size: 15px;
  }

  .totals-panel ul,
  .recent ul {
    list-style: none;
    margin: 16px 0;
    padding: 0;
  }

  .totals-panel li {
    display: grid;
    grid-template-columns: 12px minmax(0, 1fr) auto 38px;
    align-items: center;
    gap: 9px;
    min-height: 34px;
    font-size: 12px;
  }

  .totals-panel i,
  .recent li > i {
    width: 10px;
    height: 10px;
    border-radius: 3px;
  }

  .totals-panel strong,
  .totals-panel small,
  .total-row strong {
    font-variant-numeric: tabular-nums;
  }

  .totals-panel small {
    color: var(--ink-faint);
    text-align: right;
  }

  .total-row {
    align-items: center;
    padding-top: 12px;
    border-top: 1px solid var(--rule);
  }

  .activity-form > header,
  .recent > header {
    margin-bottom: 16px;
  }

  .form-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
    margin-bottom: 14px;
  }

  .form-grid .wide {
    grid-column: span 2;
  }

  .form-grid .full {
    grid-column: 1 / -1;
  }

  .form-grid textarea {
    min-height: 76px;
  }

  .recent ul {
    margin-bottom: 0;
  }

  .recent li {
    display: grid;
    grid-template-columns: 12px minmax(0, 1fr) auto;
    align-items: start;
    gap: 10px;
    padding: 10px 0;
    border-bottom: 1px solid var(--rule);
  }

  .recent li:last-child {
    border-bottom: 0;
  }

  .recent li > i {
    margin-top: 4px;
  }

  .recent li div:not(.row-actions) {
    display: flex;
    min-width: 0;
    flex-direction: column;
  }

  .recent li strong {
    overflow-wrap: anywhere;
    font-size: 12px;
  }

  .recent li span,
  .recent li small {
    color: var(--ink-faint);
    font-size: 10px;
  }

  .row-actions {
    display: flex;
    gap: 4px;
  }

  .row-actions button {
    min-height: 32px;
    font-size: 11px;
  }

  .row-actions .delete {
    color: var(--danger);
  }

  .analytics-skeleton {
    display: grid;
    grid-template-columns: 1fr 0.36fr;
    gap: 16px;
  }

  .analytics-skeleton span {
    min-height: 320px;
    border-radius: var(--radius-medium);
    background: var(--surface-subtle);
    animation: pulse 1.2s ease-in-out infinite alternate;
  }

  .analytics-skeleton span:last-child {
    display: none;
  }

  @keyframes pulse {
    to { opacity: 0.52; }
  }

  @media (max-width: 980px) {
    .analytics-layout,
    .activity-layout {
      grid-template-columns: 1fr;
    }

    .form-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 600px) {
    .progress-heading,
    .panel-heading {
      align-items: stretch;
      flex-direction: column;
    }

    .range-control {
      width: 100%;
      margin-left: 0;
    }

    .range-control button {
      flex: 1;
    }

    .chart-panel,
    .totals-panel,
    .activity-form,
    .recent {
      padding: 15px;
    }

    .form-grid {
      grid-template-columns: 1fr;
    }

    .form-grid .wide,
    .form-grid .full {
      grid-column: auto;
    }

    .recent li {
      grid-template-columns: 12px minmax(0, 1fr);
    }

    .row-actions {
      grid-column: 2;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .analytics-skeleton span {
      animation: none;
    }
  }
</style>
