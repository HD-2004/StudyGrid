<script lang="ts">
  import { IconBook, IconBrain, IconCalendarClock, IconX } from '@tabler/icons-svelte'
  import type { Completion, Recall, StudySession } from '../lib/types'

  export let session: StudySession | null = null
  export let open = false
  export let saving = false
  export let onClose: () => void
  export let onSave: (completion: Completion, recall: Recall | null) => void

  let dialog: HTMLDialogElement
  let completion: Completion = 'completed'
  let recall: Recall | null = 'well'

  $: if (open && session) {
    completion = session.completion === 'planned' ? 'completed' : session.completion
    recall = session.recall || 'well'
  }

  $: if (dialog) {
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }

  function chooseCompletion(value: Completion) {
    completion = value
    if (value === 'not_completed') recall = null
    if (value !== 'not_completed' && recall === null) recall = 'well'
  }

  function submit() {
    onSave(completion, completion === 'not_completed' ? null : recall)
  }
</script>

<dialog
  class="session-dialog"
  bind:this={dialog}
  on:close={() => open && onClose()}
  on:cancel={(event) => {
    event.preventDefault()
    onClose()
  }}
>
  {#if session}
    <div class="dialog-shell">
      <header class="dialog-header">
        <div class="session-kind">
          {session.repetition > 1 ? `Review ${session.repetition - 1}` : 'First pass'}
        </div>
        <button class="icon-button" type="button" aria-label="Close session details" on:click={onClose}>
          <IconX size={20} stroke={1.8} aria-hidden="true" />
        </button>
      </header>

      <div class="dialog-title">
        <p>{session.subject}</p>
        <h2>{session.topic}</h2>
      </div>

      <div class="session-facts">
        <div>
          <IconCalendarClock size={18} stroke={1.8} aria-hidden="true" />
          <span>{new Date(session.start).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}</span>
        </div>
        <div>
          <IconBook size={18} stroke={1.8} aria-hidden="true" />
          <span>{session.rationale}</span>
        </div>
      </div>

      <form on:submit|preventDefault={submit}>
        <fieldset>
          <legend>How did this session go?</legend>
          <div class="choice-grid completion-grid">
            <button
              class:active={completion === 'completed'}
              type="button"
              on:click={() => chooseCompletion('completed')}
            >
              Completed
            </button>
            <button
              class:active={completion === 'partial'}
              type="button"
              on:click={() => chooseCompletion('partial')}
            >
              Partially done
            </button>
            <button
              class:active={completion === 'not_completed'}
              type="button"
              on:click={() => chooseCompletion('not_completed')}
            >
              Missed
            </button>
          </div>
        </fieldset>

        {#if completion !== 'not_completed'}
          <fieldset>
            <legend>
              <IconBrain size={18} stroke={1.8} aria-hidden="true" />
              How much could you recall?
            </legend>
            <div class="choice-grid recall-grid">
              <label class:active={recall === 'well'}>
                <input type="radio" value="well" bind:group={recall} />
                <span>Mostly</span>
                <small>Confident recall</small>
              </label>
              <label class:active={recall === 'medium'}>
                <input type="radio" value="medium" bind:group={recall} />
                <span>About half</span>
                <small>Needs reinforcement</small>
              </label>
              <label class:active={recall === 'poor'}>
                <input type="radio" value="poor" bind:group={recall} />
                <span>Very little</span>
                <small>Add an earlier review</small>
              </label>
            </div>
          </fieldset>
        {/if}

        <div class="dialog-actions">
          <button class="button button-quiet" type="button" on:click={onClose}>Cancel</button>
          <button class="button button-primary" type="submit" disabled={saving}>
            {saving ? 'Updating plan...' : 'Save progress'}
          </button>
        </div>
      </form>
    </div>
  {/if}
</dialog>
