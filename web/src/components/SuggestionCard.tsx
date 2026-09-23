import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { AnswerState } from "../state/answers";
import type { Question, SuggestionChip } from "../types";
import { GlossaryTerm, withGlossary } from "./GlossaryTerm";
import { ConfidenceBar } from "./ui";

const STATUS_STYLES: Record<string, string> = {
  pending: "border-line",
  accepted: "border-brand bg-brand-light/40",
  changed: "border-amber-500 bg-amber-50",
  manual: "border-brand bg-brand-light/40",
  rejected: "border-slate-400 bg-slate-50",
};

export function SuggestionCard({
  question,
  chip,
  answer,
  glossary,
  onAccept,
  onReject,
  onToggle,
}: {
  question: Question;
  chip?: SuggestionChip;
  answer?: AnswerState;
  glossary: Record<string, string>;
  onAccept: () => void;
  onReject: () => void;
  onToggle: (code: string) => void;
}) {
  const { t } = useTranslation();
  const status = answer?.status ?? "pending";
  const [picking, setPicking] = useState(!chip);

  const optionLabel = (code: string) =>
    question.options.find((o) => o.code === code)?.label ?? code;

  const suggestedCodes = chip
    ? [chip.suggested_code, ...chip.additional_codes]
    : [];
  const chosen = answer?.codes ?? [];
  const showOptions = picking || status === "rejected" || !chip;

  const glossaryTitle = t("review.glossaryTitle");

  return (
    <li
      className={`rounded-2xl border-2 bg-white p-4 shadow-sm ${
        STATUS_STYLES[status] ?? "border-line"
      }`}
      data-testid={`card-${question.id}`}
      data-status={status}
    >
      <div className="mb-1 flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-base font-semibold text-ink">
          {withGlossary(question.label, glossary, glossaryTitle)}
        </h3>
        {chip?.needs_review && status === "pending" ? (
          <span className="rounded-full bg-[--color-warn-bg] px-2 py-0.5 text-xs font-bold text-[--color-warn-ink]">
            {t("review.needsReview")}
          </span>
        ) : null}
        {chosen.length > 0 ? (
          <span className="rounded-full bg-brand px-2 py-0.5 text-xs font-bold text-white">
            {t("review.answered")}
          </span>
        ) : null}
      </div>

      <p className="mb-3 text-sm leading-relaxed text-muted">
        {withGlossary(question.explain, glossary, glossaryTitle)}
      </p>

      {question.terms.length > 0 ? (
        <p className="mb-3 flex flex-wrap gap-2 text-sm">
          {question.terms
            .filter((term) => glossary[term])
            .map((term) => (
              <GlossaryTerm
                key={term}
                term={term}
                explanation={glossary[term]}
                title={glossaryTitle}
              />
            ))}
        </p>
      ) : null}

      {chip ? (
        <div className="mb-3 rounded-xl bg-slate-50 p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm">
              <span className="font-semibold text-muted">
                {t("review.aiSuggests")}:{" "}
              </span>
              <span className="font-bold text-ink">
                {suggestedCodes.map(optionLabel).join(", ")}
              </span>
            </p>
            <ConfidenceBar value={chip.confidence} label={t("review.confidence")} />
          </div>
          <p className="text-sm text-muted">
            <span className="font-semibold">{t("review.why")}: </span>
            {chip.reason}
          </p>
          {chip.review_reason ? (
            <p className="mt-2 text-sm font-medium text-[--color-warn-ink]">
              {chip.review_reason}
            </p>
          ) : null}
        </div>
      ) : (
        <p className="mb-3 text-sm text-muted italic">
          {t("review.noSuggestions")}
        </p>
      )}

      {chip ? (
        <div className="mb-2 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => {
              onAccept();
              setPicking(false);
            }}
            aria-pressed={status === "accepted"}
            className={`tap flex-1 rounded-xl border-2 px-3 py-2 text-sm font-semibold transition-colors ${
              status === "accepted"
                ? "border-brand bg-brand text-white"
                : "border-line bg-white text-ink hover:border-brand hover:text-brand"
            }`}
          >
            ✓ {t("review.accept")}
          </button>
          <button
            type="button"
            onClick={() => {
              onReject();
              setPicking(true);
            }}
            aria-pressed={status === "rejected"}
            className={`tap flex-1 rounded-xl border-2 px-3 py-2 text-sm font-semibold transition-colors ${
              status === "rejected"
                ? "border-slate-600 bg-slate-600 text-white"
                : "border-line bg-white text-ink hover:border-slate-600"
            }`}
          >
            ✗ {t("review.reject")}
          </button>
          <button
            type="button"
            onClick={() => setPicking((value) => !value)}
            aria-expanded={showOptions}
            className="tap rounded-xl border-2 border-line bg-white px-3 py-2 text-sm font-semibold text-ink hover:border-brand hover:text-brand"
          >
            {t("review.change")}
          </button>
        </div>
      ) : null}

      {showOptions ? (
        <fieldset className="mt-3">
          <legend className="mb-2 text-sm font-semibold text-muted">
            {t("review.chooseAnswer")}
          </legend>
          <div className="flex flex-col gap-2">
            {question.options.map((option) => {
              const selected = chosen.includes(option.code);
              return (
                <label
                  key={option.code}
                  className={`tap flex cursor-pointer items-start gap-3 rounded-xl border-2 p-3 transition-colors ${
                    selected
                      ? "border-brand bg-brand-light/50"
                      : "border-line bg-white hover:border-brand/60"
                  }`}
                >
                  <input
                    type={question.type === "multi" ? "checkbox" : "radio"}
                    name={`q-${question.id}`}
                    checked={selected}
                    onChange={() => onToggle(option.code)}
                    className="mt-1 size-5 accent-[--color-brand]"
                  />
                  <span>
                    <span className="block text-sm font-semibold text-ink">
                      {option.label}
                    </span>
                    <span className="block text-sm text-muted">
                      {option.explain}
                    </span>
                  </span>
                </label>
              );
            })}
          </div>
        </fieldset>
      ) : null}
    </li>
  );
}
