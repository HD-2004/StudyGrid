<script lang="ts">
  import { tick } from 'svelte'
  import { ApiError, sendCoachMessage } from '../lib/api'
  import type { ChatMessage } from '../lib/types'

  let {
    planId,
    focusSessionId = null,
  }: {
    planId: string
    focusSessionId?: string | null
  } = $props()

  let messages = $state<ChatMessage[]>([])
  let suggestions = $state([
    'What should I study next?',
    'How much work is left?',
    'Why is the plan ordered this way?',
  ])
  let draft = $state('')
  let sending = $state(false)
  let error = $state<string | null>(null)
  let source = $state<'ai' | 'fallback' | null>(null)
  let transcript: HTMLDivElement

  async function scrollToLatest() {
    await tick()
    transcript?.scrollTo({ top: transcript.scrollHeight, behavior: 'smooth' })
  }

  async function send(text = draft) {
    const message = text.trim()
    if (!message || sending) return

    draft = ''
    error = null
    sending = true
    messages = [...messages, { role: 'user', content: message }]
    await scrollToLatest()

    try {
      const response = await sendCoachMessage(planId, message, focusSessionId)
      messages = response.history
      suggestions = response.suggestions
      source = response.source
    } catch (reason) {
      error = reason instanceof ApiError ? reason.message : 'The coach could not reply.'
    } finally {
      sending = false
      await scrollToLatest()
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void send()
    }
  }
</script>

<section class="coach" aria-labelledby="coach-heading">
  <header>
    <div>
      <h2 id="coach-heading">Study Coach</h2>
      {#if focusSessionId}
        <span class="context">Current session selected</span>
      {:else}
        <span class="context">Your current plan</span>
      {/if}
    </div>
    {#if source}
      <span class="source">{source === 'ai' ? 'AI' : 'Offline'} guidance</span>
    {/if}
  </header>

  <div class="suggestions" aria-label="Suggested questions">
    {#each suggestions as suggestion (suggestion)}
      <button type="button" class="prompt" disabled={sending} onclick={() => send(suggestion)}>
        {suggestion}
      </button>
    {/each}
  </div>

  <div class="transcript" bind:this={transcript} aria-live="polite">
    {#if messages.length === 0}
      <div class="coach-message assistant">
        <span>Coach</span>
        <p>Your plan is ready. What would you like to work through?</p>
      </div>
    {/if}
    {#each messages as message, index (`${message.role}-${index}`)}
      <div class:assistant={message.role === 'assistant'} class:user={message.role === 'user'} class="coach-message">
        <span>{message.role === 'assistant' ? 'Coach' : 'You'}</span>
        <p>{message.content}</p>
      </div>
    {/each}
    {#if sending}
      <div class="coach-message assistant waiting">
        <span>Coach</span>
        <p>Thinking…</p>
      </div>
    {/if}
  </div>

  <form
    onsubmit={(event) => {
      event.preventDefault()
      void send()
    }}>
    <label for="coach-input">Ask about your plan</label>
    <div class="composer">
      <textarea
        id="coach-input"
        rows="2"
        maxlength="1000"
        bind:value={draft}
        onkeydown={handleKeydown}></textarea>
      <button type="submit" disabled={sending || !draft.trim()}>Send</button>
    </div>
    {#if error}
      <p class="chat-error" role="alert">{error}</p>
    {/if}
  </form>
</section>

<style>
  .coach {
    border-top: 1px solid var(--rule);
    margin-top: 24px;
    padding-top: 20px;
  }

  header,
  header > div,
  .composer {
    display: flex;
  }

  header {
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }

  header > div {
    flex-direction: column;
  }

  .context,
  .source,
  .coach-message span {
    color: var(--ink-faint);
    font-size: 10px;
  }

  .source {
    white-space: nowrap;
    margin-top: 3px;
  }

  .suggestions {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin: 12px 0;
  }

  button.prompt {
    border: 1px solid var(--rule-strong);
    background: transparent;
    color: var(--ink-soft);
    min-height: 36px;
    padding: 6px 9px;
    font-size: 10px;
  }

  button.prompt:hover:not(:disabled) {
    border-color: var(--accent);
    background: var(--surface-subtle);
    color: var(--ink);
  }

  .transcript {
    max-height: 310px;
    overflow-y: auto;
    border-block: 1px solid var(--rule);
    padding: 8px 0;
    margin-bottom: 12px;
    scrollbar-width: thin;
  }

  .coach-message {
    padding: 7px 9px;
    margin: 3px 0;
    border: 1px solid color-mix(in srgb, var(--learn) 38%, var(--rule));
    border-radius: var(--radius-small);
  }

  .coach-message.assistant {
    border-color: color-mix(in srgb, var(--review) 38%, var(--rule));
    background: color-mix(in srgb, var(--review) 10%, var(--surface));
  }

  .coach-message.user {
    background: color-mix(in srgb, var(--learn) 10%, var(--surface));
  }

  .coach-message p {
    margin: 2px 0 0;
    font-size: 12px;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  .waiting {
    color: var(--ink-soft);
  }

  .composer {
    align-items: stretch;
    gap: 7px;
  }

  textarea {
    min-width: 0;
    flex: 1;
    min-height: 58px;
    max-height: 130px;
  }

  .composer button {
    align-self: stretch;
    min-width: 60px;
    padding-inline: 10px;
  }

  .chat-error {
    color: var(--danger);
    font-size: 11px;
    margin: 7px 0 0;
  }
</style>
