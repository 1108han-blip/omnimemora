import { useCallback, useEffect, useMemo, useState } from 'react';
import { buildFeedbackMailto, getDesktopStatus, runAgentCommand, runDesktopCommand, scanAgents } from './desktopApi';
import type { AgentId, AgentStatus, DesktopCommandResult, DesktopStatus, ServiceStatus, UpdateLayerStatus } from './types';

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

export default function App() {
  const [status, setStatus] = useState<DesktopStatus | null>(null);
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [busyCommand, setBusyCommand] = useState<string | null>(null);
  const [message, setMessage] = useState<string>('Loading desktop status...');

  const refresh = useCallback(async () => {
    const next = await getDesktopStatus();
    setStatus(next);
    setMessage('Desktop status refreshed.');
  }, []);

  useEffect(() => {
    void refresh();
    void scanAgents().then(setAgents);
    const timer = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(timer);
  }, [refresh]);

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

  const run = useCallback(async (command: Parameters<typeof runDesktopCommand>[0]) => {
    setBusyCommand(command);
    setMessage(command === 'install_update' ? 'Installing update...' : 'Working...');
    try {
      const result: DesktopCommandResult = await runDesktopCommand(command);
      setMessage(result.message);
      if (result.status) setStatus(result.status);
    } finally {
      setBusyCommand(null);
    }
  }, []);

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
