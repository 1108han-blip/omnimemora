import { beforeEach, describe, expect, it, vi } from "vitest";
import plugin from "./index.js";

type RegisteredTool = {
  name: string;
  execute: (_toolCallId: string, params: Record<string, unknown>) => Promise<unknown>;
};

type HookHandler = (event: unknown, ctx?: { agentId?: string; sessionId?: string; sessionKey?: string }) => unknown;

function createApi(pluginConfig?: unknown) {
  const hooks = new Map<string, HookHandler>();
  const tools = new Map<string, RegisteredTool>();

  return {
    api: {
      pluginConfig,
      logger: {
        info: vi.fn(),
        warn: vi.fn(),
        error: vi.fn(),
        debug: vi.fn(),
      },
      registerTool: (tool: RegisteredTool) => {
        tools.set(tool.name, tool);
      },
      registerService: vi.fn(),
      on: (hookName: string, handler: HookHandler) => {
        hooks.set(hookName, handler);
      },
    },
    hooks,
    tools,
  };
}

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

describe("omnimemora-memory plugin", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("lazily initializes a client for before_prompt_build hooks", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/health")) {
        return new Response("ok", { status: 200 });
      }
      if (url.endsWith("/memory/search")) {
        return jsonResponse({ memories: [], total: 0 });
      }
      throw new Error(`Unexpected fetch in test: ${url}`);
    });
    const { api, hooks } = createApi({
      autoCapture: false,
    });

    plugin.register(api);

    const handler = hooks.get("before_prompt_build");
    expect(handler).toBeTypeOf("function");

    await expect(
      handler?.(
        { prompt: "Summarize the current runtime graph design tradeoffs." },
        { agentId: "exploration", sessionKey: "agent:exploration:test-session" },
      ),
    ).resolves.toBeUndefined();

    expect(fetchSpy).toHaveBeenCalledWith(
      "http://127.0.0.1:18011/health",
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      }),
    );
    expect(fetchSpy).toHaveBeenCalledWith(
      "http://127.0.0.1:18011/memory/search",
      expect.objectContaining({
        body: expect.stringContaining("\"agent\":\"exploration\""),
        signal: expect.any(AbortSignal),
      }),
    );
  });

  it("lazily initializes a client for memory_store tool calls", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/memory/write")) {
        return jsonResponse({ uri: "omnimemora://memory/test" });
      }
      if (url.endsWith("/memory/snapshot")) {
        return jsonResponse({
          agent: "supervisor",
          generatedAt: "2026-03-26T00:00:00.000Z",
          sourceCount: 1,
          markdown: "## Snapshot",
        });
      }
      throw new Error(`Unexpected fetch in test: ${url}`);
    });
    const { api, tools } = createApi({
      autoRecall: false,
    });

    plugin.register(api);

    const tool = tools.get("memory_store");
    expect(tool).toBeDefined();

    const result = await tool?.execute("tool-call-1", {
      text: "Remember this stability check result.",
    });

    expect(result).toEqual(
      expect.objectContaining({
        details: expect.objectContaining({
          action: "stored",
          uri: "omnimemora://memory/test",
        }),
      }),
    );
    expect(fetchSpy).toHaveBeenCalledWith(
      "http://127.0.0.1:18011/memory/write",
      expect.objectContaining({
        body: expect.stringContaining("Remember this stability check result."),
        signal: expect.any(AbortSignal),
      }),
    );
  });
});
