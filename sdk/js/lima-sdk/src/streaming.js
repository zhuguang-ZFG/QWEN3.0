/**
 * Parse a server-sent events (SSE) response body into async iterable JSON chunks.
 *
 * @param {ReadableStream<Uint8Array>} body
 * @returns {AsyncGenerator<Record<string, unknown>>}
 */
export async function* iterateSSE(body) {
  const reader = body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      const data = parseSSELine(line);
      if (data) yield data;
    }
  }
  if (buffer) {
    const data = parseSSELine(buffer);
    if (data) yield data;
  }
}

/**
 * @param {string} line
 * @returns {Record<string, unknown>|null}
 */
function parseSSELine(line) {
  const trimmed = line.trim();
  if (!trimmed.startsWith("data: ")) return null;
  const payload = trimmed.slice(6).trim();
  if (payload === "[DONE]") return null;
  if (!payload) return null;
  try {
    return JSON.parse(payload);
  } catch {
    return null;
  }
}
