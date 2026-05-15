import { useState, useEffect, useCallback, useMemo, useRef, useReducer } from 'react';
import { HeroMetrics } from './components/HeroMetrics';
import { LiveRequestFlow } from './components/LiveRequestFlow';
import { ContextComparison } from './components/ContextComparison';
import { CallChainViz } from './components/CallChainViz';
import { SkillSuggestionsPanel } from './components/SkillSuggestionsPanel';
import { AgentUsagePanel } from './components/AgentUsagePanel';
import { AgentsDashboard } from './components/AgentsDashboard';
import { fetchRecentRequests, fetchUsageSummary, fetchTenants, fetchAgentControls, fetchRequestEvidence, fetchCoreCapabilities, fetchCoreCapabilitiesTrend } from './api';
import type { RecentRequest, UsageSummary, AgentControlCard, RequestEvidence, CoreCapabilitiesResponse, CoreCapabilitiesTrendResponse } from './types';
import { SUPPORT_EMAIL, buildFeedbackMailto } from './feedback';
import { isInternalEvent, normalizeAgentUsageList, normalizeRecentRequestUsageList, rankRecentRequests } from './utils/familyNormalization';

const OVERVIEW_METRICS_POLL_MS = 5000;
const OVERVIEW_CONTROLS_SNAPSHOT_MS = 60000;
const CONTROL_FAILURE_BACKOFF_BASE_MS = 5000;
const CONTROL_FAILURE_BACKOFF_MAX_MS = 60000;
const HERO_SKELETON_KEYS = ['real-requests', 'context-compression', 'memory-enhancement', 'token-savings'] as const;

interface OverviewState {
  usage: UsageSummary | null;
  agentControls: AgentControlCard[];
  requests: RecentRequest[];
  loadingMetrics: boolean;
  error: string | null;
  coreCap24h: CoreCapabilitiesResponse | null;
  coreCapTrend: CoreCapabilitiesTrendResponse | null;
}

interface RequestSelectionState {
  selectedRequest: RecentRequest | null;
  requestEvidence: RequestEvidence | null;
  loadingEvidence: boolean;
}

const INITIAL_OVERVIEW_STATE: OverviewState = {
  usage: null,
  agentControls: [],
  requests: [],
  loadingMetrics: true,
  error: null,
  coreCap24h: null,
  coreCapTrend: null,
};

const INITIAL_REQUEST_SELECTION_STATE: RequestSelectionState = {
  selectedRequest: null,
  requestEvidence: null,
  loadingEvidence: false,
};

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

function replaceDashboardUrl(tenant: string, tab: 'overview' | 'agents', highlight: string | null = null) {
  const params = new URLSearchParams(window.location.search);
  params.set('tenant', tenant);
  params.set('tab', tab);
  if (highlight) {
    params.set('highlight', highlight);
  } else {
    params.delete('highlight');
  }
  window.history.replaceState({}, '', `${buildPathForTab(tab)}?${params.toString()}`);
}

function PersonalValueLoopPanel({
  request,
  wrapperCount,
}: {
  request: RecentRequest | null;
  wrapperCount: number;
}) {
  const valuePaths = request?.value_paths ?? [];
  const helped = request?.request_class === 'value_qualified' && valuePaths.length > 0;
  const status = helped ? 'Working' : request ? 'Not helping yet' : 'Only observing';
  const statusClass = helped
    ? 'text-emerald-700 bg-emerald-50 border-emerald-200 dark:text-emerald-300 dark:bg-emerald-950 dark:border-emerald-900'
    : request
      ? 'text-amber-800 bg-amber-50 border-amber-200 dark:text-amber-200 dark:bg-amber-950 dark:border-amber-900'
      : 'text-zinc-600 bg-zinc-50 border-zinc-200 dark:text-zinc-300 dark:bg-zinc-900 dark:border-zinc-700';

  const visibleQuery = (request?.user_visible_query || request?.query || '').trim();

  return (
    <section className={`rounded-xl border px-5 py-4 ${statusClass}`}>
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="text-sm font-semibold">Personal Value Loop</h2>
          <p className="mt-1 text-xs opacity-80">
            {helped
              ? `OmniMemora used ${valuePaths.length} value path(s): ${valuePaths.join(', ')}.`
              : request
                ? `No memory was used because ${request.qualification_reason || 'no value path was detected'}.`
                : wrapperCount > 0
                  ? `Only wrapper/context envelope traffic was observed. No user task reached the value loop yet.`
                  : `No recent user-visible task was observed.`}
          </p>
          {visibleQuery && (
            <p className="mt-2 max-w-3xl truncate font-mono text-[11px] opacity-70" title={visibleQuery}>
              Latest task: {visibleQuery}
            </p>
          )}
        </div>
        <div className="shrink-0 rounded-full border border-current px-3 py-1 text-[11px] font-semibold">
          {status}
        </div>
      </div>
    </section>
  );
}

