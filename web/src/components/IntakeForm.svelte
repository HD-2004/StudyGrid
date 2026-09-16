<script lang="ts">
  // Intake (HACKATHON.md 6.2). Editable subjects and topics, plus the seed
  // presets for the three entry points so a demo starts in one click.
  import type { PlanRequest, Strategy, Subject } from '../lib/types'
  import { SEEDS } from '../lib/seed'

  let {
    busy,
    onSubmit,
  }: { busy: boolean; onSubmit: (req: PlanRequest) => void } = $props()

  let strategy = $state<Strategy>('fresh')
  let formError = $state<string | null>(null)
  let request = $state<PlanRequest>(clone(SEEDS.fresh.request))

  // structuredClone cannot clone a $state proxy, so plain seed objects are
  // cloned with structuredClone and reactive state is unwrapped via
  // $state.snapshot first.
  function clone<T>(value: T): T {
    return structuredClone(value)
  }

  function loadSeed(s: Strategy) {
    strategy = s
    request = clone(SEEDS[s].request)
  }

  function addTopic(subject: Subject) {
    subject.topics.push({ name: '', difficulty: 'medium', estimated_minutes: 60 })
  }

  function removeTopic(subject: Subject, index: number) {
    subject.topics.splice(index, 1)
  }

  function addSubject() {
    request.subjects.push({
      name: '',
      exam_date: new Date(Date.now() + 12096e5).toISOString().slice(0, 10),
      priority: 3,
      topics: [{ name: '', difficulty: 'medium', estimated_minutes: 60 }],
    })
  }

  const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

  const totalWeeklyHours = $derived(
    Object.values(request.availability.weekday_minutes).reduce((a, b) => a + Number(b), 0) / 60,
  )

  const valid = $derived(
    request.subjects.length > 0 &&
      request.subjects.every((s) => s.name.trim() && s.topics.some((t) => t.name.trim())),
  )

  function submit(form: HTMLFormElement) {
    // Native validation blocks submission without showing anything in some
    // browsers, which looks like a dead button. Report it instead.
    if (!form.checkValidity()) {
      const bad = Array.from(form.elements).find(
        (el): el is HTMLInputElement =>
          'checkValidity' in el && (el as HTMLInputElement).willValidate && !(el as HTMLInputElement).checkValidity(),
      )
      formError = bad ? `Check that field: ${bad.validationMessage}` : 'Some values are out of range.'
      bad?.focus()
      return
    }
    formError = null

    // $state.snapshot unwraps the reactive proxy into a plain object, which is
    // what JSON.stringify in the api layer needs.
    const plain = $state.snapshot(request) as PlanRequest

    // Drop blank rows the student left behind.
    const cleaned: PlanRequest = {
      ...plain,
      strategy,
      subjects: plain.subjects
        .filter((s) => s.name.trim())
        .map((s) => ({ ...s, topics: s.topics.filter((t) => t.name.trim()) })),
    }
    onSubmit(cleaned)
  }
</script>

