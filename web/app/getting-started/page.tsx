import { Plug, Terminal, ShieldOff, Sparkles } from 'lucide-react';
import { ossViewerConfig } from '../../lib/aura-config';

export const dynamic = 'force-dynamic';

const MCP_URL = 'http://localhost:8090/mcp';

// Agents that speak MCP over local HTTP — no auth needed.
const SUPPORTED = [
  { name: 'Claude Code', note: 'Add the URL as an HTTP MCP server.' },
  { name: 'Cursor', note: 'Add it to your MCP servers config (HTTP).' },
  { name: 'Claude Desktop', note: 'Add it as a custom MCP connector.' },
  { name: 'Codex', note: 'Point the CLI at the MCP endpoint.' },
];

const FIRST_COMMANDS = [
  { prompt: '"score this session"', desc: 'Score the work you just finished.' },
  { prompt: '"show my profile"', desc: 'Your current Aura score, level and archetype.' },
  { prompt: '"import my recent history"', desc: 'Bootstrap your Aura from past sessions.' },
];

export default function GettingStartedPage() {
  return (
    <div className="mx-auto max-w-3xl py-6">
      <h1 className="text-2xl font-bold text-[var(--vibecoder-text-primary)]">Getting Started</h1>
      <p className="mt-2 text-sm leading-relaxed text-[var(--vibecoder-text-secondary)]">
        Open Aura runs entirely on your machine. Your agent connects to a local MCP server, sends a
        redacted evidence packet after a session, and Aura scores how you work with AI — no login, no
        account, nothing leaves your machine.
      </p>

      {/* 1. Connect */}
      <section className="mt-8">
        <div className="mb-3 flex items-center gap-2">
          <Plug className="h-4 w-4 text-[var(--vibecoder-accent)]" />
          <h2 className="text-base font-semibold text-[var(--vibecoder-text-primary)]">
            1. Connect your agent
          </h2>
        </div>
        <p className="text-sm text-[var(--vibecoder-text-secondary)]">
          Point your agent&apos;s MCP config at the local server. There is{' '}
          <span className="font-semibold text-[var(--vibecoder-text-primary)]">no auth</span> in local mode.
        </p>
        <pre className="mt-3 overflow-x-auto rounded-lg border border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.02)] p-4 font-mono text-[12px] leading-relaxed text-[var(--vibecoder-text-secondary)]">
{`{
  "mcpServers": {
    "aura": { "url": "${MCP_URL}" }
  }
}`}
        </pre>
      </section>

      {/* 2. Supported agents */}
      <section className="mt-8">
        <div className="mb-3 flex items-center gap-2">
          <Terminal className="h-4 w-4 text-[var(--vibecoder-accent)]" />
          <h2 className="text-base font-semibold text-[var(--vibecoder-text-primary)]">
            2. Supported agents
          </h2>
        </div>
        <p className="text-sm text-[var(--vibecoder-text-secondary)]">
          Any agent that speaks MCP over local HTTP works. Point it at{' '}
          <code className="font-mono text-[var(--vibecoder-accent)]">{MCP_URL}</code>.
        </p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {SUPPORTED.map((a) => (
            <div
              key={a.name}
              className="rounded-lg border border-[rgba(0,230,118,0.15)] bg-[rgba(0,230,118,0.03)] p-3"
            >
              <p className="text-sm font-semibold text-[var(--vibecoder-text-primary)]">{a.name}</p>
              <p className="mt-0.5 text-[12px] leading-snug text-[var(--vibecoder-text-secondary)]">{a.note}</p>
            </div>
          ))}
        </div>
      </section>

      {/* 3. Not supported locally */}
      <section className="mt-8">
        <div className="mb-3 flex items-center gap-2">
          <ShieldOff className="h-4 w-4" style={{ color: '#f59e0b' }} />
          <h2 className="text-base font-semibold text-[var(--vibecoder-text-primary)]">
            3. Not supported in local mode
          </h2>
        </div>
        <div className="rounded-lg border border-[rgba(245,158,11,0.2)] bg-[rgba(245,158,11,0.04)] p-4">
          <p className="text-sm leading-relaxed text-[var(--vibecoder-text-secondary)]">
            Open Aura is a{' '}
            <span className="font-semibold text-[var(--vibecoder-text-primary)]">no-auth, local</span> server.
            Clients that require{' '}
            <span className="font-semibold text-[var(--vibecoder-text-primary)]">OAuth or an authenticated,
            hosted endpoint</span> — like the claude.ai web connector or other remote MCP clients that expect a
            public HTTPS URL + sign-in — can&apos;t connect to a local server.
          </p>
          <p className="mt-2 text-sm leading-relaxed text-[var(--vibecoder-text-secondary)]">
            For those, plus a public profile, the shared leaderboard and team insights, use the hosted edition.
          </p>
          <a
            href={ossViewerConfig.signInHref}
            className="mt-3 inline-flex items-center justify-center rounded-lg bg-[rgba(255,255,255,0.12)] px-4 py-2 font-mono text-[13px] font-semibold text-white no-underline transition-colors hover:bg-[rgba(255,255,255,0.18)]"
          >
            Use hosted VibeLevel →
          </a>
        </div>
      </section>

      {/* 4. First commands */}
      <section className="mt-8">
        <div className="mb-3 flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-[var(--vibecoder-accent)]" />
          <h2 className="text-base font-semibold text-[var(--vibecoder-text-primary)]">
            4. First commands
          </h2>
        </div>
        <p className="text-sm text-[var(--vibecoder-text-secondary)]">Once connected, just ask your agent:</p>
        <div className="mt-3 space-y-2">
          {FIRST_COMMANDS.map((c) => (
            <div
              key={c.prompt}
              className="rounded-lg border border-[rgba(0,230,118,0.15)] bg-[rgba(0,230,118,0.03)] p-3"
            >
              <code className="block font-mono text-[13px] font-semibold text-[var(--vibecoder-accent)]">
                {c.prompt}
              </code>
              <p className="mt-1 text-[12px] leading-snug text-[var(--vibecoder-text-secondary)]">{c.desc}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
