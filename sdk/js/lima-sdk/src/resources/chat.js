import { iterateSSE } from "../streaming.js";
import { raiseForStatus } from "../client.js";

/** @typedef {import('../../types/index.d.ts').ChatCompletion} ChatCompletion */
/** @typedef {import('../../types/index.d.ts').ChatMessage} ChatMessage */
/** @typedef {import('../client.js').LiMaClient} LiMaClient */

export class ChatCompletions {
  /**
   * @param {LiMaClient} client
   */
  constructor(client) {
    this.client = client;
  }

  /**
   * @param {object} params
   * @param {string} params.model
   * @param {ChatMessage[]} params.messages
   * @param {boolean} [params.stream]
   * @param {Record<string, unknown>} [params.options]
   * @returns {Promise<ChatCompletion>|AsyncGenerator<Record<string, unknown>>}
   */
  create({ model, messages, stream = false, ...options }) {
    const body = { model, messages, stream, ...options };
    if (stream) {
      return this._stream(body);
    }
    return this._json(body);
  }

  /**
   * @param {Record<string, unknown>} body
   * @returns {Promise<ChatCompletion>}
   */
  async _json(body) {
    const response = await this.client.request("POST", "/v1/chat/completions", { json: body });
    await raiseForStatus(response);
    return /** @type {ChatCompletion} */ (await response.json());
  }

  /**
   * @param {Record<string, unknown>} body
   * @returns {AsyncGenerator<Record<string, unknown>>}
   */
  async *_stream(body) {
    const response = await this.client.request("POST", "/v1/chat/completions", { json: body });
    await raiseForStatus(response);
    if (!response.body) return;
    yield* iterateSSE(response.body);
  }
}