<form
  novalidate
  onsubmit={(e) => {
    e.preventDefault()
    submit(e.currentTarget as HTMLFormElement)
  }}>
  <fieldset class="presets">
    <legend>Where are you starting from?</legend>
    {#each Object.entries(SEEDS) as [key, seed] (key)}
      <label class="preset" class:active={strategy === key}>
        <input
          type="radio"
          name="strategy"
          value={key}
          checked={strategy === key}
          onchange={() => loadSeed(key as Strategy)}
        />
        <span class="preset-label">{seed.label}</span>
        <span class="preset-hint">{seed.hint}</span>
      </label>
    {/each}
  </fieldset>

  <section>
    <h3>Subjects</h3>
    {#each request.subjects as subject, si (si)}
      <div class="subject">
        <div class="subject-head">
          <div class="grow">
            <label for={`subject-${si}`}>Subject</label>
            <input id={`subject-${si}`} type="text" bind:value={subject.name} placeholder="e.g. Linear Algebra" />
          </div>
          <div class="narrow">
            <label for={`exam-${si}`}>Exam</label>
            <input id={`exam-${si}`} type="date" bind:value={subject.exam_date} />
          </div>
          <div class="tiny">
            <label for={`prio-${si}`}>Priority</label>
            <input id={`prio-${si}`} type="number" min="1" max="5" bind:value={subject.priority} />
          </div>
        </div>

        <table>
          <thead>
            <tr>
              <th>Topic</th>
              <th class="w-difficulty">Difficulty</th>
              <th class="w-minutes">Minutes</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {#each subject.topics as topic, ti (ti)}
              <tr>
                <td><input type="text" bind:value={topic.name} placeholder="Topic name" aria-label={`Topic ${ti + 1} name`} /></td>
                <td>
                  <select bind:value={topic.difficulty} aria-label={`Difficulty for ${topic.name || `topic ${ti + 1}`}`}>
                    <option value="easy">Easy</option>
                    <option value="medium">Medium</option>
                    <option value="hard">Hard</option>
                  </select>
                </td>
                <!-- step=5, not 15: a 100-minute topic is a normal estimate, and a
                     coarser step makes such values fail native validation, which
                     blocks submit with no visible message. -->
                <td><input type="number" min="15" max="600" step="5" bind:value={topic.estimated_minutes} aria-label={`Minutes for ${topic.name || `topic ${ti + 1}`}`} /></td>
                <td>
                  <button
                    type="button"
                    class="link"
                    onclick={() => removeTopic(subject, ti)}
                    disabled={subject.topics.length === 1}
                    aria-label={`Remove ${topic.name || 'topic'}`}>Remove</button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
        <button type="button" class="link" onclick={() => addTopic(subject)}>Add topic</button>
      </div>
    {/each}
    <button type="button" class="quiet" onclick={addSubject}>Add subject</button>
  </section>

  <section>
    <h3>Study time each week</h3>
    <div class="days">
      {#each DAYS as day, i (day)}
        <div>
          <label for={`day-${i}`}>{day}</label>
          <input
            id={`day-${i}`}
            type="number"
            min="0"
            max="720"
            step="5"
            bind:value={request.availability.weekday_minutes[String(i)]} />
        </div>
      {/each}
    </div>
    <p class="hint">
      Minutes per day. {totalWeeklyHours.toFixed(1)} hours a week,
      {request.availability.session_length_minutes}-minute sessions.
    </p>

    {#if request.availability.busy.length}
      <p class="hint">
        Working around
        {request.availability.busy.map((b) => `${DAYS[b.weekday]} ${b.label}`).join(', ')}.
      </p>
    {/if}
  </section>

  <div>
    <button type="submit" disabled={busy || !valid}>
      {busy ? 'Building your plan…' : 'Build my study plan'}
    </button>
    {#if formError}
      <p class="hint error-hint" role="alert">{formError}</p>
    {:else if !valid}
      <p class="hint">Give every subject a name and at least one topic.</p>
    {/if}
  </div>
</form>

<style>
  form {
    display: flex;
    flex-direction: column;
    gap: 26px;
  }

  fieldset {
    border: none;
    padding: 0;
    margin: 0;
  }

  legend {
    font-size: 11px;
    color: var(--ink-soft);
    padding: 0;
    margin-bottom: 8px;
  }

  .presets {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
  }

  .preset {
    border: 1px solid var(--rule-strong);
    padding: 9px 11px;
    cursor: pointer;
    margin: 0;
  }

  .preset.active {
    border-color: var(--ink);
    background: #f2efe8;
  }

  .preset input {
    position: absolute;
    opacity: 0;
    pointer-events: none;
  }

  .preset:focus-within {
    outline: 2px solid var(--learn);
    outline-offset: 2px;
  }

  .preset-label {
    display: block;
    font-size: 13px;
    font-weight: 600;
    color: var(--ink);
  }

  .preset-hint {
    display: block;
    font-size: 11px;
    color: var(--ink-soft);
    margin-top: 1px;
  }

  .subject {
    border-top: 1px solid var(--rule);
    padding-top: 12px;
    margin-bottom: 18px;
  }

  .subject-head {
    display: flex;
    gap: 12px;
    align-items: flex-end;
    margin-bottom: 10px;
  }

  .grow {
    flex: 1;
  }

  .narrow {
    width: 130px;
  }

  .tiny {
    width: 58px;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  th {
    text-align: left;
    font-size: 10px;
    font-weight: 500;
    color: var(--ink-faint);
    padding-bottom: 3px;
  }

  .w-difficulty {
    width: 100px;
  }

  .w-minutes {
    width: 74px;
  }

  td {
    padding: 1px 6px 1px 0;
  }

  .days {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 8px;
  }

  .hint {
    font-size: 12px;
    color: var(--ink-soft);
    margin: 8px 0 0;
  }

  .error-hint {
    color: #7d4715;
  }

  @media (max-width: 640px) {
    .presets {
      grid-template-columns: 1fr;
    }

    .subject-head {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 58px;
    }

    .grow {
      grid-column: 1 / -1;
    }

    .narrow {
      width: auto;
    }

    .days {
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }

    table,
    tbody,
    tr,
    td {
      display: block;
    }

    thead {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }

    tr {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(72px, 0.7fr) auto;
      gap: 6px 10px;
      padding: 6px 0 10px;
      border-bottom: 1px solid var(--rule);
    }

    td {
      min-width: 0;
      padding: 0;
    }

    td:first-child {
      grid-column: 1 / -1;
    }

    td:last-child {
      align-self: end;
      padding-bottom: 5px;
    }
  }
</style>
