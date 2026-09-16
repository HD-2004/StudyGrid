<script lang="ts">
  import { IconAlertTriangle, IconArrowRight, IconCalendarPlus } from '@tabler/icons-svelte'
  import type { PlanChange } from '../lib/types'

  export let changes: PlanChange[] = []

  function formatDate(value: string | null): string {
    if (!value) return ''
    return new Date(value).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
  }
</script>

{#if changes.length}
  <section class="change-log" aria-live="polite">
    <div class="change-log-heading">
      <h2>Your plan adapted</h2>
      <span>{changes.length} {changes.length === 1 ? 'change' : 'changes'}</span>
    </div>
    <div class="change-list">
      {#each changes as change}
        <article class="change-item">
          <div class="change-icon" class:blocked={change.type === 'blocked'}>
            {#if change.type === 'blocked'}
              <IconAlertTriangle size={18} stroke={1.8} aria-hidden="true" />
            {:else}
              <IconCalendarPlus size={18} stroke={1.8} aria-hidden="true" />
            {/if}
          </div>
          <div>
            <h3>{change.topic}</h3>
            <p>{change.why}</p>
            {#if change.moved_from && change.moved_to}
              <div class="change-dates">
                <span>{formatDate(change.moved_from)}</span>
                <IconArrowRight size={15} stroke={1.8} aria-hidden="true" />
                <span>{formatDate(change.moved_to)}</span>
              </div>
            {:else if change.moved_to}
              <div class="change-dates">Added {formatDate(change.moved_to)}</div>
            {/if}
          </div>
        </article>
      {/each}
    </div>
  </section>
{/if}
