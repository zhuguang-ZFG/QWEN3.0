import { raiseForStatus } from "../client.js";

/** @typedef {import('../client.js').LiMaClient} LiMaClient */

export class Assets {
  /**
   * @param {LiMaClient} client
   */
  constructor(client) {
    this.client = client;
  }

  /**
   * @param {Record<string, string|number>} [params]
   * @returns {Promise<{assets: Record<string, unknown>[], total: number, limit: number, offset: number}>}
   */
  async list(params = {}) {
    const query = new URLSearchParams(stringifyParams(params));
    const qs = query.toString();
    const path = qs ? `/device/v1/app/assets?${qs}` : "/device/v1/app/assets";
    const response = await this.client.request("GET", path);
    await raiseForStatus(response);
    return response.json();
  }

  /**
   * @param {Record<string, unknown>} body
   * @returns {Promise<Record<string, unknown>>}
   */
  async create(body) {
    const response = await this.client.request("POST", "/device/v1/app/assets", { json: body });
    await raiseForStatus(response);
    return response.json();
  }
}

/**
 * @param {Record<string, string|number>} params
 * @returns {Record<string, string>}
 */
function stringifyParams(params) {
  /** @type {Record<string, string>} */
  const out = {};
  for (const [key, value] of Object.entries(params)) {
    out[key] = String(value);
  }
  return out;
}
