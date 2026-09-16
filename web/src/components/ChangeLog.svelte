<script lang="ts">
  // Renders changes[] from the progress response. An adaptation the student
  // cannot see reads as a bug, so every change the scheduler makes is shown.
  import type { PlanChange } from '../lib/types'

  let { changes }: { changes: PlanChange[] } = $props()

  function time(iso: string | null): string {
    if (!iso) return ''
    return new Date(iso).toLocaleString(undefined, {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    })
  }
</script>

{#if changes.length}
  <section>
    <h3>What changed</h3>
    <ul>
      {#each changes as c (c.session_id ?? c.topic + c.why)}
        <li class={c.type}>
          <span class="topic">{c.topic}</span>
          <span class="why">{c.why}</span>
          {#if c.moved_from && c.moved_to}
            <span class="move">{time(c.moved_from)} → {time(c.moved_to)}</span>
          {:else if c.moved_to}
            <span class="move">{time(c.moved_to)}</span>
          {/if}
        </li>
      {/each}
    </ul>
  </section>
{/if}

<style>
  section {
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid var(--rule);
  }

  ul {
    list-style: none;
    margin: 10px 0 0;
    padding: 0;
  }

  li {
    font-size: 12px;
    padding: 8px 10px;
    border: 1px solid var(--rule-strong);
    border-radius: var(--radius-small);
    margin-bottom: 6px;
  }

  li.added {
    border-color: color-mix(in srgb, var(--review) 38%, var(--rule));
    background: color-mix(in srgb, var(--review) 8%, var(--surface));
  }

  li.moved {
    border-color: color-mix(in srgb, var(--learn) 38%, var(--rule));
    background: color-mix(in srgb, var(--learn) 8%, var(--surface));
  }

  li.kept {
    border-color: color-mix(in srgb, var(--review) 38%, var(--rule));
    background: color-mix(in srgb, var(--review) 8%, var(--surface));
  }

  li.blocked {
    border-color: color-mix(in srgb, var(--flag) 42%, var(--rule));
    background: color-mix(in srgb, var(--flag) 8%, var(--surface));
  }

  .topic {
    display: block;
    font-weight: 600;
  }

  .why {
    display: block;
    color: var(--ink-soft);
  }

  .move {
    display: block;
    color: var(--ink-faint);
    font-variant-numeric: tabular-nums;
    margin-top: 2px;
  }
</style>
