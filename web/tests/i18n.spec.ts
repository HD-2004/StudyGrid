import { expect, test } from '@playwright/test'
import {
  LOCALE_STORAGE_KEY,
  en,
  resolveLocale,
  setLocale,
  supportedLocales,
  translationKeys,
  vi,
  type Catalog,
  type Locale,
  type TranslationKey,
} from '../src/lib/i18n'

const PROPERTY_SEED = 0x5eeda11
const LOCALE_CASES = 384
const CATALOG_ARGUMENT_CASES = 32

function seeded(seed: number): () => number {
  let state = seed >>> 0
  return () => {
    state = (state + 0x6d2b79f5) >>> 0
    let value = state
    value = Math.imul(value ^ (value >>> 15), value | 1)
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61)
    return ((value ^ (value >>> 14)) >>> 0) / 0x1_0000_0000
  }
}

function pick<T>(random: () => number, values: readonly T[]): T {
  return values[Math.floor(random() * values.length)]
}

function generatedText(random: () => number): string {
  const parts = ['', ' ', 'en', 'vi', 'EN', 'vi-VN', 'fr-FR', 'zh-Hant', 'tiếng Việt', 'English label ', '_', '-']
  const length = Math.floor(random() * 5)
  return Array.from({ length }, () => pick(random, parts)).join('')
}

const argumentKeys = new Set<TranslationKey>([
  'setup.progress', 'calendar.moreEvents', 'calendar.eventLabel', 'session.reviewNumber',
  'plan.unscheduledCount', 'status.planGenerated', 'status.scheduleChanged',
  'duration.hoursMinutes', 'duration.hours', 'duration.minutes',
])
function validArguments(key: TranslationKey, random: () => number): unknown[] {
  const count = () => Math.floor(random() * 10_001)
  const label = () => `${generatedText(random)}Nhãn học tập ${count()}`
  switch (key) {
    case 'setup.progress': return [{ current: count(), total: count(), step: label() }]
    case 'calendar.moreEvents': return [{ count: count() }]
    case 'calendar.eventLabel': return [{
      title: label(), subject: label(), start: label(), end: label(), status: label(), review: label(),
    }]
    case 'session.reviewNumber': return [{ repetition: count() }]
    case 'plan.unscheduledCount': return [{ count: count() }]
    case 'status.planGenerated': return [{ sessions: count(), unscheduled: count() }]
    case 'status.scheduleChanged': return [{ changed: count(), unscheduled: count() }]
    case 'duration.hoursMinutes': return [{ hours: count(), minutes: count() % 60 }]
    case 'duration.hours': return [{ hours: count() }]
    case 'duration.minutes': return [{ minutes: count() }]
    default: return []
  }
}

function render(catalog: Catalog, key: TranslationKey, args: unknown[]): string {
  const message = catalog[key]
  return typeof message === 'function'
    ? (message as (value: never) => string)(args[0] as never)
    : message
}

test('Property 1: Locale totality and precedence', async () => {
  // **Validates: Requirements 1.1**
  const random = seeded(PROPERTY_SEED)
  const storedCandidates = [null, undefined, '', ' ', 'en', 'vi', 'EN', 'VI', 'en-US', 'vi_VN', 'fr', 'invalid'] as const
  const browserCandidates = ['', ' ', 'en', 'vi', 'EN-us', 'vi-VN', 'fr-FR', 'zh-Hant', 'de_DE', 'invalid'] as const

  for (let index = 0; index < LOCALE_CASES; index += 1) {
    const storedLocale = random() < 0.65 ? pick(random, storedCandidates) : generatedText(random)
    const browserLanguages = Array.from(
      { length: Math.floor(random() * 7) },
      () => random() < 0.75 ? pick(random, browserCandidates) : generatedText(random),
    )
    const resolved = resolveLocale({ storedLocale, browserLanguages })
    const expectedStored = supportedLocales.find((locale) => storedLocale === locale)
    const expectedBrowser = browserLanguages
      .map((language) => language.trim().toLowerCase().split(/[-_]/, 1)[0])
      .find((language): language is Locale => supportedLocales.includes(language as Locale))

    expect(supportedLocales, `case ${index}: ${JSON.stringify({ storedLocale, browserLanguages })}`).toContain(resolved)
    expect(resolved, `case ${index}: ${JSON.stringify({ storedLocale, browserLanguages })}`).toBe(
      expectedStored ?? expectedBrowser ?? 'vi',
    )
  }
})

test('Property 2: Catalog parity', async () => {
  // **Validates: Requirements 1.2**
  const random = seeded(PROPERTY_SEED ^ 0xca7a109)
  const expectedKeys = [...translationKeys].sort()

  for (const [locale, catalog] of Object.entries({ en, vi }) as [Locale, Catalog][]) {
    expect(Object.keys(catalog).sort(), `${locale} catalog must have exact key parity`).toEqual(expectedKeys)
    for (const key of translationKeys) {
      const message = catalog[key]
      expect(typeof message, `${locale}.${key} has the required value shape`).toBe(argumentKeys.has(key) ? 'function' : 'string')
      const cases = typeof message === 'function' ? CATALOG_ARGUMENT_CASES : 1
      for (let index = 0; index < cases; index += 1) {
        const output = render(catalog, key, validArguments(key, random))
        expect(typeof output, `${locale}.${key} case ${index}`).toBe('string')
        expect(output, `${locale}.${key} case ${index}`).not.toBe('')
        expect(output, `${locale}.${key} case ${index}`).not.toContain('undefined')
        expect(output, `${locale}.${key} case ${index}`).not.toMatch(/missing[-_ ]?key/i)
        expect(output, `${locale}.${key} case ${index}`).not.toBe(key)
      }
    }
  }
})
test('Property 3: Locale round trip', async ({ page }) => {
  // **Validates: Requirements 1.3**
  await page.goto('/')

  for (const selectedLocale of supportedLocales) {
    await page.evaluate(async ({ locale, storageKey }) => {
      localStorage.removeItem(storageKey)
      const module = await import('/src/lib/i18n/index.ts')
      module.setLocale(locale)
    }, { locale: selectedLocale, storageKey: LOCALE_STORAGE_KEY })

    await expect.poll(() => page.evaluate(() => document.documentElement.lang)).toBe(selectedLocale)
    expect(await page.evaluate((storageKey) => localStorage.getItem(storageKey), LOCALE_STORAGE_KEY)).toBe(selectedLocale)

    await page.reload()
    const restored = await page.evaluate(async ({ locale, storageKey }) => {
      const module = await import(`/src/lib/i18n/index.ts?roundtrip=${locale}`)
      return {
        persisted: localStorage.getItem(storageKey),
        resolved: module.resolveLocale({
          storedLocale: localStorage.getItem(storageKey),
          browserLanguages: navigator.languages,
        }),
        documentLanguage: document.documentElement.lang,
      }
    }, { locale: selectedLocale, storageKey: LOCALE_STORAGE_KEY })

    expect(restored).toEqual({
      persisted: selectedLocale,
      resolved: selectedLocale,
      documentLanguage: selectedLocale,
    })
  }
})
