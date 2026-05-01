import { create } from 'zustand';
import { getDesktopStatus, getProductConsoleSnapshot, runDesktopCommand, scanAgents } from '../desktopApi';
import type { AgentStatus, DesktopStatus, ProductConsoleSnapshot } from '../types';

export type PageKey = 'overview' | 'live-flow' | 'agents' | 'policies' | 'context-debug' | 'savings' | 'settings';
export type Decision = 'COMPILED' | 'BYPASS' | 'FALLBACK';
export type AgentMode = 'Observe' | 'Guided' | 'Force' | 'Off';

export interface FlowEvent {
  id: string;
  at: string;
  agent: string;
  decision: Decision;
  beforeTokens: number;
  afterTokens: number;
  savingPct: number;
  rawContext: string;
  compiledContext: string;
  reason: string;
  path: {
    runtime: 'green' | 'red' | 'yellow';
    ingress: 'green' | 'red' | 'yellow';
    memory: 'green' | 'red' | 'yellow';
    policy: 'green' | 'red' | 'yellow';
  };
}

export interface AgentModel {
  id: string;
  name: string;
  usagePct: number;
  mode: AgentMode;
  requests: number;
  savedTokens: number;
  status: 'active' | 'idle' | 'missing';
}

export interface PolicyState {
  compressionLevel: number;
  fallbackEnabled: boolean;
  aggressiveMode: boolean;
}

interface DashboardState {
  page: PageKey;
  sidebarCollapsed: boolean;
  desktopStatus: DesktopStatus | null;
  product: ProductConsoleSnapshot | null;
  desktopAgents: AgentStatus[];
  flow: FlowEvent[];
  agents: AgentModel[];
  policies: PolicyState;
  lastMessage: string;
  loading: boolean;
  setPage: (page: PageKey) => void;
  toggleSidebar: () => void;
  refreshReality: () => Promise<void>;
  startProduct: () => Promise<void>;
  stopProduct: () => Promise<void>;
  restartProduct: () => Promise<void>;
  tickMock: () => void;
  setAgentMode: (id: string, mode: AgentMode) => void;
  setPolicy: <K extends keyof PolicyState>(key: K, value: PolicyState[K]) => void;
}

const agents: AgentModel[] = [
  { id: 'openclaw', name: 'OpenClaw', usagePct: 58, mode: 'Guided', requests: 128, savedTokens: 18240, status: 'active' },
  { id: 'claude', name: 'Claude Code', usagePct: 31, mode: 'Observe', requests: 74, savedTokens: 6810, status: 'active' },
  { id: 'codex', name: 'Codex', usagePct: 11, mode: 'Off', requests: 18, savedTokens: 2975, status: 'idle' },
];

const queries = [
  'Summarize the latest legal research and reuse prior case notes.',
  'Draft a contract risk memo with remembered client preferences.',
  'Refactor the adapter validation loop without losing product boundaries.',
  'Compare today\'s agent traffic against yesterday\'s memory savings.',
  'Generate a concise support response using known installation facts.',
];

function makeEvent(index: number): FlowEvent {
  const agent = agents[index % agents.length];
  const decision: Decision = index % 7 === 0 ? 'FALLBACK' : index % 5 === 0 ? 'BYPASS' : 'COMPILED';
  const before = 1800 + ((index * 337) % 4200);
  const saving = decision === 'COMPILED' ? 28 + ((index * 9) % 48) : decision === 'FALLBACK' ? 8 : 0;
  const after = Math.max(120, Math.round(before * (1 - saving / 100)));
  return {
    id: `req_${Date.now()}_${index}`,
    at: new Date().toISOString(),
    agent: agent.name,
    decision,
    beforeTokens: before,
    afterTokens: after,
    savingPct: saving,
    rawContext: queries[index % queries.length],
    compiledContext: decision === 'COMPILED' ? `Packed memory: client preference, product boundary, recent validation.\nTask: ${queries[index % queries.length]}` : 'Compilation not applied for this request.',
    reason: decision === 'COMPILED' ? 'High memory relevance and safe compression threshold.' : decision === 'FALLBACK' ? 'Fallback kept the request safe after weak memory confidence.' : 'Bypass because request was non-value or control-plane internal.',
    path: {
      runtime: 'green',
      ingress: decision === 'BYPASS' ? 'yellow' : 'green',
      memory: decision === 'FALLBACK' ? 'yellow' : 'green',
      policy: decision === 'COMPILED' ? 'green' : 'yellow',
    },
  };
}

const initialFlow = Array.from({ length: 16 }, (_, index) => makeEvent(index));

export const useDashboardStore = create<DashboardState>((set, get) => ({
  page: 'overview',
  sidebarCollapsed: false,
  desktopStatus: null,
  product: null,
  desktopAgents: [],
  flow: initialFlow,
  agents,
  policies: {
    compressionLevel: 62,
    fallbackEnabled: true,
    aggressiveMode: false,
  },
  lastMessage: 'Desktop control plane ready.',
  loading: false,
  setPage: (page) => set({ page }),
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  refreshReality: async () => {
    set({ loading: true });
    try {
      const [desktopStatus, product, desktopAgents] = await Promise.all([
        getDesktopStatus(),
        getProductConsoleSnapshot(),
        scanAgents(),
      ]);
      set({ desktopStatus, product, desktopAgents, lastMessage: product.online ? 'Product console synced.' : 'Product console waiting for local services.' });
    } finally {
      set({ loading: false });
    }
  },
  startProduct: async () => {
    set({ loading: true, lastMessage: 'Starting OmniMemora...' });
    try {
      const result = await runDesktopCommand('start_services');
      set({ desktopStatus: result.status, lastMessage: result.message });
      await get().refreshReality();
    } finally {
      set({ loading: false });
    }
  },
  stopProduct: async () => {
    set({ loading: true, lastMessage: 'Stopping OmniMemora...' });
    try {
      const result = await runDesktopCommand('stop_services');
      set({ desktopStatus: result.status, lastMessage: result.message });
      await get().refreshReality();
    } finally {
      set({ loading: false });
    }
  },
  restartProduct: async () => {
    set({ loading: true, lastMessage: 'Restarting OmniMemora...' });
    try {
      const result = await runDesktopCommand('restart_services');
      set({ desktopStatus: result.status, lastMessage: result.message });
      await get().refreshReality();
    } finally {
      set({ loading: false });
    }
  },
  tickMock: () => set((state) => ({ flow: [makeEvent(state.flow.length + 1), ...state.flow].slice(0, 80) })),
  setAgentMode: (id, mode) => set((state) => ({ agents: state.agents.map((agent) => (agent.id === id ? { ...agent, mode } : agent)) })),
  setPolicy: (key, value) => set((state) => ({ policies: { ...state.policies, [key]: value } })),
}));
