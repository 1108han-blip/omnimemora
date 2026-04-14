interface Env {
  LEADS_DB: D1Database;
}

const json = (body: unknown, init?: ResponseInit) =>
  new Response(JSON.stringify(body, null, 2), {
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
    },
    ...init,
  });

/** Simple shared-secret Bearer check. Token is set via: wrangler secret put OPERATOR_SECRET */
function requireOperator(request: Request, env: Env): Response | null {
  const header = request.headers.get('authorization') ?? '';
  const token = header.replace(/^Bearer\s+/i, '').trim();
  if (!token) {
    return json({ ok: false, error: 'Missing Bearer token.' }, { status: 401 });
  }
  if (token !== (env as Record<string, unknown>).OPERATOR_SECRET) {
    return json({ ok: false, error: 'Invalid operator token.' }, { status: 403 });
  }
  return null;
}

/** GET /api/leads/summary — returns count of leads per status. */
export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
  const deny = requireOperator(request, env);
  if (deny) return deny;

  try {
    const all = await env.LEADS_DB
      .prepare('SELECT status, COUNT(*) as count FROM private_leads GROUP BY status')
      .all();
    const counts: Record<string, number> = { new: 0, contacted: 0, qualified: 0, closed: 0 };
    let total = 0;
    for (const row of all.results as Array<{ status: string; count: number }>) {
      if (row.status in counts) counts[row.status] = row.count;
      total += row.count;
    }
    return json({ ok: true, summary: { ...counts, total }, newCount: counts.new });
  } catch (error) {
    return json({ ok: false, error: error instanceof Error ? error.message : 'Unknown summary failure.' }, { status: 500 });
  }
};
