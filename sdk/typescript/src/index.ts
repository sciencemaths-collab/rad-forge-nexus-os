export type JsonObject = Readonly<Record<string, unknown>>;

export interface TransportRequest {
  readonly method: "GET" | "POST";
  readonly path: string;
  readonly headers: Readonly<Record<string, string>>;
  readonly body?: JsonObject;
}

export interface TransportResponse {
  readonly status: number;
  readonly body: unknown;
  readonly headers: Readonly<Record<string, string>>;
}

export interface HttpTransport {
  send(request: TransportRequest): Promise<TransportResponse>;
}

export type RunState =
  | "SPECIFYING" | "PLANNED" | "RUNNING" | "WAITING_APPROVAL" | "VERIFYING"
  | "REPAIRING" | "QUALIFYING" | "COMPLETED" | "FAILED" | "CANCELLED";

export interface Run {
  readonly run_id: string;
  readonly project_id: string;
  readonly state: RunState;
}

export class SdkValidationError extends Error {
  constructor(message = "NEXUS SDK validation failed") {
    super(message);
    this.name = "SdkValidationError";
  }
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    readonly apiMessage: string,
    readonly requestId: string,
    readonly retryable: boolean,
  ) {
    super(`NEXUS API error: ${code}`);
    this.name = "ApiError";
  }
}

const states = new Set<RunState>([
  "SPECIFYING", "PLANNED", "RUNNING", "WAITING_APPROVAL", "VERIFYING",
  "REPAIRING", "QUALIFYING", "COMPLETED", "FAILED", "CANCELLED",
]);
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const tracePattern = /^[0-9a-f]{32}$/;
const keyPattern = /^[\x21-\x7e]{16,128}$/;

export class NexusClient {
  constructor(private readonly transport: HttpTransport) {}

  async request(
    method: "GET" | "POST",
    path: string,
    options: { body?: JsonObject; idempotencyKey?: string; requestId?: string } = {},
  ): Promise<TransportResponse> {
    if (!path.startsWith("/v1/") || path.includes("..")) throw new SdkValidationError();
    const requestId = options.requestId ?? crypto.randomUUID();
    bounded(requestId);
    const headers: Record<string, string> = {
      Accept: "application/json",
      "X-Request-Id": requestId,
    };
    if (method === "POST") {
      if (!options.idempotencyKey || !keyPattern.test(options.idempotencyKey)) {
        throw new SdkValidationError("Idempotency key is invalid");
      }
      headers["Idempotency-Key"] = options.idempotencyKey;
    } else if (options.idempotencyKey !== undefined) {
      throw new SdkValidationError("Idempotency key is valid only for mutations");
    }
    let response: TransportResponse;
    try {
      const request: TransportRequest = options.body === undefined
        ? { method, path, headers: Object.freeze(headers) }
        : { method, path, headers: Object.freeze(headers), body: options.body };
      response = await this.transport.send(request);
    } catch {
      throw new ApiError(0, "transport_error", "Control transport failed", requestId, true);
    }
    if (!Number.isInteger(response.status) || response.status < 100 || response.status > 599) {
      throw new SdkValidationError("Control status is invalid");
    }
    const trace = response.headers["x-trace-id"] ?? response.headers["X-Trace-Id"];
    if (trace !== undefined && !tracePattern.test(trace)) throw new SdkValidationError();
    if (response.status >= 400) throw apiError(response.status, response.body, requestId);
    if (response.status < 200 || response.status >= 300) throw new SdkValidationError();
    return response;
  }

  async createRun(
    projectId: string,
    options: { idempotencyKey: string; requestId?: string },
  ): Promise<Run> {
    bounded(projectId);
    const response = await this.request("POST", "/v1/runs", {
      body: { project_id: projectId }, ...options,
    });
    return parseRun(response.body);
  }

  async getRun(runId: string, requestId?: string): Promise<Run> {
    const id = uuid(runId);
    const options = requestId === undefined ? {} : { requestId };
    return parseRun((await this.request("GET", `/v1/runs/${id}`, options)).body);
  }

  async cancelRun(runId: string, options: { idempotencyKey: string; requestId?: string }): Promise<Run> {
    return this.runMutation(runId, "cancel", options);
  }

  async resumeRun(runId: string, options: { idempotencyKey: string; requestId?: string }): Promise<Run> {
    return this.runMutation(runId, "resume", options);
  }

  async listProviders(requestId?: string): Promise<readonly JsonObject[]> {
    return this.list("/v1/providers", requestId);
  }

  async listCapabilities(requestId?: string): Promise<readonly JsonObject[]> {
    return this.list("/v1/capabilities", requestId);
  }

  async listEvidence(runId: string, requestId?: string): Promise<readonly JsonObject[]> {
    return this.list(`/v1/runs/${uuid(runId)}/evidence`, requestId);
  }

  private async runMutation(
    runId: string,
    action: "cancel" | "resume",
    options: { idempotencyKey: string; requestId?: string },
  ): Promise<Run> {
    const response = await this.request("POST", `/v1/runs/${uuid(runId)}/${action}`, options);
    return parseRun(response.body);
  }

  private async list(path: string, requestId?: string): Promise<readonly JsonObject[]> {
    const options = requestId === undefined ? {} : { requestId };
    const body = (await this.request("GET", path, options)).body;
    if (!Array.isArray(body) || body.some((item) => !isObject(item))) throw new SdkValidationError();
    return Object.freeze(body.map((item) => Object.freeze({ ...item })));
  }
}

function parseRun(value: unknown): Run {
  if (!isObject(value) || Object.keys(value).sort().join(",") !== "project_id,run_id,state") {
    throw new SdkValidationError("Run response is invalid");
  }
  const { run_id, project_id, state } = value;
  if (typeof run_id !== "string" || typeof project_id !== "string" || typeof state !== "string") {
    throw new SdkValidationError("Run response is invalid");
  }
  uuid(run_id); bounded(project_id);
  if (!states.has(state as RunState)) throw new SdkValidationError("Run state is invalid");
  return Object.freeze({ run_id, project_id, state: state as RunState });
}

function apiError(status: number, value: unknown, fallback: string): ApiError {
  if (isObject(value)) {
    const { code, message, request_id, retryable } = value;
    if (typeof code === "string" && code.length <= 128 && typeof message === "string" &&
        message.length <= 2000 && typeof request_id === "string" && typeof retryable === "boolean") {
      return new ApiError(status, code, message, request_id, retryable);
    }
  }
  return new ApiError(status, "api_error", "Control request failed", fallback, false);
}

function uuid(value: string): string {
  if (!uuidPattern.test(value)) throw new SdkValidationError("Identifier is invalid");
  return value.toLowerCase();
}

function bounded(value: string): void {
  if (value.length < 1 || value.length > 256) throw new SdkValidationError();
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
