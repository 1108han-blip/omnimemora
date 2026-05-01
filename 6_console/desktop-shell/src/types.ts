export type ServiceName = 'runtime' | 'adapter' | 'ui';
export type ServiceState = 'healthy' | 'unreachable' | 'unknown' | 'blocked';
export type UpdateLayer = 'desktop_shell' | 'local_components' | 'cloud_policy';
export type AgentId = 'claude' | 'openclaw' | 'codex';
export type AgentState = 'connected' | 'ready' | 'not_found';

export interface ServiceStatus {
  name: ServiceName;
  port: number;
  state: ServiceState;
  url: string;
  detail: string;
  managed_by_desktop: boolean;
  pid: number | null;
}

export interface UpdateLayerStatus {
  layer: UpdateLayer;
  current_version: string;
  available_version: string | null;
  status: 'current' | 'available' | 'not_checked' | 'blocked';
  detail: string;
}

export interface DesktopStatus {
  app_version: string;
  data_dir: string;
  services: ServiceStatus[];
  updates: UpdateLayerStatus[];
  feedback_email: string;
}

export interface DesktopCommandResult {
  ok: boolean;
  message: string;
  status: DesktopStatus | null;
}

export interface AgentStatus {
  id: AgentId;
  name: string;
  state: AgentState;
  installed: boolean;
  running: boolean;
  attached: boolean;
  supported: boolean;
  experimental: boolean;
  detail: string;
  config_path: string;
}
