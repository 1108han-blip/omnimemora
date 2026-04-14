export const DEFAULT_CAPTURE_MAX_CHARS = 24000;
export const DEFAULT_RECALL_LIMIT = 6;
export const DEFAULT_RECALL_SCORE_THRESHOLD = 0.01;
export const DEFAULT_BASE_URL = "http://memory-adapter:8000";
export const DEFAULT_AGENT_ID = "supervisor";
export const DEFAULT_TIMEOUT_MS = 30000;

export type MemoryOpenVikingConfig = {
  baseUrl?: string;
  agentId?: string;
  timeoutMs?: number;
  autoCapture?: boolean;
  captureMaxLength?: number;
  autoRecall?: boolean;
  recallLimit?: number;
  recallScoreThreshold?: number;
};

function assertAllowedKeys(value: Record<string, unknown>, allowed: string[], label: string) {
  const unknown = Object.keys(value).filter((key) => !allowed.includes(key));
  if (unknown.length === 0) {
    return;
  }
  throw new Error(`${label} has unknown keys: ${unknown.join(", ")}`);
}

export const memoryOpenVikingConfigSchema = {
  parse(value: unknown): MemoryOpenVikingConfig {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      // Return default config if no value provided
      return {
        baseUrl: DEFAULT_BASE_URL,
        agentId: DEFAULT_AGENT_ID,
        timeoutMs: DEFAULT_TIMEOUT_MS,
        autoCapture: true,
        captureMaxLength: DEFAULT_CAPTURE_MAX_CHARS,
        autoRecall: true,
        recallLimit: DEFAULT_RECALL_LIMIT,
        recallScoreThreshold: DEFAULT_RECALL_SCORE_THRESHOLD,
      };
    }
    const cfg = value as Record<string, unknown>;
    assertAllowedKeys(
      cfg,
      [
        "baseUrl",
        "agentId",
        "timeoutMs",
        "autoCapture",
        "captureMaxLength",
        "autoRecall",
        "recallLimit",
        "recallScoreThreshold",
      ],
      "memory-openviking config",
    );

    const baseUrl = typeof cfg.baseUrl === "string" ? cfg.baseUrl : DEFAULT_BASE_URL;
    const agentId = typeof cfg.agentId === "string" ? cfg.agentId : DEFAULT_AGENT_ID;
    const timeoutMs = typeof cfg.timeoutMs === "number" ? cfg.timeoutMs : DEFAULT_TIMEOUT_MS;
    const autoCapture = cfg.autoCapture !== false;
    const captureMaxLength =
      typeof cfg.captureMaxLength === "number" ? cfg.captureMaxLength : DEFAULT_CAPTURE_MAX_CHARS;
    const autoRecall = cfg.autoRecall !== false;
    const recallLimit =
      typeof cfg.recallLimit === "number" ? Math.max(1, Math.floor(cfg.recallLimit)) : DEFAULT_RECALL_LIMIT;
    const recallScoreThreshold =
      typeof cfg.recallScoreThreshold === "number"
        ? Math.max(0, Math.min(1, cfg.recallScoreThreshold))
        : DEFAULT_RECALL_SCORE_THRESHOLD;

    return {
      baseUrl,
      agentId,
      timeoutMs,
      autoCapture,
      captureMaxLength,
      autoRecall,
      recallLimit,
      recallScoreThreshold,
    };
  },
  uiHints: {
    baseUrl: {
      label: "Memory Adapter Base URL",
      placeholder: DEFAULT_BASE_URL,
      help: "Memory Adapter service URL (default: http://memory-adapter:8000)",
    },
    agentId: {
      label: "Agent ID",
      placeholder: DEFAULT_AGENT_ID,
      help: "Identifies this agent to Memory Adapter. Default: supervisor.",
    },
    timeoutMs: {
      label: "Request Timeout (ms)",
      placeholder: String(DEFAULT_TIMEOUT_MS),
      advanced: true,
    },
    autoCapture: {
      label: "Auto-Capture",
      help: "Extract memories from recent conversation messages via Memory Adapter",
    },
    captureMaxLength: {
      label: "Capture Max Length",
      placeholder: String(DEFAULT_CAPTURE_MAX_CHARS),
      advanced: true,
      help: "Maximum sanitized user text length allowed for auto-capture",
    },
    autoRecall: {
      label: "Auto-Recall",
      help: "Inject relevant OpenViking memories into agent context",
    },
    recallLimit: {
      label: "Recall Limit",
      placeholder: String(DEFAULT_RECALL_LIMIT),
      advanced: true,
    },
    recallScoreThreshold: {
      label: "Recall Score Threshold",
      placeholder: String(DEFAULT_RECALL_SCORE_THRESHOLD),
      advanced: true,
    },
  },
};
