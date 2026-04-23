import { useCallback, useEffect, useMemo, useState } from 'react';
import type { AgentControlCard, SystemStatus } from '../types';
import {
  disableAgentRoute,
  enableAgentRoute,
  fetchAgentControls,
  installAgent,
  rescanAgentControls,
  uninstallAgent,
} from '../api';

const MODE_ACTIONS = {
  install: '接入 OmniMemora',
  uninstall: '恢復原配置',
  enable: '使用 OmniMemora',
  disable: '停用產品路由',
} as const;

interface RescanResult {
  status: 'added' | 'removed' | 'no_change';
  message: string;
  added: string[];
  removed: string[];
}

function formatRelativeTime(iso?: string | null): string {
  if (!iso) return '—';
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const secs = Math.floor(diff / 1000);
    if (secs < 60) return `${secs}秒前`;
    const mins = Math.floor(secs / 60);
    if (mins < 60) return `${mins}分钟前`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}小时前`;
    return `${Math.floor(hrs / 24)}天前`;
  } catch {
    return iso;
  }
}

function isHealthySystem(systemStatus: SystemStatus | null): boolean {
  return !!systemStatus && systemStatus.status === 'healthy' && systemStatus.gateway_health === 'healthy';
}

interface AgentsDashboardProps {
  highlightFamilyId?: string | null;
}

export function AgentsDashboard({ highlightFamilyId }: AgentsDashboardProps) {
  const [cards, setCards] = useState<AgentControlCard[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [rescanResult, setRescanResult] = useState<RescanResult | null>(null);

  const load = useCallback(async (mode: 'normal' | 'rescan' = 'normal') => {
    try {
      const payload = mode === 'rescan' ? await rescanAgentControls() : await fetchAgentControls();
      setCards(payload.agents ?? []);
      setSystemStatus(payload.system_status ?? null);
      if (mode === 'rescan' && payload.rescan_status) {
        setRescanResult({
          status: payload.rescan_status,
          message: payload.rescan_message ?? '',
          added: payload.rescan_added ?? [],
          removed: payload.rescan_removed ?? [],
        });
      }
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const interval = window.setInterval(() => {
      void load();
    }, 10000);
    return () => window.clearInterval(interval);
  }, [load]);

  // Auto-clear rescan feedback after 5 seconds
  useEffect(() => {
    if (!rescanResult) return;
    const timer = setTimeout(() => setRescanResult(null), 5000);
    return () => clearTimeout(timer);
  }, [rescanResult]);

  // Auto-clear highlight after 3 seconds
  useEffect(() => {
    if (!highlightFamilyId) return;
    const timer = setTimeout(() => {
      // Parent should clear highlightFamilyId via state; we just render the highlight here
    }, 3000);
    return () => clearTimeout(timer);
  }, [highlightFamilyId]);

  const healthy = useMemo(() => isHealthySystem(systemStatus), [systemStatus]);

  const applyAction = useCallback(async (action: 'install' | 'uninstall' | 'enable' | 'disable', familyId: string) => {
    const key = `${action}:${familyId}`;
    setBusyAction(key);
    try {
      if (action === 'install') await installAgent(familyId);
      if (action === 'uninstall') await uninstallAgent(familyId);
      if (action === 'enable') await enableAgentRoute(familyId);
      if (action === 'disable') await disableAgentRoute(familyId);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyAction(null);
    }
  }, [load]);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">正式控制入口</h2>
          <p className="text-xs text-zinc-400 mt-0.5">接入层与路由层分离；控制动作统一经 :18011</p>
        </div>
        <button
          type="button"
          onClick={() => void load('rescan')}
          className="rounded-lg border border-zinc-300 dark:border-zinc-700 px-3 py-2 text-xs text-zinc-700 dark:text-zinc-200 hover:bg-zinc-50 dark:hover:bg-zinc-800"
        >
          重新扫描
        </button>
      </div>

      {systemStatus && (
        <section className="rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="text-[11px] uppercase tracking-wider text-zinc-400">System Status</div>
              <div className="mt-1 text-base font-semibold text-zinc-900 dark:text-zinc-100">{systemStatus.status}</div>
            </div>
            <div className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${
              healthy ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300' : 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300'
            }`}>
              gateway={systemStatus.gateway_health} / capability={systemStatus.capability_health}
            </div>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 text-xs text-zinc-600 dark:text-zinc-300 md:grid-cols-2">
            <div>routing_requested: <span className="font-mono">{String(systemStatus.routing_requested)}</span></div>
            <div>routing_effective: <span className="font-mono">{String(systemStatus.routing_effective)}</span></div>
            <div>recommended_action: <span className="font-mono">{systemStatus.recommended_action || 'none'}</span></div>
            <div>error_code: <span className="font-mono">{systemStatus.error_code || '—'}</span></div>
          </div>
          {(systemStatus.transition_reason || systemStatus.status_source) && (
            <div className="mt-3 rounded-lg bg-zinc-50 px-3 py-2 text-xs text-zinc-500 dark:bg-zinc-800 dark:text-zinc-300">
              source={systemStatus.status_source || 'unknown'} · reason={systemStatus.transition_reason || '—'}
            </div>
          )}
        </section>
      )}

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      )}

      {rescanResult && (
        <div className={`rounded-xl border px-4 py-3 text-xs ${
          rescanResult.status === 'added'
            ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300'
            : rescanResult.status === 'removed'
            ? 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300'
            : 'border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300'
        }`}>
          {rescanResult.message}
        </div>
      )}

      {loading && cards.length === 0 ? (
        <div className="rounded-xl border border-zinc-200 bg-white p-8 dark:border-zinc-700 dark:bg-zinc-900">
          <div className="space-y-3 animate-pulse">
            {[...Array(3)].map((_, index) => (
              <div key={index} className="h-24 rounded bg-zinc-200 dark:bg-zinc-700" />
            ))}
          </div>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {cards.map((card) => {
            const disableInstall = busyAction !== null;
            const canEnable = card.installed && healthy && !card.routing_enabled;
            const canDisable = card.installed && card.routing_enabled;
            const actionKey = (action: string) => `${action}:${card.family_id}`;
            const isHighlighted = highlightFamilyId === card.family_id;
            return (
              <article
                key={card.family_id}
                className={`rounded-xl border p-5 shadow-sm transition-all duration-500 ${
                  isHighlighted
                    ? 'border-amber-400 bg-amber-50 ring-2 ring-amber-400 dark:bg-amber-950'
                    : 'border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-900'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">{card.display_name}</h3>
                    <p className="mt-1 text-xs font-mono text-zinc-500">{card.family_id}</p>
                  </div>
                  {/* Three-section truth surface */}
                  <div className="flex flex-col items-end gap-1">
                    {/* Integration truth */}
                    {card.integration_truth && (
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                        card.integration_truth === 'attached_with_backup'
                          ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                          : card.integration_truth === 'mcp_attached'
                          ? 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300'
                          : 'bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400'
                      }`}>
                        {card.integration_truth === 'attached_with_backup' ? '接入+備份' :
                         card.integration_truth === 'mcp_attached' ? 'MCP' : '未接入'}
                      </span>
                    )}
                    {/* Route truth */}
                    {card.route_truth && (
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                        card.route_truth === 'effective'
                          ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                          : card.route_truth === 'intent_on'
                          ? 'bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300'
                          : 'bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400'
                      }`}>
                        {card.route_truth === 'effective' ? '路由生效' :
                         card.route_truth === 'intent_on' ? '路由意圖' : '路由關閉'}
                      </span>
                    )}
                    {/* Traffic truth */}
                    {card.traffic_truth && (
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                        card.traffic_truth === 'real_request_observed'
                          ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                          : card.traffic_truth === 'internal_only'
                          ? 'bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300'
                          : 'bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400'
                      }`}>
                        {card.traffic_truth === 'real_request_observed' ? '真實流量' :
                         card.traffic_truth === 'internal_only' ? '僅內部' : '無證據'}
                      </span>
                    )}
                  </div>
                </div>

                <div className="mt-4 grid grid-cols-2 gap-2 text-xs text-zinc-600 dark:text-zinc-300">
                  <div>installed: <span className="font-mono">{String(card.installed)}</span></div>
                  <div>detected: <span className="font-mono">{String(card.detected)}</span></div>
                  <div>active: <span className="font-mono">{String(card.active)}</span></div>
                  <div>backup: <span className="font-mono">{String(card.backup_available)}</span></div>
                  <div>health: <span className="font-mono">{card.health_state}</span></div>
                  <div>last_seen: <span className="font-mono">{formatRelativeTime(card.last_seen_at)}</span></div>
                </div>

                <div className="mt-3 rounded-lg px-3 py-2 text-xs text-zinc-500 dark:bg-zinc-800 dark:text-zinc-300">
                  {card.truth_message || card.message || 'ready'}
                </div>

                {card.scope_note && (
                  <div className="mt-2 rounded-lg px-3 py-2 text-[11px] text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950">
                    {card.scope_note}
                  </div>
                )}

                <div className="mt-4 space-y-2">
                  <div className="text-[11px] uppercase tracking-wider text-zinc-400">接入层</div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={disableInstall || card.installed}
                      onClick={() => void applyAction('install', card.family_id)}
                      className="rounded-lg bg-zinc-900 px-3 py-2 text-xs text-white disabled:cursor-not-allowed disabled:bg-zinc-300 dark:bg-zinc-100 dark:text-zinc-900 dark:disabled:bg-zinc-700"
                    >
                      {busyAction === actionKey('install') ? '处理中...' : MODE_ACTIONS.install}
                    </button>
                    <button
                      type="button"
                      disabled={disableInstall || !card.installed}
                      onClick={() => void applyAction('uninstall', card.family_id)}
                      className="rounded-lg border border-zinc-300 px-3 py-2 text-xs text-zinc-700 disabled:cursor-not-allowed disabled:text-zinc-400 dark:border-zinc-700 dark:text-zinc-200 dark:disabled:text-zinc-500"
                    >
                      {busyAction === actionKey('uninstall') ? '处理中...' : MODE_ACTIONS.uninstall}
                    </button>
                  </div>
                </div>

                <div className="mt-4 space-y-2">
                  <div className="text-[11px] uppercase tracking-wider text-zinc-400">路由层</div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={disableInstall || !canEnable}
                      onClick={() => void applyAction('enable', card.family_id)}
                      className="rounded-lg bg-blue-600 px-3 py-2 text-xs text-white disabled:cursor-not-allowed disabled:bg-blue-300 dark:disabled:bg-blue-900"
                    >
                      {busyAction === actionKey('enable') ? '处理中...' : MODE_ACTIONS.enable}
                    </button>
                    <button
                      type="button"
                      disabled={disableInstall || !canDisable}
                      onClick={() => void applyAction('disable', card.family_id)}
                      className="rounded-lg border border-blue-300 px-3 py-2 text-xs text-blue-700 disabled:cursor-not-allowed disabled:text-blue-300 dark:border-blue-800 dark:text-blue-300 dark:disabled:text-blue-900"
                    >
                      {busyAction === actionKey('disable') ? '处理中...' : MODE_ACTIONS.disable}
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
