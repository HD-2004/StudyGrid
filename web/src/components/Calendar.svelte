<script lang="ts">
  import type { CalendarEvent } from '../lib/types'

  type Theme = 'light' | 'dark'
  type CalendarView = 'week' | 'month'
  type AiPreview = {
    eventId: string
    title: string
    currentStart: string
    proposedStart: string
    proposedEnd: string
    explanation: string
    source: 'ai' | 'fallback'
  }
  type Interaction = {
    id: string
    kind: 'move' | 'resize'
    pointerX: number
    pointerY: number
    originalStart: Date
    originalEnd: Date
    draftStart: Date
    draftEnd: Date
    moved: boolean
  }

  let {
    events,
    unscheduled,
    theme,
    onSelect,
    onMove,
    onCreate,
    onOpenProgress,
    onToggleTheme,
    onAskAi,
    onStartNew,
    onDeleteData,
    deleteConfirm,
    deletingData,
  }: {
    events: CalendarEvent[]
    unscheduled: string[]
    theme: Theme
    onSelect: (id: string) => void
    onMove: (id: string, start: string, end: string) => Promise<void>
    onCreate: (start?: string) => void
    onOpenProgress: () => void
    onToggleTheme: () => void
    onAskAi: (message: string) => Promise<{ reply: string; source: 'ai' | 'fallback' }>
    onStartNew: () => void
    onDeleteData: () => void
    deleteConfirm: boolean
    deletingData: boolean
  } = $props()

  const START_HOUR = 7
  const END_HOUR = 23
  const ROW_HEIGHT = 56
  const HOURS = Array.from({ length: END_HOUR - START_HOUR + 1 }, (_, index) => START_HOUR + index)
  const EVENT_COLORS = ['blue', 'amber', 'teal', 'coral', 'violet', 'rose']

  let anchor = $state(new Date())
  let anchorInitialized = false
  let view = $state<CalendarView>('week')
  let sidebarOpen = $state(true)
  let aiOpen = $state(false)
  let aiPrompt = $state('Tối ưu lịch tuần này để tôi hoàn thành các việc quan trọng.')
  let aiBusy = $state(false)
  let aiError = $state<string | null>(null)
  let aiPreview = $state<AiPreview | null>(null)
  let hiddenSubjects = $state<string[]>([])
  let interaction = $state<Interaction | null>(null)
  let savingMove = $state(false)
  let suppressClick = false
  let gridElement = $state<HTMLDivElement | null>(null)

  const weekStart = $derived(startOfWeek(anchor))
  const weekDays = $derived(
    Array.from({ length: 7 }, (_, index) => addDays(weekStart, index)),
  )
  const subjects = $derived(
    [...new Set(events.map((event) => event.subject))].sort((a, b) => a.localeCompare(b)),
  )
  const visibleEvents = $derived(
    events.filter((event) => !hiddenSubjects.includes(event.subject)),
  )
  const calendarTitle = $derived(
    view === 'week'
      ? new Intl.DateTimeFormat('vi-VN', { month: 'long', year: 'numeric' }).format(weekStart)
      : new Intl.DateTimeFormat('vi-VN', { month: 'long', year: 'numeric' }).format(anchor),
  )
  const miniDays = $derived(buildMonthDays(anchor))
  const monthDays = $derived(buildMonthDays(anchor))

  $effect(() => {
    if (!anchorInitialized && events[0]) {
      anchor = new Date(events[0].start)
      anchorInitialized = true
    }
  })

  function startOfWeek(value: Date): Date {
    const result = new Date(value)
    result.setHours(0, 0, 0, 0)
    const weekday = (result.getDay() + 6) % 7
    result.setDate(result.getDate() - weekday)
    return result
  }

  function addDays(value: Date, amount: number): Date {
    const result = new Date(value)
    result.setDate(result.getDate() + amount)
    return result
  }

  function dateKey(value: Date): string {
    const year = value.getFullYear()
    const month = String(value.getMonth() + 1).padStart(2, '0')
    const day = String(value.getDate()).padStart(2, '0')
    return `${year}-${month}-${day}`
  }

  function toLocalIso(value: Date): string {
    const time = [value.getHours(), value.getMinutes(), value.getSeconds()]
      .map((part) => String(part).padStart(2, '0'))
      .join(':')
    return `${dateKey(value)}T${time}`
  }

  function isSameDay(left: Date, right: Date): boolean {
    return dateKey(left) === dateKey(right)
  }

  function isToday(value: Date): boolean {
    return isSameDay(value, new Date())
  }

  function buildMonthDays(value: Date): Date[] {
    const first = new Date(value.getFullYear(), value.getMonth(), 1)
    const start = startOfWeek(first)
    return Array.from({ length: 42 }, (_, index) => addDays(start, index))
  }

  function formatWeekday(value: Date): string {
    return new Intl.DateTimeFormat('vi-VN', { weekday: 'short' }).format(value)
  }

  function formatTime(value: Date): string {
    return new Intl.DateTimeFormat('vi-VN', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(value)
  }

  function eventColor(event: CalendarEvent): string {
    let hash = 0
    for (const character of event.subject) hash = (hash * 31 + character.charCodeAt(0)) | 0
    return EVENT_COLORS[Math.abs(hash) % EVENT_COLORS.length]
  }

  function displayTimes(event: CalendarEvent): { start: Date; end: Date } {
    if (interaction?.id === event.id) {
      return { start: interaction.draftStart, end: interaction.draftEnd }
    }
    return { start: new Date(event.start), end: new Date(event.end) }
  }

  function eventsForDay(day: Date): CalendarEvent[] {
    return visibleEvents
      .filter((event) => isSameDay(displayTimes(event).start, day))
      .sort((left, right) => displayTimes(left).start.getTime() - displayTimes(right).start.getTime())
  }

  function eventStyle(event: CalendarEvent): string {
    const { start, end } = displayTimes(event)
    const topMinutes = (start.getHours() - START_HOUR) * 60 + start.getMinutes()
    const duration = Math.max(30, (end.getTime() - start.getTime()) / 60_000)
    const top = Math.max(0, (topMinutes / 60) * ROW_HEIGHT)
    const height = Math.max(30, (duration / 60) * ROW_HEIGHT - 3)
    return `top:${top}px;height:${height}px`
  }

  function currentTimeTop(): number {
    const now = new Date()
    return ((now.getHours() - START_HOUR) * 60 + now.getMinutes()) / 60 * ROW_HEIGHT
  }

  function navigate(amount: number) {
    anchor = view === 'week' ? addDays(anchor, amount * 7) : new Date(anchor.getFullYear(), anchor.getMonth() + amount, 1)
  }

  function toggleSubject(subject: string) {
    hiddenSubjects = hiddenSubjects.includes(subject)
      ? hiddenSubjects.filter((item) => item !== subject)
      : [...hiddenSubjects, subject]
  }

  function chooseDay(day: Date) {
    anchor = new Date(day)
    view = 'week'
  }

  function gridDoubleClick(event: MouseEvent, day: Date) {
    if (!(event.target instanceof HTMLElement) || event.target.closest('.sx__event')) return
    const bounds = (event.currentTarget as HTMLElement).getBoundingClientRect()
    const minutes = Math.max(0, Math.min((END_HOUR - START_HOUR) * 60, ((event.clientY - bounds.top) / ROW_HEIGHT) * 60))
    const snapped = Math.round(minutes / 30) * 30
    const start = new Date(day)
    start.setHours(START_HOUR + Math.floor(snapped / 60), snapped % 60, 0, 0)
    onCreate(toLocalIso(start))
  }

  function beginInteraction(pointer: PointerEvent, event: CalendarEvent, kind: 'move' | 'resize') {
    if (event.completion !== 'planned' || savingMove) return
    pointer.preventDefault()
    pointer.stopPropagation()
    const start = new Date(event.start)
    const end = new Date(event.end)
    interaction = {
      id: event.id,
      kind,
      pointerX: pointer.clientX,
      pointerY: pointer.clientY,
      originalStart: start,
      originalEnd: end,
      draftStart: new Date(start),
      draftEnd: new Date(end),
      moved: false,
    }
  }

  function handlePointerMove(pointer: PointerEvent) {
    if (!interaction || !gridElement) return
    const bounds = gridElement.getBoundingClientRect()
    const columnWidth = Math.max(1, bounds.width / 7)
    const dayDelta = interaction.kind === 'move'
      ? Math.round((pointer.clientX - interaction.pointerX) / columnWidth)
      : 0
    const rawMinutes = ((pointer.clientY - interaction.pointerY) / ROW_HEIGHT) * 60
    const minuteDelta = Math.round(rawMinutes / 15) * 15

    if (interaction.kind === 'move') {
      const duration = interaction.originalEnd.getTime() - interaction.originalStart.getTime()
      const nextStart = addDays(interaction.originalStart, dayDelta)
      nextStart.setMinutes(nextStart.getMinutes() + minuteDelta)
      const startLimit = new Date(nextStart)
      startLimit.setHours(START_HOUR, 0, 0, 0)
      const endLimit = new Date(nextStart)
      endLimit.setHours(END_HOUR, 0, 0, 0)
      if (nextStart < startLimit) nextStart.setTime(startLimit.getTime())
      if (nextStart.getTime() + duration > endLimit.getTime()) nextStart.setTime(endLimit.getTime() - duration)
      interaction.draftStart = nextStart
      interaction.draftEnd = new Date(nextStart.getTime() + duration)
    } else {
      const nextEnd = new Date(interaction.originalEnd)
      nextEnd.setMinutes(nextEnd.getMinutes() + minuteDelta)
      const minimum = new Date(interaction.originalStart.getTime() + 30 * 60_000)
      const limit = new Date(interaction.originalStart)
      limit.setHours(END_HOUR, 0, 0, 0)
      interaction.draftEnd = new Date(Math.min(limit.getTime(), Math.max(minimum.getTime(), nextEnd.getTime())))
    }
    interaction.moved = Math.abs(pointer.clientX - interaction.pointerX) > 4 || Math.abs(pointer.clientY - interaction.pointerY) > 4
  }

  async function handlePointerUp() {
    if (!interaction) return
    const finished = interaction
    interaction = null
    if (!finished.moved) return
    suppressClick = true
    savingMove = true
    try {
      await onMove(finished.id, toLocalIso(finished.draftStart), toLocalIso(finished.draftEnd))
    } finally {
      savingMove = false
      setTimeout(() => (suppressClick = false), 0)
    }
  }

  function findSuggestedMove(): { event: CalendarEvent; start: Date; end: Date } | null {
    const candidate = [...events]
      .filter((event) => event.completion === 'planned')
      .sort((a, b) => Date.parse(a.start) - Date.parse(b.start))[0]
    if (!candidate) return null
    const currentStart = new Date(candidate.start)
    const duration = Date.parse(candidate.end) - currentStart.getTime()
    for (let offset = 1; offset <= 14; offset += 1) {
      const start = addDays(currentStart, offset)
      const end = new Date(start.getTime() + duration)
      const overlaps = events.some((event) => {
        if (event.id === candidate.id) return false
        const otherStart = new Date(event.start)
        const otherEnd = new Date(event.end)
        return start < otherEnd && end > otherStart
      })
      if (!overlaps) return { event: candidate, start, end }
    }
    return null
  }

  async function requestAiPreview() {
    if (!aiPrompt.trim() || aiBusy) return
    aiBusy = true
    aiError = null
    aiPreview = null
    try {
      const [answer, move] = await Promise.all([
        onAskAi(aiPrompt.trim()),
        Promise.resolve(findSuggestedMove()),
      ])
      if (!move) {
        aiError = 'Hiện chưa có công việc Pending hoặc khung giờ trống phù hợp để đề xuất.'
        return
      }
      aiPreview = {
        eventId: move.event.id,
        title: move.event.title,
        currentStart: move.event.start,
        proposedStart: toLocalIso(move.start),
        proposedEnd: toLocalIso(move.end),
        explanation: answer.reply,
        source: answer.source,
      }
    } catch (reason) {
      aiError = reason instanceof Error ? reason.message : 'Không thể tạo đề xuất lúc này.'
    } finally {
      aiBusy = false
    }
  }

  async function applyAiPreview() {
    if (!aiPreview || savingMove) return
    savingMove = true
    try {
      await onMove(aiPreview.eventId, aiPreview.proposedStart, aiPreview.proposedEnd)
      anchor = new Date(aiPreview.proposedStart)
      aiPreview = null
    } catch (reason) {
      aiError = reason instanceof Error ? reason.message : 'Không thể áp dụng đề xuất.'
    } finally {
      savingMove = false
    }
  }
</script>

<svelte:window onpointermove={handlePointerMove} onpointerup={handlePointerUp} />

<section class="calendar-app" aria-label="Lịch StudyGrid">
  <header class="calendar-toolbar">
    <div class="toolbar-brand">
      <button class="icon-button menu-button" type="button" aria-label="Ẩn hoặc hiện thanh bên" onclick={() => (sidebarOpen = !sidebarOpen)}>
        <span aria-hidden="true">☰</span>
      </button>
      <a class="calendar-brand" href="#main-content" aria-label="StudyGrid">
        <span class="grid-mark" aria-hidden="true"><i></i><i></i><i></i><i></i></span>
        <strong>StudyGrid</strong>
      </a>
    </div>

    <div class="date-navigation">
      <button type="button" class="today-button" onclick={() => (anchor = new Date())}>Hôm nay</button>
      <button type="button" class="icon-button" aria-label="Kỳ trước" onclick={() => navigate(-1)}>‹</button>
      <button type="button" class="icon-button" aria-label="Kỳ sau" onclick={() => navigate(1)}>›</button>
      <h1>{calendarTitle}</h1>
    </div>

    <div class="toolbar-actions">
      <label class="search-box">
        <span aria-hidden="true">⌕</span>
        <span class="sr-only">Tìm kiếm sự kiện</span>
        <input type="search" placeholder="Tìm sự kiện" />
      </label>
      <div class="view-switch" aria-label="Chế độ xem">
        <button type="button" class:active={view === 'week'} aria-pressed={view === 'week'} onclick={() => (view = 'week')}>Tuần</button>
        <button type="button" class:active={view === 'month'} aria-pressed={view === 'month'} onclick={() => (view = 'month')}>Tháng</button>
      </div>
      <button class="icon-button" type="button" aria-label={`Chuyển sang giao diện ${theme === 'dark' ? 'sáng' : 'tối'}`} onclick={onToggleTheme}>
        {theme === 'dark' ? '☼' : '◐'}
      </button>
      <span class="avatar" aria-label="Tài khoản thử nghiệm">SG</span>
    </div>
  </header>

  <div class="calendar-body" class:sidebar-collapsed={!sidebarOpen} class:ai-expanded={aiOpen}>
    <aside class="calendar-sidebar" aria-label="Thanh bên lịch">
      <button class="create-button" type="button" onclick={() => onCreate()}><span aria-hidden="true">＋</span>Tạo</button>

      <section class="mini-calendar" aria-label="Lịch tháng thu nhỏ">
        <header>
          <strong>{new Intl.DateTimeFormat('vi-VN', { month: 'long', year: 'numeric' }).format(anchor)}</strong>
          <span><button type="button" aria-label="Tháng trước" onclick={() => navigate(-1)}>‹</button><button type="button" aria-label="Tháng sau" onclick={() => navigate(1)}>›</button></span>
        </header>
        <div class="mini-weekdays" aria-hidden="true"><span>T2</span><span>T3</span><span>T4</span><span>T5</span><span>T6</span><span>T7</span><span>CN</span></div>
        <div class="mini-grid">
          {#each miniDays as day (dateKey(day))}
            <button
              type="button"
              class:outside={day.getMonth() !== anchor.getMonth()}
              class:today={isToday(day)}
              class:selected={isSameDay(day, anchor)}
              aria-label={day.toLocaleDateString('vi-VN')}
              onclick={() => chooseDay(day)}>{day.getDate()}</button>
          {/each}
        </div>
      </section>

      <section class="calendar-list" aria-labelledby="my-calendars">
        <header><h2 id="my-calendars">Lịch của tôi</h2><button type="button" aria-label="Thêm lịch">＋</button></header>
        {#each subjects as subject, index (subject)}
          <label>
            <input type="checkbox" checked={!hiddenSubjects.includes(subject)} onchange={() => toggleSubject(subject)} />
            <i class={`subject-color ${EVENT_COLORS[index % EVENT_COLORS.length]}`} aria-hidden="true"></i>
            <span>{subject}</span>
          </label>
        {/each}
      </section>

      {#if unscheduled.length}
        <section class="backlog-list" aria-labelledby="unscheduled-heading">
          <header><h2 id="unscheduled-heading">Chưa xếp lịch</h2><span>{unscheduled.length}</span></header>
          <ul>
            {#each unscheduled as item (item)}<li>{item}</li>{/each}
          </ul>
        </section>
      {/if}

      <button class="progress-link" type="button" onclick={onOpenProgress}><span aria-hidden="true">▥</span>Tiến độ</button>

      <div class="status-legend" aria-label="Trạng thái sự kiện">
        <p>Trạng thái</p>
        <span><i class="pending"></i>Pending</span>
        <span><i class="completed"></i>Completed</span>
        <span><i class="rescheduled"></i>Đã dời lịch</span>
      </div>
      <div class="data-actions">
        <button type="button" onclick={onStartNew}>Tạo kế hoạch mới</button>
        <button type="button" class:danger={deleteConfirm} disabled={deletingData} onclick={onDeleteData}>
          {deletingData ? 'Đang xóa…' : deleteConfirm ? 'Xác nhận xóa dữ liệu' : 'Xóa dữ liệu của tôi'}
        </button>
      </div>
    </aside>

    <main class="calendar-main">
      {#if view === 'week'}
        <div class="week-head">
          <div class="timezone">GMT+07</div>
          {#each weekDays as day (dateKey(day))}
            <button type="button" class:today={isToday(day)} onclick={() => (anchor = new Date(day))}>
              <span>{formatWeekday(day)}</span><strong>{day.getDate()}</strong>
            </button>
          {/each}
        </div>
        <div class="week-scroll" aria-label="Lịch tuần, kéo sự kiện để đổi giờ">
          <div class="time-axis" aria-hidden="true">
            {#each HOURS as hour (hour)}<span style={`top:${(hour - START_HOUR) * ROW_HEIGHT}px`}>{String(hour).padStart(2, '0')}:00</span>{/each}
          </div>
          <div class="week-grid" bind:this={gridElement} style={`height:${(END_HOUR - START_HOUR) * ROW_HEIGHT}px`}>
            {#each weekDays as day (dateKey(day))}
              <!-- svelte-ignore a11y_no_static_element_interactions -->
              <div class="day-lane" class:today={isToday(day)} ondblclick={(pointer) => gridDoubleClick(pointer, day)}>
                {#each eventsForDay(day) as event (event.id)}
                  {@const times = displayTimes(event)}
                  <button
                    type="button"
                    class={`sx__event calendar-event ${eventColor(event)}`}
                    class:completed={event.completion === 'completed'}
                    class:rescheduled={Boolean(event.rescheduled_from_id)}
                    class:dragging={interaction?.id === event.id}
                    style={eventStyle(event)}
                    aria-label={`${event.title}, ${formatTime(times.start)} đến ${formatTime(times.end)}, ${event.completion === 'completed' ? 'Completed' : 'Pending'}`}
                    onpointerdown={(pointer) => beginInteraction(pointer, event, 'move')}
                    onclick={() => {
                      if (!suppressClick) onSelect(event.id)
                    }}>
                    <span class="event-title">{event.title}</span>
                    <span class="event-time">{formatTime(times.start)} – {formatTime(times.end)}</span>
                    <span class="event-status" aria-hidden="true">{event.completion === 'completed' ? '✓' : '•'}</span>
                    {#if event.completion === 'planned'}
                      <span class="resize-handle" role="presentation" onpointerdown={(pointer) => beginInteraction(pointer, event, 'resize')}></span>
                    {/if}
                  </button>
                {/each}
                {#if isToday(day) && currentTimeTop() >= 0 && currentTimeTop() <= (END_HOUR - START_HOUR) * ROW_HEIGHT}
                  <div class="current-time" style={`top:${currentTimeTop()}px`}><i></i></div>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {:else}
        <div class="month-view">
          <div class="month-weekdays" aria-hidden="true"><span>Thứ Hai</span><span>Thứ Ba</span><span>Thứ Tư</span><span>Thứ Năm</span><span>Thứ Sáu</span><span>Thứ Bảy</span><span>Chủ Nhật</span></div>
          <div class="month-grid">
            {#each monthDays as day (dateKey(day))}
              <section class:outside={day.getMonth() !== anchor.getMonth()} class:today={isToday(day)}>
                <button type="button" onclick={() => chooseDay(day)}>{day.getDate()}</button>
                {#each eventsForDay(day).slice(0, 3) as event (event.id)}
                  <button type="button" class={`month-event ${eventColor(event)}`} onclick={() => onSelect(event.id)}>{formatTime(new Date(event.start))} {event.topic}</button>
                {/each}
                {#if eventsForDay(day).length > 3}<span class="more-events">+{eventsForDay(day).length - 3} khác</span>{/if}
              </section>
            {/each}
          </div>
        </div>
      {/if}
      {#if savingMove}<div class="saving-toast" role="status">Đang lưu thay đổi…</div>{/if}
    </main>

    <aside class="utility-area" aria-label="Công cụ StudyGrid">
      <nav class="utility-rail" aria-label="Công cụ nhanh">
        <button type="button" class:active={aiOpen} aria-label="Lập kế hoạch với AI" onclick={() => (aiOpen = !aiOpen)}><span aria-hidden="true">✦</span><small>AI</small></button>
        <button type="button" aria-label="Mở tiến độ" onclick={onOpenProgress}><span aria-hidden="true">▥</span><small>Tiến độ</small></button>
      </nav>
      {#if aiOpen}
        <section class="ai-panel" aria-labelledby="ai-title">
          <header><div><span aria-hidden="true">✦</span><h2 id="ai-title">Lập kế hoạch với AI</h2></div><button type="button" aria-label="Đóng AI" onclick={() => (aiOpen = false)}>×</button></header>
          <p>AI phân tích lịch đang có; mọi thay đổi đều cần bạn xác nhận.</p>
          <label for="ai-prompt">Bạn muốn điều chỉnh điều gì?</label>
          <textarea id="ai-prompt" rows="4" maxlength="1000" bind:value={aiPrompt}></textarea>
          <button class="ai-submit" type="button" disabled={aiBusy || !aiPrompt.trim()} onclick={requestAiPreview}>{aiBusy ? 'Đang phân tích…' : 'Tạo đề xuất'}</button>
          {#if aiError}<div class="ai-error" role="alert">{aiError}</div>{/if}
          {#if aiPreview}
            <article class="ai-preview">
              <div class="preview-label"><span>Đề xuất</span><small>{aiPreview.source === 'ai' ? 'OpenAI' : 'Scheduler dự phòng'}</small></div>
              <h3>{aiPreview.title}</h3>
              <div class="time-comparison">
                <div><span>Hiện tại</span><strong>{new Date(aiPreview.currentStart).toLocaleString('vi-VN', { weekday: 'short', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}</strong></div>
                <i aria-hidden="true">→</i>
                <div><span>Đề xuất</span><strong>{new Date(aiPreview.proposedStart).toLocaleString('vi-VN', { weekday: 'short', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}</strong></div>
              </div>
              <p>{aiPreview.explanation}</p>
              <div class="preview-actions"><button type="button" class="apply" disabled={savingMove} onclick={applyAiPreview}>Áp dụng</button><button type="button" onclick={() => (aiPreview = null)}>Bỏ qua</button></div>
            </article>
          {:else}
            <div class="ai-empty"><span aria-hidden="true">✦</span><p>Nhập mục tiêu để nhận một phương án thay đổi có thể xem trước.</p></div>
          {/if}
        </section>
      {/if}
    </aside>
  </div>
</section>

<style>
  .calendar-app { height: 100dvh; min-height: 680px; overflow: hidden; background: var(--page); color: var(--ink); }
  .calendar-toolbar { height: 64px; display: grid; grid-template-columns: 240px minmax(430px, 1fr) auto; align-items: center; gap: 16px; padding: 0 16px; border-bottom: 1px solid var(--rule); background: var(--surface); }
  .toolbar-brand, .date-navigation, .toolbar-actions, .calendar-brand, .mini-calendar header, .calendar-list header, .backlog-list header, .ai-panel header, .ai-panel header > div, .preview-actions { display: flex; align-items: center; }
  .toolbar-brand { gap: 12px; }
  .calendar-brand { gap: 10px; color: var(--ink); text-decoration: none; font-size: 18px; }
  .grid-mark { width: 28px; height: 28px; display: grid; grid-template-columns: repeat(2, 1fr); gap: 3px; }
  .grid-mark i { border: 2px solid var(--accent); border-radius: 3px; }
  .icon-button, .today-button, .view-switch button, .mini-calendar button, .calendar-list header button, .week-head button, .ai-panel header button { border: 0; background: transparent; color: var(--ink); }
  .icon-button { width: 38px; height: 38px; padding: 0; border-radius: 50%; font-size: 22px; }
  .icon-button:hover { background: var(--surface-subtle); }
  .date-navigation { gap: 5px; min-width: 0; }
  .today-button { min-height: 38px; padding: 0 16px; margin-right: 7px; border: 1px solid var(--rule-strong); border-radius: 8px; font-weight: 650; }
  .date-navigation h1 { margin: 0 0 0 10px; font-size: clamp(17px, 1.5vw, 22px); text-transform: capitalize; white-space: nowrap; }
  .toolbar-actions { justify-content: flex-end; gap: 8px; }
  .search-box { width: min(230px, 18vw); min-height: 38px; display: flex; align-items: center; gap: 8px; padding: 0 11px; border: 1px solid var(--rule); border-radius: 8px; background: var(--surface-subtle); }
  .search-box input { width: 100%; border: 0; padding: 0; background: transparent; color: var(--ink); outline: 0; }
  .view-switch { display: flex; padding: 3px; border: 1px solid var(--rule); border-radius: 8px; }
  .view-switch button { min-height: 32px; padding: 0 12px; border-radius: 5px; font-size: 12px; }
  .view-switch button.active { background: var(--accent); color: var(--accent-ink); }
  .avatar { width: 34px; height: 34px; display: grid; place-items: center; border: 2px solid var(--accent); border-radius: 50%; background: var(--surface-subtle); color: var(--ink); font-size: 11px; font-weight: 750; }

  .calendar-body { height: calc(100dvh - 64px); display: grid; grid-template-columns: 240px minmax(640px, 1fr) 56px; transition: grid-template-columns 180ms ease; }
  .calendar-body.sidebar-collapsed { grid-template-columns: 0 minmax(640px, 1fr) 56px; }
  .calendar-body.ai-expanded { grid-template-columns: 240px minmax(560px, 1fr) 370px; }
  .calendar-body.sidebar-collapsed.ai-expanded { grid-template-columns: 0 minmax(560px, 1fr) 370px; }
  .calendar-sidebar { min-width: 0; overflow: hidden auto; padding: 14px; background: var(--surface); box-shadow: inset -1px 0 var(--rule); }
  .sidebar-collapsed .calendar-sidebar { padding-inline: 0; border: 0; }
  .create-button { width: 100%; min-height: 48px; display: flex; align-items: center; gap: 12px; padding: 0 18px; border: 0; border-radius: 10px; background: var(--accent); color: var(--accent-ink); font-weight: 750; box-shadow: var(--shadow-soft); }
  .create-button span { font-size: 24px; font-weight: 400; }
  .mini-calendar { margin-top: 22px; }
  .mini-calendar header { justify-content: space-between; margin-bottom: 12px; font-size: 12px; text-transform: capitalize; }
  .mini-calendar header button { width: 28px; height: 28px; padding: 0; font-size: 18px; }
  .mini-weekdays, .mini-grid { display: grid; grid-template-columns: repeat(7, 1fr); text-align: center; }
  .mini-weekdays { margin-bottom: 4px; color: var(--ink-faint); font-size: 9px; font-weight: 700; }
  .mini-grid button { aspect-ratio: 1; min-height: 26px; padding: 0; border-radius: 50%; font-size: 10px; }
  .mini-grid button:hover { background: var(--surface-subtle); }
  .mini-grid button.outside { color: var(--ink-soft); opacity: .78; }
  .mini-grid button.today { color: var(--accent-strong); font-weight: 800; }
  .mini-grid button.selected { background: var(--accent); color: var(--accent-ink); opacity: 1; }
  .calendar-list { margin-top: 24px; }
  .calendar-list header { justify-content: space-between; margin-bottom: 7px; }
  .calendar-list h2 { margin: 0; font-size: 13px; }
  .calendar-list header button { font-size: 18px; }
  .calendar-list label { min-height: 34px; display: grid; grid-template-columns: 16px 8px 1fr; align-items: center; gap: 8px; color: var(--ink-soft); font-size: 12px; cursor: pointer; }
  .calendar-list input { width: 15px; height: 15px; accent-color: var(--accent); }
  .backlog-list { margin-top: 22px; }
  .backlog-list header { justify-content: space-between; }
  .backlog-list h2 { margin: 0; font-size: 13px; }
  .backlog-list header span { min-width: 22px; padding: 2px 6px; border-radius: 999px; background: var(--surface-subtle); color: var(--ink-soft); font-size: 10px; text-align: center; }
  .backlog-list ul { max-height: 118px; overflow: auto; margin: 8px 0 0; padding: 0; list-style: none; }
  .backlog-list li { padding: 7px 0; border-bottom: 1px solid var(--rule); color: var(--ink-soft); font-size: 10px; line-height: 1.35; }
  .subject-color { width: 7px; height: 7px; border-radius: 50%; }
  .progress-link { width: 100%; min-height: 42px; display: flex; align-items: center; gap: 12px; margin-top: 22px; border: 0; border-radius: 7px; background: transparent; color: var(--ink); font-weight: 650; text-align: left; }
  .progress-link:hover { background: var(--surface-subtle); }
  .status-legend { margin-top: 30px; display: grid; gap: 7px; color: var(--ink-soft); font-size: 10px; }
  .status-legend p { margin: 0 0 3px; color: var(--ink-faint); font-weight: 700; text-transform: uppercase; letter-spacing: .05em; }
  .status-legend span { display: flex; align-items: center; gap: 8px; }
  .status-legend i { width: 8px; height: 8px; border-radius: 50%; background: #f2c94c; }
  .status-legend i.completed { background: #4fd19a; }
  .status-legend i.rescheduled { background: #a98cf3; }
  .data-actions { display: grid; gap: 4px; margin-top: 24px; padding-top: 12px; border-top: 1px solid var(--rule); }
  .data-actions button { min-height: 34px; padding: 0 8px; border: 0; border-radius: 6px; background: transparent; color: var(--ink-soft); font-size: 10px; text-align: left; }
  .data-actions button:hover { background: var(--surface-subtle); color: var(--ink); }
  .data-actions button.danger { background: var(--danger-surface); color: var(--danger-ink); }

  .calendar-main { position: relative; min-width: 0; overflow: hidden; background: var(--surface-elevated); }
  .week-head { height: 82px; display: grid; grid-template-columns: 62px repeat(7, minmax(86px, 1fr)); border-bottom: 1px solid var(--rule); background: var(--surface-elevated); }
  .timezone { display: flex; justify-content: center; align-items: end; padding-bottom: 9px; color: var(--ink-faint); font-size: 9px; }
  .week-head button { display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 5px; box-shadow: inset 1px 0 var(--rule); }
  .week-head button span { color: var(--ink-soft); font-size: 10px; text-transform: capitalize; }
  .week-head button strong { width: 36px; height: 36px; display: grid; place-items: center; border-radius: 50%; font-size: 19px; font-weight: 500; }
  .week-head button.today span { color: var(--accent-strong); font-weight: 750; }
  .week-head button.today strong { background: var(--accent); color: var(--accent-ink); }
  .week-scroll { height: calc(100% - 82px); position: relative; overflow: auto; padding-left: 62px; scrollbar-color: var(--rule-strong) transparent; }
  .time-axis { width: 62px; height: 100%; position: absolute; left: 0; top: 0; z-index: 2; background: var(--surface-elevated); }
  .time-axis span { width: 100%; position: absolute; transform: translateY(-6px); padding-right: 9px; color: var(--ink-faint); font-size: 10px; text-align: right; }
  .week-grid { min-width: 700px; display: grid; grid-template-columns: repeat(7, minmax(100px, 1fr)); background-image: repeating-linear-gradient(to bottom, var(--rule) 0 1px, transparent 1px 28px); }
  .day-lane { position: relative; background: transparent; box-shadow: inset 1px 0 var(--rule); }
  .day-lane.today { background: color-mix(in srgb, var(--accent) 3%, transparent); }
  .calendar-event { width: calc(100% - 7px); position: absolute; left: 3px; z-index: 3; overflow: hidden; display: flex; flex-direction: column; align-items: flex-start; padding: 6px 7px; border: 0; border-radius: 5px; color: #0f201a; text-align: left; cursor: grab; touch-action: none; box-shadow: inset 3px 0 color-mix(in srgb, currentColor 72%, black); }
  .calendar-event:active { cursor: grabbing; }
  .calendar-event.dragging { z-index: 8; opacity: .88; outline: 2px solid var(--focus); box-shadow: var(--shadow-raised); }
  .calendar-event.completed { opacity: .62; cursor: pointer; }
  .calendar-event.completed .event-title { text-decoration: line-through; }
  .calendar-event.rescheduled:not(.completed) { outline: 2px solid color-mix(in srgb, #a98cf3 72%, transparent); outline-offset: -2px; }
  .event-title { width: calc(100% - 14px); overflow: hidden; font-size: 11px; font-weight: 750; line-height: 1.25; text-overflow: ellipsis; white-space: nowrap; }
  .event-time { margin-top: 2px; font-size: 9px; line-height: 1.2; }
  .event-status { position: absolute; right: 5px; top: 4px; font-size: 12px; }
  .resize-handle { height: 7px; position: absolute; left: 6px; right: 6px; bottom: 0; cursor: ns-resize; }
  .resize-handle::after { content: ''; width: 28px; height: 2px; position: absolute; left: 50%; bottom: 2px; transform: translateX(-50%); border-radius: 2px; background: currentColor; opacity: .45; }
  .blue, .subject-color.blue { background: #5aa9e6; }
  .amber, .subject-color.amber { background: #f4bd4f; }
  .teal, .subject-color.teal { background: #4fc3b1; }
  .coral, .subject-color.coral { background: #ef7655; }
  .violet, .subject-color.violet { background: #9a7be5; color: #fff; }
  .rose, .subject-color.rose { background: #df6583; color: #fff; }
  .current-time { height: 1px; position: absolute; left: 0; right: 0; z-index: 7; background: var(--accent); pointer-events: none; }
  .current-time i { width: 8px; height: 8px; position: absolute; left: -4px; top: -4px; border-radius: 50%; background: var(--accent); }
  .saving-toast { position: absolute; left: 50%; bottom: 18px; z-index: 12; transform: translateX(-50%); padding: 9px 13px; border: 1px solid var(--rule); border-radius: 8px; background: var(--surface); box-shadow: var(--shadow-raised); font-size: 12px; }

  .month-view { height: 100%; overflow: auto; }
  .month-weekdays { height: 36px; display: grid; grid-template-columns: repeat(7, 1fr); align-items: center; border-bottom: 1px solid var(--rule); color: var(--ink-soft); font-size: 10px; text-align: center; }
  .month-grid { min-width: 760px; min-height: calc(100% - 36px); display: grid; grid-template-columns: repeat(7, 1fr); grid-template-rows: repeat(6, minmax(100px, 1fr)); }
  .month-grid > section { min-width: 0; padding: 6px; border-bottom: 1px solid var(--rule); box-shadow: inset -1px 0 var(--rule); }
  .month-grid > section.outside { opacity: .38; }
  .month-grid > section.today { background: color-mix(in srgb, var(--accent) 5%, transparent); }
  .month-grid section > button:first-child { width: 26px; height: 26px; margin: 0 auto 4px; display: block; border: 0; border-radius: 50%; background: transparent; color: var(--ink); }
  .month-grid section.today > button:first-child { background: var(--accent); color: var(--accent-ink); }
  .month-event { width: 100%; display: block; overflow: hidden; margin-bottom: 3px; padding: 3px 5px; border: 0; border-radius: 3px; color: #0f201a; font-size: 9px; text-align: left; text-overflow: ellipsis; white-space: nowrap; }
  .month-event.violet, .month-event.rose { color: #fff; }
  .more-events { color: var(--ink-soft); font-size: 9px; }

  .utility-area { min-width: 0; display: flex; background: var(--surface); box-shadow: inset 1px 0 var(--rule); }
  .utility-rail { width: 55px; flex: 0 0 55px; display: flex; flex-direction: column; gap: 9px; padding: 12px 7px; box-shadow: inset -1px 0 var(--rule); }
  .utility-rail button { min-height: 48px; display: grid; place-items: center; gap: 1px; padding: 5px 2px; border: 0; border-radius: 7px; background: transparent; color: var(--ink-soft); }
  .utility-rail button span { font-size: 17px; }
  .utility-rail button small { font-size: 8px; }
  .utility-rail button.active, .utility-rail button:hover { background: color-mix(in srgb, var(--accent) 15%, transparent); color: var(--accent-strong); }
  .ai-panel { width: 314px; overflow: auto; padding: 18px 16px; }
  .ai-panel header { justify-content: space-between; gap: 12px; }
  .ai-panel header > div { gap: 8px; }
  .ai-panel h2 { margin: 0; font-size: 17px; }
  .ai-panel header > div > span { color: var(--accent); font-size: 20px; }
  .ai-panel header button { font-size: 24px; }
  .ai-panel > p { margin: 8px 0 18px; color: var(--ink-soft); font-size: 11px; line-height: 1.5; }
  .ai-panel label { display: block; margin-bottom: 6px; color: var(--ink-soft); font-size: 11px; font-weight: 650; }
  .ai-panel textarea { width: 100%; resize: vertical; padding: 10px; border: 1px solid var(--rule-strong); border-radius: 7px; background: var(--surface-elevated); color: var(--ink); font: inherit; font-size: 12px; line-height: 1.45; }
  .ai-submit { width: 100%; min-height: 40px; margin-top: 9px; border: 0; border-radius: 7px; background: var(--accent); color: var(--accent-ink); font-weight: 750; }
  .ai-error { margin-top: 12px; padding: 9px; border: 1px solid var(--danger); border-radius: 7px; color: var(--danger-ink); font-size: 11px; }
  .ai-preview { margin-top: 16px; padding: 13px; border: 1px solid color-mix(in srgb, var(--accent) 55%, var(--rule)); border-radius: 9px; background: color-mix(in srgb, var(--accent) 6%, var(--surface-elevated)); }
  .preview-label { display: flex; justify-content: space-between; color: var(--accent-strong); font-size: 10px; font-weight: 750; text-transform: uppercase; }
  .preview-label small { color: var(--ink-faint); font-size: 8px; }
  .ai-preview h3 { margin: 8px 0 10px; font-size: 13px; }
  .time-comparison { display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 7px; }
  .time-comparison div { padding: 7px; border: 1px solid var(--rule); border-radius: 6px; }
  .time-comparison span { display: block; color: var(--ink-faint); font-size: 8px; }
  .time-comparison strong { display: block; margin-top: 2px; font-size: 9px; line-height: 1.35; }
  .ai-preview > p { max-height: 98px; overflow: auto; margin: 11px 0; color: var(--ink-soft); font-size: 10px; line-height: 1.45; }
  .preview-actions { gap: 7px; }
  .preview-actions button { flex: 1; min-height: 36px; border: 1px solid var(--rule-strong); border-radius: 6px; background: transparent; color: var(--ink); }
  .preview-actions button.apply { border-color: var(--accent); background: var(--accent); color: var(--accent-ink); }
  .ai-empty { min-height: 180px; display: grid; place-content: center; justify-items: center; color: var(--ink-faint); text-align: center; }
  .ai-empty span { color: var(--accent); font-size: 24px; }
  .ai-empty p { max-width: 220px; font-size: 11px; line-height: 1.5; }
  .sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; }

  @media (max-width: 1100px) {
    .calendar-toolbar { grid-template-columns: auto 1fr auto; }
    .calendar-brand strong, .search-box { display: none; }
    .calendar-body { grid-template-columns: 0 minmax(600px, 1fr) 56px; }
    .calendar-sidebar { padding-inline: 0; border: 0; }
    .calendar-body.ai-expanded { grid-template-columns: 0 minmax(520px, 1fr) 360px; }
  }

  @media (max-width: 760px) {
    .calendar-app { min-height: 620px; }
    .calendar-toolbar { height: auto; min-height: 58px; grid-template-columns: auto 1fr auto; padding: 8px; }
    .date-navigation .icon-button, .toolbar-actions .view-switch, .toolbar-actions .avatar { display: none; }
    .today-button { padding-inline: 9px; }
    .date-navigation h1 { margin-left: 4px; font-size: 15px; }
    .calendar-body, .calendar-body.ai-expanded { height: calc(100dvh - 58px); grid-template-columns: minmax(0, 1fr) 48px; }
    .calendar-sidebar { display: none; }
    .calendar-main { grid-column: 1; }
    .utility-area { grid-column: 2; }
    .utility-rail { width: 47px; flex-basis: 47px; padding-inline: 4px; }
    .ai-expanded .utility-area { width: min(92vw, 360px); position: fixed; z-index: 30; top: 58px; right: 0; bottom: 0; box-shadow: var(--shadow-dialog); }
    .ai-panel { width: calc(100% - 47px); }
    .week-head { grid-template-columns: 48px repeat(7, minmax(82px, 1fr)); overflow: hidden; }
    .week-scroll { padding-left: 48px; }
    .time-axis { width: 48px; }
    .week-grid { min-width: 700px; }
  }
</style>
