import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { ApiError, NexusClient, SdkValidationError } from "../dist/index.js";

test("transport failures do not disclose exception text", async () => {
  const client = new NexusClient({
    async send() {
      throw new Error("SECRET_CANARY");
    },
  });
  await assert.rejects(
    client.listCapabilities(),
    (error) => error instanceof ApiError && !String(error).includes("SECRET_CANARY"),
  );
});

test("invalid paths, keys, statuses, and traces fail closed", async () => {
  const client = new NexusClient({
    async send() {
      return { status: 200, body: [], headers: { "x-trace-id": "bad" } };
    },
  });
  await assert.rejects(client.request("GET", "/v1/../secrets"), SdkValidationError);
  await assert.rejects(
    client.request("POST", "/v1/runs", { idempotencyKey: "short" }),
    SdkValidationError,
  );
  await assert.rejects(client.listProviders(), SdkValidationError);
});

test("SDK source has no ambient credential or endpoint lookup", async () => {
  const source = await readFile(new URL("../src/index.ts", import.meta.url), "utf8");
  assert.equal(source.includes("process.env"), false);
  assert.equal(source.includes("Authorization"), false);
  assert.equal(source.includes("http://"), false);
  assert.equal(source.includes("https://"), false);
});