export default function App() {
  const [overviewState, setOverviewState] = useReducer(
    (state: OverviewState, patch: Partial<OverviewState>) => ({ ...state, ...patch }),
    INITIAL_OVERVIEW_STATE
  );
  const [requestSelectionState, setRequestSelectionState] = useReducer(
    (state: RequestSelectionState, patch: Partial<RequestSelectionState>) => ({ ...state, ...patch }),
    INITIAL_REQUEST_SELECTION_STATE
  );
  const [tenant, setTenant] = useState<string>(() => {
    const fromUrl = new URLSearchParams(window.location.search).get('tenant');
    return fromUrl || 'all';
  });
  const [tenants, setTenants] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<'overview' | 'agents'>(() => inferInitialTab());
  const [highlightFamilyId, setHighlightFamilyId] = useState<string | null>(
    () => new URLSearchParams(window.location.search).get('highlight')
  );
  const { usage, agentControls, requests, loadingMetrics, error, coreCap24h, coreCapTrend } = overviewState;
  const { selectedRequest, requestEvidence, loadingEvidence } = requestSelectionState;
  const isPageVisibleRef = useRef<boolean>(document.visibilityState === 'visible');
  const controlsBackoffMsRef = useRef<number>(0);
  const controlsPollTimerRef = useRef<number | null>(null);

  const clearControlsPollTimer = useCallback(() => {
    if (controlsPollTimerRef.current !== null) {
      window.clearTimeout(controlsPollTimerRef.current);
      controlsPollTimerRef.current = null;
    }
  }, []);

  const loadOverviewMetrics = useCallback(async () => {
    const failures: string[] = [];
    try {
      const [cc24hRes, ccTrendRes, rRes, uRes] = await Promise.allSettled([
        fetchCoreCapabilities(tenant),
        fetchCoreCapabilitiesTrend(tenant, 7),
        fetchRecentRequests(tenant, 10, false),  // false = show observed task traffic (including task_non_value)
        fetchUsageSummary(tenant),
      ]);

      // Core capabilities for 四卡 (HeroMetrics)
      if (cc24hRes.status === 'fulfilled' && cc24hRes.value) {
        setOverviewState({ coreCap24h: cc24hRes.value });
      } else {
        const reason = cc24hRes.status === 'rejected' ? cc24hRes.reason : new Error('empty core capabilities response');
        failures.push(`coreCap24h: ${reason instanceof Error ? reason.message : String(reason)}`);
      }

      // Core capabilities trend for 四卡背面
      if (ccTrendRes.status === 'fulfilled' && ccTrendRes.value) {
        setOverviewState({ coreCapTrend: ccTrendRes.value });
      }

      if (rRes.status === 'fulfilled' && rRes.value) {
        // Overview shows observed task traffic (both task_non_value and value_qualified)
        // Live Request Flow reflects this observed traffic by default
        setOverviewState({
          requests: rRes.value.requests.filter((req: RecentRequest) => req.request_class !== 'internal'),
        });
      } else {
        const reason = rRes.status === 'rejected' ? rRes.reason : new Error('empty recent response');
        failures.push(`recent: ${reason instanceof Error ? reason.message : String(reason)}`);
      }

      if (uRes.status === 'fulfilled') {
        setOverviewState({ usage: uRes.value });
      } else {
        failures.push(`usage: ${uRes.reason instanceof Error ? uRes.reason.message : String(uRes.reason)}`);
      }

      setOverviewState({ error: failures.length ? failures.join(' | ') : null });
    } catch (e) {
      setOverviewState({ error: e instanceof Error ? e.message : String(e) });
    } finally {
      setOverviewState({ loadingMetrics: false });
    }
  }, [tenant]);

  const loadOverviewControlsSnapshot = useCallback(async (): Promise<boolean> => {
    try {
      const payload = await fetchAgentControls();
      setOverviewState({ agentControls: payload.agents ?? [] });
      controlsBackoffMsRef.current = 0;
      return true;
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setOverviewState({ error: `controls: ${message}` });
      const prev = controlsBackoffMsRef.current || CONTROL_FAILURE_BACKOFF_BASE_MS;
      controlsBackoffMsRef.current = Math.min(prev * 2, CONTROL_FAILURE_BACKOFF_MAX_MS);
      return false;
    }
  }, []);

  useEffect(() => {
    fetchTenants()
      .then((list) => setTenants(['all', ...list.filter((t) => t !== 'all')]))
      .catch(() => setTenants(['all']));
  }, []);

  useEffect(() => {
    if (activeTab !== 'overview') return;
    void loadOverviewMetrics();
    const interval = window.setInterval(() => {
      void loadOverviewMetrics();
    }, OVERVIEW_METRICS_POLL_MS);
    return () => window.clearInterval(interval);
  }, [activeTab, loadOverviewMetrics]);

  useEffect(() => {
    clearControlsPollTimer();
    if (activeTab !== 'overview') return;

    let cancelled = false;
    const tick = async () => {
      if (cancelled || activeTab !== 'overview' || document.visibilityState !== 'visible') return;
      const ok = await loadOverviewControlsSnapshot();
      if (!cancelled && activeTab === 'overview' && document.visibilityState === 'visible') {
        const failureBackoff = controlsBackoffMsRef.current;
        const nextDelay = ok
          ? OVERVIEW_CONTROLS_SNAPSHOT_MS
          : Math.max(CONTROL_FAILURE_BACKOFF_BASE_MS, failureBackoff);
        controlsPollTimerRef.current = window.setTimeout(() => {
          void tick();
        }, nextDelay);
      }
    };

    const onVisibilityChange = () => {
      isPageVisibleRef.current = document.visibilityState === 'visible';
      clearControlsPollTimer();
      if (isPageVisibleRef.current) void tick();
    };

    document.addEventListener('visibilitychange', onVisibilityChange);
    if (isPageVisibleRef.current) void tick();

    return () => {
      cancelled = true;
      document.removeEventListener('visibilitychange', onVisibilityChange);
      clearControlsPollTimer();
    };
  }, [activeTab, tenant, loadOverviewControlsSnapshot, clearControlsPollTimer]);

  const handleSelectRequest = useCallback(async (req: RecentRequest) => {
    setRequestSelectionState({
      selectedRequest: req,
      loadingEvidence: true,
      requestEvidence: null,
    });

    try {
      const evidence = await fetchRequestEvidence(req.request_id).catch(() => null);
      setRequestSelectionState({ requestEvidence: evidence });
    } catch {
      // ignore failures
    } finally {
      setRequestSelectionState({ loadingEvidence: false });
    }
  }, []);

  useEffect(() => {
    if (activeTab !== 'overview') return;

    const eligibleRequests = rankRecentRequests(
      requests.filter((req) => !isInternalEvent(req.query, req.agent))
    );

    if (eligibleRequests.length === 0) {
      setRequestSelectionState({
        selectedRequest: null,
        requestEvidence: null,
      });
      return;
    }
    const newest = eligibleRequests[0];
    if (selectedRequest?.request_id === newest.request_id) return;
    void handleSelectRequest(newest);
  }, [requests, activeTab, selectedRequest, handleSelectRequest]);

  const handleAgentUsageClick = useCallback((familyId: string) => {
    setHighlightFamilyId(familyId);
    setActiveTab('agents');
    replaceDashboardUrl(tenant, 'agents', familyId);
  }, [tenant]);

  // Auto-clear highlight after 3 seconds
  useEffect(() => {
    if (!highlightFamilyId) return;
    const timer = setTimeout(() => {
      setHighlightFamilyId(null);
      replaceDashboardUrl(tenant, activeTab);
    }, 3000);
    return () => clearTimeout(timer);
  }, [activeTab, highlightFamilyId, tenant]);

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
  const latestUserVisibleRequest = useMemo(
    () => rankRecentRequests(requests.filter((req) => req.request_class !== 'internal' && !isInternalEvent(req.query, req.agent)))[0] ?? null,
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

  const feedbackHref = useMemo(
    () => (requestEvidence ? buildFeedbackMailto(requestEvidence) : null),
    [requestEvidence]
  );

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
  const internalOrWrapperCount = coreCap24h?.internal_or_wrapper_count ?? Math.max(
    0,
    (coreCap24h?.observed_request_count ?? 0) -
      (coreCap24h?.non_value_count ?? 0) -
      (coreCap24h?.cards.real_requests.count ?? 0)
  );

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
              onChange={(e) => {
                const nextTenant = e.target.value;
                setTenant(nextTenant);
                replaceDashboardUrl(nextTenant, activeTab, highlightFamilyId);
              }}
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
            <button
              type="button"
              onClick={() => {
                setActiveTab('overview');
                replaceDashboardUrl(tenant, 'overview', highlightFamilyId);
              }}
              aria-current={activeTab === 'overview' ? 'page' : undefined}
              className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-colors ${
                activeTab === 'overview'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
              }`}
            >
              总览
            </button>
            <button
              type="button"
              onClick={() => {
                setActiveTab('agents');
                replaceDashboardUrl(tenant, 'agents', highlightFamilyId);
              }}
              aria-current={activeTab === 'agents' ? 'page' : undefined}
              className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-colors ${
                activeTab === 'agents'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
              }`}
            >
              Agent 控制
            </button>
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
                  {HERO_SKELETON_KEYS.map((key) => (
                    <div key={key} className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 rounded-xl p-6 animate-pulse">
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
                  <div className="w-px h-3 bg-zinc-300 dark:bg-zinc-600" />
                  <div className="flex items-center gap-1.5">
                    <span className="text-zinc-400">Internal/Wrapper</span>
                    <span className="font-mono font-semibold text-zinc-500 dark:text-zinc-400">{internalOrWrapperCount.toLocaleString()}</span>
                  </div>
                </div>
              )}
              {coreCap24h && coreCap24h.observed_request_count > 0 && coreCap24h.cards.real_requests.count === 0 && (
                <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
                  当前 OmniMemora 只观察到流量，还没有证明“用了记忆”。Non-value 请求不会再把 token reduction 当作产品价值展示。
                </div>
              )}
            </section>

            <PersonalValueLoopPanel request={latestUserVisibleRequest} wrapperCount={internalOrWrapperCount} />

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
              <LiveRequestFlow
                requests={requests}
                runningAgents={agentControls.filter(ctrl => ctrl.process_running)}
                onSelect={handleSelectRequest}
                selectedRequestId={selectedRequest?.request_id ?? null}
              />
            </section>

            <section className="rounded-xl border border-zinc-200 bg-white px-5 py-4 dark:border-zinc-700 dark:bg-zinc-900">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Feedback</h2>
                  <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                    {requestEvidence
                      ? `Send prefilled feedback for request ${requestEvidence.request.request_id} to ${SUPPORT_EMAIL}.`
                      : `Select a real request first. Feedback stays disabled until request evidence is loaded.`}
                  </p>
                </div>
                {feedbackHref ? (
                  <a
                    href={feedbackHref}
                    className="inline-flex items-center justify-center rounded-lg bg-zinc-900 px-4 py-2 text-xs font-medium text-white hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
                  >
                    提交反馈
                  </a>
                ) : (
                  <button
                    type="button"
                    disabled
                    className="inline-flex items-center justify-center rounded-lg bg-zinc-300 px-4 py-2 text-xs font-medium text-zinc-500 dark:bg-zinc-700 dark:text-zinc-400"
                  >
                    提交反馈
                  </button>
                )}
              </div>
            </section>

            {/* Modules 4/5/6: Request Evidence Views */}
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
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

              <section>
                <h2 className="text-sm font-semibold text-zinc-500 uppercase tracking-wider mb-3">
                  ⑥ Skill Advisory
                </h2>
                <SkillSuggestionsPanel evidence={requestEvidence} loading={loadingEvidence} />
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
