import { raiseForStatus } from "../client.js";

/** @typedef {import('../client.js').LiMaClient} LiMaClient */

export class Devices {
  /**
   * @param {LiMaClient} client
   */
  constructor(client) {
    this.client = client;
  }

  /**
   * @returns {Promise<{devices: Record<string, unknown>[], count: number}>}
   */
  async list() {
    return this._getJson("/device/v1/app/devices");
  }

  /**
   * @param {string} deviceId
   * @returns {Promise<Record<string, unknown>>}
   */
  async get(deviceId) {
    return this._getJson(`/device/v1/app/devices/${deviceId}`);
  }

  /**
   * @param {string} deviceId
   * @returns {Promise<Record<string, unknown>>}
   */
  async status(deviceId) {
    return this._getJson(`/device/v1/app/devices/${deviceId}/status`);
  }

  /**
   * @param {string} deviceId
   * @param {Record<string, unknown>} body
   * @returns {Promise<Record<string, unknown>>}
   */
  async createTask(deviceId, body) {
    return this._postJson(`/device/v1/app/devices/${deviceId}/tasks`, body);
  }

  /**
   * @param {string} deviceId
   * @param {Record<string, string|number>} [params]
   * @returns {Promise<{tasks: Record<string, unknown>[], count: number}>}
   */
  async listTasks(deviceId, params = {}) {
    const query = new URLSearchParams({ device_id: deviceId, ...stringifyParams(params) });
    return this._getJson(`/device/v1/app/tasks?${query.toString()}`);
  }

  /**
   * @param {string} taskId
   * @returns {Promise<Record<string, unknown>>}
   */
  async getTask(taskId) {
    return this._getJson(`/device/v1/app/tasks/${taskId}`);
  }

  /**
   * @param {string} path
   */
  async _getJson(path) {
    const response = await this.client.request("GET", path);
    await raiseForStatus(response);
    return response.json();
  }

  /**
   * @param {string} path
   * @param {Record<string, unknown>} body
   */
  async _postJson(path, body) {
    const response = await this.client.request("POST", path, { json: body });
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
