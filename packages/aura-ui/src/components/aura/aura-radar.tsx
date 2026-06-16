'use client';

// VibeLevel Aura — dimension radar.
//
// Adapted from the dashboard radar in `components/overview_v2.tsx`
// (`RadarChart`, lines ~232-337) and the per-dimension bars in
// `components/assessment/score-report.tsx`. That component is module-private
// (not exported) and hardcodes the 4 assessment dimensions, so per the spec we
// *re-implement the same SVG math/approach* here rather than importing it:
//   · concentric ring "levels" + radial axis lines
//   · score (0-10) → radius via (score / 10) * maxR
//   · axes evenly distributed starting from the top (-90°)
//   · a filled data polygon + per-vertex dots + outer axis labels
//
// The only real difference: Aura's referenceless dimension set is variable in
// length (the rubric-free subset differs coding vs non-coding), so we accept an
// arbitrary ordered list of dimensions instead of the fixed 4, and we use the
// Aura accent (violet) rather than the dashboard teal so the two scores read as
// distinct (verified vs unverified — see spec decision #16).

export interface RadarDimension {
  key: string;
  label: string;
  score: number; // 0-10
  color?: string;
}

// Aura accent — VibeLevel green (#00e676), per the white/green/dark palette.
const AURA_ACCENT = '0,230,118'; // rgb for #00e676

export function AuraRadar({
  dimensions,
  size = 240,
}: {
  dimensions: RadarDimension[];
  size?: number;
}) {
  // Geometry. Viewbox is square-ish with headroom for the outer labels.
  const vbW = 240;
  const vbH = 210;
  const cx = 120;
  const cy = 105;
  const maxR = 64;
  const levels = [2.5, 5.0, 7.5, 10.0];

  const n = Math.max(dimensions.length, 1);
  const angleOffset = -Math.PI / 2; // start from top
  const angles = dimensions.map((_, i) => angleOffset + (i * 2 * Math.PI) / n);

  const scoreToR = (score: number) => (Math.max(0, Math.min(10, score)) / 10) * maxR;

  const points = dimensions
    .map((d, i) => {
      const r = scoreToR(d.score);
      const x = cx + r * Math.cos(angles[i]);
      const y = cy + r * Math.sin(angles[i]);
      return `${x},${y}`;
    })
    .join(' ');

  const hasData = dimensions.some((d) => d.score > 0);

  // With fewer than 3 axes a polygon collapses to a line/point; still render
  // the rings + dots so a single-dimension Aura isn't a blank box.
  return (
    <svg
      viewBox={`0 0 ${vbW} ${vbH}`}
      className="w-full h-full"
      style={{ maxWidth: size, maxHeight: size }}
      role="img"
      aria-label="Aura dimension radar"
    >
      {/* Concentric rings */}
      {levels.map((level) => (
        <circle
          key={level}
          cx={cx}
          cy={cy}
          r={scoreToR(level)}
          fill="none"
          stroke={`rgba(${AURA_ACCENT},0.14)`}
          strokeWidth="1"
        />
      ))}

      {/* Axis lines */}
      {angles.map((angle, i) => (
        <line
          key={i}
          x1={cx}
          y1={cy}
          x2={cx + maxR * Math.cos(angle)}
          y2={cy + maxR * Math.sin(angle)}
          stroke="rgba(139,146,184,0.18)"
          strokeWidth="1"
        />
      ))}

      {/* Data polygon */}
      {hasData && dimensions.length >= 3 && (
        <polygon
          points={points}
          fill={`rgba(${AURA_ACCENT},0.16)`}
          stroke={`rgba(${AURA_ACCENT},0.85)`}
          strokeWidth="1.5"
        />
      )}

      {/* Data point dots */}
      {hasData &&
        dimensions.map((d, i) => {
          const r = scoreToR(d.score);
          return (
            <circle
              key={d.key}
              cx={cx + r * Math.cos(angles[i])}
              cy={cy + r * Math.sin(angles[i])}
              r="3"
              fill={d.color || `rgb(${AURA_ACCENT})`}
            />
          );
        })}

      {/* Axis labels */}
      {dimensions.map((d, i) => {
        const labelR = maxR + 22;
        const x = cx + labelR * Math.cos(angles[i]);
        const y = cy + labelR * Math.sin(angles[i]);
        const anchor =
          Math.abs(Math.cos(angles[i])) < 0.1
            ? 'middle'
            : Math.cos(angles[i]) > 0
              ? 'start'
              : 'end';
        return (
          <text
            key={d.key}
            x={x}
            y={y}
            textAnchor={anchor}
            dominantBaseline="central"
            fill={d.color || 'var(--vibecoder-text-secondary)'}
            fontSize="8.5"
            fontWeight="600"
            fontFamily="system-ui, -apple-system, sans-serif"
          >
            {d.label}
          </text>
        );
      })}
    </svg>
  );
}
