/** @typedef {import('../types/index.d.ts').LiMaAPIErrorBody} LiMaAPIErrorBody */

/** Base SDK error. */
export class LiMaSDKError extends Error {
  /**
   * @param {string} message
   */
  constructor(message) {
    super(message);
    this.name = "LiMaSDKError";
  }
}

/** Error raised when the LiMa API returns a non-2xx response. */
export class LiMaAPIError extends LiMaSDKError {
  /**
   * @param {string} message
   * @param {object} [options]
   * @param {number|null} [options.statusCode]
   * @param {string|null} [options.code]
   * @param {LiMaAPIErrorBody} [options.responseBody]
   */
  constructor(message, options = {}) {
    super(message);
    this.name = "LiMaAPIError";
    /** @type {number|null} */
    this.statusCode = options.statusCode ?? null;
    /** @type {string|null} */
    this.code = options.code ?? null;
    /** @type {LiMaAPIErrorBody} */
    this.responseBody = options.responseBody ?? {};
  }
}
