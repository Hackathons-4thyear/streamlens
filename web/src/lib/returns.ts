/** Return: quests, points, the team leaderboard, coverage and wellbeing. */

import { API_URL, ApiError } from "./api";
import type { DataScope } from "./insights";

export interface Quest {
  rule_id: string;
  name: string;
  site_id: string;
  site_name: string;
  city: string;
  priority: number;
  why: string;
  facts: Record<string, unknown>;
  lat: number | null;
  lon: number | null;
  /** True when the weather behind this quest was planted for the demo. */
  weather_synthetic: boolean;
  distance_km?: number | null;
}

export interface TeamStanding {
  team: string;
  points: number;
  sites_covered: number;
  observations: number;
  members: number;
  cities: string[];
}

export interface Leaderboard {
  teams: TeamStanding[];
  team_count: number;
  individuals_ranked: false;
  min_team_members: number;
  teams_withheld_too_small: number;
  why_teams_only: string;
  why_withheld: string;
  why_not_volume: string[];
  daily_cap: number;
}

export interface CoverageSite {
  site_id: string;
  site_name: string;
  city: string;
  lat: number | null;
  lon: number | null;
  visited: boolean;
}

export interface Coverage {
  since: string;
  city: string | null;
  total_sites: number;
  covered: number;
  share: number;
  days: number;
  sites: CoverageSite[];
}

export interface Wellbeing {
  available: boolean;
  scope: "personal" | "community";
  people: number;
  visits: number;
  by_rating: Record<
    string,
    { visits: number; positive_share: number; averages: Record<string, number> }
  >;
  headline: string;
  caveat: string;
  min_group: number;
  research_link: { text: string; url: string };
  not_a_health_measure: string;
}

export interface MyPoints {
  total_points: number;
  observations: number;
  daily_cap: number;
  awards: {
    observation_id: string;
    site_id: string;
    points: number;
    capped_from: number | null;
    recorded_at: string;
    awards: { rule_id: string; points: number; detail: string }[];
  }[];
  why_not_volume: string[];
  never_awarded_for: string[];
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

export const returns = {
  quests: (scope: DataScope, lat?: number | null, lon?: number | null) => {
    const where = lat != null && lon != null ? `&lat=${lat}&lon=${lon}` : "";
    return get<{ quests: Quest[]; total_open: number; principle: string[] }>(
      `/quests?scope=${scope}&limit=12${where}`
    );
  },

  siteQuests: (siteId: string, scope: DataScope) =>
    get<{ quests: Quest[] }>(
      `/sites/${encodeURIComponent(siteId)}/quests?scope=${scope}`
    ),

  leaderboard: (scope: DataScope, city?: string | null) =>
    get<Leaderboard>(
      `/leaderboard?scope=${scope}${city ? `&city=${encodeURIComponent(city)}` : ""}`
    ),

  coverage: (scope: DataScope, days = 30, city?: string | null) =>
    get<Coverage>(
      `/coverage?scope=${scope}&days=${days}${city ? `&city=${encodeURIComponent(city)}` : ""}`
    ),

  wellbeing: (scope: DataScope, clientId: string, community: boolean) =>
    get<Wellbeing>(
      `/wellbeing?scope=${scope}&community=${community}` +
        (community ? "" : `&client_id=${encodeURIComponent(clientId)}`)
    ),

  myPoints: (scope: DataScope, clientId: string) =>
    get<MyPoints>(
      `/points/me?scope=${scope}&client_id=${encodeURIComponent(clientId)}`
    ),

  fhirUrl: (observationId: string) =>
    `${API_URL}/observations/${encodeURIComponent(observationId)}/fhir`,

  cityFhirUrl: (city: string, scope: DataScope) =>
    `${API_URL}/cities/${encodeURIComponent(city)}/fhir?scope=${scope}`,
};
