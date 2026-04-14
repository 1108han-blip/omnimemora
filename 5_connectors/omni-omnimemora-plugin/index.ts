import { Type } from "@sinclair/typebox";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, posix as pathPosix } from "node:path";
import { memoryOpenVikingConfigSchema, type MemoryOpenVikingConfig } from "./config.js";
import { MemoryAdapterClient, type MemoryItem } from "./client.js";
import {
  extractLatestUserText,
  isTranscriptLikeIngest,
  shouldCaptureText,
  sanitizeTextForMemory,
} from "./text-utils.js";
import {
  clampScore,
  postProcessMemories,
  formatMemoryLines,
  toJsonLog,
  summarizeInjectionMemories,
  pickMemoriesForInjection,
} from "./memory-ranking.js";

type PluginLogger = {
  debug?: (message: string) => void;
  info: (message: string) => void;
  warn: (message: string) => void;
  error: (message: string) => void;
};

type HookAgentContext = {
  agentId?: string;
  sessionId?: string;
  sessionKey?: string;
};

type OpenClawPluginApi = {
  pluginConfig?: unknown;
  logger: PluginLogger;
  registerTool: (
    tool: {
      name: string;
      label: string;
      description: string;
      parameters: unknown;
      execute: (_toolCallId: string, params: Record<string, unknown>) => Promise<unknown>;
    },
    opts?: { name?: string; names?: string[] },
  ) => void;
  registerService: (service: {
    id: string;
    start: (ctx?: unknown) => void | Promise<void>;
    stop?: (ctx?: unknown) => void | Promise<void>;
  }) => void;
  on: (
    hookName: string,
    handler: (event: unknown, ctx?: HookAgentContext) => unknown,
    opts?: { priority?: number },
  ) => void;
};

const AUTO_START_MARKER = "<!-- AUTO-GENERATED:START -->";
const AUTO_END_MARKER = "<!-- AUTO-GENERATED:END -->";
const MANUAL_START_MARKER = "<!-- MANUAL:START -->";
const MANUAL_END_MARKER = "<!-- MANUAL:END -->";

function buildMemorySnapshotPath(agentId: string): string {
  return pathPosix.join("/home/node/.openclaw/workspace", agentId || "supervisor", "MEMORY.md");
}

function extractSection(content: string, startMarker: string, endMarker: string): string | null {
  const start = content.indexOf(startMarker);
  const end = content.indexOf(endMarker);
  if (start === -1 || end === -1 || end <= start) {
    return null;
  }
  return content.slice(start + startMarker.length, end).trim();
}

function renderMemorySnapshotDocument(autoMarkdown: string, manualContent?: string): string {
  const preservedManual = (manualContent ?? "").trim();
  const manualSection =
    preservedManual ||
    [
      "## 人工保留区",
      "- 这里用于保留不会被自动同步覆盖的手工说明。",
    ].join("\n");

  return [
    "# 🧠 MEMORY.md - 启动快照",
    "",
    "## 基础说明",
    "- 仅在主会话（与用户的直接聊天）加载，不在群组/共享会话泄露。",
    "- OpenViking 是长期记忆主库，本文件是自动生成的启动快照从库。",
    "- 自动生成区会由 memory-openviking 插件刷新。",
    "- 手工备注请写在人工保留区，自动同步不会覆盖该区域。",
    "",
    AUTO_START_MARKER,
    autoMarkdown.trim(),
    AUTO_END_MARKER,
    "",
    MANUAL_START_MARKER,
    manualSection,
    MANUAL_END_MARKER,
    "",
  ].join("\n");
}

