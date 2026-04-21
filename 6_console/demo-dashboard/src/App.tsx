import { useState, useEffect, useCallback, useMemo } from 'react';
import { HeroMetrics } from './components/HeroMetrics';
import { LiveRequestFlow } from './components/LiveRequestFlow';
import { ContextComparison } from './components/ContextComparison';
import { CallChainViz } from './components/CallChainViz';
import { AgentUsagePanel } from './components/AgentUsagePanel';
import { AgentsDashboard } from './components/AgentsDashboard';
import { fetchRecentRequests, fetchUsageSummary, fetchTenants, fetchAgentControls, fetchRequestEvidence, fetchCoreCapabilities, fetchCoreCapabilitiesTrend } from './api';
import type { RecentRequest, UsageSummary, AgentControlCard, RequestEvidence, CoreCapabilitiesResponse, CoreCapabilitiesTrendResponse } from './types';
import { isInternalEvent, normalizeAgentUsageList, normalizeRecentRequestUsageList, rankRecentRequests } from './utils/familyNormalization';

function inferInitialTab(): 'overview' | 'agents' {
  const params = new URLSearchParams(window.location.search);
  const tab = params.get('tab');
  if (tab === 'agents') return 'agents';
  if (window.location.pathname.toLowerCase().endsWith('/agents')) return 'agents';
  return 'overview';
}

function buildPathForTab(tab: 'overview' | 'agents'): string {
  const current = window.location.pathname;
  const lower = current.toLowerCase();
  const base = lower.endsWith('/agents') ? current.slice(0, -7) || '/' : current;
  if (tab === 'agents') {
    return base.endsWith('/') ? `${base}agents` : `${base}/agents`;
  }
  return base || '/';
}

function buildHrefForTab(tab: 'overview' | 'agents', tenant: string): string {
  const params = new URLSearchParams();
  params.set('tenant', tenant);
  params.set('tab', tab);
  return `${buildPathForTab(tab)}?${params.toString()}`;
}

