/**
 * The answer state machine.
 *
 * This is where "AI suggests, humans decide" is actually implemented. A chip
 * starts `pending`: the AI has proposed something and nobody has agreed to it.
 * It only becomes an answer when the citizen accepts it, changes it, or answers
 * a question the AI said nothing about. A `pending` chip is NOT submitted -
 * silence is not consent.
 *
 * Kept as plain functions so it can be tested without rendering anything.
 */

import type { ObservationAnswerPayload, Question, SuggestionChip } from "../types";

export type AnswerStatus =
  /** The AI suggested it; the citizen has not responded yet. Not submitted. */
  | "pending"
  /** The citizen kept the AI's suggestion. */
  | "accepted"
  /** The citizen rejected it and has not chosen anything instead. Not submitted. */
  | "rejected"
  /** The citizen chose something other than what the AI suggested. */
  | "changed"
  /** The citizen answered a question the AI did not suggest. */
  | "manual";

export interface AnswerState {
  codes: string[];
  status: AnswerStatus;
  aiSuggestedCode?: string;
  aiAllCodes?: string[];
  aiConfidence?: number;
}

export type AnswersState = Record<string, AnswerState>;

/** Codes that mean "none of the above" and cannot combine with anything else. */
const EXCLUSIVE_CODES = new Set(["NONE", "NS"]);

export type AnswerAction =
  | { type: "init"; chips: SuggestionChip[] }
  | { type: "accept"; questionId: string }
  | { type: "reject"; questionId: string }
  | { type: "set"; questionId: string; codes: string[] }
  | { type: "toggle"; questionId: string; code: string; multi: boolean }
  | { type: "reset" };

export function initialAnswers(chips: SuggestionChip[] = []): AnswersState {
  const state: AnswersState = {};
  for (const chip of chips) {
    state[chip.question_id] = {
      codes: [],
      status: "pending",
      aiSuggestedCode: chip.suggested_code,
      aiAllCodes: [chip.suggested_code, ...chip.additional_codes],
      aiConfidence: chip.confidence,
    };
  }
  return state;
}

function statusFor(previous: AnswerState | undefined, codes: string[]): AnswerStatus {
  if (codes.length === 0) {
    return previous?.aiSuggestedCode ? "rejected" : "pending";
  }
  if (!previous?.aiSuggestedCode) return "manual";

  const suggested = [...(previous.aiAllCodes ?? [])].sort().join("|");
  const chosen = [...codes].sort().join("|");
  return suggested === chosen ? "accepted" : "changed";
}

export function answersReducer(
  state: AnswersState,
  action: AnswerAction
): AnswersState {
  switch (action.type) {
    case "init":
      return initialAnswers(action.chips);

    case "reset":
      return {};

    case "accept": {
      const previous = state[action.questionId];
      if (!previous?.aiSuggestedCode) return state;
      return {
        ...state,
        [action.questionId]: {
          ...previous,
          codes: previous.aiAllCodes ?? [previous.aiSuggestedCode],
          status: "accepted",
        },
      };
    }

    case "reject": {
      const previous = state[action.questionId];
      if (!previous) return state;
      return {
        ...state,
        [action.questionId]: { ...previous, codes: [], status: "rejected" },
      };
    }

    case "set": {
      const previous = state[action.questionId];
      return {
        ...state,
        [action.questionId]: {
          ...previous,
          codes: action.codes,
          status: statusFor(previous, action.codes),
        },
      };
    }

    case "toggle": {
      const previous = state[action.questionId];
      const current = previous?.codes ?? [];
      let next: string[];

      if (!action.multi) {
        next = current.includes(action.code) ? [] : [action.code];
      } else if (current.includes(action.code)) {
        next = current.filter((c) => c !== action.code);
      } else if (EXCLUSIVE_CODES.has(action.code)) {
        next = [action.code];
      } else {
        next = [...current.filter((c) => !EXCLUSIVE_CODES.has(c)), action.code];
      }

      return {
        ...state,
        [action.questionId]: {
          ...previous,
          codes: next,
          status: statusFor(previous, next),
        },
      };
    }

    default:
      return state;
  }
}

// --------------------------------------------------------------------------
// Selectors
// --------------------------------------------------------------------------

/** Chips the citizen has not responded to yet. */
export function pendingChips(state: AnswersState): string[] {
  return Object.entries(state)
    .filter(([, value]) => value.status === "pending" && value.aiSuggestedCode)
    .map(([id]) => id);
}

export function answeredCount(state: AnswersState): number {
  return Object.values(state).filter((value) => value.codes.length > 0).length;
}

/**
 * What gets submitted: only questions the citizen actually answered, each
 * carrying what the AI had suggested so agreement can be measured later.
 */
export function toPayloadAnswers(
  state: AnswersState,
  questions: Question[]
): ObservationAnswerPayload[] {
  const known = new Set(questions.map((q) => q.id));
  return Object.entries(state)
    .filter(([id, value]) => value.codes.length > 0 && known.has(id) && id !== "overall")
    .map(([id, value]) => ({
      question_id: id,
      codes: value.codes,
      ai_suggested_code: value.aiSuggestedCode ?? null,
      ai_confidence: value.aiConfidence ?? null,
    }));
}

export interface AgreementStats {
  accepted: number;
  changed: number;
  rejected: number;
  pending: number;
  manual: number;
  /** Share of AI suggestions the citizen kept, or null if there were none. */
  rate: number | null;
}

export function agreementStats(state: AnswersState): AgreementStats {
  const counts = { accepted: 0, changed: 0, rejected: 0, pending: 0, manual: 0 };
  for (const value of Object.values(state)) {
    counts[value.status] += 1;
  }
  const judged = counts.accepted + counts.changed;
  return {
    ...counts,
    rate: judged > 0 ? counts.accepted / judged : null,
  };
}
