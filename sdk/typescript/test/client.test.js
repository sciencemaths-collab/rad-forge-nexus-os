import assert from "node:assert/strict";
import test from "node:test";

import { ApiError, NexusClient, SdkValidationError } from "../dist/index.js";

const run = {
  run_id: "00000000-0000-4000-8000-000000000001",
  project_id: "project-1",
  state: "SPECIFYING",
};

test("createRun returns validated immutable run and preserves headers", async () => {
  const calls = [];
  const transport = {
    async send(request) {
      calls.push(request);
      return { status: 202, body: run, headers: { "x-trace-id": "a".repeat(32) } };
    },
  };
  const value = await new NexusClient(transport).createRun("project-1", {
    idempotencyKey: "1234567890abcdef",
    requestId: "request-1",
  });
  assert.deepEqual(value, run);
  assert.equal(Object.isFrozen(value), true);
  assert.equal(calls[0].path, "/v1/runs");
  assert.equal(calls[0].headers["Idempotency-Key"], "1234567890abcdef");
  assert.equal(calls[0].headers["X-Request-Id"], "request-1");
});

test("read collections and run paths are typed", async () => {
  const transport = {
    async send(request) {
      if (request.path === "/v1/providers") return { status: 200, body: [], headers: {} };
      return { status: 200, body: run, headers: {} };
    },
  };
  const client = new NexusClient(transport);
  assert.deepEqual(await client.listProviders(), []);
  assert.equal((await client.getRun(run.run_id)).state, "SPECIFYING");
});

test("errors and hostile responses fail safely", async () => {
  const denied = new NexusClient({
    async send() {
      return {
        status: 403,
        body: { code: "forbidden", message: "Denied", request_id: "r1", retryable: false },
        headers: {},
      };
    },
  });
  await assert.rejects(denied.listProviders(), ApiError);

  const hostile = new NexusClient({
    async send() {
      return { status: 200, body: { unexpected: "SECRET_CANARY" }, headers: {} };
    },
  });
  await assert.rejects(hostile.getRun(run.run_id), SdkValidationError);
  await assert.rejects(hostile.getRun("not-a-uuid"), SdkValidationError);
});
