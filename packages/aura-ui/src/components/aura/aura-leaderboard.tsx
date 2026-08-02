'use client';

/**
 * VibeLevel Aura — Aura Score leaderboard view.
 *
 * Ranks builders by their *Aura Score* (the referenceless score from real AI
 * sessions). In Open Aura this is a read-only pull of the public hosted board.
 *
 * Data: GET /api/aura/leaderboard → AuraLeaderboardEntry[]. Each handle links to
 * the public profile at /u/[handle]. Aura Score is colored by AURA_LEVEL_COLORS.
 */

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Heart, Loader2, Sparkles, Trophy } from 'lucide-react';
import {
  AURA_LEVEL_COLORS,
  type AuraLeaderboardEntry,
} from '../../lib/aura/types';

function levelColor(level: string): string {
  return AURA_LEVEL_COLORS[level] || AURA_LEVEL_COLORS.Emerging;
}

export function AuraLeaderboard({
  limit = 100,
  className = '',
}: {
  limit?: number;
  className?: string;
}) {
  const [entries, setEntries] = useState<AuraLeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  // Local override of like counts (handle -> count) for optimistic updates;
  // falls back to the entry's server count until the user likes.
  const [likes, setLikes] = useState<Record<string, number>>({});

  // Count-only like: optimistic +1, then reconcile to the server's authoritative
  // total (which may be higher if others liked concurrently). No auth/dedup.
  const likeProfile = async (handle: string, current: number) => {
    if (!handle) return;
    setLikes((prev) => ({ ...prev, [handle]: current + 1 }));
    try {
      const res = await fetch(
        `/api/aura/profile/${encodeURIComponent(handle)}/like`,
        { method: 'POST' },
      );
      if (res.ok) {
        const data = await res.json();
        if (typeof data?.like_count === 'number') {
          setLikes((prev) => ({ ...prev, [handle]: data.like_count }));
        }
      }
    } catch {
      /* keep the optimistic value on network error */
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(false);
      try {
        const res = await fetch(`/api/aura/leaderboard?limit=${limit}`);
        if (!res.ok) throw new Error(`Load failed (${res.status})`);
        const data = await res.json();
        if (!cancelled) {
          setEntries(Array.isArray(data) ? data : data?.entries ?? []);
        }
      } catch {
        if (!cancelled) setError(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [limit]);

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Header — clearly labels this as the Aura ranking, distinct from the
          assessment leaderboard. */}
      <div className="flex items-start gap-2">
        <Sparkles className="h-5 w-5 text-[var(--vibecoder-accent)] mt-0.5 flex-shrink-0" />
        <div>
          <h3 className="text-base font-semibold text-[var(--vibecoder-text-primary)]">
            Aura Score Leaderboard
          </h3>
          <p className="text-xs text-[var(--vibecoder-text-secondary)] leading-snug">
            Ranked by VibeLevel Aura — your real AI work.
          </p>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-6">
          <Loader2 className="h-4 w-4 animate-spin text-[var(--vibecoder-accent)]" />
        </div>
      ) : error ? (
        <p className="text-sm text-red-400">Failed to load the Aura leaderboard.</p>
      ) : entries.length === 0 ? (
        <div className="rounded-lg border border-[rgba(139,146,184,0.1)] bg-[rgba(139,146,184,0.02)] p-6 text-center text-sm text-[var(--vibecoder-text-secondary)]">
          <Trophy className="h-6 w-6 mx-auto mb-2 opacity-30" />
          No Aura scores yet. Connect your agent and score a session to appear here.
        </div>
      ) : (
        <div className="rounded-lg border border-[rgba(139,146,184,0.1)] overflow-x-auto vibecoder-panel">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[rgba(139,146,184,0.05)] text-xs uppercase tracking-wider text-[var(--vibecoder-text-secondary)]">
                <th className="text-center px-3 py-2 font-medium w-14">Rank</th>
                <th className="text-left px-3 py-2 font-medium">Builder</th>
                <th className="text-left px-3 py-2 font-medium hidden sm:table-cell">
                  Archetype
                </th>
                <th className="text-right px-3 py-2 font-medium">Aura Score</th>
                <th className="text-right px-3 py-2 font-medium pr-5">Likes</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => {
                const medalColors = ['#FFD700', '#C0C0C0', '#CD7F32'];
                const isTop3 = entry.rank <= 3;
                const color = levelColor(entry.aura_level);
                const name = entry.handle || entry.display_name || '—';
                return (
                  <tr
                    key={`${entry.handle}-${entry.rank}`}
                    className={`border-t border-[rgba(139,146,184,0.1)] transition-colors ${
                      isTop3
                        ? 'bg-[rgba(255,200,50,0.02)]'
                        : 'hover:bg-[rgba(139,146,184,0.03)]'
                    }`}
                  >
                    {/* Rank */}
                    <td className="px-3 py-2.5 text-center w-14">
                      {isTop3 ? (
                        <Trophy
                          className="h-4 w-4 mx-auto"
                          style={{ color: medalColors[entry.rank - 1] }}
                        />
                      ) : (
                        <span className="text-sm font-bold text-[var(--vibecoder-text-secondary)]">
                          {entry.rank}
                        </span>
                      )}
                    </td>

                    {/* Builder → public profile */}
                    <td className="px-3 py-2.5">
                      <Link
                        href={`/u/${entry.handle}`}
                        className="text-sm font-medium text-[var(--vibecoder-text-primary)] hover:text-[var(--vibecoder-accent)] transition-colors"
                      >
                        {name}
                      </Link>
                    </td>

                    {/* Archetype */}
                    <td className="px-3 py-2.5 hidden sm:table-cell">
                      {entry.archetype ? (
                        <span className="text-[10px] px-2 py-0.5 rounded border border-[rgba(139,146,184,0.2)] bg-[rgba(139,146,184,0.06)] text-[var(--vibecoder-text-secondary)]">
                          {entry.archetype}
                        </span>
                      ) : (
                        <span className="text-xs text-[var(--vibecoder-text-secondary)] opacity-40">
                          —
                        </span>
                      )}
                    </td>

                    {/* Aura Score (colored by level band) */}
                    <td className="px-3 py-2.5 text-right">
                      <span
                        className="text-sm font-bold"
                        style={{ color }}
                      >
                        {entry.aura_score.toFixed(1)}
                      </span>
                    </td>

                    {/* Likes — count-only, tap the heart to like (no auth) */}
                    <td className="px-3 py-2.5 text-right pr-5">
                      {(() => {
                        const count = likes[entry.handle] ?? entry.like_count ?? 0;
                        return (
                          <button
                            type="button"
                            onClick={() => likeProfile(entry.handle, count)}
                            disabled={!entry.handle}
                            title={entry.handle ? `Like ${name}` : 'No public profile'}
                            aria-label={`Like ${name}`}
                            className="group inline-flex items-center gap-1.5 rounded-full border border-[rgba(139,146,184,0.2)] px-2.5 py-1 text-xs font-semibold text-[var(--vibecoder-text-secondary)] transition-colors hover:border-[rgba(244,63,94,0.5)] hover:text-rose-400 disabled:opacity-40 disabled:cursor-not-allowed"
                          >
                            <Heart className="h-3.5 w-3.5 transition-colors group-hover:fill-rose-400 group-hover:text-rose-400" />
                            {count}
                          </button>
                        );
                      })()}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default AuraLeaderboard;