const contextEnginePlugin = {
  id: "memory-openviking",
  name: "Memory (OpenViking via Adapter)",
  description: "OpenViking-backed memory through Memory Adapter layer with auto-recall/capture",
  kind: "memory" as const,
  configSchema: memoryOpenVikingConfigSchema,

  register(api: OpenClawPluginApi) {
    const cfg = memoryOpenVikingConfigSchema.parse(api.pluginConfig);
    const baseUrl = cfg.baseUrl ?? "http://memory-adapter:8000";
    const agentId = cfg.agentId ?? "supervisor";
    const timeoutMs = cfg.timeoutMs ?? 30000;

    let client: MemoryAdapterClient | undefined;
    const sessionAgentIds = new Map<string, string>();

    const getClient = (resolvedAgentId?: string, reason?: string): MemoryAdapterClient => {
      const nextAgentId = resolvedAgentId || agentId;
      if (!client) {
        client = new MemoryAdapterClient(baseUrl, nextAgentId, timeoutMs);
        return client;
      }
      if (client.getAgentId() !== nextAgentId) {
        client = new MemoryAdapterClient(baseUrl, nextAgentId, timeoutMs);
        if (reason) {
          api.logger.info(`memory-openviking: switched to agentId=${nextAgentId} for ${reason}`);
        }
      }
      return client;
    };

    const syncMemorySnapshot = async (resolvedAgentId: string) => {
      try {
        const snapshotClient =
          client?.getAgentId() === resolvedAgentId
            ? client
            : new MemoryAdapterClient(baseUrl, resolvedAgentId, timeoutMs);
        const snapshot = await snapshotClient.buildMemorySnapshot();
        const snapshotPath = buildMemorySnapshotPath(resolvedAgentId);
        await mkdir(dirname(snapshotPath), { recursive: true });

        let existing = "";
        try {
          existing = await readFile(snapshotPath, "utf8");
        } catch {
          existing = "";
        }

        const preservedManual =
          extractSection(existing, MANUAL_START_MARKER, MANUAL_END_MARKER) ||
          (existing.trim() ? existing.trim() : "");

        const nextContent = renderMemorySnapshotDocument(snapshot.markdown, preservedManual);
        await writeFile(snapshotPath, nextContent, "utf8");
        api.logger.info(
          `memory-openviking: synced MEMORY.md for agentId=${resolvedAgentId} (sourceCount=${snapshot.sourceCount})`,
        );
      } catch (err) {
        api.logger.warn(`memory-openviking: snapshot sync failed: ${String(err)}`);
      }
    };

    const rememberSessionAgentId = (ctx: {
      agentId?: string;
      sessionId?: string;
      sessionKey?: string;
    }) => {
      if (!ctx?.agentId) {
        return;
      }
      if (ctx.sessionId) {
        sessionAgentIds.set(ctx.sessionId, ctx.agentId);
      }
      if (ctx.sessionKey) {
        sessionAgentIds.set(ctx.sessionKey, ctx.agentId);
      }
    };

    const resolveAgentId = (sessionId: string): string =>
      sessionAgentIds.get(sessionId) ?? agentId;

    api.registerTool(
      {
        name: "memory_recall",
        label: "Memory Recall (OpenViking)",
        description:
          "Search long-term memories from OpenViking via Memory Adapter. Use when you need past user preferences, facts, or decisions.",
        parameters: Type.Object({
          query: Type.String({ description: "Search query" }),
          limit: Type.Optional(
            Type.Number({ description: "Max results (default: plugin config)" }),
          ),
          scoreThreshold: Type.Optional(
            Type.Number({ description: "Minimum score (0-1, default: plugin config)" }),
          ),
        }),
        async execute(_toolCallId: string, params: Record<string, unknown>) {
          const { query } = params as { query: string };
          const limit =
            typeof (params as { limit?: number }).limit === "number"
              ? Math.max(1, Math.floor((params as { limit: number }).limit))
              : cfg.recallLimit ?? 6;
          const scoreThreshold =
            typeof (params as { scoreThreshold?: number }).scoreThreshold === "number"
              ? Math.max(0, Math.min(1, (params as { scoreThreshold: number }).scoreThreshold))
              : cfg.recallScoreThreshold ?? 0.01;
          const requestLimit = Math.max(limit * 4, 20);

          const activeClient = getClient();
          const result = await activeClient.searchMemories(query, {
            limit: requestLimit,
            scoreThreshold: 0,
          });

          const memories = postProcessMemories(result.memories ?? [], {
            limit,
            scoreThreshold,
          });

          if (memories.length === 0) {
            return {
              content: [{ type: "text", text: "No relevant OpenViking memories found." }],
              details: { count: 0, total: result.total ?? 0, scoreThreshold },
            };
          }
          return {
            content: [
              {
                type: "text",
                text: `Found ${memories.length} memories:\n\n${formatMemoryLines(memories)}`,
              },
            ],
            details: {
              count: memories.length,
              memories,
              total: result.total ?? memories.length,
              scoreThreshold,
              requestLimit,
            },
          };
        },
      },
      { name: "memory_recall" },
    );

    api.registerTool(
      {
        name: "memory_store",
        label: "Memory Store (OpenViking)",
        description:
          "Store text in OpenViking memory via Memory Adapter.",
        parameters: Type.Object({
          text: Type.String({ description: "Information to store as memory" }),
          type: Type.Optional(Type.String({ description: "Memory type, default 'fact'" })),
          tags: Type.Optional(Type.Array(Type.String(), { description: "Optional tags" })),
        }),
        async execute(_toolCallId: string, params: Record<string, unknown>) {
          const { text } = params as { text: string };
          const memoryType =
            typeof (params as { type?: string }).type === "string"
              ? (params as { type: string }).type
              : "fact";
          const tags = Array.isArray((params as { tags?: string[] }).tags)
            ? (params as { tags: string[] }).tags
            : undefined;

          api.logger.info?.(
            `memory-openviking: memory_store invoked (textLength=${text?.length ?? 0})`,
          );

          try {
            const sanitized = sanitizeTextForMemory(text, cfg.captureMaxLength);
            const activeClient = getClient();
            const result = await activeClient.writeMemory(sanitized, memoryType, tags);
            void syncMemorySnapshot(activeClient.getAgentId());
            return {
              content: [
                {
                  type: "text",
                  text: `Stored in OpenViking via Memory Adapter.`,
                },
              ],
              details: { action: "stored", uri: result.uri },
            };
          } catch (err) {
            api.logger.warn(`memory-openviking: memory_store failed: ${String(err)}`);
            throw err;
          }
        },
      },
      { name: "memory_store" },
    );

    api.registerTool(
      {
        name: "memory_forget",
        label: "Memory Forget (OpenViking)",
        description: "Forget memory by URI, or search then delete when a strong single match is found.",
        parameters: Type.Object({
          uri: Type.Optional(Type.String({ description: "Exact memory URI to delete" })),
          query: Type.Optional(Type.String({ description: "Search query to find memory URI" })),
          limit: Type.Optional(Type.Number({ description: "Search limit (default: 5)" })),
          scoreThreshold: Type.Optional(
            Type.Number({ description: "Minimum score (0-1, default: plugin config)" }),
          ),
        }),
        async execute(_toolCallId: string, params: Record<string, unknown>) {
          const uri = (params as { uri?: string }).uri;
          if (uri) {
            const activeClient = getClient();
            await activeClient.deleteMemory(uri);
            void syncMemorySnapshot(activeClient.getAgentId());
            return {
              content: [{ type: "text", text: `Forgotten: ${uri}` }],
              details: { action: "deleted", uri },
            };
          }

          const query = (params as { query?: string }).query;
          if (!query) {
            return {
              content: [{ type: "text", text: "Provide uri or query." }],
              details: { error: "missing_param" },
            };
          }

          const limit =
            typeof (params as { limit?: number }).limit === "number"
              ? Math.max(1, Math.floor((params as { limit: number }).limit))
              : 5;
          const scoreThreshold =
            typeof (params as { scoreThreshold?: number }).scoreThreshold === "number"
              ? Math.max(0, Math.min(1, (params as { scoreThreshold: number }).scoreThreshold))
              : cfg.recallScoreThreshold ?? 0.01;
          const requestLimit = Math.max(limit * 4, 20);

          const activeClient = getClient();
          const result = await activeClient.searchMemories(query, {
            limit: requestLimit,
            scoreThreshold: 0,
          });
          const candidates = postProcessMemories(result.memories ?? [], {
            limit: requestLimit,
            scoreThreshold,
            leafOnly: true,
          });

          if (candidates.length === 0) {
            return {
              content: [
                {
                  type: "text",
                  text: "No matching memory candidates found. Try a more specific query.",
                },
              ],
              details: { action: "none", scoreThreshold },
            };
          }
          const top = candidates[0];
          if (candidates.length === 1 && clampScore(top.score) >= 0.85) {
            await activeClient.deleteMemory(top.uri);
            void syncMemorySnapshot(activeClient.getAgentId());
            return {
              content: [{ type: "text", text: `Forgotten: ${top.uri}` }],
              details: { action: "deleted", uri: top.uri, score: top.score ?? 0 },
            };
          }

          const list = candidates
            .map((item) => `- ${item.uri} (${(clampScore(item.score) * 100).toFixed(0)}%)`)
            .join("\n");

          return {
            content: [
              {
                type: "text",
                text: `Found ${candidates.length} candidates. Specify uri:\n${list}`,
              },
            ],
            details: { action: "candidates", candidates, scoreThreshold, requestLimit },
          };
        },
      },
      { name: "memory_forget" },
    );

    api.on("session_start", async (_event: unknown, ctx?: HookAgentContext) => {
      rememberSessionAgentId(ctx ?? {});
    });
    api.on("session_end", async (_event: unknown, ctx?: HookAgentContext) => {
      rememberSessionAgentId(ctx ?? {});
    });
    api.on("before_prompt_build", async (event: unknown, ctx?: HookAgentContext) => {
      rememberSessionAgentId(ctx ?? {});

      const hookSessionId = ctx?.sessionId ?? ctx?.sessionKey ?? "";
      const resolvedAgentId = resolveAgentId(hookSessionId);
      const activeClient = getClient(resolvedAgentId, "before_prompt_build");

      const eventObj = (event ?? {}) as { messages?: unknown[]; prompt?: string };
      const queryText =
        extractLatestUserText(eventObj.messages) ||
        (typeof eventObj.prompt === "string" ? eventObj.prompt.trim() : "");
      if (!queryText) {
        return;
      }

      const prependContextParts: string[] = [];

      if (cfg.autoRecall && queryText.length >= 5) {
        try {
          const healthy = await activeClient.healthCheck();
          if (!healthy) {
            api.logger.info(
              `memory-openviking: skipping auto-recall because adapter health check failed`,
            );
          } else {
            const candidateLimit = Math.max((cfg.recallLimit ?? 6) * 4, 20);
            const result = await activeClient.searchMemories(queryText, {
              limit: candidateLimit,
              scoreThreshold: 0,
            });

            const leafOnly = (result.memories ?? []).filter((m) => m.level >= 1 && m.level <= 2);
            const processed = postProcessMemories(leafOnly, {
              limit: candidateLimit,
              scoreThreshold: cfg.recallScoreThreshold ?? 0.01,
            });
            const memories = pickMemoriesForInjection(processed, cfg.recallLimit ?? 6, queryText);

            if (memories.length > 0) {
              const memoryLines = await Promise.all(
                memories.map(async (item: MemoryItem) => {
                  if (item.level === 2 && item.uri) {
                    try {
                      const content = await activeClient.readMemory(item.uri);
                      if (content && typeof content === "string" && content.trim()) {
                        return `- [${item.category ?? "memory"}] ${content.trim()}`;
                      }
                    } catch {
                      // fallback to abstract
                    }
                  }
                  return `- [${item.category ?? "memory"}] ${item.abstract ?? item.uri}`;
                }),
              );
              const memoryContext = memoryLines.join("\n");
              api.logger.info(`memory-openviking: injecting ${memories.length} memories into context`);
              api.logger.info(
                `memory-openviking: inject-detail ${toJsonLog({ count: memories.length, memories: summarizeInjectionMemories(memories) })}`,
              );
              prependContextParts.push(
                "<relevant-memories>\nThe following OpenViking memories may be relevant:\n" +
                  `${memoryContext}\n` +
                "</relevant-memories>",
              );
            }
          }
        } catch (err) {
          api.logger.warn(`memory-openviking: auto-recall failed: ${String(err)}`);
        }
      }

      if (true) {
        const decision = isTranscriptLikeIngest(queryText, {
          minSpeakerTurns: 2,
          minChars: 120,
        });
        if (decision.shouldAssist) {
          api.logger.info(
            `memory-openviking: ingest-reply-assist applied (reason=${decision.reason}, speakerTurns=${decision.speakerTurns}, chars=${decision.chars})`,
          );
          prependContextParts.push(
            "<ingest-reply-assist>\n" +
              "The latest user input looks like a multi-speaker transcript used for memory ingestion.\n" +
              "Reply with 1-2 concise sentences to acknowledge or summarize key points.\n" +
              "Do not output NO_REPLY or an empty reply.\n" +
              "Do not fabricate facts beyond the provided transcript and recalled memories.\n" +
            "</ingest-reply-assist>",
          );
        }
      }

      if (prependContextParts.length > 0) {
        return {
          prependContext: prependContextParts.join("\n\n"),
        };
      }
    });

    api.on("agent_end", async (event: unknown, ctx?: HookAgentContext) => {
      rememberSessionAgentId(ctx ?? {});

      if (!cfg.autoCapture) {
        return;
      }

      const eventObj = (event ?? {}) as { success?: boolean; messages?: unknown[] };
      if (!eventObj.success || !eventObj.messages || !Array.isArray(eventObj.messages)) {
        return;
      }

      const hookSessionId = ctx?.sessionId ?? ctx?.sessionKey ?? "";
      const resolvedAgentId = resolveAgentId(hookSessionId);
      const activeClient = getClient(resolvedAgentId);

      try {
        const texts: string[] = [];
        for (const msg of eventObj.messages) {
          if (!msg || typeof msg !== "object") {
            continue;
          }
          const msgObj = msg as Record<string, unknown>;
          const role = msgObj.role;
          if (role !== "user") {
            continue;
          }

          const content = msgObj.content;
          if (typeof content === "string") {
            texts.push(content);
            continue;
          }

          if (Array.isArray(content)) {
            for (const block of content) {
              if (
                block &&
                typeof block === "object" &&
                "type" in block &&
                (block as Record<string, unknown>).type === "text" &&
                "text" in block &&
                typeof (block as Record<string, unknown>).text === "string"
              ) {
                texts.push((block as Record<string, unknown>).text as string);
              }
            }
          }
        }

        const toCapture = texts.filter(
          (text) => text && shouldCaptureText(text, { maxLength: cfg.captureMaxLength }),
        );

        if (toCapture.length > 0) {
          let stored = 0;
          for (const text of toCapture.slice(0, 3)) {
            try {
              const sanitized = sanitizeTextForMemory(text, cfg.captureMaxLength);
              await activeClient.writeMemory(sanitized, "fact");
              stored++;
            } catch (err) {
              api.logger.warn(`memory-openviking: auto-capture failed: ${String(err)}`);
            }
          }
          if (stored > 0) {
            api.logger.info(`memory-openviking: auto-captured ${stored} memories`);
            void syncMemorySnapshot(activeClient.getAgentId());
          }
        }
      } catch (err) {
        api.logger.warn(`memory-openviking: auto-capture hook failed: ${String(err)}`);
      }
    });

    api.registerService({
      id: "memory-openviking",
      start: async () => {
        const activeClient = getClient(agentId);
        const healthy = await activeClient.healthCheck().catch(() => false);
        if (healthy) {
          api.logger.info(
            `memory-openviking: initialized (url: ${baseUrl}, agentId: ${agentId})`,
          );
          void syncMemorySnapshot(agentId);
        } else {
          api.logger.warn(
            `memory-openviking: adapter health check failed (url: ${baseUrl}) - will retry on demand`,
          );
        }
      },
      stop: () => {
        api.logger.info("memory-openviking: stopped");
      },
    });
  },
};

export default contextEnginePlugin;
