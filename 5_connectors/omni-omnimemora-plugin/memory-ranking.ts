import type { MemoryItem } from "./client.js";

export function clampScore(score: number | undefined | null): number {
  if (score == null || isNaN(score)) {
    return 0;
  }
  return Math.max(0, Math.min(1, score));
}

export function postProcessMemories(
  memories: MemoryItem[],
  options: {
    limit?: number;
    scoreThreshold?: number;
    leafOnly?: boolean;
  }
): MemoryItem[] {
  const { limit, scoreThreshold = 0, leafOnly = false } = options;

  let processed = [...memories];

  // Filter by score
  if (scoreThreshold > 0) {
    processed = processed.filter((m) => clampScore(m.score) >= scoreThreshold);
  }

  // Filter leaf nodes only (level 1 and 2)
  if (leafOnly) {
    processed = processed.filter((m) => m.level >= 1 && m.level <= 2);
  }

  // Sort by score descending
  processed.sort((a, b) => clampScore(b.score) - clampScore(a.score));

  // Apply limit
  if (limit && limit > 0) {
    processed = processed.slice(0, limit);
  }

  return processed;
}

export function formatMemoryLines(memories: MemoryItem[]): string {
  return memories
    .map((item, index) => {
      const score = clampScore(item.score);
      const scorePercent = (score * 100).toFixed(0);
      const category = item.category || "memory";
      const content = item.content || item.abstract || item.uri;
      return `${index + 1}. [${category}] ${content} (${scorePercent}%)`;
    })
    .join("\n");
}

export function toJsonLog(obj: unknown): string {
  try {
    return JSON.stringify(obj);
  } catch {
    return "[serialization_failed]";
  }
}

export function summarizeInjectionMemories(memories: MemoryItem[]): Array<{
  uri: string;
  score: number;
  category?: string;
}> {
  return memories.map((m) => ({
    uri: m.uri,
    score: clampScore(m.score),
    category: m.category,
  }));
}

export function pickMemoriesForInjection(
  memories: MemoryItem[],
  limit: number,
  queryText: string
): MemoryItem[] {
  // Simple strategy: take top N by score
  return memories.slice(0, Math.max(1, limit));
}
