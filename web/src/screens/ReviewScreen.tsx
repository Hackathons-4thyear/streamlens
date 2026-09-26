import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { SuggestionCard } from "../components/SuggestionCard";
import { Button, MockBadge, Notice, Spinner } from "../components/ui";
import {
  answeredCount,
  pendingChips,
  type AnswerAction,
  type AnswersState,
} from "../state/answers";
import type { QuestionSet, SuggestResponse } from "../types";

export function ReviewScreen({
  loading,
  error,
  suggestion,
  useAi,
  questionSet,
  answers,
  dispatch,
  onBack,
  onNext,
}: {
  loading: boolean;
  error: string;
  suggestion: SuggestResponse | null;
  /** False when the citizen chose to answer without AI help. */
  useAi: boolean;
  questionSet: QuestionSet;
  answers: AnswersState;
  dispatch: (action: AnswerAction) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  const { t } = useTranslation();
  const [showAll, setShowAll] = useState(false);

  const chipsById = useMemo(() => {
    const map = new Map<string, SuggestResponse["suggestions"][number]>();
    for (const chip of suggestion?.suggestions ?? []) map.set(chip.question_id, chip);
    return map;
  }, [suggestion]);

  // With no suggestions at all - offline, or the provider failed - showing only
  // the suggested questions would show an empty screen, so show everything.
  const everything = showAll || chipsById.size === 0 || !useAi;

  const questions = useMemo(
    () =>
      questionSet.questions
        .filter((question) => question.id !== "overall")
        .filter((question) => (everything ? true : chipsById.has(question.id)))
        .sort((a, b) => a.order - b.order),
    [questionSet, everything, chipsById]
  );

  const sections = useMemo(() => {
    const grouped = new Map<string, typeof questions>();
    for (const question of questions) {
      const list = grouped.get(question.section) ?? [];
      list.push(question);
      grouped.set(question.section, list);
    }
    return questionSet.sections
      .filter((section) => grouped.has(section.id))
      .map((section) => ({ section, items: grouped.get(section.id)! }));
  }, [questions, questionSet.sections]);

  const pending = pendingChips(answers).length;
  const answered = answeredCount(answers);

  // Not a stream: the model's own gate. Nothing is shown, because an
  // assessment of a watercourse that is not in the photo is worse than none.
  if (!loading && suggestion && !suggestion.is_watercourse && !showAll) {
    return (
      <div className="flex flex-col gap-4">
        <header>
          <h2 className="text-xl font-bold text-ink">{t("review.notWatercourse")}</h2>
        </header>

        <Notice tone="warn" title={t("review.notWatercourse")}>
          <p>{t("review.notWatercourseBody")}</p>
          {suggestion.not_watercourse_reason ? (
            <p className="mt-2 italic">{suggestion.not_watercourse_reason}</p>
          ) : null}
        </Notice>

        <div className="flex flex-col gap-2">
          <Button full onClick={onBack}>
            {t("review.retakePhoto")}
          </Button>
          <Button variant="secondary" full onClick={() => setShowAll(true)}>
            {t("review.answerAnyway")}
          </Button>
        </div>
      </div>
    );
  }

  if (!useAi) {
    // Answering unaided: the same questions, no chips, and no mention of an AI
    // that was never asked.
    return (
      <div className="flex flex-col gap-4">
        <header>
          <h2 className="text-xl font-bold text-ink">{t("review.manualTitle")}</h2>
          <p className="text-sm text-muted">{t("aiChoice.manualOnly")}</p>
        </header>

        <div
          className="sticky top-0 z-20 -mx-4 bg-surface/95 px-4 py-2 backdrop-blur"
          role="status"
        >
          <p className="text-sm text-muted">
            {answered} {t("common.of")} {questionSet.questions.length - 1}{" "}
            {t("review.answered").toLowerCase()}
          </p>
        </div>

        {sections.map(({ section, items }) => (
          <section key={section.id}>
            <h3 className="mb-2 text-sm font-bold tracking-wide text-muted uppercase">
              {section.label}
            </h3>
            <ul className="flex flex-col gap-3">
              {items.map((question) => (
                <SuggestionCard
                  key={question.id}
                  question={question}
                  answer={answers[question.id]}
                  glossary={questionSet.glossary}
                  onAccept={() => undefined}
                  onReject={() => undefined}
                  onToggle={(code) =>
                    dispatch({
                      type: "toggle",
                      questionId: question.id,
                      code,
                      multi: question.type === "multi",
                    })
                  }
                />
              ))}
            </ul>
          </section>
        ))}

        <div className="flex gap-2 pb-2">
          <Button variant="secondary" onClick={onBack}>
            {t("common.back")}
          </Button>
          <Button full onClick={onNext}>
            {t("common.next")}
          </Button>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-4 py-10">
        <Spinner label={t("review.analysing")} />
        <p className="text-sm text-muted">{t("review.analysingLong")}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <header>
        <div className="mb-1 flex flex-wrap items-center gap-2">
          <h2 className="text-xl font-bold text-ink">{t("review.title")}</h2>
          {suggestion?.is_mock ? (
            <MockBadge
              label={
                suggestion.degraded
                  ? t("review.aiUnavailable")
                  : t("review.mockBadge")
              }
              explanation={
                suggestion.degraded
                  ? t("review.aiUnavailableBody", {
                      reason: suggestion.degraded_reason,
                    })
                  : t("review.mockExplain")
              }
            />
          ) : null}
        </div>
        <p className="text-sm text-muted">{t("review.lead")}</p>
      </header>

      {suggestion?.degraded ? (
        <Notice tone="danger" title={t("review.aiUnavailable")}>
          {t("review.aiUnavailableBody", { reason: suggestion.degraded_reason })}
        </Notice>
      ) : null}

      {suggestion?.is_mock && !suggestion.degraded ? (
        <Notice tone="warn" title={t("review.mockBadge")}>
          {t("review.mockExplain")}
        </Notice>
      ) : null}

      {error ? <Notice tone="warn">{error}</Notice> : null}

      {suggestion ? (
        <>
          {suggestion.photo_quality.some((photo) => !photo.ok) ? (
            <Notice tone="warn" title={t("review.photoQuality")}>
              <ul className="list-disc pl-5">
                {suggestion.photo_quality.flatMap((photo) =>
                  photo.issues.map((issue) => (
                    <li key={`${photo.role}-${issue.code}`}>
                      <strong>{photo.role}:</strong> {issue.message}
                    </li>
                  ))
                )}
              </ul>
            </Notice>
          ) : null}

          {suggestion.location.far_from_site ? (
            <Notice tone="warn" title={t("review.locationCheck")}>
              {suggestion.location.message}
            </Notice>
          ) : null}

          {suggestion.dropped.length > 0 ? (
            <Notice tone="info">
              {t("review.dropped", { count: suggestion.dropped.length })}
            </Notice>
          ) : null}
        </>
      ) : null}

      <div
        className="sticky top-0 z-20 -mx-4 flex flex-wrap items-center justify-between gap-2 bg-surface/95 px-4 py-2 backdrop-blur"
        role="status"
      >
        <p className="text-sm font-semibold text-ink">
          {pending > 0
            ? t("review.pendingCount", { count: pending })
            : t("review.allChecked")}
        </p>
        <p className="text-sm text-muted">
          {answered} {t("common.of")} {questionSet.questions.length - 1}{" "}
          {t("review.answered").toLowerCase()}
        </p>
      </div>

      {chipsById.size > 0 ? (
        <Button variant="ghost" onClick={() => setShowAll((value) => !value)}>
          {everything ? t("review.showSuggestions") : t("review.showAll")}
        </Button>
      ) : null}

      {sections.map(({ section, items }) => (
        <section key={section.id}>
          <h3 className="mb-2 text-sm font-bold tracking-wide text-muted uppercase">
            {section.label}
          </h3>
          <ul className="flex flex-col gap-3">
            {items.map((question) => (
              <SuggestionCard
                key={question.id}
                question={question}
                chip={chipsById.get(question.id)}
                answer={answers[question.id]}
                glossary={questionSet.glossary}
                onAccept={() =>
                  dispatch({ type: "accept", questionId: question.id })
                }
                onReject={() =>
                  dispatch({ type: "reject", questionId: question.id })
                }
                onToggle={(code) =>
                  dispatch({
                    type: "toggle",
                    questionId: question.id,
                    code,
                    multi: question.type === "multi",
                  })
                }
              />
            ))}
          </ul>
        </section>
      ))}

      <div className="flex gap-2 pb-2">
        <Button variant="secondary" onClick={onBack}>
          {t("common.back")}
        </Button>
        <Button full onClick={onNext}>
          {t("review.skipToRating")}
        </Button>
      </div>
    </div>
  );
}
