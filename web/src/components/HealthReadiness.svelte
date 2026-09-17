<script lang="ts">
  import {
    ApiError,
    applyHealthSchedule,
    createHealthPairing,
    deleteHealthConnection,
    getHealthDashboard,
    saveHealthCheckIn,
    setHealthSyncPaused,
  } from '../lib/api'
  import type {
    DailyHealthSummary,
    HealthDashboard,
    HealthPairingResponse,
    ReadinessStatus,
  } from '../lib/types'

  let {
    planId,
    days,
    onChanged,
  }: {
    planId: string
    days: 7 | 30
    onChanged: () => void | Promise<void>
  } = $props()

  let dashboard = $state<HealthDashboard | null>(null)
  let pairing = $state<HealthPairingResponse | null>(null)
  let loading = $state(true)
  let busy = $state(false)
  let error = $state<string | null>(null)
  let notice = $state<string | null>(null)
  let applyArmed = $state(false)
  let deleteArmed = $state(false)
  let energy = $state(3)
  let feelsUnwell = $state(false)

  const summaries = $derived(dashboard?.summaries ?? [])
  const maxSleep = $derived(Math.max(480, ...summaries.map((item) => item.sleep_minutes ?? 0)))
  const heartRates = $derived(summaries.filter((item) => item.resting_heart_rate_bpm !== null))
  const minHeartRate = $derived(Math.min(55, ...heartRates.map((item) => item.resting_heart_rate_bpm ?? 55)))
  const maxHeartRate = $derived(Math.max(75, ...heartRates.map((item) => item.resting_heart_rate_bpm ?? 75)))
  const canApply = $derived(
    dashboard?.recommendations.some((item) => item.kind === 'shorten_move') ?? false,
  )

  $effect(() => {
    planId
    days
    void load()
  })

  function today(): string {
    const now = new Date()
    return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10)
  }

  function statusCopy(status: ReadinessStatus): { label: string; detail: string } {
    return {
      insufficient_data: {
        label: 'Chưa đủ dữ liệu',
        detail: 'Đồng bộ thêm dữ liệu để tạo mức nền cá nhân.',
      },
      ready: {
        label: 'Sẵn sàng',
        detail: 'Có thể theo khối lượng đã lên lịch.',
      },
      reduce_load: {
        label: 'Giảm tải',
        detail: 'Nên rút gọn các khối linh hoạt và giữ việc khẩn cấp.',
      },
      recovery: {
        label: 'Phục hồi',
        detail: 'Ưu tiên nghỉ và chỉ giữ công việc quan trọng nhất.',
      },
    }[status]
  }

  function formatMinutes(value: number | null): string {
    if (value === null) return '—'
    const hours = Math.floor(value / 60)
    const minutes = value % 60
    return minutes ? `${hours}g ${minutes}p` : `${hours}g`
  }

  function formatDate(value: string, compact = false): string {
    return new Intl.DateTimeFormat('vi-VN', compact
      ? { day: '2-digit', month: '2-digit' }
      : { weekday: 'short', day: '2-digit', month: '2-digit' })
      .format(new Date(`${value}T12:00:00`))
  }

  function formatSync(value: string | null): string {
    if (!value) return 'Chưa đồng bộ'
    return new Intl.DateTimeFormat('vi-VN', {
      day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
    }).format(new Date(value))
  }

  function heartHeight(summary: DailyHealthSummary): number {
    if (summary.resting_heart_rate_bpm === null) return 0
    const range = Math.max(1, maxHeartRate - minHeartRate)
    return 24 + ((summary.resting_heart_rate_bpm - minHeartRate) / range) * 68
  }

  async function load() {
    loading = true
    error = null
    try {
      dashboard = await getHealthDashboard(planId, days, today())
    } catch (reason) {
      error = reason instanceof ApiError ? reason.message : 'Không thể tải dữ liệu sức khỏe.'
    } finally {
      loading = false
    }
  }

  async function startPairing() {
    busy = true
    error = null
    notice = null
    try {
      pairing = await createHealthPairing(planId)
      notice = 'Nhập mã này trong ứng dụng StudyGrid Companion trên Android.'
    } catch (reason) {
      error = reason instanceof ApiError ? reason.message : 'Không thể tạo mã ghép nối.'
    } finally {
      busy = false
    }
  }

  async function saveCheckIn() {
    busy = true
    error = null
    try {
      dashboard = await saveHealthCheckIn(planId, today(), energy, feelsUnwell)
      notice = 'Đã lưu check-in hôm nay.'
      await onChanged()
    } catch (reason) {
      error = reason instanceof ApiError ? reason.message : 'Không thể lưu check-in.'
    } finally {
      busy = false
    }
  }

  async function toggleSync() {
    if (!dashboard?.connection) return
    busy = true
    error = null
    try {
      const paused = dashboard.connection.status === 'connected'
      dashboard = await setHealthSyncPaused(planId, paused)
      notice = paused ? 'Đã tạm dừng đồng bộ.' : 'Đã tiếp tục đồng bộ.'
      await onChanged()
    } catch (reason) {
      error = reason instanceof ApiError ? reason.message : 'Không thể đổi trạng thái đồng bộ.'
    } finally {
      busy = false
    }
  }

  async function disconnect() {
    if (!deleteArmed) {
      deleteArmed = true
      return
    }
    busy = true
    error = null
    try {
      await deleteHealthConnection(planId)
      pairing = null
      deleteArmed = false
      notice = 'Đã ngắt kết nối và xóa dữ liệu sức khỏe đã lưu.'
      await load()
      await onChanged()
    } catch (reason) {
      error = reason instanceof ApiError ? reason.message : 'Không thể ngắt kết nối.'
    } finally {
      busy = false
    }
  }

  async function applyRecommendation() {
    if (!applyArmed) {
      applyArmed = true
      return
    }
    busy = true
    error = null
    try {
      const result = await applyHealthSchedule(planId, today())
      applyArmed = false
      notice = result.changes.length
        ? `Đã áp dụng ${result.changes.length} thay đổi. Deadline và việc ưu tiên vẫn được giữ.`
        : 'Không có khối linh hoạt nào cần thay đổi.'
      await load()
      await onChanged()
    } catch (reason) {
      error = reason instanceof ApiError ? reason.message : 'Không thể áp dụng đề xuất.'
    } finally {
      busy = false
    }
  }
