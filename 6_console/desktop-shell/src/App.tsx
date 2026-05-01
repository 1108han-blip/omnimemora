import { useCallback, useEffect, useMemo, useState } from 'react';
import { buildFeedbackMailto, getDesktopStatus, getProductConsoleSnapshot, runAgentCommand, runDesktopCommand, scanAgents } from './desktopApi';
import type {
  AgentControlCard,
  AgentId,
  AgentStatus,
  DesktopCommandResult,
  DesktopStatus,
  ProductConsoleSnapshot,
  RecentRequest,
  ServiceStatus,
  UpdateLayerStatus,
} from './types';

const serviceCopy: Record<ServiceStatus['name'], { title: string; eyebrow: string; summary: string }> = {
  runtime: {
    title: 'Memory Runtime',
    eyebrow: 'Core plane',
    summary: 'Private local memory service that powers recall and token saving.',
  },
  adapter: {
    title: 'Product Gateway',
    eyebrow: 'Opt-in ingress',
    summary: 'Routes approved agent traffic into OmniMemora without exposing ports to users.',
  },
  ui: {
    title: 'Control Surface',
    eyebrow: 'Desktop GUI',
    summary: 'The user-facing console for startup, health, updates, and feedback.',
  },
};

const updateCopy: Record<UpdateLayerStatus['layer'], { title: string; eyebrow: string }> = {
  desktop_shell: { title: 'Desktop App', eyebrow: 'Installer' },
  local_components: { title: 'Local Components', eyebrow: 'Manifest update' },
  cloud_policy: { title: 'Cloud Policy', eyebrow: 'Candidate only' },
};

const agentCopy: Record<AgentId, { summary: string; accent: string }> = {
  claude: {
    summary: 'Connect Claude Code to OmniMemora through the product gateway after opt-in.',
    accent: 'Claude-ready',
  },
  openclaw: {
    summary: 'Attach OpenClaw with the stable marker and provider configuration.',
    accent: 'Recommended',
  },
  codex: {
    summary: 'Experimental connection path. Keep disabled unless you explicitly want to test it.',
    accent: 'Experimental',
  },
};

function statusTone(state: string): 'good' | 'attention' | 'neutral' | 'active' {
  if (state === 'healthy' || state === 'current' || state === 'connected') return 'good';
  if (state === 'available' || state === 'blocked' || state === 'unreachable') return 'attention';
  if (state === 'updating' || state === 'ready') return 'active';
  return 'neutral';
}

function serviceAction(service: ServiceStatus): string {
  if (service.state === 'healthy' && service.managed_by_desktop) return `Managed locally${service.pid ? ` · PID ${service.pid}` : ''}`;
  if (service.state === 'healthy') return 'Healthy external process detected';
  if (service.state === 'blocked') return 'Needs attention before desktop can start it';
  return 'Ready for desktop startup';
}

function statusMessage(shellState: string): string {
  if (shellState === 'Ready') return 'All local services are online and supervised.';
  if (shellState === 'Updating') return 'Installing component update with checksum and rollback protection.';
  if (shellState === 'Port blocked') return 'A local process is occupying a required service entry.';
  return 'Start OmniMemora from here. No terminal commands are required.';
}

function formatPercent(value: number | undefined | null): string {
  if (!Number.isFinite(value ?? NaN)) return '0%';
  const normalized = Math.abs(value as number) <= 1 ? (value as number) * 100 : (value as number);
  return `${Math.round(normalized)}%`;
}

function formatNumber(value: number | undefined | null): string {
  return new Intl.NumberFormat('en-US').format(Math.max(0, Math.round(value ?? 0)));
}

