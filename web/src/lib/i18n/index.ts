import { readable, writable, type Readable } from 'svelte/store'
import { en } from './en'
import {
  enumTranslationKeys,
  supportedLocales,
  type Catalog,
  type EnumGroup,
  type EnumValue,
  type Locale,
  type TranslationArgs,
  type TranslationKey,
} from './keys'
import { vi } from './vi'

export * from './keys'
export { en, vi }

export const LOCALE_STORAGE_KEY = 'studygrid-locale'
export type DateValue = Date | string | number
export type TranslationArguments<K extends TranslationKey> =
  K extends keyof TranslationArgs ? [TranslationArgs[K]] : []

export interface LocaleEnvironment {
  storedLocale?: string | null
  browserLanguages?: readonly string[]
}

export interface I18n {
  readonly locale: Locale
  t<K extends TranslationKey>(key: K, ...args: TranslationArguments<K>): string
  date(value: DateValue, options?: Intl.DateTimeFormatOptions): string
  time(value: DateValue, options?: Intl.DateTimeFormatOptions): string
  dateTime(value: DateValue, options?: Intl.DateTimeFormatOptions): string
  number(value: number, options?: Intl.NumberFormatOptions): string
  plural(value: number, options?: Intl.PluralRulesOptions): Intl.LDMLPluralRule
  duration(minutes: number): string
  timezone(): string
  enumLabel<G extends EnumGroup>(group: G, value: EnumValue<G>, fallback?: string): string
}

const catalogs = { en, vi } as const satisfies Record<Locale, Catalog>

export function isLocale(value: unknown): value is Locale {
  return typeof value === 'string' && (supportedLocales as readonly string[]).includes(value)
}

export function baseLocale(value: string): Locale | null {
  const base = value.trim().toLowerCase().split(/[-_]/, 1)[0]
  return isLocale(base) ? base : null
}

export function resolveLocale({
  storedLocale = null,
  browserLanguages = [],
}: LocaleEnvironment = {}): Locale {
  if (isLocale(storedLocale)) return storedLocale
  for (const language of browserLanguages) {
    const locale = baseLocale(language)
    if (locale) return locale
  }
  return 'vi'
}

function parseDate(value: DateValue): Date {
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) throw new RangeError(`Invalid date value: ${String(value)}`)
  return date
}

function normalizeMinutes(value: number): number {
  if (!Number.isFinite(value)) throw new RangeError('Duration must be a finite number of minutes.')
  return Math.max(0, Math.round(value))
}

function formatMessage<K extends TranslationKey>(
  catalog: Catalog,
  key: K,
  args: TranslationArguments<K>,
): string {
  const message = catalog[key]
  return typeof message === 'function'
    ? (message as (value: TranslationArgs[keyof TranslationArgs]) => string)(args[0] as never)
    : message
}

export function createI18n(locale: Locale): I18n {
  const catalog = catalogs[locale]
  const numberFormat = new Intl.NumberFormat(locale)
  const pluralRules = new Intl.PluralRules(locale)

  return {
    locale,
    t: <K extends TranslationKey>(key: K, ...args: TranslationArguments<K>) =>
      formatMessage(catalog, key, args),
    date: (value, options = {}) =>
      new Intl.DateTimeFormat(locale, { dateStyle: 'medium', ...options }).format(parseDate(value)),
    time: (value, options = {}) =>
      new Intl.DateTimeFormat(locale, { hour: '2-digit', minute: '2-digit', ...options }).format(parseDate(value)),
    dateTime: (value, options = {}) =>
      new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short', ...options }).format(parseDate(value)),
    number: (value, options) => options
      ? new Intl.NumberFormat(locale, options).format(value)
      : numberFormat.format(value),
    plural: (value, options) => options
      ? new Intl.PluralRules(locale, options).select(value)
      : pluralRules.select(value),
    duration: (value) => {
      const minutes = normalizeMinutes(value)
      const hours = Math.floor(minutes / 60)
      const remainder = minutes % 60
      if (hours && remainder) return formatMessage(catalog, 'duration.hoursMinutes', [{ hours, minutes: remainder }])
      if (hours) return formatMessage(catalog, 'duration.hours', [{ hours }])
      return formatMessage(catalog, 'duration.minutes', [{ minutes: remainder }])
    },
    timezone: () => Intl.DateTimeFormat(locale).resolvedOptions().timeZone || formatMessage(catalog, 'app.localTime', []),
    enumLabel: <G extends EnumGroup>(group: G, value: EnumValue<G>, fallback?: string) => {
      const key = (enumTranslationKeys[group] as Record<string, TranslationKey>)[value]
      return key ? formatMessage(catalog, key, []) : (fallback ?? value)
    },
  }
}

function browserEnvironment(): LocaleEnvironment {
  if (typeof window === 'undefined') return {}
  let storedLocale: string | null = null
  try {
    storedLocale = window.localStorage.getItem(LOCALE_STORAGE_KEY)
  } catch {
    // Storage may be unavailable in privacy-restricted browser contexts.
  }
  const browserLanguages = window.navigator.languages?.length
    ? window.navigator.languages
    : [window.navigator.language]
  return { storedLocale, browserLanguages }
}

function applyLocale(locale: Locale): void {
  if (typeof document !== 'undefined') document.documentElement.lang = locale
  if (typeof window !== 'undefined') {
    try {
      window.localStorage.setItem(LOCALE_STORAGE_KEY, locale)
    } catch {
      // The active in-memory locale remains usable if persistence is blocked.
    }
  }
}

const initialLocale = resolveLocale(browserEnvironment())
const localeState = writable<Locale>(initialLocale)
applyLocale(initialLocale)

export const locale: Readable<Locale> = readable(initialLocale, (set) =>
  localeState.subscribe(set),
)
export const i18n: Readable<I18n> = readable(createI18n(initialLocale), (set) =>
  localeState.subscribe((value) => set(createI18n(value))),
)

export function setLocale(nextLocale: Locale): void {
  if (!isLocale(nextLocale)) return
  applyLocale(nextLocale)
  localeState.set(nextLocale)
}
