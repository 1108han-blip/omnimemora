/**
 * Family name normalization utility
 * Maps internal agent/family identifiers to canonical display names.
 * Ensures user-facing surfaces show consistent, meaningful names.
 */

// Mapping from internal identifiers to canonical family names
const FAMILY_NAME_MAP: Record<string, string> = {
  // OpenClaw family
  'openclaw': 'OpenClaw',
  'openclaw-agent': 'OpenClaw',
  'openclaw-bundle-mcp': 'OpenClaw',
  'openclaw_bundle_mcp': 'OpenClaw',

  // Claude Code family
  'claude_code': 'Claude Code',
  'claude-code': 'Claude Code',

  // Codex family
  'codex': 'Codex',
  'codex_cli': 'Codex',
  'codex-cli': 'Codex',

  // Test/development agents (canonical)
  'test': 'Test',
  'test-agent': 'Test',
};

/**
 * Returns the canonical display name for a given agent/family identifier.
 * Falls back to the original identifier if no mapping exists.
 */
export function normalizeFamilyName(id: string): string {
  const lower = id.toLowerCase();
  return FAMILY_NAME_MAP[lower] ?? id;
}

/**
 * Returns true if the identifier represents an internal event that should
 * not be shown prominently in the user-facing Live Request Flow.
 */
export function isInternalEvent(query: string, agent: string): boolean {
  // Session bootstrap is an internal handshake event, not a real user request
  if (query === 'session bootstrap context handshake') {
    return true;
  }

  // Internal MCP bundle events
  if (agent.toLowerCase() === 'openclaw-bundle-mcp' && query.includes('bootstrap')) {
    return true;
  }

  return false;
}

/**
 * Groups agents by their canonical family, aggregating request counts.
 */
export interface NormalizedAgentUsage {
  family: string;
  displayName: string;
  requests: number;
  savedTokens: number;
  savingsRatio: number;
  lastRequestAt: string | null;
}

export function normalizeAgentUsageList(
  agents: Array<{
    agent: string;
    requests: number;
    saved_tokens: number;
    savings_ratio: number;
    last_request_at?: string | null;
  }>
): NormalizedAgentUsage[] {
  const familyMap = new Map<string, NormalizedAgentUsage>();

  for (const a of agents) {
    const family = normalizeFamilyName(a.agent);
    const existing = familyMap.get(family);

    if (existing) {
      existing.requests += a.requests;
      existing.savedTokens += a.saved_tokens;
      // Recalculate weighted average ratio
      // savings_ratio = saved_tokens / baseline_tokens
      // So baseline_tokens = saved_tokens / savings_ratio (when savings_ratio > 0)
      const existingBaseline = existing.savedTokens > 0 && existing.savingsRatio > 0
        ? existing.savedTokens / existing.savingsRatio
        : 0;
      const newBaseline = a.saved_tokens > 0 && a.savings_ratio > 0
        ? a.saved_tokens / a.savings_ratio
        : 0;
      const totalBaseline = existingBaseline + newBaseline;
      existing.savingsRatio = totalBaseline > 0 ? existing.savedTokens / totalBaseline : 0;
      // Keep most recent timestamp
      if (a.last_request_at && (!existing.lastRequestAt || a.last_request_at > existing.lastRequestAt)) {
        existing.lastRequestAt = a.last_request_at;
      }
    } else {
      familyMap.set(family, {
        family,
        displayName: family,
        requests: a.requests,
        savedTokens: a.saved_tokens,
        savingsRatio: a.savings_ratio,
        lastRequestAt: a.last_request_at ?? null,
      });
    }
  }

  return Array.from(familyMap.values());
}

/**
 * Determines if an agent should be considered "active" based on recent requests.
 * Uses the same truth source as AgentControlCard.active.
 */
export function isAgentActive(
  lastSeenAt: string | null | undefined,
  windowMinutes: number = 5
): boolean {
  if (!lastSeenAt) return false;

  try {
    const lastSeen = new Date(lastSeenAt).getTime();
    const now = Date.now();
    const windowMs = windowMinutes * 60 * 1000;
    return (now - lastSeen) <= windowMs;
  } catch {
    return false;
  }
}
