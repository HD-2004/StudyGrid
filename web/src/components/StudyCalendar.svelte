<script lang="ts">
  import { onDestroy, onMount } from 'svelte'
  import {
    createCalendar,
    createViewDay,
    createViewMonthGrid,
    createViewWeek,
    type CalendarApp,
  } from '@schedule-x/calendar'
  import { createEventsServicePlugin } from '@schedule-x/events-service'
  import '@schedule-x/theme-default/dist/index.css'
  import 'temporal-polyfill/global'
  import type { CalendarEvent } from '../lib/types'

  export let events: CalendarEvent[] = []
  export let theme: 'light' | 'dark' = 'light'
  export let onSelect: (eventId: string) => void

  let host: HTMLDivElement
  let app: CalendarApp | null = null
  let mounted = false
  const eventsService = createEventsServicePlugin()

  function selectedDate() {
    const value = events[0]?.start.slice(0, 10) || new Date().toISOString().slice(0, 10)
    return Temporal.PlainDate.from(value)
  }

  function toCalendarEvent(event: CalendarEvent) {
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
    return {
      ...event,
      start: Temporal.PlainDateTime.from(event.start).toZonedDateTime(timezone),
      end: Temporal.PlainDateTime.from(event.end).toZonedDateTime(timezone),
      calendarId: event.completion === 'completed' ? 'completed' : event.is_review ? 'review' : 'study',
      _options: { disableDND: true, disableResize: true },
    }
  }

  onMount(() => {
    app = createCalendar(
      {
        views: [createViewWeek(), createViewDay(), createViewMonthGrid()],
        defaultView: 'week',
        selectedDate: selectedDate(),
        timezone: (Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC') as never,
        locale: navigator.language || 'en-US',
        firstDayOfWeek: 1,
        dayBoundaries: { start: '07:00', end: '23:00' },
        weekOptions: { gridStep: 30 },
        events: events.map(toCalendarEvent),
        isDark: theme === 'dark',
        calendars: {
          study: {
            colorName: 'study',
            lightColors: { main: '#0b57d0', container: '#d3e3fd', onContainer: '#041e49' },
            darkColors: { main: '#a8c7fa', container: '#0842a0', onContainer: '#d3e3fd' },
          },
          review: {
            colorName: 'review',
            lightColors: { main: '#5e5e72', container: '#e2e2f9', onContainer: '#1a1b2c' },
            darkColors: { main: '#c6c5dc', container: '#45455a', onContainer: '#e2e2f9' },
          },
          completed: {
            colorName: 'completed',
            lightColors: { main: '#747775', container: '#e3e3e3', onContainer: '#444746' },
            darkColors: { main: '#a9aca9', container: '#444746', onContainer: '#e3e3e3' },
          },
        },
        callbacks: {
          onEventClick: (event) => onSelect(String(event.id)),
        },
      },
      [eventsService],
    )
    app.render(host)
    mounted = true
  })

  $: if (mounted) {
    eventsService.set(events.map(toCalendarEvent))
  }

  $: if (mounted && app) {
    app.setTheme(theme)
  }

  onDestroy(() => {
    app?.destroy()
  })
</script>

<div class="calendar-frame" aria-label="Study plan calendar" bind:this={host}></div>
