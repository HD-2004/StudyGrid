<script lang="ts">
  import {
    IconBook2,
    IconBrain,
    IconCalendarDue,
    IconClock,
    IconPlus,
    IconSparkles,
    IconTrash,
  } from '@tabler/icons-svelte'
  import type { Availability, DraftSubject, Strategy, Topic } from '../lib/types'
  import { blankSubject } from '../lib/sample'

  export let subjects: DraftSubject[]
  export let availability: Availability
  export let strategy: Strategy
  export let startDate: string
  export let analyzingIndex: number | null = null
  export let generating = false
  export let onAnalyze: (index: number) => void
  export let onGenerate: () => void
  export let onLoadSample: (strategy: Strategy) => void

  const weekdays = [
    { index: 0, short: 'Mon' },
    { index: 1, short: 'Tue' },
    { index: 2, short: 'Wed' },
    { index: 3, short: 'Thu' },
    { index: 4, short: 'Fri' },
    { index: 5, short: 'Sat' },
    { index: 6, short: 'Sun' },
  ]

  const strategies: Array<{ value: Strategy; label: string; description: string }> = [
    { value: 'fresh', label: 'Fresh start', description: 'Learn and review every topic' },
    { value: 'remaining', label: 'Mid-semester', description: 'Focus on what remains' },
    { value: 'exam_rush', label: 'Exam rush', description: 'Prioritize fast coverage' },
  ]

  function addSubject() {
    subjects = [...subjects, blankSubject()]
  }

  function removeSubject(index: number) {
    subjects = subjects.filter((_, subjectIndex) => subjectIndex !== index)
  }

  function addTopic(subjectIndex: number) {
    const topic: Topic = {
      name: '',
      difficulty: 'medium',
      estimated_minutes: 60,
      already_studied: false,
      depends_on: [],
    }
    subjects[subjectIndex].topics = [...subjects[subjectIndex].topics, topic]
    subjects = [...subjects]
  }

  function removeTopic(subjectIndex: number, topicIndex: number) {
    subjects[subjectIndex].topics = subjects[subjectIndex].topics.filter(
      (_, index) => index !== topicIndex,
    )
    subjects = [...subjects]
  }

  function addBusyBlock() {
    availability.busy = [
      ...availability.busy,
      { weekday: 0, start: '09:00', end: '10:00', label: 'Class' },
    ]
    availability = { ...availability }
  }

  function removeBusyBlock(index: number) {
    availability.busy = availability.busy.filter((_, blockIndex) => blockIndex !== index)
    availability = { ...availability }
  }
</script>

