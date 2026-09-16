<script lang="ts">
  // Progress entry (HACKATHON.md 6.6) plus miss-reason capture (8.3).
  // Two axes for completion and recall, because "I finished it but remember
  // nothing" is the case that should trigger an earlier review.
  import type { CalendarEvent, Completion, MissReason, Recall, ReasonOption } from '../lib/types'

  let {
    event,
    busy,
    reasons,
    onSubmit,
    onClose,
  }: {
    event: CalendarEvent
    busy: boolean
    reasons: ReasonOption[]
    onSubmit: (completion: Completion, recall: Recall | null, missReason: MissReason | null) => void
    onClose: () => void
  } = $props()

  let completion = $state<Completion>('completed')
  let recall = $state<Recall>('medium')
  let missReason = $state<MissReason | null>(null)

  // Recall only means something if the session actually happened.
  const asksRecall = $derived(completion === 'completed' || completion === 'partial')
  // A reason only makes sense when time was lost (8.3).
  const asksReason = $derived(completion === 'partial' || completion === 'not_completed')

  function when(iso: string): string {
    return new Date(iso).toLocaleString(undefined, {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    })
  }
</script>

<section class="session-detail" aria-labelledby="session-title">
  <header>
    <div>
      <h2 id="session-title">{event.topic}</h2>
      <p class="meta">{event.subject}</p>
    </div>
    <button class="link" onclick={onClose}>Close</button>
  </header>

  <dl>
    <dt>Scheduled</dt>
    <dd>{when(event.start)}</dd>
    <dt>Pass</dt>
    <dd>{event.is_review ? `Review ${event.repetition - 1}` : 'First study'}</dd>
    <dt>Why now</dt>
    <dd>{event.rationale}</dd>
  </dl>

  <div class="field">
    <label for="completion">Did you study it?</label>
    <select id="completion" bind:value={completion}>
      <option value="completed">Finished the session</option>
      <option value="partial">Got partway</option>
      <option value="not_completed">Did not study</option>
    </select>
  </div>

  {#if asksRecall}
    <div class="field">
      <label for="recall">How much could you recall?</label>
      <select id="recall" bind:value={recall}>
        <option value="well">Strong recall (most of it)</option>
        <option value="medium">Difficult recall (about half)</option>
        <option value="poor">Forgot (very little)</option>
      </select>
    </div>
  {/if}

  {#if asksReason}
    <div class="field">
      <span class="field-label" id="reason-label">What came up instead?</span>
      <div class="reasons" role="group" aria-labelledby="reason-label">
        {#each reasons as option (option.value)}
          <button
            type="button"
            class="chip"
            class:selected={missReason === option.value}
            aria-pressed={missReason === option.value}
            onclick={() => (missReason = missReason === option.value ? null : option.value)}>
            {option.label}
          </button>
        {/each}
      </div>
      <p class="aside-note">Optional. Helps spot what keeps eating your study time.</p>
    </div>
  {/if}

  <button
    disabled={busy}
    onclick={() =>
      onSubmit(completion, asksRecall ? recall : null, asksReason ? missReason : null)}>
    {busy ? 'Updating plan…' : 'Save and update plan'}
  </button>

  <p class="note">
    {#if completion === 'not_completed'}
      This session moves to your next free slot.
    {:else if asksRecall && recall === 'poor'}
      The next review targets the first viable slot from tomorrow.
    {:else if asksRecall && recall === 'medium'}
      The next review targets the first viable slot in about three days.
    {:else}
      Strong recall expands the next review interval.
    {/if}
  </p>
</section>

<style>
  .session-detail {
    min-width: 0;
  }

  header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 12px;
    margin-bottom: 16px;
  }

  .meta {
    margin: 2px 0 0;
    color: var(--ink-soft);
    font-size: 12px;
  }

  dl {
    margin: 0 0 20px;
    display: grid;
    grid-template-columns: 74px 1fr;
    gap: 5px 12px;
    font-size: 12px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--rule);
  }

  dt {
    color: var(--ink-faint);
  }

  dd {
    margin: 0;
  }

  .field {
    margin-bottom: 14px;
  }

  .field-label {
    display: block;
    font-size: 11px;
    color: var(--ink-soft);
    margin-bottom: 5px;
  }

  .reasons {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
  }

  .chip {
    background: transparent;
    border: 1px solid var(--rule-strong);
    color: var(--ink-soft);
    min-height: 38px;
    padding: 6px 10px;
    font-size: 12px;
    border-radius: var(--radius-small);
  }

  .chip:hover {
    background: var(--surface-subtle);
  }

  .chip.selected {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--accent-ink);
  }

  .aside-note,
  .note {
    font-size: 12px;
    color: var(--ink-soft);
    margin: 8px 0 0;
  }

  .session-detail > button:not(.link) {
    width: 100%;
  }
</style>
