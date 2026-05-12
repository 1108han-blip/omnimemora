import assert from "node:assert/strict";
import test from "node:test";

import plugin, { createOmniMemoraWebSearchProvider } from "./index.mjs";

test("registers omnimemora web search provider", () => {
  const providers = [];
  plugin.register({
    registerWebSearchProvider(provider) {
      providers.push(provider);
    }
  });

  assert.equal(providers.length, 1);
  assert.equal(providers[0].id, "omnimemora");
});

test("provider calls OmniMemora tool search and normalizes results", async () => {
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async (url, options) => {
      assert.equal(url, "http://127.0.0.1:18011/tools/search");
      const body = JSON.parse(options.body);
      assert.equal(body.query, "MiniMax AI");
      assert.equal(body.provider, "mmx");
      return new Response(
        JSON.stringify({
          status: "ok",
          provider: "mmx",
          content: JSON.stringify({
            organic: [
              {
                title: "MiniMax",
                link: "https://www.minimaxi.com",
                snippet: "AI company"
              }
            ]
          })
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" }
        }
      );
    };

    const provider = createOmniMemoraWebSearchProvider();
    const tool = provider.createTool({ config: {} });
    const result = await tool.execute({ query: "MiniMax AI", count: 1 });

    assert.equal(result.provider, "omnimemora");
    assert.equal(result.upstreamProvider, "mmx");
    assert.equal(result.count, 1);
    assert.equal(result.results[0].url, "https://www.minimaxi.com");
    assert.equal(result.externalContent.untrusted, true);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("provider returns bounded error payload on failed OmniMemora response", async () => {
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () =>
      new Response(JSON.stringify({ detail: "x".repeat(2000) }), { status: 502 });
    const provider = createOmniMemoraWebSearchProvider();
    const tool = provider.createTool({ config: {} });
    const result = await tool.execute({ query: "failure" });

    assert.equal(result.error, "omnimemora_tool_search_failed");
    assert.equal(result.status, 502);
    assert.ok(result.message.length <= 1000);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