</script>

<section class="health-section" aria-labelledby="health-heading">
  <header class="health-heading">
    <div>
      <p class="eyebrow">Sức khỏe &amp; năng lượng</p>
      <h3 id="health-heading">Mức sẵn sàng hôm nay</h3>
      <p>Giấc ngủ và nhịp tim chỉ điều chỉnh khối linh hoạt; deadline và ưu tiên vẫn là ràng buộc cứng.</p>
    </div>
    {#if dashboard}
      {@const copy = statusCopy(dashboard.readiness.status)}
      <div class={`readiness-badge ${dashboard.readiness.status}`}>
        <span>{copy.label}</span>
        <strong>{dashboard.readiness.capacity_percent}%</strong>
      </div>
    {/if}
  </header>

  {#if error}<div class="health-error" role="alert">{error}</div>{/if}
  {#if notice}<p class="health-notice" role="status">{notice}</p>{/if}

  {#if loading && !dashboard}
    <div class="health-skeleton" aria-label="Đang tải dữ liệu sức khỏe" aria-busy="true"><span></span><span></span><span></span></div>
  {:else if dashboard}
    <div class="readiness-grid">
      <article class={`readiness-card ${dashboard.readiness.status}`}>
        <div class="readiness-main">
          <div class="readiness-ring" style={`--value:${dashboard.readiness.capacity_percent * 3.6}deg`}>
            <strong>{dashboard.readiness.capacity_percent}</strong><span>% tải</span>
          </div>
          <div>
            <h4>{statusCopy(dashboard.readiness.status).label}</h4>
            <p>{statusCopy(dashboard.readiness.status).detail}</p>
            <small>Độ tin cậy: {dashboard.readiness.confidence} · nền {dashboard.readiness.baseline_days}/{dashboard.policy.baseline_days} ngày</small>
          </div>
        </div>
        <ul class="factor-list">
          {#each dashboard.readiness.factors as factor (factor.key)}
            <li class={factor.impact}><i aria-hidden="true"></i><div><strong>{factor.label}</strong><span>{factor.detail}</span></div></li>
          {/each}
        </ul>
        <p class="disclaimer">{dashboard.readiness.disclaimer}</p>
      </article>

      <article class="connection-card">
        {#if dashboard.connection}
          <div class="connection-head">
            <span class="health-connect-mark" aria-hidden="true">H+</span>
            <div><h4>Health Connect</h4><p>{dashboard.connection.status === 'connected' ? 'Đang kết nối' : 'Đã tạm dừng'}</p></div>
            <i class:paused={dashboard.connection.status === 'paused'} aria-hidden="true"></i>
          </div>
          <dl>
            <div><dt>Lần đồng bộ cuối</dt><dd>{formatSync(dashboard.connection.last_synced_at)}</dd></div>
            <div><dt>Nguồn</dt><dd>{dashboard.connection.sources.join(', ') || 'Thiết bị Android'}</dd></div>
            <div><dt>Lưu trữ</dt><dd>{dashboard.policy.retention_days} ngày tổng hợp</dd></div>
          </dl>
          <div class="connection-actions">
            <button type="button" disabled={busy} onclick={toggleSync}>{dashboard.connection.status === 'connected' ? 'Tạm dừng' : 'Tiếp tục'}</button>
            <button type="button" class:danger={deleteArmed} disabled={busy} onclick={disconnect}>{deleteArmed ? 'Xác nhận xóa' : 'Ngắt kết nối'}</button>
          </div>
        {:else}
          <div class="connection-empty">
            <span class="health-connect-mark" aria-hidden="true">H+</span>
            <div><h4>Kết nối điện thoại Android</h4><p>Đồng bộ giấc ngủ, nhịp tim nghỉ và HRV từ Health Connect. StudyGrid không lưu mẫu nhịp tim thô.</p></div>
          </div>
          {#if pairing}
            <div class="pairing-code" aria-live="polite"><span>Mã ghép nối</span><strong>{pairing.code}</strong><small>Hết hạn {formatSync(pairing.expires_at)}</small></div>
          {/if}
          <button type="button" class="connect-button" disabled={busy} onclick={startPairing}>{busy ? 'Đang tạo mã…' : pairing ? 'Tạo mã mới' : 'Kết nối Health Connect'}</button>
        {/if}
      </article>
    </div>

    {#if summaries.length}
      <div class="health-charts">
        <article class="metric-chart">
          <header><div><span>Giấc ngủ</span><strong>{formatMinutes(summaries.at(-1)?.sleep_minutes ?? null)}</strong></div><small>Nền {formatMinutes(dashboard.readiness.sleep_baseline_minutes === null ? null : Math.round(dashboard.readiness.sleep_baseline_minutes))}</small></header>
          <div class="metric-bars" style={`--columns:${summaries.length}`} role="img" aria-label="Biểu đồ thời lượng ngủ theo ngày">
            {#each summaries as summary (summary.occurred_on)}
              <div title={`${formatDate(summary.occurred_on)}: ${formatMinutes(summary.sleep_minutes)}`}><i style={`height:${((summary.sleep_minutes ?? 0) / maxSleep) * 100}%`}></i><span>{formatDate(summary.occurred_on, true)}</span></div>
            {/each}
          </div>
        </article>
        <article class="metric-chart heart">
          <header><div><span>Nhịp tim nghỉ</span><strong>{summaries.at(-1)?.resting_heart_rate_bpm?.toFixed(0) ?? '—'} bpm</strong></div><small>Nền {dashboard.readiness.resting_hr_baseline_bpm?.toFixed(0) ?? '—'} bpm</small></header>
          <div class="metric-bars" style={`--columns:${summaries.length}`} role="img" aria-label="Biểu đồ nhịp tim nghỉ theo ngày">
            {#each summaries as summary (summary.occurred_on)}
              <div title={`${formatDate(summary.occurred_on)}: ${summary.resting_heart_rate_bpm?.toFixed(0) ?? 'không có'} bpm`}><i style={`height:${heartHeight(summary)}%`}></i><span>{formatDate(summary.occurred_on, true)}</span></div>
            {/each}
          </div>
        </article>
      </div>
    {/if}

    <div class="health-actions-grid">
      <article class="recommendations-card">
        <header><div><span>Đề xuất lịch hôm nay</span><small>Xem trước, không tự áp dụng</small></div></header>
        <ul>
          {#each dashboard.recommendations as item (item.id)}
            <li class:protected={item.protected}><i aria-hidden="true">{item.protected ? '◆' : item.kind === 'shorten_move' ? '↗' : '·'}</i><div><strong>{item.title}</strong><span>{item.detail}</span></div></li>
          {/each}
        </ul>
        {#if canApply}
          <div class="apply-row">
            <p>{applyArmed ? 'Xác nhận: các phần linh hoạt sẽ được dời sang khung trống trước deadline.' : 'Bạn luôn xem trước và xác nhận trước khi lịch thay đổi.'}</p>
            <button type="button" class:confirm={applyArmed} disabled={busy} onclick={applyRecommendation}>{busy ? 'Đang áp dụng…' : applyArmed ? 'Xác nhận áp dụng' : 'Áp dụng giảm tải'}</button>
          </div>
        {/if}
        {#if dashboard.adjustments.length}
          <details class="adjustment-history">
            <summary>Thay đổi sức khỏe gần đây ({dashboard.adjustments.length})</summary>
            <ul>
              {#each dashboard.adjustments.slice(0, 4) as adjustment (adjustment.id)}
                <li><i aria-hidden="true">✓</i><div><strong>{formatDate(adjustment.occurred_on)} · {statusCopy(adjustment.readiness_status).label}</strong><span>{adjustment.changes.length} thay đổi được ghi vào Tiến độ lúc {formatSync(adjustment.applied_at)}</span></div></li>
              {/each}
            </ul>
          </details>
        {/if}
      </article>

      <form class="checkin-card" onsubmit={(event) => { event.preventDefault(); void saveCheckIn() }}>
        <header><span>Check-in nhanh</span><small>Bổ sung cảm nhận của bạn</small></header>
        <label for="energy-level">Năng lượng hôm nay <strong>{energy}/5</strong></label>
        <input id="energy-level" type="range" min="1" max="5" step="1" bind:value={energy} />
        <label class="unwell"><input type="checkbox" bind:checked={feelsUnwell} /><span>Tôi cảm thấy không khỏe</span></label>
        <button type="submit" disabled={busy}>{busy ? 'Đang lưu…' : 'Lưu check-in'}</button>
      </form>
    </div>
  {/if}
</section>

<style>
  .health-section { margin-bottom: 22px; }
  .health-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 14px; }
  .health-heading h3 { margin: 0; font-size: 22px; }
  .health-heading > div:first-child > p:last-child { max-width: 72ch; margin: 5px 0 0; color: var(--ink-soft); font-size: 12px; }
  .eyebrow { margin: 0 0 4px; color: var(--accent-strong); font-size: 11px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
  .readiness-badge { min-width: 128px; display: flex; align-items: center; justify-content: space-between; gap: 14px; padding: 9px 12px; border: 1px solid var(--rule-strong); border-radius: 10px; background: var(--surface-elevated); }
  .readiness-badge span { font-size: 11px; font-weight: 700; }
  .readiness-badge strong { font-size: 18px; font-variant-numeric: tabular-nums; }
  .readiness-badge.ready strong, .ready .readiness-ring strong { color: var(--success); }
  .readiness-badge.reduce_load strong, .reduce_load .readiness-ring strong { color: var(--activity-unexpected); }
  .readiness-badge.recovery strong, .recovery .readiness-ring strong { color: var(--danger); }
  .readiness-badge.insufficient_data strong { color: var(--ink-faint); }
  .health-error, .health-notice { margin: 0 0 12px; padding: 10px 12px; border-radius: 8px; font-size: 12px; }
  .health-error { background: var(--danger-surface); color: var(--danger-ink); }
  .health-notice { border: 1px solid color-mix(in srgb, var(--accent-strong) 32%, var(--rule)); background: color-mix(in srgb, var(--accent-strong) 7%, var(--surface)); }
  .readiness-grid, .health-charts, .health-actions-grid { display: grid; gap: 14px; }
  .readiness-grid { grid-template-columns: minmax(0, 1.55fr) minmax(280px, .65fr); }
  .health-charts { grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: 14px; }
  .health-actions-grid { grid-template-columns: minmax(0, 1.4fr) minmax(260px, .6fr); margin-top: 14px; }
  .readiness-card, .connection-card, .metric-chart, .recommendations-card, .checkin-card { min-width: 0; border: 1px solid var(--rule); border-radius: 12px; background: var(--surface); padding: 18px; }
  .readiness-card { box-shadow: inset 3px 0 var(--ink-faint); }
  .readiness-card.ready { box-shadow: inset 3px 0 var(--success); }
  .readiness-card.reduce_load { box-shadow: inset 3px 0 var(--activity-unexpected); }
  .readiness-card.recovery { box-shadow: inset 3px 0 var(--danger); }
  .readiness-main { display: flex; align-items: center; gap: 18px; }
  .readiness-main h4, .connection-card h4 { margin: 0; font-size: 17px; }
  .readiness-main p, .connection-card p { margin: 5px 0; color: var(--ink-soft); font-size: 12px; line-height: 1.5; }
  .readiness-main small, .metric-chart small, .recommendations-card small, .checkin-card small { color: var(--ink-faint); font-size: 10px; }
  .readiness-ring { width: 78px; aspect-ratio: 1; flex: 0 0 auto; display: grid; place-content: center; border-radius: 50%; background: radial-gradient(circle closest-side, var(--surface) 77%, transparent 78% 99%), conic-gradient(var(--accent-strong) var(--value), var(--rule) 0); text-align: center; }
  .readiness-ring strong { font-size: 22px; line-height: 1; }
  .readiness-ring span { margin-top: 3px; color: var(--ink-faint); font-size: 9px; }
  .factor-list, .recommendations-card ul { list-style: none; margin: 16px 0 0; padding: 0; }
  .factor-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 7px; }
  .factor-list li, .recommendations-card li { display: flex; align-items: flex-start; gap: 9px; }
  .factor-list li { padding: 9px; border: 1px solid var(--rule); border-radius: 8px; background: var(--surface-subtle); }
  .factor-list i { width: 7px; height: 7px; flex: 0 0 auto; margin-top: 4px; border-radius: 50%; background: var(--ink-faint); }
  .factor-list .positive i { background: var(--success); }
  .factor-list .negative i { background: var(--danger); }
  .factor-list div, .recommendations-card li div { display: flex; min-width: 0; flex-direction: column; }
  .factor-list strong, .recommendations-card li strong { font-size: 11px; }
  .factor-list span, .recommendations-card li span { color: var(--ink-soft); font-size: 10px; line-height: 1.45; }
  .disclaimer { margin: 13px 0 0; color: var(--ink-faint); font-size: 9px; }
  .connection-head, .connection-empty { display: flex; align-items: flex-start; gap: 11px; }
  .connection-head > i { width: 8px; height: 8px; margin: 7px 0 0 auto; border-radius: 50%; background: var(--success); }
  .connection-head > i.paused { background: var(--activity-unexpected); }
  .health-connect-mark { width: 34px; height: 34px; display: grid; flex: 0 0 auto; place-content: center; border-radius: 9px; background: color-mix(in srgb, var(--accent-strong) 18%, var(--surface)); color: var(--accent-strong); font-size: 12px; font-weight: 900; }
  .connection-card dl { margin: 16px 0; }
  .connection-card dl div { display: flex; justify-content: space-between; gap: 12px; padding: 7px 0; border-bottom: 1px solid var(--rule); font-size: 10px; }
  .connection-card dt { color: var(--ink-faint); }
  .connection-card dd { margin: 0; text-align: right; }
  .connection-actions { display: flex; gap: 7px; }
  .connection-actions button, .connect-button { min-height: 36px; flex: 1; font-size: 11px; }
  .connection-actions .danger { border-color: var(--danger); color: var(--danger); }
  .connection-empty { margin-bottom: 16px; }
  .pairing-code { display: grid; place-items: center; margin: 12px 0; padding: 12px; border: 1px dashed var(--accent-strong); border-radius: 9px; background: var(--surface-subtle); }
  .pairing-code span, .pairing-code small { color: var(--ink-faint); font-size: 9px; }
  .pairing-code strong { margin: 3px 0; color: var(--accent-strong); font-size: 23px; letter-spacing: .12em; }
  .metric-chart header, .recommendations-card header, .checkin-card header { display: flex; align-items: flex-end; justify-content: space-between; gap: 10px; }
  .metric-chart header div { display: flex; flex-direction: column; }
  .metric-chart header span, .recommendations-card header span, .checkin-card header span { color: var(--ink-soft); font-size: 11px; }
  .metric-chart header strong { margin-top: 3px; font-size: 18px; }
  .metric-bars { height: 140px; display: grid; grid-template-columns: repeat(var(--columns), minmax(8px, 1fr)); gap: 5px; align-items: end; margin-top: 14px; padding: 10px 3px 0; border-bottom: 1px solid var(--rule-strong); background: linear-gradient(var(--rule), var(--rule)) 0 35% / 100% 1px no-repeat, linear-gradient(var(--rule), var(--rule)) 0 70% / 100% 1px no-repeat; }
  .metric-bars > div { height: 130px; display: grid; grid-template-rows: 108px 22px; align-items: end; }
  .metric-bars i { width: min(22px, 80%); min-height: 2px; justify-self: center; border-radius: 4px 4px 1px 1px; background: var(--accent-strong); opacity: .78; }
  .heart .metric-bars i { background: var(--activity-unexpected); }
  .metric-bars span { overflow: hidden; padding-top: 5px; color: var(--ink-faint); font-size: 8px; text-align: center; text-overflow: ellipsis; white-space: nowrap; }
  .recommendations-card li { padding: 10px 0; border-bottom: 1px solid var(--rule); }
  .recommendations-card li > i { width: 18px; flex: 0 0 auto; color: var(--accent-strong); font-style: normal; text-align: center; }
  .recommendations-card li.protected > i { color: var(--activity-unexpected); }
  .apply-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 14px; }
  .apply-row p { max-width: 52ch; margin: 0; color: var(--ink-soft); font-size: 10px; }
  .apply-row button { white-space: nowrap; }
  .apply-row button.confirm { border-color: var(--activity-unexpected); background: var(--activity-unexpected); color: #18120a; }
  .adjustment-history { margin-top: 13px; padding-top: 12px; border-top: 1px solid var(--rule); }
  .adjustment-history summary { color: var(--ink-soft); font-size: 10px; cursor: pointer; }
  .adjustment-history ul { margin-top: 6px; }
  .checkin-card { display: flex; flex-direction: column; gap: 13px; }
  .checkin-card > label:not(.unwell) { display: flex; justify-content: space-between; color: var(--ink-soft); font-size: 11px; }
  .checkin-card input[type='range'] { width: 100%; accent-color: var(--accent-strong); }
  .unwell { display: flex; align-items: center; gap: 8px; color: var(--ink-soft); font-size: 11px; }
  .unwell input { accent-color: var(--danger); }
  .checkin-card button { margin-top: auto; }
  .health-skeleton { display: grid; grid-template-columns: 1.5fr .7fr; gap: 14px; }
  .health-skeleton span { min-height: 220px; border-radius: 12px; background: var(--surface-subtle); }
  .health-skeleton span:last-child { display: none; }
  @media (max-width: 900px) { .readiness-grid, .health-charts, .health-actions-grid { grid-template-columns: 1fr; } }
  @media (max-width: 600px) { .health-heading { align-items: stretch; flex-direction: column; } .readiness-badge { width: 100%; } .readiness-main { align-items: flex-start; } .factor-list { grid-template-columns: 1fr; } .apply-row { align-items: stretch; flex-direction: column; } }
</style>
