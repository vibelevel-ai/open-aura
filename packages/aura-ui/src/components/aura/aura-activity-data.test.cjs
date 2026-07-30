const assert = require('node:assert/strict');
const fs = require('node:fs');
const Module = require('node:module');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');

function loadProductionModule() {
  const filename = path.join(__dirname, 'aura-activity-data.ts');
  const source = fs.readFileSync(filename, 'utf8');
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      esModuleInterop: true,
    },
    fileName: filename,
  }).outputText;
  const loaded = new Module(filename, module);
  loaded.filename = filename;
  loaded.paths = Module._nodeModulePaths(path.dirname(filename));
  loaded._compile(output, filename);
  return loaded.exports;
}

const NOW = new Date('2026-07-25T12:00:00Z');

function session(created_at, source = 'codex') {
  return { created_at, source };
}

test('empty collection returns exactly 365 UTC dates ending today', () => {
  const { buildAuraActivity } = loadProductionModule();
  const result = buildAuraActivity([], { now: NOW });
  assert.equal(result.days.length, 365);
  assert.equal(result.days.at(-1).date, '2026-07-25');
  assert.equal(result.days[0].date, '2025-07-26');
  assert.deepEqual(result.summary, {
    sessionCount: 0,
    activeDays: 0,
    currentStreak: 0,
    longestStreak: 0,
  });
});

test('one valid session is counted on its UTC date', () => {
  const { buildAuraActivity } = loadProductionModule();
  const result = buildAuraActivity([session('2026-07-25T08:00:00Z')], { now: NOW });
  assert.equal(result.days.at(-1).count, 1);
  assert.equal(result.summary.activeDays, 1);
});

test('multiple sessions on one day share one active date', () => {
  const { buildAuraActivity } = loadProductionModule();
  const result = buildAuraActivity(
    [
      session('2026-07-24T01:00:00Z'),
      session('2026-07-24T22:00:00Z'),
      session('2026-07-24T23:59:59Z'),
    ],
    { now: NOW },
  );
  assert.equal(result.days.find((day) => day.date === '2026-07-24').count, 3);
  assert.equal(result.summary.sessionCount, 3);
  assert.equal(result.summary.activeDays, 1);
});

test('activity today continues the current streak', () => {
  const { buildAuraActivity } = loadProductionModule();
  const result = buildAuraActivity(
    [
      session('2026-07-23T10:00:00Z'),
      session('2026-07-24T10:00:00Z'),
      session('2026-07-25T10:00:00Z'),
    ],
    { now: NOW },
  );
  assert.equal(result.summary.currentStreak, 3);
  assert.equal(result.summary.longestStreak, 3);
});

test('activity yesterday continues the current streak when today is empty', () => {
  const { buildAuraActivity } = loadProductionModule();
  const result = buildAuraActivity(
    [session('2026-07-23T10:00:00Z'), session('2026-07-24T10:00:00Z')],
    { now: NOW },
  );
  assert.equal(result.summary.currentStreak, 2);
});

test('stale activity has current streak zero while retaining longest streak', () => {
  const { buildAuraActivity } = loadProductionModule();
  const result = buildAuraActivity(
    [
      session('2026-06-01T10:00:00Z'),
      session('2026-06-02T10:00:00Z'),
      session('2026-06-04T10:00:00Z'),
    ],
    { now: NOW },
  );
  assert.equal(result.summary.currentStreak, 0);
  assert.equal(result.summary.longestStreak, 2);
});

test('invalid and out-of-range timestamps are excluded', () => {
  const { buildAuraActivity } = loadProductionModule();
  const result = buildAuraActivity(
    [session('broken'), session('2025-07-25T23:59:59Z'), session('')],
    { now: NOW },
  );
  assert.equal(result.summary.sessionCount, 0);
});

test('future timestamps are rejected before same-day UTC bucketing', () => {
  const { buildAuraActivity } = loadProductionModule();
  const result = buildAuraActivity(
    [
      session('2026-07-25T10:00:00Z'),
      session('2026-07-25T23:00:00Z'),
      session('2026-07-26T01:00:00Z'),
    ],
    { now: NOW },
  );
  assert.equal(result.summary.sessionCount, 1);
  assert.equal(result.days.at(-1).count, 1);
});

test('missing empty and whitespace sources normalize to unknown and filter', () => {
  const { buildAuraActivity } = loadProductionModule();
  const sessions = [
    { created_at: '2026-07-25T08:00:00Z' },
    session('2026-07-25T09:00:00Z', ''),
    session('2026-07-25T10:00:00Z', '   '),
    session('2026-07-25T11:00:00Z', 'custom-agent'),
  ];
  const all = buildAuraActivity(sessions, { now: NOW });
  assert.deepEqual(all.sources, [
    { source: 'unknown', count: 3 },
    { source: 'custom-agent', count: 1 },
  ]);
  const unknown = buildAuraActivity(sessions, { now: NOW, source: 'unknown' });
  assert.equal(unknown.summary.sessionCount, 3);
});

test('equal source counts use locale-independent lexical ordering', () => {
  const { buildAuraActivity } = loadProductionModule();
  const result = buildAuraActivity(
    [
      session('2026-07-25T08:00:00Z', 'zeta'),
      session('2026-07-25T09:00:00Z', 'Alpha'),
      session('2026-07-25T10:00:00Z', 'beta'),
    ],
    { now: NOW },
  );
  assert.deepEqual(result.sources.map((item) => item.source), ['Alpha', 'beta', 'zeta']);
});

