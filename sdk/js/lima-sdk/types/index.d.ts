export interface LiMaClientConfig {
  baseUrl?: string;
  timeout?: number;
  fetch?: typeof globalThis.fetch;
}

export interface RequestOptions {
  json?: Record<string, unknown>;
}

export interface LiMaAPIErrorBody {
  error?: { message?: string; type?: string };
  message?: string;
  code?: string;
  [key: string]: unknown;
}

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface ChatCompletion {
  id: string;
  object: string;
  choices: { message: ChatMessage; finish_reason?: string }[];
  [key: string]: unknown;
}

export interface ImageGeneration {
  data: { url?: string; b64_json?: string }[];
  [key: string]: unknown;
}

export class LiMaSDKError extends Error {}

export class LiMaAPIError extends LiMaSDKError {
  statusCode: number | null;
  code: string | null;
  responseBody: LiMaAPIErrorBody;
  constructor(
    message: string,
    options?: { statusCode?: number; code?: string; responseBody?: LiMaAPIErrorBody }
  );
}

export class ChatCompletions {
  create(params: {
    model: string;
    messages: ChatMessage[];
    stream?: boolean;
    [key: string]: unknown;
  }): Promise<ChatCompletion> | AsyncGenerator<Record<string, unknown>>;
}

export class Images {
  generate(params: {
    model: string;
    prompt: string;
    size?: string;
    n?: number;
    [key: string]: unknown;
  }): Promise<ImageGeneration>;
}

export class Devices {
  list(): Promise<{ devices: Record<string, unknown>[]; count: number }>;
  get(deviceId: string): Promise<Record<string, unknown>>;
  status(deviceId: string): Promise<Record<string, unknown>>;
  createTask(deviceId: string, body: Record<string, unknown>): Promise<Record<string, unknown>>;
  listTasks(deviceId: string, params?: Record<string, string | number>): Promise<{
    tasks: Record<string, unknown>[];
    count: number;
  }>;
  getTask(taskId: string): Promise<Record<string, unknown>>;
}

export class Assets {
  list(params?: Record<string, string | number>): Promise<{
    assets: Record<string, unknown>[];
    total: number;
    limit: number;
    offset: number;
  }>;
  create(body: Record<string, unknown>): Promise<Record<string, unknown>>;
}

export class LiMaClient {
  constructor(apiKey: string, config?: LiMaClientConfig);
  apiKey: string;
  baseUrl: string;
  timeout: number;
  fetch: typeof globalThis.fetch;
  chat: ChatCompletions;
  images: Images;
  devices: Devices;
  assets: Assets;
}
