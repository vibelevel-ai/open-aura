import { NextRequest, NextResponse } from 'next/server';

// Runtime proxy for the viewer components' relative /api/aura/* fetches → the
// FastAPI backend. Done as a route handler (not a next.config rewrite) so the
// backend URL is read PER REQUEST at runtime — a build-time rewrite bakes in
// localhost and fails inside the container. (No auth header — local mode needs
// none.)
export const dynamic = 'force-dynamic';

function backend(): string {
  return (process.env.INTERNAL_API_URL || 'http://localhost:8090').replace(/\/$/, '');
}

async function proxy(req: NextRequest, slug: string[]): Promise<NextResponse> {
  const url = `${backend()}/api/aura/${slug.map(encodeURIComponent).join('/')}${req.nextUrl.search}`;
  const init: RequestInit = { method: req.method, cache: 'no-store', headers: { accept: 'application/json' } };
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    init.body = await req.text();
    (init.headers as Record<string, string>)['content-type'] =
      req.headers.get('content-type') || 'application/json';
  }
  try {
    const res = await fetch(url, init);
    const body = await res.text();
    return new NextResponse(body, {
      status: res.status,
      headers: { 'content-type': res.headers.get('content-type') || 'application/json' },
    });
  } catch {
    return NextResponse.json({ error: 'backend unreachable' }, { status: 502 });
  }
}

export function GET(req: NextRequest, ctx: { params: { slug: string[] } }) {
  return proxy(req, ctx.params.slug);
}
export function POST(req: NextRequest, ctx: { params: { slug: string[] } }) {
  return proxy(req, ctx.params.slug);
}
