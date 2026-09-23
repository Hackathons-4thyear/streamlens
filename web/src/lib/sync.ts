/**
 * Flushing the outbox.
 *
 * The rule that matters: a network failure leaves the item in the queue, while
 * a server rejection (a 4xx - a malformed payload, an unknown site) marks it
 * permanently failed. Retrying a 422 forever would hide a bug and quietly burn
 * the citizen's battery.
 */

import { ApiError, api } from "./api";
import {
  markAttemptFailed,
  markSent,
  pendingItems,
  toBlob,
  type StreamLensDB,
  db as defaultDb,
} from "./db";

export interface FlushResult {
  sent: number;
  failed: number;
  remaining: number;
  offline: boolean;
}

export async function flushOutbox(
  database: StreamLensDB = defaultDb,
  client = api
): Promise<FlushResult> {
  const items = await pendingItems(database);
  let sent = 0;
  let failed = 0;
  let offline = false;

  for (const item of items) {
    if (item.id == null) continue;
    try {
      await client.createObservation(item.payload, {
        upstream: toBlob(item.upstream),
        downstream: toBlob(item.downstream),
      });
      await markSent(item.id, database);
      sent += 1;
    } catch (error) {
      const apiError =
        error instanceof ApiError
          ? error
          : new ApiError(String(error), 0, error);

      if (apiError.isRetryable) {
        // Still offline, or the server is down. Keep it and stop trying the
        // rest - they would all fail the same way.
        await markAttemptFailed(item.id, apiError.message, false, database);
        offline = true;
        break;
      }

      await markAttemptFailed(item.id, apiError.message, true, database);
      failed += 1;
    }
  }

  const remaining = (await pendingItems(database)).length;
  return { sent, failed, remaining, offline };
}

/** Flush now, and again whenever the browser says the network is back. */
export function startAutoSync(
  onResult: (result: FlushResult) => void,
  database: StreamLensDB = defaultDb
): () => void {
  let running = false;

  const run = async () => {
    if (running || !navigator.onLine) return;
    running = true;
    try {
      onResult(await flushOutbox(database));
    } finally {
      running = false;
    }
  };

  void run();
  window.addEventListener("online", run);
  return () => window.removeEventListener("online", run);
}