<form class="intake-form" on:submit|preventDefault={onGenerate}>
  <section class="form-section form-intro">
    <div class="section-heading-row">
      <div>
        <h2>Build around your real week</h2>
        <p class="section-copy">
          Add subjects, deadlines, and the time you can study. You can change these settings later.
        </p>
      </div>
      <button
        class="button button-quiet sample-button"
        type="button"
        on:click={() => onLoadSample(strategy)}
      >
        Load sample
      </button>
    </div>
  </section>

  <section class="form-section">
    <div class="section-title">
      <IconBrain size={19} stroke={1.8} aria-hidden="true" />
      <h2>Planning mode</h2>
    </div>
    <div class="strategy-grid" role="radiogroup" aria-label="Planning strategy">
      {#each strategies as option}
        <label class:active={strategy === option.value} class="strategy-option">
          <input type="radio" name="strategy" value={option.value} bind:group={strategy} />
          <span>{option.label}</span>
          <small>{option.description}</small>
        </label>
      {/each}
    </div>
    <label class="field compact-field">
      <span>Plan starts</span>
      <input type="date" bind:value={startDate} required />
    </label>
  </section>

  <section class="form-section subjects-section">
    <div class="section-title section-title-between">
      <div class="section-title-label">
        <IconBook2 size={19} stroke={1.8} aria-hidden="true" />
        <h2>Subjects</h2>
      </div>
      <button class="icon-text-button" type="button" on:click={addSubject}>
        <IconPlus size={17} stroke={1.8} aria-hidden="true" />
        Add subject
      </button>
    </div>

    <div class="subject-stack">
      {#each subjects as subject, subjectIndex}
        <article class="subject-editor">
          <div class="subject-header">
            <div class="subject-number">{String(subjectIndex + 1).padStart(2, '0')}</div>
            <div class="subject-name-block">
              <label class="field">
                <span>Subject name</span>
                <input
                  type="text"
                  bind:value={subject.name}
                  placeholder="e.g. Molecular Biology"
                  required
                />
              </label>
              <div class="inline-fields">
                <label class="field">
                  <span>Exam date</span>
                  <input type="date" bind:value={subject.exam_date} required />
                </label>
                <label class="field">
                  <span>Priority</span>
                  <select bind:value={subject.priority}>
                    <option value={1}>1 - Low</option>
                    <option value={2}>2</option>
                    <option value={3}>3 - Normal</option>
                    <option value={4}>4</option>
                    <option value={5}>5 - High</option>
                  </select>
                </label>
              </div>
            </div>
            {#if subjects.length > 1}
              <button
                class="icon-button danger-button"
                type="button"
                aria-label={`Remove ${subject.name || 'subject'}`}
                title="Remove subject"
                on:click={() => removeSubject(subjectIndex)}
              >
                <IconTrash size={18} stroke={1.8} aria-hidden="true" />
              </button>
            {/if}
          </div>

          <div class="material-panel">
            <label class="field">
              <span>Course material</span>
              <textarea
                rows="4"
                bind:value={subject.materialText}
                placeholder="Paste a syllabus, topic list, or course outline"
              ></textarea>
            </label>
            <div class="material-actions">
              <p>
                {#if subject.analysisSource === 'ai'}
                  Topics extracted with AI
                {:else if subject.analysisSource === 'fallback'}
                  Topics extracted locally
                {:else}
                  AI suggests topics, difficulty, and study time
                {/if}
              </p>
              <button
                class="button button-secondary"
                type="button"
                disabled={!subject.materialText.trim() || analyzingIndex !== null}
                on:click={() => onAnalyze(subjectIndex)}
              >
                <IconSparkles size={17} stroke={1.8} aria-hidden="true" />
                {analyzingIndex === subjectIndex ? 'Analyzing...' : 'Analyze material'}
              </button>
            </div>
          </div>

          <div class="topics-header">
            <span>Topics</span>
            <button class="icon-text-button" type="button" on:click={() => addTopic(subjectIndex)}>
              <IconPlus size={16} stroke={1.8} aria-hidden="true" />
              Add manually
            </button>
          </div>

          {#if subject.topics.length}
            <div class="topic-list">
              {#each subject.topics as topic, topicIndex}
                <div class="topic-row">
                  <label class="field topic-name-field">
                    <span class="sr-only">Topic name</span>
                    <input type="text" bind:value={topic.name} aria-label="Topic name" required />
                  </label>
                  <label class="field topic-select-field">
                    <span class="sr-only">Difficulty</span>
                    <select bind:value={topic.difficulty} aria-label="Topic difficulty">
                      <option value="easy">Easy</option>
                      <option value="medium">Medium</option>
                      <option value="hard">Hard</option>
                    </select>
                  </label>
                  <label class="field topic-minutes-field">
                    <span class="sr-only">Estimated minutes</span>
                    <input
                      type="number"
                      min="15"
                      max="600"
                      step="5"
                      bind:value={topic.estimated_minutes}
                      aria-label="Estimated minutes"
                    />
                    <small>min</small>
                  </label>
                  {#if strategy === 'remaining'}
                    <label class="studied-check">
                      <input type="checkbox" bind:checked={topic.already_studied} />
                      <span>Studied</span>
                    </label>
                  {/if}
                  <button
                    class="icon-button"
                    type="button"
                    aria-label={`Remove ${topic.name || 'topic'}`}
                    title="Remove topic"
                    on:click={() => removeTopic(subjectIndex, topicIndex)}
                  >
                    <IconTrash size={17} stroke={1.8} aria-hidden="true" />
                  </button>
                </div>
              {/each}
            </div>
          {:else}
            <div class="inline-empty-state">
              Paste material for analysis or add the first topic manually.
            </div>
          {/if}
        </article>
      {/each}
    </div>
  </section>

  <section class="form-section">
    <div class="section-title">
      <IconClock size={19} stroke={1.8} aria-hidden="true" />
      <h2>Weekly availability</h2>
    </div>
    <div class="weekday-grid">
      {#each weekdays as day}
        <label class="weekday-field">
          <span>{day.short}</span>
          <input
            type="number"
            min="0"
            max="720"
            step="15"
            bind:value={availability.weekday_minutes[day.index]}
            aria-label={`${day.short} available minutes`}
          />
          <small>min</small>
        </label>
      {/each}
    </div>

    <div class="availability-settings">
      <label class="field">
        <span>Earliest</span>
        <input type="time" bind:value={availability.earliest} />
      </label>
      <label class="field">
        <span>Latest</span>
        <input type="time" bind:value={availability.latest} />
      </label>
      <label class="field">
        <span>Session</span>
        <select bind:value={availability.session_length_minutes}>
          <option value={25}>25 min</option>
          <option value={40}>40 min</option>
          <option value={50}>50 min</option>
          <option value={60}>60 min</option>
          <option value={90}>90 min</option>
        </select>
      </label>
      <label class="field">
        <span>Break</span>
        <select bind:value={availability.break_minutes}>
          <option value={0}>No break</option>
          <option value={5}>5 min</option>
          <option value={10}>10 min</option>
          <option value={15}>15 min</option>
          <option value={20}>20 min</option>
        </select>
      </label>
    </div>

    <details class="commitments">
      <summary>
        <span>Fixed commitments</span>
        <span>{availability.busy.length}</span>
      </summary>
      <div class="commitment-list">
        {#each availability.busy as block, blockIndex}
          <div class="commitment-row">
            <label class="field">
              <span class="sr-only">Commitment name</span>
              <input type="text" bind:value={block.label} aria-label="Commitment name" />
            </label>
            <label class="field">
              <span class="sr-only">Weekday</span>
              <select bind:value={block.weekday} aria-label="Commitment weekday">
                {#each weekdays as day}
                  <option value={day.index}>{day.short}</option>
                {/each}
              </select>
            </label>
            <label class="field">
              <span class="sr-only">Start time</span>
              <input type="time" bind:value={block.start} aria-label="Commitment start time" />
            </label>
            <label class="field">
              <span class="sr-only">End time</span>
              <input type="time" bind:value={block.end} aria-label="Commitment end time" />
            </label>
            <button
              class="icon-button"
              type="button"
              aria-label={`Remove ${block.label || 'commitment'}`}
              title="Remove commitment"
              on:click={() => removeBusyBlock(blockIndex)}
            >
              <IconTrash size={17} stroke={1.8} aria-hidden="true" />
            </button>
          </div>
        {/each}
        <button class="icon-text-button" type="button" on:click={addBusyBlock}>
          <IconPlus size={16} stroke={1.8} aria-hidden="true" />
          Add commitment
        </button>
      </div>
    </details>
  </section>

  <div class="generate-bar">
    <div>
      <IconCalendarDue size={20} stroke={1.8} aria-hidden="true" />
      <span>{subjects.reduce((count, subject) => count + subject.topics.length, 0)} topics ready</span>
    </div>
    <button class="button button-primary" type="submit" disabled={generating}>
      {generating ? 'Building plan...' : 'Generate study plan'}
    </button>
  </div>
</form>