test('consecutive activity crosses month and year boundaries', () => {
  const { buildAuraActivity } = loadProductionModule();
  const result = buildAuraActivity(
    [
      session('2025-12-31T20:00:00Z'),
      session('2026-01-01T01:00:00Z'),
      session('2026-01-02T01:00:00Z'),
    ],
    { now: new Date('2026-01-02T12:00:00Z') },
  );
  assert.equal(result.summary.currentStreak, 3);
  assert.equal(result.summary.longestStreak, 3);
});

test('leap day is represented as a stable UTC date', () => {
  const { buildAuraActivity } = loadProductionModule();
  const result = buildAuraActivity(
    [
      session('2024-02-28T23:00:00Z'),
      session('2024-02-29T12:00:00Z'),
      session('2024-03-01T01:00:00Z'),
    ],
    { now: new Date('2024-03-01T12:00:00Z') },
  );
  assert.equal(result.days.find((day) => day.date === '2024-02-29').count, 1);
  assert.equal(result.summary.currentStreak, 3);
});

test('supported timeline windows include their first UTC day and today', () => {
  const { buildAuraActivity } = loadProductionModule();
  const cases = [
    { windowDays: 7, firstDay: '2026-07-19', beforeFirstDay: '2026-07-18' },
    { windowDays: 30, firstDay: '2026-06-26', beforeFirstDay: '2026-06-25' },
    { windowDays: 365, firstDay: '2025-07-26', beforeFirstDay: '2025-07-25' },
  ];

  for (const { windowDays, firstDay, beforeFirstDay } of cases) {
    const result = buildAuraActivity(
      [
        session(`${beforeFirstDay}T23:59:59Z`),
        session(`${firstDay}T00:00:00Z`),
        session('2026-07-25T11:59:59Z'),
        session('2026-07-25T12:00:01Z'),
        session('2026-07-26T00:00:00Z'),
      ],
      { now: NOW, windowDays },
    );

    assert.equal(result.days.length, windowDays);
    assert.equal(result.days[0].date, firstDay);
    assert.equal(result.days[0].count, 1);
    assert.equal(result.days.at(-1).date, '2026-07-25');
    assert.equal(result.days.at(-1).count, 1);
    assert.equal(result.summary.sessionCount, 2);
    assert.equal(result.summary.activeDays, 2);
  }
});

test('timeline windows recalculate counts and streaks within the selected range', () => {
  const { buildAuraActivity } = loadProductionModule();
  const sessions = [
    session('2025-07-26T10:00:00Z'),
    session('2025-07-27T10:00:00Z'),
    session('2025-07-28T10:00:00Z'),
    session('2026-06-26T10:00:00Z'),
    session('2026-06-27T10:00:00Z'),
    session('2026-07-19T10:00:00Z'),
    session('2026-07-20T10:00:00Z'),
    session('2026-07-22T10:00:00Z'),
    session('2026-07-23T10:00:00Z'),
    session('2026-07-24T10:00:00Z'),
    session('2026-07-25T10:00:00Z'),
  ];

  const week = buildAuraActivity(sessions, { now: NOW, windowDays: 7 });
  assert.deepEqual(week.summary, {
    sessionCount: 6,
    activeDays: 6,
    currentStreak: 4,
    longestStreak: 4,
  });

  const month = buildAuraActivity(sessions, { now: NOW, windowDays: 30 });
  assert.deepEqual(month.summary, {
    sessionCount: 8,
    activeDays: 8,
    currentStreak: 4,
    longestStreak: 4,
  });

  const year = buildAuraActivity(sessions, { now: NOW, windowDays: 365 });
  assert.deepEqual(year.summary, {
    sessionCount: 11,
    activeDays: 11,
    currentStreak: 4,
    longestStreak: 4,
  });
});

test('source filtering composes with each supported timeline', () => {
  const { buildAuraActivity } = loadProductionModule();
  const cases = [
    { windowDays: 7, firstDay: '2026-07-19' },
    { windowDays: 30, firstDay: '2026-06-26' },
    { windowDays: 365, firstDay: '2025-07-26' },
  ];

  for (const { windowDays, firstDay } of cases) {
    const result = buildAuraActivity(
      [
        session(`${firstDay}T08:00:00Z`, 'codex'),
        session(`${firstDay}T09:00:00Z`, 'cursor'),
        session('2026-07-25T08:00:00Z', 'codex'),
      ],
      { now: NOW, source: 'codex', windowDays },
    );

    assert.equal(result.days.length, windowDays);
    assert.equal(result.summary.sessionCount, 2);
    assert.equal(result.summary.activeDays, 2);
    assert.equal(result.days[0].count, 1);
    assert.equal(result.days.at(-1).count, 1);
  }
});

test('invalid timeline window values fall back to 365 days', () => {
  const { buildAuraActivity } = loadProductionModule();

  for (const windowDays of [Number.NaN, Number.POSITIVE_INFINITY, 0, -7, 7.5, 14]) {
    const result = buildAuraActivity([], { now: NOW, windowDays });
    assert.equal(result.days.length, 365);
    assert.equal(result.days[0].date, '2025-07-26');
    assert.equal(result.days.at(-1).date, '2026-07-25');
  }
});
