import type {
  ActivityCategory,
  ActivitySource,
  ChangeType,
  Completion,
  Difficulty,
  MissReason,
  Recall,
  ReadinessStatus,
  RescheduleStatus,
  Strategy,
} from '../types'

export const supportedLocales = ['vi', 'en'] as const
export type Locale = (typeof supportedLocales)[number]

export interface TranslationArgs {
  'setup.progress': { current: number; total: number; step: string }
  'calendar.moreEvents': { count: number }
  'calendar.eventLabel': {
    title: string
    subject: string
    start: string
    end: string
    status: string
    review: string
  }
  'session.reviewNumber': { repetition: number }
  'plan.unscheduledCount': { count: number }
  'status.planGenerated': { sessions: number; unscheduled: number }
  'status.scheduleChanged': { changed: number; unscheduled: number }
  'duration.hoursMinutes': { hours: number; minutes: number }
  'duration.hours': { hours: number }
  'duration.minutes': { minutes: number }
}

export const translationKeys = [
  'app.skipToSchedule',
  'app.localTime',
  'app.privacy',
  'app.deleteData',
  'app.dismiss',
  'nav.createPlan',
  'nav.language',
  'nav.theme',
  'nav.schedule',
  'nav.progress',
  'onboarding.title',
  'onboarding.description',
  'onboarding.createPlan',
  'setup.progress',
  'setup.back',
  'setup.continue',
  'setup.generate',
  'setup.basics.title',
  'setup.materials.title',
  'setup.topics.title',
  'setup.availability.title',
  'setup.commitments.title',
  'setup.review.title',
  'calendar.today',
  'calendar.week',
  'calendar.month',
  'calendar.agenda',
  'calendar.previous',
  'calendar.next',
  'calendar.createSession',
  'calendar.filters',
  'calendar.showAll',
  'calendar.moreEvents',
  'calendar.eventLabel',
  'session.status.planned',
  'session.status.completed',
  'session.status.partial',
  'session.status.notCompleted',
  'session.review',
  'session.firstPass',
  'session.reviewNumber',
  'plan.unscheduled',
  'plan.unscheduledCount',
  'adaptation.noChange',
  'progress.title',
  'coach.title',
  'source.ai',
  'source.fallback',
  'status.planGenerated',
  'status.scheduleChanged',
  'duration.hoursMinutes',
  'duration.hours',
  'duration.minutes',
  'difficulty.easy',
  'difficulty.medium',
  'difficulty.hard',
  'recall.well',
  'recall.medium',
  'recall.poor',
  'strategy.fresh',
  'strategy.remaining',
  'strategy.examRush',
  'change.moved',
  'change.added',
  'change.kept',
  'change.blocked',
  'change.cancelled',
  'reason.club',
  'reason.exercise',
  'reason.social',
  'reason.rest',
  'reason.mood',
  'reason.emergency',
  'reason.work',
  'reason.illness',
  'reason.other',
  'activity.category.study',
  'activity.category.work',
  'activity.category.entertainment',
  'activity.category.illness',
  'activity.category.unexpected',
  'activity.category.rest',
  'activity.category.other',
  'activity.source.manual',
  'activity.source.studySession',
  'activity.source.cancelledSession',
  'readiness.insufficientData',
  'readiness.ready',
  'readiness.reduceLoad',
  'readiness.recovery',
  'reschedule.fullSlot',
  'reschedule.noFullSlot',
  'reschedule.needsLimitApproval',
  'reschedule.scheduled',
  'reschedule.backlog',
] as const

export type TranslationKey = (typeof translationKeys)[number]
export type Message<K extends TranslationKey> = K extends keyof TranslationArgs
  ? (args: TranslationArgs[K]) => string
  : string
export type Catalog = { [K in TranslationKey]: Message<K> }

export type EnumTranslationMap<T extends string> = Readonly<Record<T, TranslationKey>>

export const enumTranslationKeys = {
  completion: {
    planned: 'session.status.planned',
    completed: 'session.status.completed',
    partial: 'session.status.partial',
    not_completed: 'session.status.notCompleted',
  },
  difficulty: {
    easy: 'difficulty.easy',
    medium: 'difficulty.medium',
    hard: 'difficulty.hard',
  },
  recall: {
    well: 'recall.well',
    medium: 'recall.medium',
    poor: 'recall.poor',
  },
  strategy: {
    fresh: 'strategy.fresh',
    remaining: 'strategy.remaining',
    exam_rush: 'strategy.examRush',
  },
  changeType: {
    moved: 'change.moved',
    added: 'change.added',
    kept: 'change.kept',
    blocked: 'change.blocked',
    cancelled: 'change.cancelled',
  },
  missReason: {
    club: 'reason.club',
    exercise: 'reason.exercise',
    social: 'reason.social',
    rest: 'reason.rest',
    mood: 'reason.mood',
    emergency: 'reason.emergency',
    work: 'reason.work',
    illness: 'reason.illness',
    other: 'reason.other',
  },
  activityCategory: {
    study: 'activity.category.study',
    work: 'activity.category.work',
    entertainment: 'activity.category.entertainment',
    illness: 'activity.category.illness',
    unexpected: 'activity.category.unexpected',
    rest: 'activity.category.rest',
    other: 'activity.category.other',
  },
  activitySource: {
    manual: 'activity.source.manual',
    study_session: 'activity.source.studySession',
    cancelled_session: 'activity.source.cancelledSession',
  },
  readiness: {
    insufficient_data: 'readiness.insufficientData',
    ready: 'readiness.ready',
    reduce_load: 'readiness.reduceLoad',
    recovery: 'readiness.recovery',
  },
  rescheduleStatus: {
    full_slot: 'reschedule.fullSlot',
    no_full_slot: 'reschedule.noFullSlot',
    needs_limit_approval: 'reschedule.needsLimitApproval',
    scheduled: 'reschedule.scheduled',
    backlog: 'reschedule.backlog',
  },
} as const satisfies {
  completion: EnumTranslationMap<Completion>
  difficulty: EnumTranslationMap<Difficulty>
  recall: EnumTranslationMap<Recall>
  strategy: EnumTranslationMap<Strategy>
  changeType: EnumTranslationMap<ChangeType>
  missReason: EnumTranslationMap<MissReason>
  activityCategory: EnumTranslationMap<ActivityCategory>
  activitySource: EnumTranslationMap<ActivitySource>
  readiness: EnumTranslationMap<ReadinessStatus>
  rescheduleStatus: EnumTranslationMap<RescheduleStatus>
}

export type EnumGroup = keyof typeof enumTranslationKeys
export type EnumValue<G extends EnumGroup> = keyof (typeof enumTranslationKeys)[G] & string

export const localeNames = {
  vi: 'Tiếng Việt',
  en: 'English',
} as const satisfies Record<Locale, string>
