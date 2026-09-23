import type {
  HealthResponse,
  ObservationPayload,
  ObservationResponse,
  QuestionSet,
  SitesResponse,
  SuggestResponse,
} from "../types";

export const API_URL = (
  import.meta.env.VITE_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** A failed request that a later retry could still succeed at. */
  get isRetryable(): boolean {
    return this.status === 0 || this.status >= 500;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, init);
  } catch (cause) {
    throw new ApiError(
      "Could not reach StreamLens. You may be offline.",
      0,
      cause
    );
  }

  if (!response.ok) {
    let detail: unknown;
    try {
      detail = (await response.json())?.detail;
    } catch {
      detail = await response.text().catch(() => undefined);
    }
    throw new ApiError(
      typeof detail === "string" ? detail : `Request failed (${response.status})`,
      response.status,
      detail
    );
  }

  return (await response.json()) as T;
}

export const api = {
  health: () => request<HealthResponse>("/health"),

  sites: () => request<SitesResponse>("/sites"),

  questions: (lang: string) =>
    request<QuestionSet>(`/questions?lang=${encodeURIComponent(lang)}`),

  suggest: (args: {
    siteId: string;
    upstream?: Blob | null;
    downstream?: Blob | null;
    lat?: number | null;
    lon?: number | null;
  }) => {
    const form = new FormData();
    form.append("site_id", args.siteId);
    if (args.upstream) form.append("upstream", args.upstream, "upstream.jpg");
    if (args.downstream) form.append("downstream", args.downstream, "downstream.jpg");
    if (args.lat != null) form.append("lat", String(args.lat));
    if (args.lon != null) form.append("lon", String(args.lon));
    return request<SuggestResponse>("/assess/suggest", {
      method: "POST",
      body: form,
    });
  },

  createObservation: (
    payload: ObservationPayload,
    photos: { upstream?: Blob | null; downstream?: Blob | null } = {}
  ) => {
    const form = new FormData();
    form.append("payload", JSON.stringify(payload));
    if (photos.upstream) form.append("upstream", photos.upstream, "upstream.jpg");
    if (photos.downstream)
      form.append("downstream", photos.downstream, "downstream.jpg");
    return request<ObservationResponse>("/observations", {
      method: "POST",
      body: form,
    });
  },
};
