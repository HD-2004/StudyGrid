<script lang="ts">
  // Time-use insights (HACKATHON.md 8.3).
  // Shows counts always, pattern claims only when the backend says the sample
  // supports them. Presenting noise as insight would undermine trust in the
  // parts of the plan that are real.
  import type { Insights } from '../lib/types'

  let { insights }: { insights: Insights | null } = $props()

  const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

  function hours(minutes: number): string {
    if (minutes < 60) return `${minutes}m`
    return `${(minutes / 60).toFixed(1)}h`
  }

  // Widest reason bar sets the scale, so proportions read at a glance.
  const peak = $derived(
    insights?.reasons.length ? Math.max(...insights.reasons.map((r) => r.minutes_lost)) : 0,
  )
</script>

{#if insights && insights.sessions_logged > 0}
  <section>
    <h3>Where your time went</h3>

    <div class="figures">
      <div>
        <span class="value">{hours(insights.minutes_studied)}</span>
        <span class="caption">studied</span>
      </div>
      <div>
        <span class="value lost">{hours(insights.minutes_lost)}</span>
        <span class="caption">lost</span>
      </div>
      <div>
        <span class="value">{insights.completed}/{insights.sessions_logged}</span>
        <span class="caption">sessions kept</span>
      </div>
    </div>

    {#if insights.reasons.length}
      <ul class="reasons">
        {#each insights.reasons as r (r.reason)}
          <li>
            <span class="label">{r.label}</span>
            <span class="bar" style={`--fill: ${peak ? (r.minutes_lost / peak) * 100 : 0}%`}></span>
            <span class="amount">{hours(r.minutes_lost)}</span>
          </li>
        {/each}
      </ul>
    {/if}

    {#if insights.observations.length}
      <ul class="observations">
        {#each insights.observations as line (line)}
          <li>{line}</li>
        {/each}
      </ul>
    {/if}

    {#if insights.confident && insights.weak_weekdays.length}
      <p class="note">
        Hardest days to keep: {insights.weak_weekdays.map((d) => DAYS[d]).join(', ')}.
      </p>
    {/if}
  </section>
{/if}

<style>
  section {
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid var(--rule);
  }

  .figures {
    display: flex;
    gap: 20px;
    margin: 12px 0 14px;
  }

  .figures div {
    display: flex;
    flex-direction: column;
  }

  .value {
    font-family: var(--serif);
    font-size: 20px;
    font-variant-numeric: tabular-nums;
    line-height: 1.1;
  }

  .value.lost {
    color: var(--flag);
  }

  .caption {
    font-size: 11px;
    color: var(--ink-faint);
  }

  .reasons {
    list-style: none;
    margin: 0 0 12px;
    padding: 0;
  }

  .reasons li {
    display: grid;
    grid-template-columns: 84px 1fr 34px;
    align-items: center;
    gap: 7px;
    font-size: 12px;
    margin-bottom: 4px;
  }

  .label {
    color: var(--ink-soft);
  }

  .bar {
    height: 5px;
    background: var(--rule);
    position: relative;
  }

  .bar::after {
    content: '';
    position: absolute;
    inset: 0 auto 0 0;
    width: var(--fill);
    background: var(--flag);
  }

  .amount {
    text-align: right;
    font-variant-numeric: tabular-nums;
    color: var(--ink-soft);
  }

  .observations {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .observations li {
    font-size: 12px;
    color: var(--ink-soft);
    padding: 7px 9px;
    border: 1px solid var(--rule);
    border-radius: var(--radius-small);
    background: var(--surface-subtle);
    margin-bottom: 6px;
  }

  .note {
    font-size: 12px;
    color: var(--ink-faint);
    margin: 8px 0 0;
  }
</style>
