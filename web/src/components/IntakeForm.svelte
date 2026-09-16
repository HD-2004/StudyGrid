<script lang="ts">
  // Intake (HACKATHON.md 6.2). Every value stays editable; sample-course
  // presets were removed so user testing starts from the student's real data.
  import {
    analyzeMaterial,
    analyzeMaterialFile,
    analyzeMaterialUrl,
    ApiError,
  } from '../lib/api'
  import type { AnalyzeResponse, MaterialAnalyzeResponse, PlanRequest, Subject } from '../lib/types'

  type AnalysisState = {
    busy: boolean
    source: 'ai' | 'fallback' | null
    message: string | null
    error: string | null
  }

  let {
    busy,
    onSubmit,
  }: { busy: boolean; onSubmit: (req: PlanRequest) => void } = $props()

  let formError = $state<string | null>(null)
  let request = $state<PlanRequest>(newRequest())
  let materialDrafts = $state<string[]>([''])
  let materialFiles = $state<(File | null)[]>([null])
  let materialUrls = $state<string[]>([''])
  let analysisStates = $state<AnalysisState[]>([emptyAnalysisState()])
  const SESSION_LENGTHS = [30, 60, 90, 120]
  let sessionLengthMode = $state(sessionMode(request.availability.session_length_minutes))

  function isoDaysFromNow(days: number): string {
    return new Date(Date.now() + days * 86_400_000).toISOString().slice(0, 10)
  }

  function newRequest(): PlanRequest {
    return {
      strategy: 'fresh',
      start_date: isoDaysFromNow(0),
      notes: '',
      subjects: [
        {
          name: '',
          exam_date: isoDaysFromNow(21),
          priority: 3,
          topics: [{ name: '', difficulty: 'medium', estimated_minutes: 60 }],
        },
      ],
      availability: {
        weekday_minutes: {
          '0': 120,
          '1': 120,
          '2': 120,
          '3': 120,
          '4': 120,
          '5': 60,
          '6': 60,
        },
        earliest: '09:00',
        latest: '22:00',
        session_length_minutes: 60,
        break_minutes: 6,
        long_break_minutes: 45,
        busy: [],
      },
    }
  }

  function sessionMode(minutes: number): string {
    return SESSION_LENGTHS.includes(minutes) ? String(minutes) : 'custom'
  }

  function emptyAnalysisState(): AnalysisState {
    return { busy: false, source: null, message: null, error: null }
  }

  function selectSessionLength(value: string) {
    sessionLengthMode = value
    if (value !== 'custom') request.availability.session_length_minutes = Number(value)
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
    materialDrafts.push('')
    materialFiles.push(null)
    materialUrls.push('')
    analysisStates.push(emptyAnalysisState())
  }

  function removeSubject(index: number) {
    if (request.subjects.length === 1) return
    request.subjects.splice(index, 1)
    materialDrafts.splice(index, 1)
    materialFiles.splice(index, 1)
    materialUrls.splice(index, 1)
    analysisStates.splice(index, 1)
  }

  function setMaterialFile(index: number, files: FileList | null) {
    materialFiles[index] = files?.item(0) ?? null
  }

  function applyAnalysis(
    subject: Subject,
    index: number,
    result: AnalyzeResponse | MaterialAnalyzeResponse,
  ) {
    subject.topics = result.topics
    const material = 'material_name' in result ? ` from ${result.material_name}` : ''
    const truncated = 'truncated' in result && result.truncated ? ' A bounded excerpt was analyzed.' : ''
    analysisStates[index] = {
      busy: false,
      source: result.source,
      message: `${result.topics.length} topics extracted${material} and added below.${truncated}`,
      error: null,
    }
  }

  function validateSubject(subject: Subject, index: number): boolean {
    if (!subject.name.trim()) {
      analysisStates[index] = {
        ...emptyAnalysisState(),
        error: 'Name the subject before analyzing its material.',
      }
      return false
    }
    return true
  }

  async function analyzePastedText(subject: Subject, index: number) {
    const text = materialDrafts[index]?.trim() ?? ''
    if (!validateSubject(subject, index)) return
    if (!text) {
      analysisStates[index] = {
        ...emptyAnalysisState(),
        error: 'Paste notes, a syllabus, or a topic outline first.',
      }
      return
    }

    analysisStates[index] = { busy: true, source: null, message: null, error: null }
    try {
      const result = await analyzeMaterial(subject.name, text)
      applyAnalysis(subject, index, result)
    } catch (reason) {
      analysisStates[index] = {
        ...emptyAnalysisState(),
        error: reason instanceof ApiError ? reason.message : 'The material could not be analyzed.',
      }
    }
  }

  async function analyzeFile(subject: Subject, index: number) {
    if (!validateSubject(subject, index)) return
    const file = materialFiles[index]
    if (!file) {
      analysisStates[index] = { ...emptyAnalysisState(), error: 'Choose a file first.' }
      return
    }
    analysisStates[index] = { busy: true, source: null, message: null, error: null }
    try {
      applyAnalysis(subject, index, await analyzeMaterialFile(subject.name, file))
    } catch (reason) {
      analysisStates[index] = {
        ...emptyAnalysisState(),
        error: reason instanceof ApiError ? reason.message : 'The file could not be analyzed.',
      }
    }
  }

  async function analyzeUrl(subject: Subject, index: number) {
    if (!validateSubject(subject, index)) return
    const url = materialUrls[index]?.trim() ?? ''
    if (!url) {
      analysisStates[index] = { ...emptyAnalysisState(), error: 'Enter a public URL first.' }
      return
    }
    analysisStates[index] = { busy: true, source: null, message: null, error: null }
    try {
      applyAnalysis(subject, index, await analyzeMaterialUrl(subject.name, url))
    } catch (reason) {
      analysisStates[index] = {
        ...emptyAnalysisState(),
        error: reason instanceof ApiError ? reason.message : 'The URL could not be analyzed.',
      }
    }
  }

  function addBusyBlock() {
    request.availability.busy.push({ weekday: 0, start: '09:00', end: '10:00', label: '' })
  }

  function removeBusyBlock(index: number) {
    request.availability.busy.splice(index, 1)
  }

  const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

  const totalWeeklyHours = $derived(
    Object.values(request.availability.weekday_minutes).reduce((a, b) => a + Number(b), 0) / 60,
  )
  const activeStudyDays = $derived(
    Object.values(request.availability.weekday_minutes).filter((minutes) => Number(minutes) > 0).length,
  )
  const shortStudyDays = $derived(
    DAYS.filter((_, index) => {
      const minutes = Number(request.availability.weekday_minutes[String(index)] ?? 0)
      return minutes > 0 && minutes < request.availability.session_length_minutes
    }),
  )
  const shortBreakMinutes = $derived(Math.ceil(request.availability.session_length_minutes * 0.10))

  function dailyHours(index: number): number {
    return Number(request.availability.weekday_minutes[String(index)] ?? 0) / 60
  }

  function setDailyHours(index: number, hours: number) {
    if (!Number.isFinite(hours)) return
    request.availability.weekday_minutes[String(index)] = Math.round(hours * 60)
  }

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
      strategy: 'fresh',
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
  <section>
    <h3>Plan dates and daily window</h3>
    <p class="section-copy">Choose when planning begins and the earliest and latest times StudyGrid may schedule a session.</p>
    <div class="planning-window">
      <div>
        <label for="plan-start">Plan starts</label>
        <input id="plan-start" type="date" required bind:value={request.start_date} />
      </div>
      <div>
        <label for="earliest-time">Earliest study time</label>
        <input id="earliest-time" type="time" required bind:value={request.availability.earliest} />
      </div>
      <div>
        <label for="latest-time">Latest study time</label>
        <input id="latest-time" type="time" required bind:value={request.availability.latest} />
      </div>
    </div>
  </section>

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
            <label for={`prio-${si}`}>Priority (1 low, 5 high)</label>
            <input id={`prio-${si}`} type="number" min="1" max="5" bind:value={subject.priority} />
          </div>
          <button
            type="button"
            class="link remove-subject"
            disabled={request.subjects.length === 1}
            onclick={() => removeSubject(si)}>
            Remove subject
          </button>
        </div>

        <details class="material-import" open={si === 0}>
          <summary>Import course material</summary>
          <div class="material-body">
            <div class="import-option">
              <label for={`material-file-${si}`}>Upload a document or recording</label>
              <input
                id={`material-file-${si}`}
                type="file"
                accept=".docx,.txt,.md,.markdown,.pdf,.mp3,.mp4,.mpeg,.mpga,.m4a,.wav,.webm"
                onchange={(event) => setMaterialFile(si, event.currentTarget.files)} />
              <div class="material-actions">
                <button
                  type="button"
                  class="quiet"
                  disabled={analysisStates[si]?.busy || !materialFiles[si]}
                  onclick={() => analyzeFile(subject, si)}>
                  {analysisStates[si]?.busy ? 'Analyzing…' : 'Analyze file'}
                </button>
                <span class="format-note">DOCX, TXT, MD and PDF are fastest. Video/audio uses AI transcription.</span>
              </div>
            </div>

            <div class="import-option">
              <label for={`material-url-${si}`}>Import a public URL</label>
              <div class="url-input">
                <input
                  id={`material-url-${si}`}
                  type="url"
                  bind:value={materialUrls[si]}
                  placeholder="https://example.edu/syllabus" />
                <button
                  type="button"
                  class="quiet"
                  disabled={analysisStates[si]?.busy || !materialUrls[si]?.trim()}
                  onclick={() => analyzeUrl(subject, si)}>
                  {analysisStates[si]?.busy ? 'Analyzing…' : 'Analyze URL'}
                </button>
              </div>
            </div>

            <div class="import-option pasted-text">
            <label for={`material-${si}`}>Or paste a syllabus, notes, or topic outline</label>
            <textarea
              id={`material-${si}`}
              rows="5"
              maxlength="30000"
              bind:value={materialDrafts[si]}
              placeholder="Paste course material here. The extracted topics stay editable." ></textarea>
            <div class="material-actions">
              <button
                type="button"
                class="quiet"
                disabled={analysisStates[si]?.busy || !materialDrafts[si]?.trim()}
                onclick={() => analyzePastedText(subject, si)}>
                {analysisStates[si]?.busy ? 'Analyzing…' : 'Analyze pasted text'}
              </button>
              {#if analysisStates[si]?.source}
                <span class:offline={analysisStates[si]?.source === 'fallback'} class="analysis-source">
                  {analysisStates[si]?.source === 'ai' ? 'OpenAI analysis' : 'Offline fallback'}
                </span>
              {/if}
            </div>
            </div>
            {#if analysisStates[si]?.message}
              <p class="analysis-message" role="status">{analysisStates[si]?.message}</p>
            {/if}
            {#if analysisStates[si]?.error}
              <p class="analysis-error" role="alert">{analysisStates[si]?.error}</p>
            {/if}
          </div>
        </details>

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
    <h3>Study time each day</h3>
    <div class="timing">
      <div>
        <label for="session-length">Study session</label>
        <select
          id="session-length"
          value={sessionLengthMode}
          onchange={(event) => selectSessionLength(event.currentTarget.value)}>
          <option value="30">30 minutes</option>
          <option value="60">1 hour</option>
          <option value="90">1 hour 30 minutes</option>
          <option value="120">2 hours</option>
          <option value="custom">Custom</option>
        </select>
      </div>
      {#if sessionLengthMode === 'custom'}
        <div>
          <label for="custom-session-length">Custom minutes</label>
          <input
            id="custom-session-length"
            type="number"
            min="15"
            max="240"
            step="5"
            bind:value={request.availability.session_length_minutes} />
        </div>
      {/if}
      <div>
        <label for="long-break">Long break (minutes)</label>
        <input
          id="long-break"
          type="number"
          min="30"
          max="180"
          step="5"
          bind:value={request.availability.long_break_minutes} />
      </div>
    </div>
    <p class="hint">
      {shortBreakMinutes} minutes of rest after each session; {request.availability.long_break_minutes}
      minutes after about 4 hours of study.
    </p>
    <div class="days">
      {#each DAYS as day, i (day)}
        <div>
          <label for={`day-${i}`}>{day}</label>
          <input
            id={`day-${i}`}
            type="number"
            min="0"
            max="12"
            step="0.5"
            value={dailyHours(i)}
            aria-label={`${day} available study hours`}
            onchange={(event) => setDailyHours(i, event.currentTarget.valueAsNumber)} />
        </div>
      {/each}
    </div>
    <p class="hint">
      Hours available each day. {totalWeeklyHours.toFixed(1)} weekly hours across
      {activeStudyDays} active study {activeStudyDays === 1 ? 'day' : 'days'}.
    </p>

    {#if shortStudyDays.length}
      <p class="hint capacity-warning" role="status">
        {shortStudyDays.join(', ')} {shortStudyDays.length === 1 ? 'is' : 'are'} shorter than the selected
        session, so {shortStudyDays.length === 1 ? 'that day' : 'those days'} will stay unused.
      </p>
    {/if}

    <div class="commitments">
      <div class="commitments-heading">
        <div>
          <h3>Fixed commitments</h3>
          <p class="hint">Classes, shifts, appointments, or commute blocks that study sessions must avoid.</p>
        </div>
        <button type="button" class="quiet" onclick={addBusyBlock}>Add commitment</button>
      </div>
      {#if request.availability.busy.length}
        <div class="commitment-list">
          {#each request.availability.busy as block, bi (bi)}
            <div class="commitment-row">
              <div class="commitment-label">
                <label for={`busy-label-${bi}`}>Label</label>
                <input id={`busy-label-${bi}`} type="text" maxlength="120" bind:value={block.label} placeholder="e.g. Part-time shift" />
              </div>
              <div>
                <label for={`busy-day-${bi}`}>Day</label>
                <select id={`busy-day-${bi}`} bind:value={block.weekday}>
                  {#each DAYS as day, dayIndex (day)}
                    <option value={dayIndex}>{day}</option>
                  {/each}
                </select>
              </div>
              <div>
                <label for={`busy-start-${bi}`}>Starts</label>
                <input id={`busy-start-${bi}`} type="time" required bind:value={block.start} />
              </div>
              <div>
                <label for={`busy-end-${bi}`}>Ends</label>
                <input id={`busy-end-${bi}`} type="time" required bind:value={block.end} />
              </div>
              <button type="button" class="link" onclick={() => removeBusyBlock(bi)}>Remove</button>
            </div>
          {/each}
        </div>
      {:else}
        <p class="empty-commitments">No fixed commitments added.</p>
      {/if}
    </div>
  </section>

  <div>
    <button type="submit" disabled={busy || !valid}>
      {busy ? 'Building your plan…' : 'Generate study plan'}
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

  .section-copy {
    max-width: 65ch;
    margin: 5px 0 12px;
    color: var(--ink-soft);
    font-size: 12px;
  }

  .planning-window {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
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

  .remove-subject {
    flex: 0 0 auto;
  }

  .material-import {
    margin: 0 0 14px;
    border: 1px solid var(--rule);
    border-radius: var(--radius-small);
    background: var(--surface-subtle);
  }

  .material-import summary {
    cursor: pointer;
    padding: 10px 12px;
    color: var(--ink-soft);
    font-size: 12px;
    font-weight: 600;
  }

  .material-import summary:hover {
    color: var(--ink);
  }

  .material-body {
    padding: 0 12px 12px;
  }

  .import-option {
    padding: 12px 0;
    border-top: 1px solid var(--rule);
  }

  .import-option:first-child {
    padding-top: 2px;
    border-top: 0;
  }

  .import-option input[type='file'] {
    width: 100%;
    min-height: 42px;
    padding: 7px;
    border: 1px solid var(--rule-strong);
    border-radius: var(--radius-small);
    background: var(--surface-elevated);
    color: var(--ink-soft);
  }

  .import-option input[type='file']::file-selector-button {
    min-height: 30px;
    margin-right: 10px;
    border: 1px solid var(--rule-strong);
    border-radius: 6px;
    background: var(--surface-subtle);
    color: var(--ink);
    padding: 5px 9px;
    font: inherit;
    font-weight: 600;
  }

  .url-input {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 8px;
  }

  .format-note {
    max-width: 52ch;
    color: var(--ink-faint);
    font-size: 11px;
  }

  .material-actions {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 9px;
  }

  .analysis-source {
    color: var(--success);
    font-size: 11px;
    font-weight: 600;
  }

  .analysis-source.offline {
    color: var(--ink-soft);
  }

  .analysis-message,
  .analysis-error {
    margin: 8px 0 0;
    font-size: 12px;
  }

  .analysis-message {
    color: var(--success);
  }

  .analysis-error {
    color: var(--danger);
  }

  .grow {
    flex: 1;
  }

  .narrow {
    width: 9.5rem;
  }

  .tiny {
    width: 6rem;
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
    width: 7.5rem;
  }

  .w-minutes {
    width: 5.5rem;
  }

  td {
    padding: 1px 6px 1px 0;
  }

  .days {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 8px;
  }

  .commitments {
    margin-top: 22px;
    padding-top: 18px;
    border-top: 1px solid var(--rule);
  }

  .commitments-heading {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 18px;
  }

  .commitments-heading .hint {
    margin-top: 3px;
  }

  .commitment-list {
    margin-top: 12px;
  }

  .commitment-row {
    display: grid;
    grid-template-columns: minmax(150px, 1fr) 90px 110px 110px auto;
    align-items: end;
    gap: 8px;
    padding: 10px 0;
    border-top: 1px solid var(--rule);
  }

  .empty-commitments {
    margin: 12px 0 0;
    color: var(--ink-faint);
    font-size: 12px;
  }

  .timing {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
    margin-bottom: 14px;
  }

  .hint {
    font-size: 12px;
    color: var(--ink-soft);
    margin: 8px 0 0;
  }

  .error-hint {
    color: var(--danger);
  }

  .capacity-warning {
    color: var(--danger);
    padding: 8px 10px;
    border: 1px solid color-mix(in srgb, var(--flag) 42%, var(--rule));
    border-radius: var(--radius-small);
    background: color-mix(in srgb, var(--flag) 8%, var(--surface));
  }

  @media (max-width: 640px) {
    .planning-window {
      grid-template-columns: 1fr;
    }

    .subject-head {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(5.5rem, 0.45fr);
    }

    .grow {
      grid-column: 1 / -1;
    }

    .narrow {
      width: auto;
    }

    .tiny {
      width: auto;
    }

    .days {
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }

    .timing {
      grid-template-columns: 1fr;
    }

    .url-input {
      grid-template-columns: 1fr;
    }

    .commitments-heading {
      align-items: stretch;
      flex-direction: column;
    }

    .commitment-row {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .commitment-label,
    .commitment-row button {
      grid-column: 1 / -1;
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
