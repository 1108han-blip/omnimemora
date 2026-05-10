import type { RecentRequest } from '../types';

/**
 * Family name normalization utility
 * Maps internal agent/family identifiers to canonical display names.
 * Ensures user-facing surfaces show consistent, meaningful names.
 */

const FAMILY_ID_MAP: Record<string, string> = {
  // OpenClaw family
  'openclaw': 'openclaw',
  'openclaw-agent': 'openclaw',
  'openclaw-bundle-mcp': 'openclaw',
  'openclaw_bundle_mcp': 'openclaw',

  // Claude Code family
  'claude_code': 'claude_code',
  'claude-code': 'claude_code',
  'claude': 'claude_code',

  // Codex family
  'codex': 'codex_cli',
  'codex_cli': 'codex_cli',
  'codex-cli': 'codex_cli',

  // Test/development agents (canonical)
  'test': 'test',
  'test-agent': 'test',
};

const FAMILY_NAME_MAP: Record<string, string> = {
  openclaw: 'OpenClaw',
  claude_code: 'Claude Code',
  codex_cli: 'Codex',
  test: 'Test',
};

export function normalizeFamilyId(id: string): string {
  const lower = id.toLowerCase();
  return FAMILY_ID_MAP[lower] ?? lower;
}

/**
 * Returns the canonical display name for a given agent/family identifier.
 * Falls back to the original identifier if no mapping exists.
 */
export function normalizeFamilyName(id: string): string {
  const familyId = normalizeFamilyId(id);
  return FAMILY_NAME_MAP[familyId] ?? id;
}

/**
 * Returns true if the identifier represents an internal event that should
 * not be shown prominently in the user-facing Live Request Flow.
 */
export function isInternalEvent(query: string, agent: string): boolean {
  const visibleQuery = extractUserVisibleQuery(query);
  const lowerQuery = query.toLowerCase();
  const lowerVisibleQuery = visibleQuery.toLowerCase();

  // Session bootstrap is an internal handshake event, not a real user request
  if (query === 'session bootstrap context handshake' || visibleQuery === 'session bootstrap context handshake') {
    return true;
  }

  // Untrusted control-surface metadata should not dominate the user-facing flow
  if (lowerQuery.startsWith('sender (untrusted metadata):') && lowerQuery.includes('openclaw-control-ui')) {
    return !lowerVisibleQuery;
  }

  // Internal MCP bundle events
  if (agent.toLowerCase() === 'openclaw-bundle-mcp' && lowerVisibleQuery.includes('bootstrap')) {
    return true;
  }

  return false;
}

export function extractUserVisibleQuery(query: string): string {
  const raw = query.trim();
  if (!raw) return '';
  const lower = raw.toLowerCase();
  if (!lower.startsWith('sender (untrusted metadata):') && !lower.startsWith('system (untrusted):')) {
    return raw;
  }

  const firstFence = raw.indexOf('```');
  if (firstFence === -1) return '';
  const secondFence = raw.indexOf('```', firstFence + 3);
  if (secondFence === -1) return '';
  return raw.slice(secondFence + 3).trim();
}

export function scoreRecentRequest(req: RecentRequest): number {
  const isUnknownAgent = req.agent.toLowerCase() === 'unknown';
  const taskKnown = req.task_type !== 'unknown';
  const realSavedTokens = req.real_input_saved_tokens ?? 0;

  let score = 0;
  if (!req.bypass) score += 1000;
  if (realSavedTokens > 0) score += 500;
  if (req.packed_memory_count > 0) score += 250;
  if (!isUnknownAgent) score += 100;
  if (taskKnown) score += 25;
  score += Math.min(realSavedTokens, 99);
  return score;
}

export function rankRecentRequests(requests: RecentRequest[]): RecentRequest[] {
  return [...requests].sort((a, b) => {
    // Live flow must be time-first to reflect real-time traffic.
    // Keep score as a secondary tie-breaker only.
    const tsDiff = new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
    if (tsDiff !== 0) return tsDiff;
    return scoreRecentRequest(b) - scoreRecentRequest(a);
  });
}

export function normalizeRecentRequestUsageList(requests: RecentRequest[]): NormalizedAgentUsage[] {
  const familyMap = new Map<string, NormalizedAgentUsage>();

  for (const req of requests) {
    if (isInternalEvent(req.query, req.agent)) {
      continue;
    }

    const family = normalizeFamilyId(req.agent);
    const displayName = normalizeFamilyName(family);
    const existing = familyMap.get(family);

    if (existing) {
      const existingSaved = existing.savedTokens;
      const existingRatio = existing.savingsRatio;
      const existingBaseline = existingSaved > 0 && existingRatio > 0
        ? existingSaved / existingRatio
        : 0;
      const realSaved = req.real_input_saved_tokens ?? 0;
      const realRatio = req.real_input_savings_ratio ?? 0;
      const newBaseline = realSaved > 0 && realRatio > 0
        ? realSaved / realRatio
        : 0;

      existing.requests += 1;
      existing.savedTokens = existingSaved + realSaved;
      const totalBaseline = existingBaseline + newBaseline;
      existing.savingsRatio = totalBaseline > 0 ? existing.savedTokens / totalBaseline : 0;
      if (!existing.lastRequestAt || req.timestamp > existing.lastRequestAt) {
        existing.lastRequestAt = req.timestamp;
      }
    } else {
      familyMap.set(family, {
        family,
        displayName,
        requests: 1,
        savedTokens: req.real_input_saved_tokens ?? 0,
        savingsRatio: req.real_input_savings_ratio ?? 0,
        lastRequestAt: req.timestamp,
      });
    }
  }

  return Array.from(familyMap.values());
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
    const family = normalizeFamilyId(a.agent);
    const displayName = normalizeFamilyName(family);
    const existing = familyMap.get(family);

    if (existing) {
      const existingSaved = existing.savedTokens;
      const existingRatio = existing.savingsRatio;
      const existingBaseline = existingSaved > 0 && existingRatio > 0
        ? existingSaved / existingRatio
        : 0;
      const newBaseline = a.saved_tokens > 0 && a.savings_ratio > 0
        ? a.saved_tokens / a.savings_ratio
        : 0;

      existing.requests += a.requests;
      existing.savedTokens = existingSaved + a.saved_tokens;
      const totalBaseline = existingBaseline + newBaseline;
      existing.savingsRatio = totalBaseline > 0 ? existing.savedTokens / totalBaseline : 0;
      // Keep most recent timestamp
      if (a.last_request_at && (!existing.lastRequestAt || a.last_request_at > existing.lastRequestAt)) {
        existing.lastRequestAt = a.last_request_at;
      }
    } else {
      familyMap.set(family, {
        family,
        displayName,
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
