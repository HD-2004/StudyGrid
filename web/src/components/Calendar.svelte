<script lang="ts">
  // Schedule-X v4 expects Temporal.ZonedDateTime. The backend sends naive local
  // ISO strings, so the browser timezone is attached here — the single place in
  // the app that deals with timezones.
  import 'temporal-polyfill/global'
  import { createCalendar, createViewWeek, createViewMonthGrid } from '@schedule-x/calendar'
  import '@schedule-x/theme-default/dist/index.css'
  import type { CalendarEvent } from '../lib/types'

  let {
    events,
    theme,
    onSelect,
  }: {
    events: CalendarEvent[]
    theme: 'light' | 'dark'
    onSelect: (id: string) => void
  } = $props()

  const TZ = Intl.DateTimeFormat().resolvedOptions().timeZone

  function toZoned(iso: string) {
    return Temporal.PlainDateTime.from(iso).toZonedDateTime(TZ)
  }

  function cssClass(e: CalendarEvent): string {
    if (e.completion === 'completed' && e.recall !== 'poor') return 'sg-done'
    if (e.recall === 'poor' || e.completion === 'not_completed') return 'sg-flag'
    return e.is_review ? 'sg-review' : 'sg-learn'
  }

  function calendarId(e: CalendarEvent): string {
    return cssClass(e).replace('sg-', '')
  }

  function toSxEvents(list: CalendarEvent[]) {
    return list.map((e) => ({
      id: e.id,
      title: e.title,
      start: toZoned(e.start),
      end: toZoned(e.end),
      calendarId: calendarId(e),
      _options: { additionalClasses: [cssClass(e)] },
    }))
  }

  let host: HTMLDivElement
  let calendar: ReturnType<typeof createCalendar> | null = null
  let observer: MutationObserver | null = null

  function normalizeCalendarAccessibility() {
    host.querySelectorAll<HTMLElement>('.sx__date-grid[aria-label]').forEach((element) => {
      element.setAttribute('role', 'group')
    })
    host.querySelectorAll<HTMLElement>('.sx__time-grid-day[aria-label]').forEach((element) => {
      element.setAttribute('role', 'group')
    })
    host.querySelectorAll<HTMLElement>('.sx__view-container').forEach((element) => {
      element.tabIndex = 0
      if (!element.hasAttribute('aria-label')) {
        element.setAttribute('aria-label', 'Scrollable calendar view')
      }
    })
  }

  $effect(() => {
    // Depend on events so the calendar rebuilds when the plan adapts.
    const sxEvents = toSxEvents(events)

    if (!calendar) {
      calendar = createCalendar({
        views: [createViewWeek(), createViewMonthGrid()],
        defaultView: 'week',
        selectedDate: Temporal.PlainDate.from(
          events[0]?.start.slice(0, 10) ?? new Date().toISOString().slice(0, 10),
        ),
        timezone: TZ,
        locale: navigator.language || 'en-US',
        firstDayOfWeek: 1,
        dayBoundaries: { start: '08:00', end: '23:00' },
        weekOptions: { gridStep: 30 },
        isDark: theme === 'dark',
        calendars: {
          learn: {
            colorName: 'learn',
            lightColors: { main: '#176b58', container: '#d9eee6', onContainer: '#0d4033' },
            darkColors: { main: '#4fc39b', container: '#163c31', onContainer: '#d9f7eb' },
          },
          review: {
            colorName: 'review',
            lightColors: { main: '#53638c', container: '#e1e5f1', onContainer: '#25304f' },
            darkColors: { main: '#9aa8df', container: '#2e3657', onContainer: '#edf0ff' },
          },
          done: {
            colorName: 'done',
            lightColors: { main: '#84928d', container: '#edf1ef', onContainer: '#52615c' },
            darkColors: { main: '#778983', container: '#24322e', onContainer: '#b5c4bf' },
          },
          flag: {
            colorName: 'flag',
            lightColors: { main: '#a55a28', container: '#f6e6d9', onContainer: '#703813' },
            darkColors: { main: '#e09b62', container: '#4b2d1c', onContainer: '#ffddc2' },
          },
        },
        events: sxEvents,
        callbacks: {
          onEventClick: (event) => onSelect(String(event.id)),
        },
      })
      calendar.render(host)
      observer = new MutationObserver(normalizeCalendarAccessibility)
      observer.observe(host, { childList: true, subtree: true })
      queueMicrotask(normalizeCalendarAccessibility)
    } else {
      calendar.events.set(sxEvents)
    }
  })

  $effect(() => {
    calendar?.setTheme(theme)
  })

  $effect(() => {
    return () => {
      observer?.disconnect()
      observer = null
      calendar?.destroy?.()
      calendar = null
    }
  })
</script>

<div class="calendar" aria-label="Study plan calendar" bind:this={host}></div>

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
