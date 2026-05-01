import { create } from 'zustand';
import {
  disableAgentRoute,
  enableAgentRoute,
  fetchRequestEvidence,
  getDesktopStatus,
  getProductConsoleSnapshot,
  installAgent,
  runDesktopCommand,
  scanAgents,
  uninstallAgent,
} from '../desktopApi';
import type { AgentStatus, DesktopStatus, ProductConsoleSnapshot, RecentRequest, RequestEvidence } from '../types';
import { copy, detectLanguage, type Language } from '../lib/i18n';

export type PageKey = 'overview' | 'live-flow' | 'agents' | 'policies' | 'context-debug' | 'savings' | 'settings';

export interface PolicyState {
  compressionLevel: number;
  fallbackEnabled: boolean;
  aggressiveMode: boolean;
}

interface DashboardState {
  page: PageKey;
  sidebarCollapsed: boolean;
  language: Language;
  desktopStatus: DesktopStatus | null;
  product: ProductConsoleSnapshot | null;
  desktopAgents: AgentStatus[];
  selectedRequestId: string | null;
  evidenceByRequestId: Record<string, RequestEvidence | null>;
  evidenceLoading: boolean;
  evidenceError: string | null;
  policies: PolicyState;
  lastMessage: string;
  loading: boolean;
  agentBusy: string | null;
  setPage: (page: PageKey) => void;
  toggleSidebar: () => void;
  setLanguage: (language: Language) => void;
  refreshReality: () => Promise<void>;
  startProduct: () => Promise<void>;
  stopProduct: () => Promise<void>;
  restartProduct: () => Promise<void>;
  selectRequest: (request: RecentRequest | null) => Promise<void>;
  attachAgent: (familyId: string) => Promise<void>;
  detachAgent: (familyId: string) => Promise<void>;
  enableRouting: (familyId: string) => Promise<void>;
  disableRouting: (familyId: string) => Promise<void>;
  setPolicy: <K extends keyof PolicyState>(key: K, value: PolicyState[K]) => void;
}

function userFacingRequests(product: ProductConsoleSnapshot | null): RecentRequest[] {
  return (product?.recent?.requests ?? []).filter((request) => request.request_class !== 'internal');
}

export const useDashboardStore = create<DashboardState>((set, get) => {
  const language = detectLanguage();
  return {
    page: 'overview',
    sidebarCollapsed: false,
    language,
    desktopStatus: null,
    product: null,
    desktopAgents: [],
    selectedRequestId: null,
    evidenceByRequestId: {},
    evidenceLoading: false,
    evidenceError: null,
    policies: {
      compressionLevel: 62,
      fallbackEnabled: true,
      aggressiveMode: false,
    },
    lastMessage: copy[language].header.ready,
    loading: false,
    agentBusy: null,
    setPage: (page) => set({ page }),
    toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
    setLanguage: (nextLanguage) => {
      window.localStorage.setItem('omnimemora.language', nextLanguage);
      set({ language: nextLanguage, lastMessage: copy[nextLanguage].header.ready });
    },
    refreshReality: async () => {
      set({ loading: true });
      try {
        const [desktopStatus, product, desktopAgents] = await Promise.all([
          getDesktopStatus(),
          getProductConsoleSnapshot(),
          scanAgents(),
        ]);
        const requests = userFacingRequests(product);
        set((state) => ({
          desktopStatus,
          product,
          desktopAgents,
          selectedRequestId: state.selectedRequestId && requests.some((request) => request.request_id === state.selectedRequestId) ? state.selectedRequestId : (requests[0]?.request_id ?? null),
          lastMessage: product.online ? copy[state.language].header.synced : copy[state.language].header.waiting,
        }));
      } finally {
        set({ loading: false });
      }
    },
    startProduct: async () => {
      set((state) => ({ loading: true, lastMessage: copy[state.language].header.starting }));
      try {
        const result = await runDesktopCommand('start_services');
        set({ desktopStatus: result.status, lastMessage: result.message });
        await get().refreshReality();
      } finally {
        set({ loading: false });
      }
    },
    stopProduct: async () => {
      set((state) => ({ loading: true, lastMessage: copy[state.language].header.stopping }));
      try {
        const result = await runDesktopCommand('stop_services');
        set({ desktopStatus: result.status, lastMessage: result.message });
        await get().refreshReality();
      } finally {
        set({ loading: false });
      }
    },
    restartProduct: async () => {
      set((state) => ({ loading: true, lastMessage: copy[state.language].header.restarting }));
      try {
        const result = await runDesktopCommand('restart_services');
        set({ desktopStatus: result.status, lastMessage: result.message });
        await get().refreshReality();
      } finally {
        set({ loading: false });
      }
    },
    selectRequest: async (request) => {
      if (!request) {
        set({ selectedRequestId: null, evidenceError: null, evidenceLoading: false });
        return;
      }
      set({ selectedRequestId: request.request_id, evidenceError: null });
      if (Object.prototype.hasOwnProperty.call(get().evidenceByRequestId, request.request_id)) return;
      set({ evidenceLoading: true });
      try {
        const evidence = await fetchRequestEvidence(request.request_id);
        set((state) => ({ evidenceByRequestId: { ...state.evidenceByRequestId, [request.request_id]: evidence } }));
      } catch (error) {
        set((state) => ({
          evidenceByRequestId: { ...state.evidenceByRequestId, [request.request_id]: null },
          evidenceError: error instanceof Error ? error.message : String(error),
        }));
      } finally {
        set({ evidenceLoading: false });
      }
    },
    attachAgent: async (familyId) => {
      set({ agentBusy: familyId });
      try {
        await installAgent(familyId);
        await get().refreshReality();
      } finally {
        set({ agentBusy: null });
      }
    },
    detachAgent: async (familyId) => {
      set({ agentBusy: familyId });
      try {
        await uninstallAgent(familyId);
        await get().refreshReality();
      } finally {
        set({ agentBusy: null });
      }
    },
    enableRouting: async (familyId) => {
      set({ agentBusy: familyId });
      try {
        await enableAgentRoute(familyId);
        await get().refreshReality();
      } finally {
        set({ agentBusy: null });
      }
    },
    disableRouting: async (familyId) => {
      set({ agentBusy: familyId });
      try {
        await disableAgentRoute(familyId);
        await get().refreshReality();
      } finally {
        set({ agentBusy: null });
      }
    },
    setPolicy: (key, value) => set((state) => ({ policies: { ...state.policies, [key]: value } })),
  };
});
