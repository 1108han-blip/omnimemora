import { useState, useEffect, useCallback } from 'react';
import { HeroMetrics } from './components/HeroMetrics';
import { LiveRequestFlow } from './components/LiveRequestFlow';
import { ContextComparison } from './components/ContextComparison';
import { CallChainViz } from './components/CallChainViz';
import { AgentUsagePanel } from './components/AgentUsagePanel';
import { AgentsDashboard } from './components/AgentsDashboard';
import { fetchMetricsSummary, fetchRecentRequests, fetchContextDiff, fetchCallChain, fetchUsageSummary, fetchTenants, fetchLiveAgents } from './api';
import type { MetricsSummary, RecentRequest, ContextDiff, CallChain, UsageSummary, LiveAgent } from './types';

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
  const [summary, setSummary] = useState<MetricsSummary | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [liveAgents24h, setLiveAgents24h] = useState<LiveAgent[]>([]);
  const [liveAgents5m, setLiveAgents5m] = useState<LiveAgent[]>([]);
  const [requests, setRequests] = useState<RecentRequest[]>([]);
  const [_selectedRequest, setSelectedRequest] = useState<RecentRequest | null>(null);
  const [contextDiff, setContextDiff] = useState<ContextDiff | null>(null);
  const [callChain, setCallChain] = useState<CallChain | null>(null);
  const [loadingMetrics, setLoadingMetrics] = useState(true);
  const [loadingDiff, setLoadingDiff] = useState(false);
  const [loadingChain, setLoadingChain] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadMetrics = useCallback(async () => {
    const failures: string[] = [];
    try {
      const [sRes, rRes, uRes, l24Res, l5Res] = await Promise.allSettled([
        fetchMetricsSummary(tenant),
        fetchRecentRequests(tenant, 30),
        fetchUsageSummary(tenant),
        fetchLiveAgents(1440),
        fetchLiveAgents(5),
      ]);

      if (sRes.status === 'fulfilled') {
        setSummary(sRes.value);
      } else {
        failures.push(`summary: ${sRes.reason instanceof Error ? sRes.reason.message : String(sRes.reason)}`);
      }

      if (rRes.status === 'fulfilled') {
        setRequests(rRes.value.requests);
      } else {
        failures.push(`recent: ${rRes.reason instanceof Error ? rRes.reason.message : String(rRes.reason)}`);
      }

      if (uRes.status === 'fulfilled') {
        const usageValue = uRes.value;
        const requestCounts: Record<string, number> = {};
        if (rRes.status === 'fulfilled') {
          for (const req of rRes.value.requests) {
            requestCounts[req.agent] = (requestCounts[req.agent] ?? 0) + 1;
          }
        }
        const usageWithFallback = {
          ...usageValue,
          by_agent: usageValue.by_agent.map((agent) => ({
            ...agent,
            requests: agent.requests > 0 ? agent.requests : (requestCounts[agent.agent] ?? 0),
          })),
        };
        setUsage(usageWithFallback);
      } else {
        failures.push(`usage: ${uRes.reason instanceof Error ? uRes.reason.message : String(uRes.reason)}`);
      }

      if (l24Res.status === 'fulfilled') {
        setLiveAgents24h(l24Res.value);
      } else {
        failures.push(`live24h: ${l24Res.reason instanceof Error ? l24Res.reason.message : String(l24Res.reason)}`);
      }

      if (l5Res.status === 'fulfilled') {
        setLiveAgents5m(l5Res.value);
      } else {
        failures.push(`live5m: ${l5Res.reason instanceof Error ? l5Res.reason.message : String(l5Res.reason)}`);
      }

      setError(failures.length ? failures.join(' | ') : null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingMetrics(false);
    }
  }, [tenant]);

  useEffect(() => {
    fetchTenants()
      .then((list) => setTenants(['all', ...list.filter((t) => t !== 'all')]))
      .catch(() => setTenants(['all']));
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    params.set('tenant', tenant);
    params.set('tab', activeTab);
    const targetPath = buildPathForTab(activeTab);
    window.history.replaceState({}, '', `${targetPath}?${params.toString()}`);
    loadMetrics();
    const interval = setInterval(loadMetrics, 5000);
    return () => clearInterval(interval);
  }, [loadMetrics, tenant, activeTab]);

  const handleSelectRequest = useCallback(async (req: RecentRequest) => {
    setSelectedRequest(req);
    setLoadingDiff(true);
    setLoadingChain(true);
    setContextDiff(null);
    setCallChain(null);

    try {
      const [diff, chain] = await Promise.all([
        fetchContextDiff(req.request_id).catch(() => null),
        fetchCallChain(req.request_id).catch(() => null),
      ]);
      setContextDiff(diff);
      setCallChain(chain);
    } catch {
      // ignore individual failures
    } finally {
      setLoadingDiff(false);
      setLoadingChain(false);
    }
  }, []);

  const historicalAgentCount = usage?.by_agent.length ?? 0;
  const live24hCount = liveAgents24h.length;
  const live5mCount = liveAgents5m.length;
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
              Agent 监控
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
              ) : summary ? (
                <HeroMetrics data={summary} />
              ) : null}
            </section>

            {/* Module 2: Live Request Flow */}
            <section>
              <h2 className="text-sm font-semibold text-zinc-500 uppercase tracking-wider mb-3">
                ② Agent Breakdown
              </h2>
              <AgentUsagePanel agents={usage?.by_agent ?? []} />
            </section>

            <section>
              <h2 className="text-sm font-semibold text-zinc-500 uppercase tracking-wider mb-3">
                ③ Live Request Flow
              </h2>
              <LiveRequestFlow requests={requests} onSelect={handleSelectRequest} />
            </section>

            {/* Modules 3 & 4: Context Comparison + Call Chain */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <section>
                <h2 className="text-sm font-semibold text-zinc-500 uppercase tracking-wider mb-3">
                  ④ Context Before / After
                </h2>
                <ContextComparison diff={contextDiff} loading={loadingDiff} />
              </section>

              <section>
                <h2 className="text-sm font-semibold text-zinc-500 uppercase tracking-wider mb-3">
                  ⑤ Call Chain
                </h2>
                <CallChainViz chain={callChain} loading={loadingChain} />
              </section>
            </div>
          </>
        )}

        {activeTab === 'agents' && (
          <AgentsDashboard />
        )}
      </div>
    </div>
  );
}
