/**
 * The bundled sample photographs.
 *
 * They exist so the app can be tried at a desk, in a lecture hall, or by a
 * judge with no stream within reach. Every one is a Creative Commons or public
 * domain photograph from Wikimedia Commons, shipped at the size the app would
 * send anyway, with its author and licence carried alongside it rather than
 * buried in a repository file: the attribution has to be visible where the
 * photograph is used.
 */

export interface SamplePhoto {
  id: string;
  /** Path under the site root, e.g. "samples/oslo.jpg". */
  file: string;
  shows: string;
  /** Why this one is in the set: what a visitor should watch it do. */
  purpose: string;
  author: string;
  licence: string;
  licence_url: string;
  source_url: string;
  width: number;
  height: number;
  kb: number;
}

const base = import.meta.env.BASE_URL || "/";

let cached: Promise<SamplePhoto[]> | null = null;

export function loadSamples(): Promise<SamplePhoto[]> {
  if (!cached) {
    cached = fetch(`${base}samples/samples.json`)
      .then((response) => {
        if (!response.ok) throw new Error(`samples.json (${response.status})`);
        return response.json() as Promise<{ samples: SamplePhoto[] }>;
      })
      .then((doc) => doc.samples)
      .catch((error) => {
        // Let a later attempt work: a failed fetch should not poison the cache.
        cached = null;
        throw error;
      });
  }
  return cached;
}

export function sampleUrl(sample: SamplePhoto): string {
  return `${base}${sample.file}`;
}

/** Fetch one sample as a Blob, so it enters the flow exactly like a camera photo. */
export async function fetchSampleBlob(sample: SamplePhoto): Promise<Blob> {
  const response = await fetch(sampleUrl(sample));
  if (!response.ok) throw new Error(`${sample.id} (${response.status})`);
  return response.blob();
}
