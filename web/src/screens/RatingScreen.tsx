import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button, Notice } from "../components/ui";
import type { Emotion, QuestionSet } from "../types";

const RATING_STYLES: Record<string, string> = {
  GOOD: "border-[--color-good] data-[selected=true]:bg-[--color-good]",
  MODERATE: "border-[--color-moderate] data-[selected=true]:bg-[--color-moderate]",
  POOR: "border-[--color-poor] data-[selected=true]:bg-[--color-poor]",
};

const EMOTIONS: Emotion[] = ["joy", "serenity", "anger", "fear"];

export function RatingScreen({
  questionSet,
  overall,
  emotions,
  note,
  onOverall,
  onEmotion,
  onNote,
  onBack,
  onNext,
}: {
  questionSet: QuestionSet;
  overall: string;
  emotions: Partial<Record<Emotion, number>>;
  note: string;
  onOverall: (code: string) => void;
  onEmotion: (emotion: Emotion, level: number) => void;
  onNote: (note: string) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  const { t } = useTranslation();
  const [touched, setTouched] = useState(false);

  const question = questionSet.questions.find((q) => q.id === "overall");

  return (
    <div className="flex flex-col gap-5">
      <header>
        <h2 className="text-xl font-bold text-ink">{t("rating.title")}</h2>
        <p className="text-sm text-muted">{t("rating.lead")}</p>
      </header>

      <Notice tone="info">{t("rating.aiSilent")}</Notice>

      <fieldset>
        <legend className="mb-3 text-base font-semibold text-ink">
          {question?.label ?? t("rating.title")}
        </legend>
        <div className="flex flex-col gap-3">
          {question?.options.map((option) => {
            const selected = overall === option.code;
            return (
              <label
                key={option.code}
                data-selected={selected}
                className={`tap flex cursor-pointer items-start gap-3 rounded-2xl border-2 bg-white p-4 transition-colors data-[selected=true]:text-white ${
                  RATING_STYLES[option.code] ?? "border-line"
                }`}
              >
                <input
                  type="radio"
                  name="overall"
                  value={option.code}
                  checked={selected}
                  onChange={() => onOverall(option.code)}
                  className="mt-1 size-5"
                />
                <span>
                  <span className="block text-base font-bold">{option.label}</span>
                  <span
                    className={`block text-sm ${
                      selected ? "text-white/90" : "text-muted"
                    }`}
                  >
                    {option.explain}
                  </span>
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>

      <section>
        <h3 className="text-base font-semibold text-ink">
          {t("rating.emotionsTitle")}{" "}
          <span className="text-sm font-normal text-muted">
            ({t("common.optional")})
          </span>
        </h3>
        <p className="mb-3 text-sm text-muted">{t("rating.emotionsLead")}</p>

        <div className="flex flex-col gap-4">
          {EMOTIONS.map((emotion) => (
            <div key={emotion}>
              <div className="mb-1 flex items-center justify-between">
                <label
                  htmlFor={`emotion-${emotion}`}
                  className="font-medium text-ink"
                >
                  {t(`rating.${emotion}`)}
                </label>
                <span className="text-sm tabular-nums text-muted">
                  {emotions[emotion] ?? 0} / 4
                </span>
              </div>
              <input
                id={`emotion-${emotion}`}
                type="range"
                min={0}
                max={4}
                step={1}
                value={emotions[emotion] ?? 0}
                onChange={(event) =>
                  onEmotion(emotion, Number(event.target.value))
                }
                className="h-11 w-full accent-[--color-brand]"
                aria-valuetext={`${emotions[emotion] ?? 0} ${t("common.of")} 4`}
              />
              <div className="flex justify-between text-xs text-muted">
                <span>{t("rating.intensity0")}</span>
                <span>{t("rating.intensity4")}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      <label className="flex flex-col gap-1">
        <span className="font-medium text-ink">{t("rating.noteLabel")}</span>
        <textarea
          value={note}
          onChange={(event) => onNote(event.target.value)}
          rows={3}
          placeholder={t("rating.notePlaceholder")}
          className="rounded-xl border-2 border-line bg-white p-3 text-base"
        />
      </label>

      {touched && !overall ? (
        <Notice tone="warn">{t("rating.chooseRating")}</Notice>
      ) : null}

      <div className="flex gap-2">
        <Button variant="secondary" onClick={onBack}>
          {t("common.back")}
        </Button>
        <Button
          full
          disabled={!overall}
          onClick={() => {
            setTouched(true);
            if (overall) onNext();
          }}
        >
          {t("common.next")}
        </Button>
      </div>
    </div>
  );
}