export default function App() {
  const [tenant, setTenant] = useState<string>(() => {
    const fromUrl = new URLSearchParams(window.location.search).get('tenant');
    return fromUrl || 'all';
  });
  const [tenants, setTenants] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<'overview' | 'agents'>(() => inferInitialTab());
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [agentControls, setAgentControls] = useState<AgentControlCard[]>([]);
  const [requests, setRequests] = useState<RecentRequest[]>([]);
  const [_selectedRequest, setSelectedRequest] = useState<RecentRequest | null>(null);
  const [requestEvidence, setRequestEvidence] = useState<RequestEvidence | null>(null);
  const [loadingMetrics, setLoadingMetrics] = useState(true);
  const [loadingEvidence, setLoadingEvidence] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [highlightFamilyId, setHighlightFamilyId] = useState<string | null>(null);
  const [coreCap24h, setCoreCap24h] = useState<CoreCapabilitiesResponse | null>(null);
  const [coreCapTrend, setCoreCapTrend] = useState<CoreCapabilitiesTrendResponse | null>(null);

  const loadMetrics = useCallback(async () => {
    const failures: string[] = [];
    try {
      const controlTab = activeTab === 'agents';
      const [cc24hRes, ccTrendRes, rRes, uRes, ctrlRes] = await Promise.allSettled([
        controlTab ? Promise.resolve(null) : fetchCoreCapabilities(tenant),
        controlTab ? Promise.resolve(null) : fetchCoreCapabilitiesTrend(tenant, 7),
        controlTab ? Promise.resolve(null) : fetchRecentRequests(tenant, 10, false),  // false = show observed task traffic (including task_non_value)
        fetchUsageSummary(tenant),
        fetchAgentControls(),
      ]);

      // Core capabilities for 四卡 (HeroMetrics)
      if (!controlTab && cc24hRes.status === 'fulfilled' && cc24hRes.value) {
        setCoreCap24h(cc24hRes.value);
      } else if (!controlTab) {
        const reason = cc24hRes.status === 'rejected' ? cc24hRes.reason : new Error('empty core capabilities response');
        failures.push(`coreCap24h: ${reason instanceof Error ? reason.message : String(reason)}`);
      }

      // Core capabilities trend for 四卡背面
      if (!controlTab && ccTrendRes.status === 'fulfilled' && ccTrendRes.value) {
        setCoreCapTrend(ccTrendRes.value);
      }

      if (!controlTab && rRes.status === 'fulfilled' && rRes.value) {
        // Overview shows observed task traffic (both task_non_value and value_qualified)
        // Live Request Flow reflects this observed traffic by default
        setRequests(rRes.value.requests.filter((req: RecentRequest) => req.request_class !== 'internal'));
      } else if (!controlTab) {
        const reason = rRes.status === 'rejected' ? rRes.reason : new Error('empty recent response');
        failures.push(`recent: ${reason instanceof Error ? reason.message : String(reason)}`);
      }

      if (uRes.status === 'fulfilled') {
        setUsage(uRes.value);
      } else {
        failures.push(`usage: ${uRes.reason instanceof Error ? uRes.reason.message : String(uRes.reason)}`);
      }

      // Fetch agent controls for unified activity truth
      if (ctrlRes.status === 'fulfilled' && ctrlRes.value) {
        setAgentControls(ctrlRes.value.agents ?? []);
      } else if (ctrlRes.status === 'rejected') {
        failures.push(`controls: ${ctrlRes.reason instanceof Error ? ctrlRes.reason.message : String(ctrlRes.reason)}`);
      }

      setError(failures.length ? failures.join(' | ') : null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingMetrics(false);
    }
  }, [tenant, activeTab]);

  useEffect(() => {
    fetchTenants()
      .then((list) => setTenants(['all', ...list.filter((t) => t !== 'all')]))
      .catch(() => setTenants(['all']));
  }, []);

  // Read highlight param on mount
  useEffect(() => {
    const highlightParam = new URLSearchParams(window.location.search).get('highlight');
    if (highlightParam) setHighlightFamilyId(highlightParam);
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    params.set('tenant', tenant);
    params.set('tab', activeTab);
    if (highlightFamilyId) params.set('highlight', highlightFamilyId);
    const targetPath = buildPathForTab(activeTab);
    window.history.replaceState({}, '', `${targetPath}?${params.toString()}`);
    loadMetrics();
    const interval = setInterval(loadMetrics, 5000);
    return () => clearInterval(interval);
  }, [loadMetrics, tenant, activeTab, highlightFamilyId]);

  const handleSelectRequest = useCallback(async (req: RecentRequest) => {
    setSelectedRequest(req);
    setLoadingEvidence(true);
    setRequestEvidence(null);

    try {
      const evidence = await fetchRequestEvidence(req.request_id).catch(() => null);
      setRequestEvidence(evidence);
    } catch {
      // ignore failures
    } finally {
      setLoadingEvidence(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab !== 'overview') return;

    const eligibleRequests = rankRecentRequests(
      requests.filter((req) => !isInternalEvent(req.query, req.agent))
    );

    if (eligibleRequests.length === 0) {
      setSelectedRequest(null);
      setRequestEvidence(null);
      return;
    }
    const newest = eligibleRequests[0];
    if (_selectedRequest?.request_id === newest.request_id) return;
    void handleSelectRequest(newest);
  }, [requests, activeTab, _selectedRequest, handleSelectRequest]);

  const handleAgentUsageClick = useCallback((familyId: string) => {
    setHighlightFamilyId(familyId);
    setActiveTab('agents');
    const params = new URLSearchParams(window.location.search);
    params.set('tab', 'agents');
    params.set('highlight', familyId);
    window.history.replaceState({}, '', `${window.location.pathname}?${params.toString()}`);
  }, []);

  // Auto-clear highlight after 3 seconds
  useEffect(() => {
    if (!highlightFamilyId) return;
    const timer = setTimeout(() => {
      setHighlightFamilyId(null);
      const params = new URLSearchParams(window.location.search);
      params.delete('highlight');
      window.history.replaceState({}, '', `${window.location.pathname}?${params.toString()}`);
    }, 3000);
    return () => clearTimeout(timer);
  }, [highlightFamilyId]);

  // Calculate active counts from AgentControlCard.active field (unified activity truth)
  // This ensures overview active(*) matches the Agent control card's active status
  const now = Date.now();
  const isWithinWindow = (isoTime: string | null | undefined, windowMinutes: number): boolean => {
    if (!isoTime) return false;
    try {
      const lastSeen = new Date(isoTime).getTime();
      return (now - lastSeen) <= windowMinutes * 60 * 1000;
    } catch {
      return false;
    }
  };

  const activeAgentControls = agentControls.filter(ctrl => ctrl.active);
  const live5mCount = activeAgentControls.filter(ctrl => isWithinWindow(ctrl.last_seen_at, 5)).length;
  const live24hCount = activeAgentControls.filter(ctrl => isWithinWindow(ctrl.last_seen_at, 1440)).length;
  const recentRequestFamilies = useMemo(
    () => normalizeRecentRequestUsageList(requests),
    [requests]
  );
  const usageFamilies = useMemo(
    () => normalizeAgentUsageList(usage?.by_agent ?? []),
    [usage?.by_agent]
  );

  // Overview prefers cleaned request evidence when available.
  const historicalAgentCount = recentRequestFamilies.length > 0 ? recentRequestFamilies.length : usageFamilies.length;

  const agentBreakdownRows = useMemo(() => {
    const requestFamiliesById = new Map(recentRequestFamilies.map((item) => [item.family, item]));
    const usageFamiliesById = new Map(usageFamilies.map((item) => [item.family, item]));
    const seenFamilies = new Set<string>();

    const rows = agentControls.map((ctrl) => {
      seenFamilies.add(ctrl.family_id);
      const has24hFields =
        ctrl.requests_24h !== undefined ||
        ctrl.saved_tokens_24h !== undefined ||
        ctrl.savings_ratio_24h !== undefined;

      if (has24hFields) {
        return {
          agent: ctrl.family_id,
          requests: ctrl.requests_24h ?? 0,
          saved_tokens: ctrl.saved_tokens_24h ?? 0,
          savings_ratio: ctrl.savings_ratio_24h ?? 0,
          last_request_at: ctrl.last_request_at ?? null,
        };
      }

      const requestFallback = requestFamiliesById.get(ctrl.family_id);
      if (requestFallback) {
        return {
          agent: requestFallback.family,
          requests: requestFallback.requests,
          saved_tokens: requestFallback.savedTokens,
          savings_ratio: requestFallback.savingsRatio,
          last_request_at: requestFallback.lastRequestAt,
        };
      }

      const usageFallback = usageFamiliesById.get(ctrl.family_id);
      if (usageFallback) {
        return {
          agent: usageFallback.family,
          requests: usageFallback.requests,
          saved_tokens: usageFallback.savedTokens,
          savings_ratio: usageFallback.savingsRatio,
          last_request_at: usageFallback.lastRequestAt,
        };
      }

      return {
        agent: ctrl.family_id,
        requests: 0,
        saved_tokens: 0,
        savings_ratio: 0,
        last_request_at: null,
      };
    });

    for (const requestFamily of recentRequestFamilies) {
      if (seenFamilies.has(requestFamily.family)) {
        continue;
      }
      rows.push({
        agent: requestFamily.family,
        requests: requestFamily.requests,
        saved_tokens: requestFamily.savedTokens,
        savings_ratio: requestFamily.savingsRatio,
        last_request_at: requestFamily.lastRequestAt,
      });
    }

    return rows;
  }, [agentControls, recentRequestFamilies, usageFamilies]);

  const statusColor = error
    ? 'bg-red-500'
    : live5mCount > 0
      ? 'bg-emerald-500'
      : live24hCount > 0
        ? 'bg-amber-500'
        : 'bg-zinc-400';
  const statusText = error
    ? 'error'
    : live5mCount > 0
      ? 'active'
      : live24hCount > 0
        ? 'idle'
        : 'no-active';
  const hasRecentControlSignal = activeAgentControls.some((ctrl) => isWithinWindow(ctrl.last_seen_at, 5));
  const overviewHasOnlyControlSignal = activeTab === 'overview' && requests.length === 0 && hasRecentControlSignal;

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
      {/* Header */}
      <div className="bg-white dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-700 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">
              OmniMemora Dashboard
            </h1>
            <p className="text-xs text-zinc-400 mt-0.5">
              Memory Control Plane — real-time metrics
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-xs text-zinc-400">
              tenant:
            </div>
            <select
              value={tenant}
              onChange={(e) => setTenant(e.target.value)}
              className="text-xs font-mono border border-zinc-300 dark:border-zinc-700 rounded px-2 py-1 bg-white dark:bg-zinc-800 text-zinc-700 dark:text-zinc-200"
            >
              {tenants.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
              {!tenants.includes(tenant) && <option value={tenant}>{tenant}</option>}
            </select>
            <div className="text-xs text-zinc-400">
              active(5m): <span className="font-mono text-zinc-600 dark:text-zinc-300">{live5mCount}</span>
            </div>
            <div className="text-xs text-zinc-400">
              active(24h): <span className="font-mono text-zinc-600 dark:text-zinc-300">{live24hCount}</span>
            </div>
            <div className="text-xs text-zinc-400">
              history: <span className="font-mono text-zinc-600 dark:text-zinc-300">{historicalAgentCount}</span>
            </div>
            <div className={`w-2 h-2 rounded-full ${statusColor}`} />
            <span className="text-xs text-zinc-500">{statusText}</span>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="bg-white dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-700">
        <div className="max-w-6xl mx-auto px-6">
          <nav className="flex gap-1">
            <a
              href={buildHrefForTab('overview', tenant)}
              onClick={(e) => {
                e.preventDefault();
                setActiveTab('overview');
              }}
              className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-colors ${
                activeTab === 'overview'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
              }`}
            >
              总览
            </a>
            <a
              href={buildHrefForTab('agents', tenant)}
              onClick={(e) => {
                e.preventDefault();
                setActiveTab('agents');
              }}
              className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-colors ${
                activeTab === 'agents'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
              }`}
            >
              Agent 控制
            </a>
          </nav>
        </div>
      </div>

      {/* Main content */}
      <div className="max-w-6xl mx-auto px-6 py-6 space-y-6">
        {error && (
          <div className="bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-900 rounded-xl px-4 py-3 text-xs text-red-700 dark:text-red-300">
            Data refresh warning: {error}
          </div>
        )}
        {!error && overviewHasOnlyControlSignal && (
          <div className="bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-900 rounded-xl px-4 py-3 text-xs text-amber-800 dark:text-amber-200">
            Agent 卡片的 last_seen 包含控制层心跳；总览只显示真实请求（默认过滤 internal）。当前未检测到可展示的真实请求。
          </div>
        )}

        {activeTab === 'overview' && (
          <>
            {/* Module 1: Hero Metrics */}
            <section>
              <h2 className="text-sm font-semibold text-zinc-500 uppercase tracking-wider mb-3">
                ① Core Metrics
              </h2>
              {loadingMetrics ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {[...Array(4)].map((_, i) => (
                    <div key={i} className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-6 animate-pulse">
                      <div className="h-3 bg-zinc-200 dark:bg-zinc-700 rounded w-20 mb-3" />
                      <div className="h-8 bg-zinc-200 dark:bg-zinc-700 rounded w-16" />
                    </div>
                  ))}
                </div>
              ) : (
                <HeroMetrics
                  data={coreCap24h}
                  trendData={coreCapTrend}
                />
              )}
              {/* Observed Traffic Summary Strip */}
              {coreCap24h && (
                <div className="mt-3 flex items-center gap-6 text-xs">
                  <div className="flex items-center gap-1.5">
                    <span className="text-zinc-400">Observed Through Product</span>
                    <span className="font-mono font-semibold text-zinc-700 dark:text-zinc-200">{coreCap24h.observed_request_count.toLocaleString()}</span>
                  </div>
                  <div className="w-px h-3 bg-zinc-300 dark:bg-zinc-600" />
                  <div className="flex items-center gap-1.5">
                    <span className="text-zinc-400">Value Qualified</span>
                    <span className="font-mono font-semibold text-emerald-600 dark:text-emerald-400">{coreCap24h.cards.real_requests.count.toLocaleString()}</span>
                  </div>
                  <div className="w-px h-3 bg-zinc-300 dark:bg-zinc-600" />
                  <div className="flex items-center gap-1.5">
                    <span className="text-zinc-400">Non-Value</span>
                    <span className="font-mono font-semibold text-amber-600 dark:text-amber-400">{coreCap24h.non_value_count.toLocaleString()}</span>
                  </div>
                </div>
              )}
            </section>

            {/* Module 2: Agent Usage */}
            <section>
              <h2 className="text-sm font-semibold text-zinc-500 uppercase tracking-wider mb-3">
                ② Agent Breakdown
              </h2>
              <AgentUsagePanel
                agents={agentBreakdownRows}
                onAgentClick={handleAgentUsageClick}
                observedCounts={Object.fromEntries(
                  agentControls.map(c => [c.family_id, c.observed_requests_24h ?? 0])
                )}
              />
            </section>

            <section>
              <h2 className="text-sm font-semibold text-zinc-500 uppercase tracking-wider mb-3">
                ③ Live Request Flow
              </h2>
              <LiveRequestFlow requests={requests} onSelect={handleSelectRequest} selectedRequestId={_selectedRequest?.request_id ?? null} />
            </section>

            {/* Modules 3 & 4: Context Comparison + Call Chain */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <section>
                <h2 className="text-sm font-semibold text-zinc-500 uppercase tracking-wider mb-3">
                  ④ Context Before / After
                </h2>
                <ContextComparison evidence={requestEvidence} loading={loadingEvidence} />
              </section>

              <section>
                <h2 className="text-sm font-semibold text-zinc-500 uppercase tracking-wider mb-3">
                  ⑤ Call Chain
                </h2>
                <CallChainViz evidence={requestEvidence} loading={loadingEvidence} />
              </section>
            </div>
          </>
        )}

        {activeTab === 'agents' && (
          <AgentsDashboard highlightFamilyId={highlightFamilyId} />
        )}
      </div>
    </div>
  );
}
