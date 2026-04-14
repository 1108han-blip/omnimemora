// Text extraction and processing utilities

/**
 * Extract the latest user text from messages array
 */
export function extractLatestUserText(messages: unknown[] | undefined): string {
  if (!messages || !Array.isArray(messages)) {
    return "";
  }

  for (let i = messages.length - 1; i >= 0; i--) {
    const msg = messages[i];
    if (!msg || typeof msg !== "object") {
      continue;
    }

    const msgObj = msg as Record<string, unknown>;
    if (msgObj.role !== "user") {
      continue;
    }

    const content = msgObj.content;
    if (typeof content === "string") {
      return content.trim();
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
          return (block as Record<string, unknown>).text as string;
        }
      }
    }
  }

  return "";
}

/**
 * Detect if text looks like a transcript for ingestion
 */
export function isTranscriptLikeIngest(
  text: string,
  options?: { minSpeakerTurns?: number; minChars?: number }
): {
  shouldAssist: boolean;
  reason: string;
  speakerTurns: number;
  chars: number;
} {
  const minSpeakerTurns = options?.minSpeakerTurns ?? 2;
  const minChars = options?.minChars ?? 120;
  const chars = text.length;

  if (chars < minChars) {
    return {
      shouldAssist: false,
      reason: "text_too_short",
      speakerTurns: 0,
      chars,
    };
  }

  // Count speaker patterns like "Name:", "User:", "Agent:" etc.
  const speakerPattern = /^[A-Z][a-zA-Z0-9_]+:\s/gm;
  const matches = text.match(speakerPattern);
  const speakerTurns = matches ? matches.length : 0;

  if (speakerTurns >= minSpeakerTurns) {
    return {
      shouldAssist: true,
      reason: "speaker_turns_detected",
      speakerTurns,
      chars,
    };
  }

  return {
    shouldAssist: false,
    reason: "no_speaker_patterns",
    speakerTurns,
    chars,
  };
}

/**
 * Sanitize text for memory storage
 */
export function sanitizeTextForMemory(text: string, maxLength?: number): string {
  let sanitized = text.trim();

  // Remove injection patterns
  sanitized = sanitized.replace(/<\s*(system|assistant|developer|tool|function)\b/gi, "[$1]");

  // Truncate if needed
  if (maxLength && sanitized.length > maxLength) {
    sanitized = sanitized.slice(0, maxLength - 3) + "...";
  }

  return sanitized;
}

/**
 * Check if text should be captured
 */
export function shouldCaptureText(
  text: string,
  options?: { maxLength?: number; minLength?: number }
): boolean {
  const maxLength = options?.maxLength ?? 24000;
  const minLength = options?.minLength ?? 10;

  const trimmed = text.trim();

  if (trimmed.length < minLength || trimmed.length > maxLength) {
    return false;
  }

  // Skip injected context
  if (trimmed.includes("<relevant-memories>")) {
    return false;
  }

  // Skip system-generated tags
  if (trimmed.startsWith("<") && trimmed.includes("</")) {
    return false;
  }

  // Skip markdown-heavy agent responses
  if (trimmed.includes("**") && trimmed.includes("\n-")) {
    return false;
  }

  // Skip emoji-heavy content
  const emojiCount = (trimmed.match(/[\u{1F300}-\u{1F9FF}]/gu) || []).length;
  if (emojiCount > 3) {
    return false;
  }

  return true;
}
