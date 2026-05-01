import type { DesktopCommandResult, DesktopStatus } from './types';

const DEFAULT_STATUS: DesktopStatus = {
  app_version: '1.0.0-beta.2',
  data_dir: '~/.omnimemora/app/current',
  services: [
    {
      name: 'runtime',
      port: 8765,
      state: 'unknown',
      url: 'http://127.0.0.1:8765/health',
      detail: 'Waiting for desktop host status.',
      managed_by_desktop: false,
      pid: null,
    },
    {
      name: 'adapter',
      port: 18011,
      state: 'unknown',
      url: 'http://127.0.0.1:18011/health',
      detail: 'Waiting for desktop host status.',
      managed_by_desktop: false,
      pid: null,
    },
    {
      name: 'ui',
      port: 5173,
      state: 'unknown',
      url: 'http://127.0.0.1:5173/',
      detail: 'Waiting for desktop host status.',
      managed_by_desktop: false,
      pid: null,
    },
  ],
  updates: [
    {
      layer: 'desktop_shell',
      current_version: '1.0.0-beta.2',
      available_version: null,
      status: 'not_checked',
      detail: 'Desktop shell updates are installer-based in this beta.',
    },
    {
      layer: 'local_components',
      current_version: '1.0.0-beta.2',
      available_version: null,
      status: 'not_checked',
      detail: 'Local component updates use release manifests.',
    },
    {
      layer: 'cloud_policy',
      current_version: 'local-active',
      available_version: null,
      status: 'not_checked',
      detail: 'Cloud policy candidates never auto-promote.',
    },
  ],
  feedback_email: 'support@doloclaw.com',
};

async function invokeDesktop<T>(command: string): Promise<T> {
  if (!('__TAURI_INTERNALS__' in window)) {
    return Promise.reject(new Error('Tauri host is not available in browser preview.'));
  }
  const mod = await import('@tauri-apps/api/core');
  return mod.invoke<T>(command);
}

export async function getDesktopStatus(): Promise<DesktopStatus> {
  try {
    return await invokeDesktop<DesktopStatus>('get_desktop_status');
  } catch {
    return DEFAULT_STATUS;
  }
}

export async function runDesktopCommand(command: 'start_services' | 'stop_services' | 'restart_services' | 'check_for_updates' | 'install_update' | 'rollback'): Promise<DesktopCommandResult> {
  try {
    return await invokeDesktop<DesktopCommandResult>(command);
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : String(error),
      status: DEFAULT_STATUS,
    };
  }
}

export function buildFeedbackMailto(status: DesktopStatus): string {
  const subject = encodeURIComponent('OmniMemora Desktop Beta Feedback');
  const services = status.services.map((service) => `${service.name}:${service.state}`).join(',');
  const updates = status.updates.map((update) => `${update.layer}:${update.status}`).join(',');
  const body = encodeURIComponent([
    `version: ${status.app_version}`,
    `platform: ${navigator.userAgent || 'unknown'}`,
    `services: ${services}`,
    `updates: ${updates}`,
    'request_id: ',
    'error_code: ',
    'steps:',
    '- ',
  ].join('\n'));
  return `mailto:${status.feedback_email}?subject=${subject}&body=${body}`;
}
