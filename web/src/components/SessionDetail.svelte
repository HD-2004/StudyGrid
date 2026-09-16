<script lang="ts">
  import type { CalendarEvent, Completion, MissReason, Recall, ReasonOption } from '../lib/types'

  let {
    event,
    busy,
    reasons,
    onSubmit,
    onMove,
    onDelete,
    onClose,
  }: {
    event: CalendarEvent
    busy: boolean
    reasons: ReasonOption[]
    onSubmit: (completion: Completion, recall: Recall | null, missReason: MissReason | null) => void
    onMove: (start: string, end: string, subject: string, topic: string) => Promise<void>
    onDelete: () => void
    onClose: () => void
  } = $props()

  let mode = $state<'pending' | 'completed' | 'cancel'>('pending')
  let recall = $state<Recall>('medium')
  let missReason = $state<MissReason | null>(null)
  let subject = $state('')
  let topic = $state('')
  let start = $state('')
  let end = $state('')
  let initialized = false
  let savingTime = $state(false)
  let timeError = $state<string | null>(null)
  let deleteArmed = $state(false)

  $effect(() => {
    if (!initialized) {
      subject = event.subject
      topic = event.topic
      start = toInput(event.start)
      end = toInput(event.end)
      initialized = true
    }
  })

  function toInput(iso: string): string {
    return iso.slice(0, 16)
  }

  function when(iso: string): string {
    return new Date(iso).toLocaleString('vi-VN', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  async function saveDetails() {
    savingTime = true
    timeError = null
    try {
      await onMove(start, end, subject.trim(), topic.trim())
    } catch (reason) {
      timeError = reason instanceof Error ? reason.message : 'Không thể lưu thay đổi.'
    } finally {
      savingTime = false
    }
  }
</script>

<section class="session-detail" aria-labelledby="session-title">
  <header>
    <div class="title-block">
      <span class="status-dot" class:done={event.completion === 'completed'} aria-hidden="true"></span>
      <div>
        <h2 id="session-title">{event.topic}</h2>
        <p>{event.subject} · {when(event.start)}</p>
      </div>
    </div>
    <button class="icon-close" type="button" aria-label="Đóng chi tiết công việc" onclick={onClose}>×</button>
  </header>

  <div class="edit-grid">
    <label for="detail-topic">Công việc</label>
    <input id="detail-topic" type="text" maxlength="200" required bind:value={topic} />
    <label for="detail-subject">Lịch / nhóm</label>
    <input id="detail-subject" type="text" maxlength="120" required bind:value={subject} />
    <div class="time-fields">
      <div><label for="detail-start">Bắt đầu</label><input id="detail-start" type="datetime-local" required bind:value={start} /></div>
      <div><label for="detail-end">Kết thúc</label><input id="detail-end" type="datetime-local" required bind:value={end} /></div>
    </div>
    {#if timeError}<p class="inline-error" role="alert">{timeError}</p>{/if}
    <button class="save-details" type="button" disabled={busy || savingTime || event.completion !== 'planned'} onclick={saveDetails}>
      {savingTime ? 'Đang lưu…' : 'Lưu nội dung & thời gian'}
    </button>
  </div>

  <div class="status-section">
    <span class="field-label">Trạng thái công việc</span>
    <div class="status-actions" role="group" aria-label="Cập nhật trạng thái">
      <button type="button" class:active={mode === 'pending'} class="pending" aria-pressed={mode === 'pending'} onclick={() => (mode = 'pending')}><i aria-hidden="true"></i>Pending</button>
      <button type="button" class:active={mode === 'completed'} class="completed" aria-pressed={mode === 'completed'} onclick={() => (mode = 'completed')}><i aria-hidden="true">✓</i>Completed</button>
      <button type="button" class:active={mode === 'cancel'} class="cancel" aria-pressed={mode === 'cancel'} onclick={() => (mode = 'cancel')}><i aria-hidden="true">×</i>Cancel</button>
    </div>
  </div>

  {#if mode === 'completed'}
    <div class="outcome-panel">
      <label for="recall">Bạn nhớ nội dung ở mức nào?</label>
      <select id="recall" bind:value={recall}>
        <option value="well">Tốt — nhớ phần lớn</option>
        <option value="medium">Trung bình — nhớ khoảng một nửa</option>
        <option value="poor">Cần ôn lại — nhớ rất ít</option>
      </select>
      <button type="button" class="confirm completed-confirm" disabled={busy} onclick={() => onSubmit('completed', recall, null)}>{busy ? 'Đang cập nhật…' : 'Xác nhận hoàn thành'}</button>
      <p>Tiến độ và thời gian học sẽ được cập nhật vào Dashboard.</p>
    </div>
  {:else if mode === 'cancel'}
    <div class="outcome-panel cancel-panel">
      <span class="field-label" id="reason-label">Vì sao bạn hủy công việc này?</span>
      <div class="reasons" role="group" aria-labelledby="reason-label">
        {#each reasons as option (option.value)}
          <button type="button" class:selected={missReason === option.value} aria-pressed={missReason === option.value} onclick={() => (missReason = option.value)}>{option.label}</button>
        {/each}
      </div>
      <div class="reschedule-note"><span aria-hidden="true">↻</span><div><strong>Tự động tìm lịch mới</strong><p>StudyGrid sẽ dời công việc đến slot trống tiếp theo và lưu lý do vào Dashboard.</p></div></div>
      <button type="button" class="confirm cancel-confirm" disabled={busy || !missReason} onclick={() => onSubmit('not_completed', null, missReason)}>{busy ? 'Đang tìm lịch…' : 'Xác nhận & dời lịch'}</button>
    </div>
  {:else}
    <p class="pending-note">Công việc đang chờ thực hiện. Bạn có thể kéo khung trên lịch hoặc sửa thời gian trực tiếp tại đây.</p>
  {/if}

  <footer>
    <span>{event.rationale}</span>
    <button type="button" class:armed={deleteArmed} disabled={busy} onclick={() => {
      if (deleteArmed) onDelete()
      else deleteArmed = true
    }} onblur={() => (deleteArmed = false)}>{deleteArmed ? 'Xác nhận xóa' : 'Xóa'}</button>
  </footer>
</section>

<style>
  .session-detail { width: min(390px, calc(100vw - 28px)); max-height: calc(100dvh - 100px); overflow: auto; padding: 18px; border: 1px solid var(--rule-strong); border-radius: 10px; background: var(--surface); box-shadow: var(--shadow-raised); color: var(--ink); }
  header, .title-block, .status-actions, .reschedule-note, footer { display: flex; align-items: center; }
  header { justify-content: space-between; gap: 16px; margin-bottom: 16px; }
  .title-block { min-width: 0; gap: 10px; }
  .title-block > div { min-width: 0; }
  .status-dot { width: 10px; height: 10px; flex: 0 0 auto; border-radius: 50%; background: #f2c94c; }
  .status-dot.done { background: var(--success); }
  h2 { overflow: hidden; margin: 0; font-size: 16px; text-overflow: ellipsis; white-space: nowrap; }
  header p { margin: 3px 0 0; color: var(--ink-soft); font-size: 10px; }
  .icon-close { width: 32px; height: 32px; padding: 0; border: 0; border-radius: 50%; background: transparent; color: var(--ink); font-size: 22px; }
  .icon-close:hover { background: var(--surface-subtle); }
  .edit-grid { padding-bottom: 14px; border-bottom: 1px solid var(--rule); }
  label, .field-label { display: block; margin: 9px 0 5px; color: var(--ink-soft); font-size: 10px; font-weight: 650; }
  input, select { width: 100%; min-height: 38px; padding: 7px 9px; border: 1px solid var(--rule); border-radius: 6px; background: var(--surface-elevated); color: var(--ink); font: inherit; font-size: 11px; }
  .time-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  .save-details { width: 100%; min-height: 36px; margin-top: 9px; border: 1px solid var(--rule-strong); border-radius: 6px; background: transparent; color: var(--ink); font-size: 11px; font-weight: 650; }
  .inline-error { margin: 8px 0 0; color: var(--danger-ink); font-size: 10px; }
  .status-section { padding: 13px 0; border-bottom: 1px solid var(--rule); }
  .status-section .field-label { margin-top: 0; }
  .status-actions { gap: 6px; }
  .status-actions button { min-width: 0; flex: 1; min-height: 38px; display: flex; justify-content: center; align-items: center; gap: 5px; padding: 0 7px; border: 1px solid var(--rule-strong); border-radius: 6px; background: transparent; color: var(--ink-soft); font-size: 10px; }
  .status-actions i { width: 13px; height: 13px; display: grid; place-items: center; border-radius: 50%; font-size: 10px; font-style: normal; }
  .status-actions .pending i { background: #f2c94c; }
  .status-actions .completed i { background: var(--success); color: #092119; }
  .status-actions .cancel i { background: var(--danger); color: #fff; }
  .status-actions button.active { border-color: var(--accent); background: color-mix(in srgb, var(--accent) 11%, transparent); color: var(--ink); }
  .status-actions button.cancel.active { border-color: var(--danger); }
  .outcome-panel { padding: 13px 0; }
  .outcome-panel > label:first-child { margin-top: 0; }
  .confirm { width: 100%; min-height: 40px; margin-top: 11px; border: 0; border-radius: 6px; font-weight: 750; }
  .completed-confirm { background: var(--accent); color: var(--accent-ink); }
  .cancel-confirm { background: var(--danger); color: #fff; }
  .confirm:disabled { opacity: .5; }
  .outcome-panel > p, .pending-note { margin: 9px 0 0; color: var(--ink-soft); font-size: 10px; line-height: 1.45; }
  .reasons { display: flex; flex-wrap: wrap; gap: 5px; }
  .reasons button { min-height: 32px; padding: 4px 8px; border: 1px solid var(--rule-strong); border-radius: 6px; background: transparent; color: var(--ink-soft); font-size: 9px; }
  .reasons button.selected { border-color: var(--danger); background: var(--danger-surface); color: var(--danger-ink); }
  .reschedule-note { align-items: flex-start; gap: 8px; margin-top: 11px; padding: 9px; border: 1px solid var(--rule); border-radius: 6px; background: var(--surface-subtle); }
  .reschedule-note > span { color: var(--accent-strong); font-size: 18px; }
  .reschedule-note strong { font-size: 10px; }
  .reschedule-note p { margin: 2px 0 0; color: var(--ink-soft); font-size: 9px; line-height: 1.4; }
  .pending-note { padding: 12px 0; }
  footer { justify-content: space-between; gap: 12px; padding-top: 12px; border-top: 1px solid var(--rule); }
  footer span { max-width: 250px; color: var(--ink-faint); font-size: 9px; line-height: 1.35; }
  footer button { min-height: 32px; padding: 0 10px; border: 1px solid var(--rule); border-radius: 6px; background: transparent; color: var(--danger-ink); font-size: 10px; }
  footer button.armed { border-color: var(--danger); background: var(--danger-surface); }
  @media (max-width: 520px) { .session-detail { max-height: 76dvh; border-radius: 12px 12px 0 0; } .time-fields { grid-template-columns: 1fr; } }
</style>
