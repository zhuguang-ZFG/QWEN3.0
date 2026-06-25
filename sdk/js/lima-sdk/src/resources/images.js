import { raiseForStatus } from "../client.js";

/** @typedef {import('../../types/index.d.ts').ImageGeneration} ImageGeneration */
/** @typedef {import('../client.js').LiMaClient} LiMaClient */

export class Images {
  /**
   * @param {LiMaClient} client
   */
  constructor(client) {
    this.client = client;
  }

  /**
   * @param {object} params
   * @param {string} params.model
   * @param {string} params.prompt
   * @param {string} [params.size]
   * @param {number} [params.n]
   * @param {Record<string, unknown>} [params.options]
   * @returns {Promise<ImageGeneration>}
   */
  async generate({ model, prompt, size = "1024x1024", n = 1, ...options }) {
    const response = await this.client.request("POST", "/v1/images/generations", {
      json: { model, prompt, size, n, ...options },
    });
    await raiseForStatus(response);
    return /** @type {ImageGeneration} */ (await response.json());
  }
}
