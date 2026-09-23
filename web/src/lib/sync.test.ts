import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "./api";
import {
  StreamLensDB,
  failedItems,
  pendingCount,
  pendingItems,
  queueObservation,
  toBlob,
} from "./db";
import { flushOutbox } from "./sync";
import type { ObservationPayload } from "../types";

function payload(siteId = "C1"): ObservationPayload {
  return {
    site_id: siteId,
    overall: "MODERATE",
    answers: [{ question_id: "channelType", codes: ["NAT"] }],
    emotions: { joy: 2 },
    lang: "en",
    lat: null,
    lon: null,
    accuracy_m: null,
    note: "",
    consent_given: true,
    synthetic: false,
    client_id: "test",
    recorded_at: new Date().toISOString(),
    ai_provider: "mock",
    ai_model: "heuristic-colour-v1",
  };
}

let db: StreamLensDB;

beforeEach(async () => {
  db = new StreamLensDB(`test-${Math.random()}`);
  await db.open();
});

describe("the outbox", () => {
  it("keeps a queued observation with its photos", async () => {
    await queueObservation(
      {
        payload: payload(),
        upstream: new Blob(["jpeg-bytes"], { type: "image/jpeg" }),
      },
      db
    );

    const items = await pendingItems(db);
    expect(items).toHaveLength(1);
    expect(items[0].payload.site_id).toBe("C1");
    expect(items[0].attempts).toBe(0);

    // The photo survives storage byte for byte, whatever the engine does
    // with Blobs.
    const stored = items[0].upstream!;
    expect(stored.type).toBe("image/jpeg");
    expect(new TextDecoder().decode(stored.bytes)).toBe("jpeg-bytes");
    expect(toBlob(stored)).toBeInstanceOf(Blob);
  });
});

describe("flushing", () => {
  it("sends everything queued and empties the outbox", async () => {
    await queueObservation({ payload: payload("C1") }, db);
    await queueObservation({ payload: payload("C2") }, db);

    const client = {
      createObservation: vi.fn().mockResolvedValue({ id: "saved" }),
    };

    const result = await flushOutbox(db, client as never);

    expect(result.sent).toBe(2);
    expect(result.remaining).toBe(0);
    expect(client.createObservation).toHaveBeenCalledTimes(2);
    expect(await pendingCount(db)).toBe(0);
  });

  it("rebuilds the photo as a Blob when sending", async () => {
    const upstream = new Blob(["up"], { type: "image/jpeg" });
    await queueObservation({ payload: payload(), upstream }, db);

    const client = {
      createObservation: vi.fn().mockResolvedValue({ id: "saved" }),
    };
    await flushOutbox(db, client as never);

    expect(client.createObservation).toHaveBeenCalledWith(
      expect.objectContaining({ site_id: "C1" }),
      expect.objectContaining({ upstream: expect.any(Blob) })
    );
  });

  it("keeps an observation queued when the network is down", async () => {
    await queueObservation({ payload: payload() }, db);

    const client = {
      createObservation: vi
        .fn()
        .mockRejectedValue(new ApiError("offline", 0)),
    };
    const result = await flushOutbox(db, client as never);

    expect(result.sent).toBe(0);
    expect(result.offline).toBe(true);
    expect(result.remaining).toBe(1);

    const items = await pendingItems(db);
    expect(items[0].attempts).toBe(1);
    expect(items[0].permanentlyFailed).toBe(false);
  });

  it("stops after the first network failure instead of hammering the rest", async () => {
    await queueObservation({ payload: payload("C1") }, db);
    await queueObservation({ payload: payload("C2") }, db);

    const client = {
      createObservation: vi.fn().mockRejectedValue(new ApiError("offline", 0)),
    };
    await flushOutbox(db, client as never);

    expect(client.createObservation).toHaveBeenCalledTimes(1);
  });

  it("gives up on an observation the server rejected outright", async () => {
    await queueObservation({ payload: payload() }, db);

    const client = {
      createObservation: vi
        .fn()
        .mockRejectedValue(new ApiError("unknown site", 404)),
    };
    const result = await flushOutbox(db, client as never);

    expect(result.failed).toBe(1);
    expect(result.remaining).toBe(0);

    const failed = await failedItems(db);
    expect(failed).toHaveLength(1);
    expect(failed[0].lastError).toBe("unknown site");
  });

  it("retries a server error but not a bad request", async () => {
    expect(new ApiError("boom", 500).isRetryable).toBe(true);
    expect(new ApiError("offline", 0).isRetryable).toBe(true);
    expect(new ApiError("bad", 422).isRetryable).toBe(false);
  });
});
