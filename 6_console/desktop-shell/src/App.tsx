import { useCallback, useEffect, useMemo, useState } from 'react';
import { buildFeedbackMailto, getDesktopStatus, runDesktopCommand } from './desktopApi';
import type { DesktopCommandResult, DesktopStatus, ServiceStatus, UpdateLayerStatus } from './types';

function serviceLabel(name: ServiceStatus['name']): string {
  if (name === 'runtime') return 'Memory Runtime';
  if (name === 'adapter') return 'Product Gateway';
  return 'Control GUI';
}

function updateLabel(layer: UpdateLayerStatus['layer']): string {
  if (layer === 'desktop_shell') return 'Desktop App';
  if (layer === 'local_components') return 'Local Product Components';
  return 'Cloud Policy Candidate';
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

  const run = useCallback(async (command: Parameters<typeof runDesktopCommand>[0]) => {
    setBusyCommand(command);
    try {
      const result: DesktopCommandResult = await runDesktopCommand(command);
      setMessage(result.message);
      if (result.status) setStatus(result.status);
    } finally {
      setBusyCommand(null);
    }
  }, []);

  if (!status) {
    return <main className="shell"><section className="panel"><p>{message}</p></section></main>;
  }

  return (
    <main className="shell">
      <section className="hero panel">
        <div>
          <span className="eyebrow">OmniMemora Desktop Beta</span>
          <h1>Use OmniMemora without ports or terminal commands.</h1>
          <p>
            The desktop app is the user-facing control entry. It supervises the local runtime, gateway, and control GUI while keeping cloud policy updates candidate-only.
          </p>
        </div>
        <div className={allHealthy ? 'status healthy' : 'status warning'}>{shellState}</div>
      </section>

      <section className="grid">
        <div className="panel">
          <h2>Local Product</h2>
          <div className="cards">
            {status.services.map((service) => (
              <article className="card" key={service.name}>
                <div className="card-row">
                  <strong>{serviceLabel(service.name)}</strong>
                  <span className={`pill ${service.state}`}>{service.state}</span>
                </div>
                <p>{service.detail}</p>
                <code>{service.managed_by_desktop ? `managed pid: ${service.pid ?? 'unknown'}` : 'external or not managed by desktop'}</code>
              </article>
            ))}
          </div>
          <div className="actions">
            <button disabled={!!busyCommand} onClick={() => void run('start_services')}>Start</button>
            <button disabled={!!busyCommand} onClick={() => void run('restart_services')}>Restart</button>
            <button disabled={!!busyCommand} onClick={() => void run('stop_services')}>Stop</button>
          </div>
        </div>

        <div className="panel">
          <h2>Three-Layer Updates</h2>
          <div className="cards">
            {status.updates.map((update) => (
              <article className="card" key={update.layer}>
                <div className="card-row">
                  <strong>{updateLabel(update.layer)}</strong>
                  <span className={`pill ${update.status}`}>{update.status}</span>
                </div>
                <p>{update.detail}</p>
                <code>current: {update.current_version}</code>
                {update.available_version && <code>available: {update.available_version}</code>}
              </article>
            ))}
          </div>
          <div className="actions">
            <button disabled={!!busyCommand} onClick={() => void run('check_for_updates')}>Check</button>
            <button disabled={!!busyCommand} onClick={() => void run('install_update')}>Install Components</button>
            <button disabled={!!busyCommand} onClick={() => void run('rollback')}>Rollback</button>
          </div>
        </div>
      </section>

      <section className="panel footer-panel">
        <div>
          <h2>Support</h2>
          <p>{message}</p>
          <p className="muted">Version {status.app_version}. Data directory: {status.data_dir}</p>
          <p className="muted">Advanced diagnostics show ports, but users do not need to open them manually.</p>
          <p className="muted">Agent access: Claude Code ready, OpenClaw ready, Codex experimental and off by default.</p>
        </div>
        <a className="feedback" href={buildFeedbackMailto(status)}>Send Feedback</a>
      </section>
    </main>
  );
}
