/** Understand & Act: health cards, alerts, measures and the city overview. */

import { API_URL, ApiError } from "./api";

/** Which records a view is built from. Never mixed without saying so. */
export type DataScope = "all" | "real" | "demo";

export interface SectionStatus {
  section_id: string;
  label: string;
  status: "GOOD" | "MODERATE" | "POOR" | "UNKNOWN";
  answered: number;
  total: number;
  problem_hits: { problem_id: string; problem_name: string; codes: string[] }[];
  reason: string;
}

export interface ProblemFound {
  id: string;
  name: string;
  why_it_matters: string;
  detection_note?: string;
  matched: { question_id: string; codes: string[] }[];
}

export interface HealthCard {
  site_id: string;
  site_name: string;
  city: string;
  visits: number;
  last_visit: string | null;
  first_visit: string | null;
  latest_overall: string | null;
  overall_history: {
    observation_id: string;
    overall: string;
    recorded_at: string;
    synthetic: boolean;
  }[];
  sections: SectionStatus[];
  problems: ProblemFound[];
  completeness: number;
  completeness_label: string;
  answered_questions: number;
  total_questions: number;
  emotions: Record<string, number>;
  synthetic_count: number;
  real_count: number;
  disclaimer: string;
  scope: DataScope;
  built_from: string;
}

export interface AlertCondition {
  key: string;
  operator: string;
  threshold: number;
  value: number | null;
  unit: string;
  passed: boolean;
  source: string;
}

export interface StreamAlert {
  rule_id: string;
  name: string;
  severity: "high" | "medium" | "low";
  message: string;
  why: string;
  conditions: AlertCondition[];
  evidence: {
    observation_id: string;
    question_id: string;
    codes: string[];
    recorded_at: string;
    synthetic: boolean;
  }[];
  advice_sources: {
    claim: string;
    source: string;
    quote?: string;
    url?: string;
    note?: string;
  }[];
  forecast_stale: boolean;
}

export interface ForecastSummary {
  available: boolean;
  rain_mm_48h: number;
  temp_max_c: number | null;
  temp_min_c: number | null;
  fetched_at: string | null;
  stale: boolean;
  age_seconds: number;
  summary: string;
  error: string;
  source: string;
  synthetic: boolean;
}

export interface SiteAlerts {
  site_id: string;
  site_name: string;
  city: string;
  scope: DataScope;
  distance_km?: number;
  forecast: ForecastSummary;
  alerts: StreamAlert[];
  always_include: string;
  never_a_diagnosis: string;
}

export interface Measure {
  id: string;
  name: string;
  type: "nature-based" | "structural";
  plain_language: string;
  ecosystem_benefit: string;
  health_cobenefits: string[];
  effort: "low" | "medium" | "high";
  source: {
    catalogue_name: string;
    section: string;
    page: number;
    doi: string;
    licence: string;
    verified: boolean | null;
  };
  addresses?: { problem_id: string; problem_name: string }[];
}

export interface SiteActions {
  site_id: string;
  site_name: string;
  scope: DataScope;
  problems: ProblemFound[];
  measures: Measure[];
  catalogue: Record<string, string>;
  health_note: string;
}

export interface CityRow {
  site_id: string;
  site_name: string;
  city: string;
  visits: number;
  last_visit: string | null;
  latest_overall: string | null;
  completeness: number;
  completeness_label: string;
  alert_count: number;
  alerts: { rule_id: string; name: string; severity: string }[];
  top_problems: string[];
  synthetic_count: number;
  real_count: number;
}

export interface CityOverview {
  city: string;
  scope: DataScope;
  site_count: number;
  visited: number;
  with_alerts: number;
  disclaimer: string;
  rows: CityRow[];
}

async function get<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`);
  } catch (cause) {
    throw new ApiError("Could not reach StreamLens. You may be offline.", 0, cause);
  }
  if (!response.ok) {
    throw new ApiError(`Request failed (${response.status})`, response.status);
  }
  return (await response.json()) as T;
}

export const insights = {
  healthCard: (siteId: string, scope: DataScope) =>
    get<HealthCard>(`/sites/${encodeURIComponent(siteId)}/health-card?scope=${scope}`),

  siteAlerts: (siteId: string, scope: DataScope) =>
    get<SiteAlerts>(`/sites/${encodeURIComponent(siteId)}/alerts?scope=${scope}`),

  siteActions: (siteId: string, scope: DataScope) =>
    get<SiteActions>(`/sites/${encodeURIComponent(siteId)}/actions?scope=${scope}`),

  alertsNear: (lat: number, lon: number, scope: DataScope, radiusKm = 25) =>
    get<{ results: SiteAlerts[]; checked: number; sites_with_alerts: number }>(
      `/alerts/near?lat=${lat}&lon=${lon}&radius_km=${radiusKm}&scope=${scope}`
    ),

  cityOverview: (city: string, scope: DataScope) =>
    get<CityOverview>(
      `/cities/${encodeURIComponent(city)}/overview?scope=${scope}`
    ),

  cityCsvUrl: (city: string, scope: DataScope) =>
    `${API_URL}/cities/${encodeURIComponent(city)}/overview.csv?scope=${scope}`,
};
