/**
 * Local storage for a field app that expects to be offline.
 *
 * Two tables:
 *  - `outbox`  submitted observations waiting for a network, photos and all.
 *  - `cache`   the site list and question set, so a cold start beside a stream
 *              with no signal still works.
 */

import Dexie, { type Table } from "dexie";

import type { ObservationPayload } from "../types";

/**
 * A photo on its way out, stored as raw bytes rather than as a Blob.
 *
 * IndexedDB is supposed to store Blobs, but Safari has shipped versions that
 * lose them, and test fakes drop them silently. An ArrayBuffer plus its media
 * type survives structured cloning everywhere, and a Blob is cheap to rebuild.
 * Losing a citizen's photo because of a storage quirk is not acceptable.
 */
export interface StoredPhoto {
  bytes: ArrayBuffer;
  type: string;
}

/** Blob.arrayBuffer() only arrived in Safari 14, so fall back to FileReader. */
function readBytes(blob: Blob): Promise<ArrayBuffer> {
  if (typeof blob.arrayBuffer === "function") return blob.arrayBuffer();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as ArrayBuffer);
    reader.onerror = () => reject(reader.error ?? new Error("could not read photo"));
    reader.readAsArrayBuffer(blob);
  });
}

export async function toStoredPhoto(
  blob: Blob | null | undefined
): Promise<StoredPhoto | undefined> {
  if (!blob) return undefined;
  return { bytes: await readBytes(blob), type: blob.type || "image/jpeg" };
}

export function toBlob(photo: StoredPhoto | null | undefined): Blob | undefined {
  if (!photo) return undefined;
  return new Blob([photo.bytes], { type: photo.type });
}

export interface OutboxItem {
  id?: number;
  payload: ObservationPayload;
  upstream?: StoredPhoto | null;
  downstream?: StoredPhoto | null;
  createdAt: string;
  attempts: number;
  lastError?: string;
  /** Set when the server rejected it for good - retrying will not help. */
  permanentlyFailed?: boolean;
}

export interface CacheItem {
  key: string;
  value: unknown;
  savedAt: string;
}

export class StreamLensDB extends Dexie {
  outbox!: Table<OutboxItem, number>;
  cache!: Table<CacheItem, string>;

  constructor(name = "streamlens") {
    super(name);
    this.version(1).stores({
      outbox: "++id, createdAt, permanentlyFailed",
      cache: "key",
    });
  }
}

export const db = new StreamLensDB();

// --------------------------------------------------------------------------
// Outbox
// --------------------------------------------------------------------------

export async function queueObservation(
  item: {
    payload: ObservationPayload;
    upstream?: Blob | null;
    downstream?: Blob | null;
  },
  database: StreamLensDB = db
): Promise<number> {
  return database.outbox.add({
    payload: item.payload,
    upstream: await toStoredPhoto(item.upstream),
    downstream: await toStoredPhoto(item.downstream),
    createdAt: new Date().toISOString(),
    attempts: 0,
  });
}

/** Items still worth sending, oldest first. */
export async function pendingItems(
  database: StreamLensDB = db
): Promise<OutboxItem[]> {
  const all = await database.outbox.orderBy("createdAt").toArray();
  return all.filter((item) => !item.permanentlyFailed);
}

export async function pendingCount(database: StreamLensDB = db): Promise<number> {
  return (await pendingItems(database)).length;
}

export async function failedItems(
  database: StreamLensDB = db
): Promise<OutboxItem[]> {
  const all = await database.outbox.toArray();
  return all.filter((item) => item.permanentlyFailed);
}

export async function markSent(
  id: number,
  database: StreamLensDB = db
): Promise<void> {
  await database.outbox.delete(id);
}

export async function markAttemptFailed(
  id: number,
  error: string,
  permanent: boolean,
  database: StreamLensDB = db
): Promise<void> {
  const item = await database.outbox.get(id);
  if (!item) return;
  await database.outbox.update(id, {
    attempts: item.attempts + 1,
    lastError: error,
    permanentlyFailed: permanent,
  });
}

// --------------------------------------------------------------------------
// Catalogue cache
// --------------------------------------------------------------------------

export async function cacheSet(
  key: string,
  value: unknown,
  database: StreamLensDB = db
): Promise<void> {
  await database.cache.put({ key, value, savedAt: new Date().toISOString() });
}

export async function cacheGet<T>(
  key: string,
  database: StreamLensDB = db
): Promise<T | undefined> {
  const row = await database.cache.get(key);
  return row?.value as T | undefined;
}
