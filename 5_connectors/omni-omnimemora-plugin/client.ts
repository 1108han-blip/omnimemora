export type MemoryWriteRequest = {
  agent: string;
  type: string;
  content: string;
  tags?: string[];
};

export type MemorySearchRequest = {
  query: string;
  agent: string;
  limit?: number;
  scoreThreshold?: number;
};

export type MemoryItem = {
  uri: string;
  content: string;
  abstract?: string;
  score?: number;
  category?: string;
  level?: number;
};

export type MemorySearchResponse = {
  memories: MemoryItem[];
  total: number;
};

export type MemorySnapshotResponse = {
  agent: string;
  generatedAt: string;
  sourceCount: number;
  markdown: string;
  sections?: Record<string, number>;
};

export class MemoryAdapterClient {
  private baseUrl: string;
  private agentId: string;
  private timeoutMs: number;

  constructor(baseUrl: string, agentId: string, timeoutMs: number = 30000) {
    this.baseUrl = baseUrl;
    this.agentId = agentId;
    this.timeoutMs = timeoutMs;
  }

  getAgentId(): string {
    return this.agentId;
  }

  setAgentId(agentId: string): void {
    this.agentId = agentId;
  }

  getBaseUrl(): string {
    return this.baseUrl;
  }

  private async fetchWithTimeout(
    url: string,
    options: RequestInit = {}
  ): Promise<Response> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      return response;
    } catch (err) {
      clearTimeout(timeoutId);
      if (err instanceof Error && err.name === "AbortError") {
        throw new Error(`Request timeout after ${this.timeoutMs}ms`);
      }
      throw err;
    }
  }

  async healthCheck(): Promise<boolean> {
    try {
      const response = await this.fetchWithTimeout(`${this.baseUrl}/health`);
      return response.ok;
    } catch {
      return false;
    }
  }

  async writeMemory(
    content: string,
    type: string = "fact",
    tags?: string[]
  ): Promise<{ success: boolean; uri?: string }> {
    const payload: MemoryWriteRequest = {
      agent: this.agentId,
      type,
      content,
      tags,
    };

    const response = await this.fetchWithTimeout(`${this.baseUrl}/memory/write`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Failed to write memory: ${response.status} ${text}`);
    }

    const result = await response.json();
    return {
      success: true,
      uri: result.uri,
    };
  }

  async searchMemories(
    query: string,
    options?: { limit?: number; scoreThreshold?: number }
  ): Promise<MemorySearchResponse> {
    const payload: MemorySearchRequest = {
      query,
      agent: this.agentId,
      limit: options?.limit,
      scoreThreshold: options?.scoreThreshold,
    };

    const response = await this.fetchWithTimeout(`${this.baseUrl}/memory/search`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Failed to search memories: ${response.status} ${text}`);
    }

    return await response.json();
  }

  async deleteMemory(uri: string): Promise<boolean> {
    const response = await this.fetchWithTimeout(`${this.baseUrl}/memory/delete`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ uri }),
    });

    return response.ok;
  }

  async readMemory(uri: string): Promise<string | null> {
    const response = await this.fetchWithTimeout(`${this.baseUrl}/memory/read`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ uri }),
    });

    if (!response.ok) {
      return null;
    }

    const result = await response.json();
    return result.content || null;
  }

  async buildMemorySnapshot(): Promise<MemorySnapshotResponse> {
    const response = await this.fetchWithTimeout(`${this.baseUrl}/memory/snapshot`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ agent: this.agentId }),
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Failed to build memory snapshot: ${response.status} ${text}`);
    }

    return await response.json();
  }
}
