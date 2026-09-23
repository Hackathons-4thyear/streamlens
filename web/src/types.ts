/** Shapes shared with the API. Mirrors api/app/schemas.py. */

export interface Site {
  id: string;
  name: string;
  city: string;
  city_id: string;
  country: string;
  lang: string;
  lat: number | null;
  lon: number | null;
  altitude_m: number | null;
}

export interface SitesResponse {
  attribution: string;
  source: string | null;
  fetched_at: string | null;
  count: number;
  cities: string[];
  synthetic: boolean;
  sites: Site[];
}

export interface AnswerOption {
  code: string;
  label: string;
  explain: string;
  source: string;
}

export interface Question {
  id: string;
  section: string;
  type: "single" | "multi";
  ai_suggestable: boolean;
  source: string;
  order: number;
  label: string;
  explain: string;
  photo_hint?: string | Record<string, never>;
  terms: string[];
  options: AnswerOption[];
}

export interface Section {
  id: string;
  order: number;
  label: string;
}

export interface QuestionSet {
  version: string;
  lang: string;
  lang_requested: string;
  languages: string[];
  machine_translated: string[];
  translation_note: string;
  unknown_code: string;
  sections: Section[];
  glossary: Record<string, string>;
  questions: Question[];
}

export interface QualityIssue {
  code: string;
  severity: "warn" | "block";
  message: string;
}

export interface PhotoQuality {
  role: string;
  width: number;
  height: number;
  blur_score: number;
  brightness: number;
  issues: QualityIssue[];
  ok: boolean;
  exif_stripped: boolean;
}

export interface LocationCheck {
  provided: boolean;
  distance_m: number | null;
  far_from_site: boolean;
  message: string;
}

export interface SuggestionChip {
  question_id: string;
  suggested_code: string;
  additional_codes: string[];
  confidence: number;
  reason: string;
  needs_review: boolean;
  review_reason: string;
}

export interface DroppedSuggestion {
  question_id: string;
  codes: string[];
  why: string;
}

export interface SuggestResponse {
  site_id: string;
  site_name: string;
  provider: string;
  model: string;
  is_mock: boolean;
  prompt_version: string;
  provider_note: string;
  generated_at: string;
  photo_quality: PhotoQuality[];
  location: LocationCheck;
  suggestions: SuggestionChip[];
  dropped: DroppedSuggestion[];
  notice: string;
}

export type Emotion = "joy" | "serenity" | "anger" | "fear";

export interface ObservationAnswerPayload {
  question_id: string;
  codes: string[];
  ai_suggested_code?: string | null;
  ai_confidence?: number | null;
}

export interface ObservationPayload {
  site_id: string;
  overall: string;
  answers: ObservationAnswerPayload[];
  emotions: Partial<Record<Emotion, number>>;
  lang: string;
  lat: number | null;
  lon: number | null;
  accuracy_m: number | null;
  note: string;
  consent_given: boolean;
  synthetic: boolean;
  client_id: string;
  recorded_at: string;
  ai_provider: string;
  ai_model: string;
}

export interface ObservationResponse {
  id: string;
  site_id: string;
  site_name: string;
  overall: string;
  ai_agreement: number | null;
  recorded_at: string;
  created_at: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  ai_provider: string;
  ai_model: string;
  ai_is_mock: boolean;
  questions: number;
  sites: number;
  prompt_version: string;
}
