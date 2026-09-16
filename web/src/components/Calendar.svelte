<script lang="ts">
  // Schedule-X v4 expects Temporal.ZonedDateTime. The backend sends naive local
  // ISO strings, so the browser timezone is attached here — the single place in
  // the app that deals with timezones.
  import 'temporal-polyfill/global'
  import { createCalendar, createViewWeek, createViewMonthGrid } from '@schedule-x/calendar'
  import '@schedule-x/theme-default/dist/index.css'
  import type { CalendarEvent } from '../lib/types'

  let { events, onSelect }: { events: CalendarEvent[]; onSelect: (id: string) => void } = $props()

  const TZ = Intl.DateTimeFormat().resolvedOptions().timeZone

  function toZoned(iso: string) {
    return Temporal.PlainDateTime.from(iso).toZonedDateTime(TZ)
  }

  function cssClass(e: CalendarEvent): string {
    if (e.completion === 'completed' && e.recall !== 'poor') return 'sg-done'
    if (e.recall === 'poor' || e.completion === 'not_completed') return 'sg-flag'
    return e.is_review ? 'sg-review' : 'sg-learn'
  }

  function toSxEvents(list: CalendarEvent[]) {
    return list.map((e) => ({
      id: e.id,
      title: e.title,
      start: toZoned(e.start),
      end: toZoned(e.end),
      _options: { additionalClasses: [cssClass(e)] },
    }))
  }

  let host: HTMLDivElement
  let calendar: ReturnType<typeof createCalendar> | null = null

  $effect(() => {
    // Depend on events so the calendar rebuilds when the plan adapts.
    const sxEvents = toSxEvents(events)

    if (!calendar) {
      calendar = createCalendar({
        views: [createViewWeek(), createViewMonthGrid()],
        defaultView: 'week',
        events: sxEvents,
        callbacks: {
          onEventClick: (event) => onSelect(String(event.id)),
        },
      })
      calendar.render(host)
    } else {
      calendar.events.set(sxEvents)
    }
  })

  $effect(() => {
    return () => {
      calendar?.destroy?.()
      calendar = null
    }
  })
</script>

<div class="calendar" bind:this={host}></div>

<style>
  .calendar {
    height: 640px;
    max-width: 100%;
    overflow-x: auto;
  }

  @media (max-width: 600px) {
    .calendar {
      height: 560px;
    }
  }
</style>
