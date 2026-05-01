import { useCallback, useEffect, useMemo, useState } from 'react';
import { buildFeedbackMailto, getDesktopStatus, runDesktopCommand } from './desktopApi';
import type { DesktopCommandResult, DesktopStatus, ServiceStatus, UpdateLayerStatus } from './types';

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

function statusTone(state: string): 'good' | 'attention' | 'neutral' | 'active' {
  if (state === 'healthy' || state === 'current') return 'good';
  if (state === 'available' || state === 'blocked' || state === 'unreachable') return 'attention';
  if (state === 'updating') return 'active';
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
  const [busyCommand, setBusyCommand] = useState<string | null>(null);
  const [message, setMessage] = useState<string>('Loading desktop status...');

  const refresh = useCallback(async () => {
    const next = await getDesktopStatus();
    setStatus(next);
    setMessage('Desktop status refreshed.');
  }, []);

  useEffect(() => {
    void refresh();
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
              Check
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
          <small>Claude Code ready · OpenClaw ready · Codex experimental/off by default · Advanced diagnostics hide ports from normal setup.</small>
        </div>
        <a className="feedback" href={buildFeedbackMailto(status)}>Send Feedback</a>
      </section>
    </main>
  );
}
