import { describe, expect, it } from "vitest";

import type { Question, SuggestionChip } from "../types";
import {
  agreementStats,
  answeredCount,
  answersReducer,
  initialAnswers,
  pendingChips,
  toPayloadAnswers,
} from "./answers";

function chip(overrides: Partial<SuggestionChip> = {}): SuggestionChip {
  return {
    question_id: "channelType",
    suggested_code: "ART",
    additional_codes: [],
    confidence: 0.8,
    reason: "The bed is grey concrete.",
    needs_review: false,
    review_reason: "",
    ...overrides,
  };
}

function question(overrides: Partial<Question> = {}): Question {
  return {
    id: "channelType",
    section: "channel",
    type: "single",
    ai_suggestable: true,
    source: "streamcheck-fhir-docs",
    order: 2,
    label: "Channel bed",
    explain: "",
    terms: [],
    options: [
      { code: "NAT", label: "Natural", explain: "", source: "x" },
      { code: "ART", label: "Artificial", explain: "", source: "x" },
      { code: "NS", label: "Not sure", explain: "", source: "x" },
    ],
    ...overrides,
  };
}

describe("a suggestion starts as pending and is not an answer", () => {
  it("holds no codes until the citizen acts", () => {
    const state = initialAnswers([chip()]);
    expect(state.channelType.codes).toEqual([]);
    expect(state.channelType.status).toBe("pending");
    expect(answeredCount(state)).toBe(0);
    expect(pendingChips(state)).toEqual(["channelType"]);
  });

  it("is never submitted while still pending - silence is not consent", () => {
    const state = initialAnswers([chip()]);
    expect(toPayloadAnswers(state, [question()])).toEqual([]);
  });
});

describe("accepting", () => {
  it("adopts the AI's code and records agreement", () => {
    let state = initialAnswers([chip()]);
    state = answersReducer(state, { type: "accept", questionId: "channelType" });

    expect(state.channelType.codes).toEqual(["ART"]);
    expect(state.channelType.status).toBe("accepted");
    expect(pendingChips(state)).toEqual([]);
  });

  it("adopts every code of a multi-answer suggestion", () => {
    let state = initialAnswers([
      chip({ question_id: "habitats", suggested_code: "SB", additional_codes: ["RF"] }),
    ]);
    state = answersReducer(state, { type: "accept", questionId: "habitats" });
    expect(state.habitats.codes).toEqual(["SB", "RF"]);
    expect(state.habitats.status).toBe("accepted");
  });
});

describe("rejecting", () => {
  it("clears the answer and leaves it unsubmitted", () => {
    let state = initialAnswers([chip()]);
    state = answersReducer(state, { type: "reject", questionId: "channelType" });

    expect(state.channelType.codes).toEqual([]);
    expect(state.channelType.status).toBe("rejected");
    expect(toPayloadAnswers(state, [question()])).toEqual([]);
  });

  it("keeps what the AI had said, so the disagreement is recorded", () => {
    let state = initialAnswers([chip()]);
    state = answersReducer(state, { type: "reject", questionId: "channelType" });
    state = answersReducer(state, {
      type: "toggle",
      questionId: "channelType",
      code: "NAT",
      multi: false,
    });

    expect(state.channelType.status).toBe("changed");
    expect(toPayloadAnswers(state, [question()])).toEqual([
      {
        question_id: "channelType",
        codes: ["NAT"],
        ai_suggested_code: "ART",
        ai_confidence: 0.8,
      },
    ]);
  });
});

describe("choosing answers", () => {
  it("replaces the choice on a single-answer question", () => {
    let state = initialAnswers([chip()]);
    state = answersReducer(state, {
      type: "toggle",
      questionId: "channelType",
      code: "NAT",
      multi: false,
    });
    state = answersReducer(state, {
      type: "toggle",
      questionId: "channelType",
      code: "NS",
      multi: false,
    });
    expect(state.channelType.codes).toEqual(["NS"]);
  });

  it("accumulates choices on a multi-answer question", () => {
    let state = {};
    for (const code of ["SB", "RF"]) {
      state = answersReducer(state, {
        type: "toggle",
        questionId: "habitats",
        code,
        multi: true,
      });
    }
    expect((state as never as Record<string, { codes: string[] }>).habitats.codes).toEqual([
      "SB",
      "RF",
    ]);
  });

  it("treats 'none' as exclusive of everything else", () => {
    let state = answersReducer({}, {
      type: "toggle",
      questionId: "habitats",
      code: "SB",
      multi: true,
    });
    state = answersReducer(state, {
      type: "toggle",
      questionId: "habitats",
      code: "NONE",
      multi: true,
    });
    expect(state.habitats.codes).toEqual(["NONE"]);

    state = answersReducer(state, {
      type: "toggle",
      questionId: "habitats",
      code: "RF",
      multi: true,
    });
    expect(state.habitats.codes).toEqual(["RF"]);
  });

  it("marks an answer to a question the AI ignored as the citizen's own", () => {
    const state = answersReducer({}, {
      type: "toggle",
      questionId: "sewage",
      code: "N",
      multi: false,
    });
    expect(state.sewage.status).toBe("manual");
    expect(state.sewage.aiSuggestedCode).toBeUndefined();
  });

  it("counts choosing the AI's own code as agreement, however it was reached", () => {
    let state = initialAnswers([chip()]);
    state = answersReducer(state, {
      type: "toggle",
      questionId: "channelType",
      code: "ART",
      multi: false,
    });
    expect(state.channelType.status).toBe("accepted");
  });
});

describe("agreement statistics", () => {
  it("reports the share of suggestions the citizen kept", () => {
    let state = initialAnswers([
      chip({ question_id: "channelType", suggested_code: "ART" }),
      chip({ question_id: "bankType", suggested_code: "NAT" }),
      chip({ question_id: "sewage", suggested_code: "N" }),
    ]);
    state = answersReducer(state, { type: "accept", questionId: "channelType" });
    state = answersReducer(state, { type: "accept", questionId: "bankType" });
    state = answersReducer(state, {
      type: "toggle",
      questionId: "sewage",
      code: "Y",
      multi: false,
    });

    const stats = agreementStats(state);
    expect(stats.accepted).toBe(2);
    expect(stats.changed).toBe(1);
    expect(stats.rate).toBeCloseTo(2 / 3);
  });

  it("reports no rate when the AI suggested nothing that was acted on", () => {
    expect(agreementStats({}).rate).toBeNull();
  });
});

describe("the submitted payload", () => {
  it("never includes the overall rating, which travels in its own field", () => {
    const state = answersReducer({}, {
      type: "toggle",
      questionId: "overall",
      code: "GOOD",
      multi: false,
    });
    expect(toPayloadAnswers(state, [question({ id: "overall" })])).toEqual([]);
  });

  it("drops answers to questions that are not in the catalogue", () => {
    const state = answersReducer({}, {
      type: "toggle",
      questionId: "notAQuestion",
      code: "Y",
      multi: false,
    });
    expect(toPayloadAnswers(state, [question()])).toEqual([]);
  });
});
