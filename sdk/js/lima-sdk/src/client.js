import { LiMaAPIError } from "./errors.js";
import { iterateSSE } from "./streaming.js";
import { ChatCompletions } from "./resources/chat.js";
import { Images } from "./resources/images.js";
import { Devices } from "./resources/devices.js";
import { Assets } from "./resources/assets.js";

/**
 * @typedef {import('../types/index.d.ts').RequestOptions} RequestOptions
 * @typedef {import('../types/index.d.ts').LiMaClientConfig} LiMaClientConfig
 */

export class LiMaClient {
  /**
   * @param {string} apiKey
   * @param {LiMaClientConfig} [config]
   */
  constructor(apiKey, config = {}) {
    this.apiKey = apiKey;
    this.baseUrl = (config.baseUrl ?? "https://chat.donglicao.com").replace(/\/$/, "");
    this.timeout = config.timeout ?? 60000;
    this.fetch = config.fetch ?? globalThis.fetch.bind(globalThis);

    this.chat = new ChatCompletions(this);
    this.images = new Images(this);
    this.devices = new Devices(this);
    this.assets = new Assets(this);
  }

  /**
   * @param {string} method
   * @param {string} path
   * @param {RequestOptions} [options]
   * @returns {Promise<Response>}
   */
  async request(method, path, options = {}) {
    const url = `${this.baseUrl}${path}`;
    /** @type {Record<string, string>} */
    const headers = {
      Authorization: `Bearer ${this.apiKey}`,
      Accept: "application/json",
      ...(options.json ? { "Content-Type": "application/json" } : {}),
    };

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await this.fetch(url, {
        method,
        headers,
        body: options.json ? JSON.stringify(options.json) : undefined,
        signal: controller.signal,
      });
      return response;
    } finally {
      clearTimeout(timeoutId);
    }
  }

}

/**
 * @param {Response} response
 */
export async function raiseForStatus(response) {
  if (response.ok) return;
  const status = response.status;
  /** @type {any} */
  let body = {};
  try {
    body = await response.json();
  } catch {
    // ignore
  }
  const message = body?.error?.message ?? body?.message ?? response.statusText;
  const code = body?.error?.type ?? body?.code ?? null;
  throw new LiMaAPIError(String(message), { statusCode: status, code, responseBody: body });
}

export { ChatCompletions, Images, Devices, Assets, LiMaAPIError };