function formatTime(value: string | undefined | null): string {
  if (!value) return 'No recent request';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function requestTitle(request: RecentRequest): string {
  return request.user_visible_query || request.query || request.raw_query || request.task_type || request.request_id;
}

function requestTone(request: RecentRequest): 'good' | 'attention' | 'neutral' | 'active' {
  if (request.request_class === 'value_qualified') return 'good';
  if (request.bypass) return 'attention';
  if (request.request_class === 'internal') return 'neutral';
  return 'active';
}

function agentControlTone(agent: AgentControlCard): 'good' | 'attention' | 'neutral' | 'active' {
  if (agent.routing_enabled && agent.active) return 'good';
  if (agent.installed || agent.detected || agent.active) return 'active';
  if (agent.health_state === 'error') return 'attention';
  return 'neutral';
}

export default function App() {
  const [status, setStatus] = useState<DesktopStatus | null>(null);
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [productConsole, setProductConsole] = useState<ProductConsoleSnapshot | null>(null);
  const [loadingProductConsole, setLoadingProductConsole] = useState<boolean>(false);
  const [busyCommand, setBusyCommand] = useState<string | null>(null);
  const [message, setMessage] = useState<string>('Loading desktop status...');

  const refresh = useCallback(async () => {
    const next = await getDesktopStatus();
    setStatus(next);
    setMessage('Desktop status refreshed.');
  }, []);

  const refreshProductConsole = useCallback(async () => {
    setLoadingProductConsole(true);
    try {
      setProductConsole(await getProductConsoleSnapshot());
    } finally {
      setLoadingProductConsole(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    void refreshProductConsole();
    void scanAgents().then(setAgents);
    const timer = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(timer);
  }, [refresh, refreshProductConsole]);

  const allHealthy = useMemo(() => {
    return status?.services.every((service) => service.state === 'healthy') ?? false;
  }, [status]);

  const shellState = useMemo(() => {
    if (busyCommand === 'install_update') return 'Updating';
    if (status?.services.some((service) => service.state === 'blocked')) return 'Port blocked';
    if (allHealthy) return 'Ready';
    return 'Needs attention';
  }, [allHealthy, busyCommand, status]);

  const readyCount = useMemo(() => {
    return status?.services.filter((service) => service.state === 'healthy').length ?? 0;
  }, [status]);

  const updateAvailable = useMemo(() => {
    return status?.updates.some((update) => update.status === 'available') ?? false;
  }, [status]);

  const connectedCount = useMemo(() => agents.filter((agent) => agent.attached).length, [agents]);

  const recentRequests = useMemo(() => productConsole?.recent?.requests ?? [], [productConsole]);

  const latestValueRequest = useMemo(() => {
    return recentRequests.find((request) => request.request_class === 'value_qualified') ?? recentRequests[0] ?? null;
  }, [recentRequests]);

  const productAgents = useMemo(() => productConsole?.controls?.agents ?? [], [productConsole]);

  const run = useCallback(async (command: Parameters<typeof runDesktopCommand>[0]) => {
    setBusyCommand(command);
    setMessage(command === 'install_update' ? 'Installing update...' : 'Working...');
    try {
      const result: DesktopCommandResult = await runDesktopCommand(command);
      setMessage(result.message);
      if (result.status) setStatus(result.status);
      if (command === 'start_services' || command === 'restart_services' || command === 'install_update' || command === 'rollback') {
        void refreshProductConsole();
      }
    } finally {
      setBusyCommand(null);
    }
  }, [refreshProductConsole]);

  const rescanAgents = useCallback(async () => {
    setBusyCommand('scan_agents');
    setMessage('Scanning local AI tools...');
    try {
      const next = await scanAgents();
      setAgents(next);
      const found = next.filter((agent) => agent.installed || agent.running).length;
      setMessage(found ? `Found ${found} AI tool connection candidate(s).` : 'No AI tools detected yet. Manual connection cards remain available.');
    } finally {
      setBusyCommand(null);
    }
  }, []);

  const connectAgent = useCallback(async (agent: AgentId) => {
    setBusyCommand(`attach_${agent}`);
    setMessage(`Connecting ${agent}...`);
    try {
      const result = await runAgentCommand('attach_agent', agent);
      setMessage(result.message);
      if (result.status) setStatus(result.status);
      setAgents(await scanAgents());
    } finally {
      setBusyCommand(null);
    }
  }, []);

  const disconnectAgent = useCallback(async (agent: AgentId) => {
    setBusyCommand(`detach_${agent}`);
    setMessage(`Disconnecting ${agent}...`);
    try {
      const result = await runAgentCommand('detach_agent', agent);
      setMessage(result.message);
      if (result.status) setStatus(result.status);
      setAgents(await scanAgents());
    } finally {
      setBusyCommand(null);
    }
  }, []);

  if (!status) {
    return (
      <main className="app-shell loading-shell">
        <section className="loading-card">
          <div className="brand-orb" aria-hidden="true"><span /></div>
          <p>{message}</p>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <section className="hero-card">
        <div className="hero-copy">
          <div className="brand-lockup">
            <div className="brand-orb" aria-hidden="true"><span /></div>
            <div>
              <span className="eyebrow">OmniMemora Desktop Beta</span>
              <strong>Dolo Claw AI Memory</strong>
            </div>
          </div>
          <h1>Private AI memory, controlled from one calm desktop.</h1>
          <p>
            Start, repair, update, and send feedback from a single polished control surface. OmniMemora keeps ports and runtime details behind the app.
          </p>
          <div className="hero-actions" aria-label="Primary actions">
            <button className="primary" disabled={!!busyCommand || allHealthy} onClick={() => void run('start_services')}>
              {busyCommand === 'start_services' ? 'Starting...' : 'Start OmniMemora'}
            </button>
            <button className="secondary" disabled={!!busyCommand} onClick={() => void run('restart_services')}>
              Restart
            </button>
            <button className="ghost" disabled={!!busyCommand} onClick={() => void run('stop_services')}>
              Stop
            </button>
          </div>
        </div>

        <aside className={`command-center state-${statusTone(allHealthy ? 'healthy' : shellState === 'Port blocked' ? 'blocked' : 'unknown')}`}>
          <span className="status-kicker">System status</span>
          <strong>{shellState}</strong>
          <p>{statusMessage(shellState)}</p>
          <div className="signal-ring" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
        </aside>
      </section>

      <section className="metrics-strip" aria-label="Product summary">
        <article>
          <span>Services online</span>
          <strong>{readyCount}/3</strong>
          <p>Runtime, gateway, GUI</p>
        </article>
        <article>
          <span>Version</span>
          <strong>{status.app_version}</strong>
          <p>Controlled beta</p>
        </article>
        <article>
          <span>Updates</span>
          <strong>{updateAvailable ? 'Available' : 'Current'}</strong>
          <p>Manifest + rollback</p>
        </article>
        <article>
          <span>AI tools</span>
          <strong>{connectedCount}/{agents.length || 3}</strong>
          <p>GUI connection control</p>
        </article>
      </section>

      <section className="product-console">
        <div className="section-heading with-action">
          <div>
            <span className="eyebrow">5173 Product Console</span>
            <h2>Token-saving value, request evidence, and agent control.</h2>
            <p>
              The desktop app now keeps the original 5173 product modules inside the GUI: core metrics, live request flow,
              value loop, context comparison, call chain, skill suggestions, and agent usage.
            </p>
          </div>
          <button className="mini" disabled={loadingProductConsole} onClick={() => void refreshProductConsole()}>
            {loadingProductConsole ? 'Refreshing...' : 'Refresh Console'}
          </button>
        </div>

        {!productConsole?.online ? (
          <div className="console-empty">
            <div className="empty-orb" aria-hidden="true" />
            <div>
              <h3>Start OmniMemora to activate the product console.</h3>
              <p>
                Product metrics and request evidence come from the local gateway after the user starts the product. The GUI stays usable for setup,
                updates, and feedback while the product is offline.
              </p>
              <small>{productConsole?.error ?? 'Waiting for local product data.'}</small>
            </div>
          </div>
        ) : (
          <>
            <div className="capability-grid" aria-label="Core product capability cards">
              <article className="capability-card">
                <span>Real Requests</span>
                <strong>{formatNumber(productConsole.core?.cards.real_requests.count)}</strong>
                <p>{formatPercent(productConsole.core?.cards.real_requests.ratio)} value-qualified traffic</p>
              </article>
              <article className="capability-card">
                <span>Context Compression</span>
                <strong>{formatPercent(productConsole.core?.cards.context_compression.ratio)}</strong>
                <p>
                  {formatNumber(productConsole.core?.cards.context_compression.baseline_tokens)} →{' '}
                  {formatNumber(productConsole.core?.cards.context_compression.actual_tokens)} tokens
                </p>
              </article>
              <article className="capability-card">
                <span>Memory Enhancement</span>
                <strong>{formatPercent(productConsole.core?.cards.memory_enhancement.rate)}</strong>
                <p>{formatNumber(productConsole.core?.cards.memory_enhancement.memory_count)} memory cards used</p>
              </article>
              <article className="capability-card">
                <span>Token Savings</span>
                <strong>{formatNumber(productConsole.core?.cards.token_savings.saved_tokens)}</strong>
                <p>{formatPercent(productConsole.core?.cards.token_savings.ratio)} estimated saving</p>
              </article>
            </div>

            <div className="console-grid">
              <article className="console-module live-flow">
                <div className="module-head">
                  <span className="eyebrow">Live Request Flow</span>
                  <strong>{formatNumber(recentRequests.length)}</strong>
                </div>
                <div className="request-list">
                  {recentRequests.length ? recentRequests.map((request) => (
                    <div className="request-row" key={request.request_id}>
                      <span className={`status-dot tone-${requestTone(request)}`} aria-hidden="true" />
                      <div>
                        <strong>{requestTitle(request)}</strong>
                        <p>
                          {request.agent || 'unknown agent'} · {request.task_type || 'request'} · saved {formatNumber(request.saved_tokens)} tokens
                        </p>
                      </div>
                      <small>{formatTime(request.timestamp)}</small>
                    </div>
                  )) : (
                    <div className="module-empty">No requests yet. Connect an agent and run a real request to populate this flow.</div>
                  )}
                </div>
              </article>

              <article className="console-module value-loop">
                <div className="module-head">
                  <span className="eyebrow">Personal Value Loop</span>
                  <strong>{formatPercent(productConsole.usage?.average_savings_ratio)}</strong>
                </div>
                <h3>{latestValueRequest ? requestTitle(latestValueRequest) : 'No value-qualified request yet'}</h3>
                <p>
                  {latestValueRequest
                    ? `${latestValueRequest.packed_memory_count} memories packed · ${formatNumber(latestValueRequest.saved_tokens)} tokens saved · ${latestValueRequest.request_class.replace('_', ' ')}`
                    : 'The value loop will show what OmniMemora remembered, compressed, and saved after real user traffic arrives.'}
                </p>
                <div className="value-stats">
                  <span><strong>{formatNumber(productConsole.usage?.total_requests)}</strong>Total requests</span>
                  <span><strong>{formatNumber(productConsole.usage?.saved_tokens_total)}</strong>Tokens saved</span>
                  <span><strong>{formatTime(productConsole.usage?.last_request_at)}</strong>Last request</span>
                </div>
              </article>

              <article className="console-module mini-modules">
                <div className="module-head">
                  <span className="eyebrow">Evidence Modules</span>
                  <strong>3</strong>
                </div>
                <div className="evidence-grid">
                  <div>
                    <span>Context Before/After</span>
                    <p>{latestValueRequest ? `${formatNumber(latestValueRequest.saved_tokens)} tokens saved on selected request` : 'Select a request after traffic appears.'}</p>
                  </div>
                  <div>
                    <span>Call Chain</span>
                    <p>{latestValueRequest ? 'Request evidence is available from the local diagnostics layer.' : 'Waiting for a traceable request.'}</p>
                  </div>
                  <div>
                    <span>Skill Suggestions</span>
                    <p>Candidate suggestions stay visible as evidence, not silent automation.</p>
                  </div>
                </div>
              </article>

              <article className="console-module agent-usage-module">
                <div className="module-head">
                  <span className="eyebrow">Agent Usage</span>
                  <strong>{formatNumber(productAgents.length)}</strong>
                </div>
                <div className="agent-control-list">
                  {productAgents.length ? productAgents.map((agent) => (
                    <div className="agent-control-row" key={agent.family_id}>
                      <span className={`pill tone-${agentControlTone(agent)}`}>{agent.routing_enabled ? 'route on' : agent.active ? 'active' : agent.health_state}</span>
                      <div>
                        <strong>{agent.display_name}</strong>
                        <p>
                          {formatNumber(agent.requests_24h ?? agent.observed_requests_24h)} requests ·{' '}
                          {formatNumber(agent.saved_tokens_24h)} saved · {agent.traffic_truth ?? 'no traffic evidence'}
                        </p>
                      </div>
                    </div>
                  )) : (
                    <div className="module-empty">Agent usage cards appear here after the local product reports control status.</div>
                  )}
                </div>
              </article>
            </div>
          </>
        )}
      </section>

      <section className="agent-panel">
        <div className="section-heading with-action">
          <div>
            <span className="eyebrow">AI tool connections</span>
            <h2>Connect agents without terminal setup.</h2>
            <p>Scan finds local configs and running tools. If a tool is not found, use its manual connection card to create the config from the GUI.</p>
          </div>
          <button className="mini" disabled={!!busyCommand} onClick={() => void rescanAgents()}>
            {busyCommand === 'scan_agents' ? 'Scanning...' : 'Scan AI Tools'}
          </button>
        </div>
        <div className="agent-grid">
          {(agents.length ? agents : []).map((agent) => {
            const copy = agentCopy[agent.id];
            return (
              <article className={`agent-card ${agent.experimental ? 'is-experimental' : ''}`} key={agent.id}>
                <div className="agent-topline">
                  <span>{copy.accent}</span>
                  <span className={`pill tone-${statusTone(agent.state)}`}>{agent.state.replace('_', ' ')}</span>
                </div>
                <h3>{agent.name}</h3>
                <p>{copy.summary}</p>
                <small>{agent.detail}</small>
                <div className="agent-facts">
                  <span>{agent.installed ? 'Config found' : 'Config missing'}</span>
                  <span>{agent.running ? 'Running now' : 'Not running'}</span>
                </div>
                <div className="agent-actions">
                  <button className="secondary" disabled={!!busyCommand || agent.attached} onClick={() => void connectAgent(agent.id)}>
                    {busyCommand === `attach_${agent.id}` ? 'Connecting...' : agent.experimental ? 'Connect Experimental' : agent.installed || agent.running ? 'Connect' : 'Create Connection'}
                  </button>
                  <button className="ghost" disabled={!!busyCommand || !agent.attached} onClick={() => void disconnectAgent(agent.id)}>
                    Disconnect
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="content-grid">
        <div className="panel service-panel">
          <div className="section-heading">
            <span className="eyebrow">Local product</span>
            <h2>Service orchestration</h2>
          </div>
          <div className="service-list">
            {status.services.map((service) => {
              const copy = serviceCopy[service.name];
              return (
                <article className="service-card" key={service.name}>
                  <div className="service-icon" data-service={service.name} aria-hidden="true" />
                  <div>
                    <div className="card-head">
                      <span>{copy.eyebrow}</span>
                      <span className={`pill tone-${statusTone(service.state)}`}>{service.state.replace('_', ' ')}</span>
                    </div>
                    <h3>{copy.title}</h3>
                    <p>{copy.summary}</p>
                    <small>{serviceAction(service)}</small>
                  </div>
                </article>
              );
            })}
          </div>
        </div>

        <div className="panel update-panel">
          <div className="section-heading with-action">
            <div>
              <span className="eyebrow">Three-layer update</span>
              <h2>Safe upgrades</h2>
            </div>
            <button className="mini" disabled={!!busyCommand} onClick={() => void run('check_for_updates')}>
              Check Updates
            </button>
          </div>
          <div className="timeline">
            {status.updates.map((update, index) => {
              const copy = updateCopy[update.layer];
              return (
                <article className="timeline-row" key={update.layer}>
                  <div className="timeline-index">0{index + 1}</div>
                  <div>
                    <div className="card-head">
                      <span>{copy.eyebrow}</span>
                      <span className={`pill tone-${statusTone(update.status)}`}>{update.status.replace('_', ' ')}</span>
                    </div>
                    <h3>{copy.title}</h3>
                    <p>{update.detail}</p>
                    <small>
                      Current {update.current_version}{update.available_version ? ` · Available ${update.available_version}` : ''}
                    </small>
                  </div>
                </article>
              );
            })}
          </div>
          <div className="update-actions">
            <button className="secondary" disabled={!!busyCommand || !updateAvailable} onClick={() => void run('install_update')}>
              {busyCommand === 'install_update' ? 'Updating...' : 'Install Components'}
            </button>
            <button className="ghost" disabled={!!busyCommand} onClick={() => void run('rollback')}>
              Rollback
            </button>
          </div>
        </div>
      </section>

      <section className="support-panel">
        <div>
          <span className="eyebrow">Support packet</span>
          <h2>Feedback with diagnostics, not prompts.</h2>
          <p>{message}</p>
          <small>Agent connections are explicit and reversible · Codex remains experimental/off by default · Advanced diagnostics hide ports from normal setup.</small>
        </div>
        <a className="feedback" href={buildFeedbackMailto(status)}>Send Feedback</a>
      </section>
    </main>
  );
}
