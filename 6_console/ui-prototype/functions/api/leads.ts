interface Env {
  LEADS_DB: D1Database;
}

const VALID_STATUSES = ['new', 'contacted', 'qualified', 'closed'] as const;
type LeadStatus = (typeof VALID_STATUSES)[number];

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

export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
  const deny = requireOperator(request, env);
  if (deny) return deny;

  const url = new URL(request.url);

  // List endpoint.
  const rawStatus = url.searchParams.get('status');
  const limit = Math.min(Number(url.searchParams.get('limit') ?? '50'), 200);
  const offset = Number(url.searchParams.get('offset') ?? '0');

  let query = `SELECT id, name, email, use_case, monthly_token_usage, message, source, status, created_at, user_agent FROM private_leads`;
  const params: (string | number)[] = [];

  if (rawStatus && VALID_STATUSES.includes(rawStatus as LeadStatus)) {
    query += ` WHERE status = ?`;
    params.push(rawStatus);
  }

  query += ` ORDER BY created_at DESC LIMIT ? OFFSET ?`;
  params.push(limit, offset);

  try {
    const result = await env.LEADS_DB.prepare(query).bind(...params).all();
    return json({ ok: true, leads: result.results, count: result.results.length });
  } catch (error) {
    return json({ ok: false, error: error instanceof Error ? error.message : 'Unknown query failure.' }, { status: 500 });
  }
};

export const onRequestPatch: PagesFunction<Env> = async ({ request, env }) => {
  const deny = requireOperator(request, env);
  if (deny) return deny;

  const contentType = request.headers.get('content-type') ?? '';
  if (!contentType.includes('application/json')) {
    return json({ ok: false, error: 'Expected application/json body.' }, { status: 415 });
  }

  const body = (await request.json()) as { id?: string; status?: string };
  const { id, status } = body;

  if (!id) {
    return json({ ok: false, error: 'id is required.' }, { status: 400 });
  }
  if (!status || !VALID_STATUSES.includes(status as LeadStatus)) {
    return json({ ok: false, error: 'status must be one of: ' + VALID_STATUSES.join(', ') + '.' }, { status: 400 });
  }

  try {
    const result = await env.LEADS_DB.prepare(
      "UPDATE private_leads SET status = ? WHERE id = ?"
    )
      .bind(status, id)
      .run();

    if (result.meta.changes === 0) {
      return json({ ok: false, error: 'Lead not found.' }, { status: 404 });
    }

    return json({ ok: true, id, status });
  } catch (error) {
    return json({ ok: false, error: error instanceof Error ? error.message : 'Unknown update failure.' }, { status: 500 });
  }
};
