export const ACTIVITY_WINDOW_DAYS = 365;
export const ACTIVITY_WINDOW_OPTIONS = [7, 30, 365] as const;

export type AuraActivityWindowDays = (typeof ACTIVITY_WINDOW_OPTIONS)[number];

const DAY_MS = 86_400_000;

export interface AuraActivitySession {
  created_at?: string | null;
  source?: string | null;
}

export interface AuraActivityDay {
  date: string;
  count: number;
  bySource: Record<string, number>;
}

export interface AuraActivityResult {
  days: AuraActivityDay[];
  sources: Array<{ source: string; count: number }>;
  summary: {
    sessionCount: number;
    activeDays: number;
    currentStreak: number;
    longestStreak: number;
  };
}

export interface AuraActivityOptions {
  now?: Date;
  source?: string | null;
  windowDays?: AuraActivityWindowDays;
}

function utcDayMs(date: Date): number {
  return Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate());
}

function utcDateKey(dayMs: number): string {
  return new Date(dayMs).toISOString().slice(0, 10);
}

export function normalizeActivitySource(value?: string | null): string {
  const normalized = value?.trim();
  return normalized || 'unknown';
}

function lexicalCompare(left: string, right: string): number {
  return left < right ? -1 : left > right ? 1 : 0;
}

export function resolveActivityWindowDays(value: unknown): AuraActivityWindowDays {
  if (
    typeof value !== 'number' ||
    !Number.isFinite(value) ||
    !Number.isInteger(value) ||
    value <= 0 ||
    !ACTIVITY_WINDOW_OPTIONS.includes(value as AuraActivityWindowDays)
  ) {
    return ACTIVITY_WINDOW_DAYS;
  }
  return value as AuraActivityWindowDays;
}

export function buildAuraActivity(
  sessions: AuraActivitySession[],
  options: AuraActivityOptions = {},
): AuraActivityResult {
  const candidateNow = options.now ?? new Date();
  const safeNow = Number.isFinite(candidateNow.getTime()) ? candidateNow : new Date();
  const windowDays = resolveActivityWindowDays(options.windowDays);
  const todayMs = utcDayMs(safeNow);
  const startMs = todayMs - (windowDays - 1) * DAY_MS;
  const sourceFilter = options.source
    ? normalizeActivitySource(options.source)
    : null;

  const accepted: Array<{ dayMs: number; source: string }> = [];
  const sourceCounts = new Map<string, number>();

  for (const session of sessions) {
    if (!session.created_at) continue;
    const parsed = new Date(session.created_at);
    if (!Number.isFinite(parsed.getTime())) continue;
    if (parsed.getTime() > safeNow.getTime()) continue;
    const dayMs = utcDayMs(parsed);
    if (dayMs < startMs || dayMs > todayMs) continue;
    const source = normalizeActivitySource(session.source);
    accepted.push({ dayMs, source });
    sourceCounts.set(source, (sourceCounts.get(source) ?? 0) + 1);
  }

  const visible = sourceFilter
    ? accepted.filter((session) => session.source === sourceFilter)
    : accepted;
  const buckets = new Map<number, Record<string, number>>();
  for (const session of visible) {
    const bySource = buckets.get(session.dayMs) ?? {};
    bySource[session.source] = (bySource[session.source] ?? 0) + 1;
    buckets.set(session.dayMs, bySource);
  }

  const days: AuraActivityDay[] = [];
  for (let index = 0; index < windowDays; index += 1) {
    const dayMs = startMs + index * DAY_MS;
    const bySource = buckets.get(dayMs) ?? {};
    days.push({
      date: utcDateKey(dayMs),
      count: Object.values(bySource).reduce((total, count) => total + count, 0),
      bySource,
    });
  }

  let longestStreak = 0;
  let running = 0;
  for (const day of days) {
    running = day.count > 0 ? running + 1 : 0;
    longestStreak = Math.max(longestStreak, running);
  }

  let streakIndex = days.length - 1;
  if (days[streakIndex]?.count === 0) streakIndex -= 1;
  let currentStreak = 0;
  while (streakIndex >= 0 && days[streakIndex].count > 0) {
    currentStreak += 1;
    streakIndex -= 1;
  }

  return {
    days,
    sources: [...sourceCounts.entries()]
      .sort(
        ([leftName, leftCount], [rightName, rightCount]) =>
          rightCount - leftCount || lexicalCompare(leftName, rightName),
      )
      .map(([source, count]) => ({ source, count })),
    summary: {
      sessionCount: visible.length,
      activeDays: days.filter((day) => day.count > 0).length,
      currentStreak,
      longestStreak,
    },
  };
}
