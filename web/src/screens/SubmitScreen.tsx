import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button, Card, Notice } from "../components/ui";
import { agreementStats, type AnswersState } from "../state/answers";
import { returns, type MyPoints } from "../lib/returns";
import type { DataScope } from "../lib/insights";
import type { Site } from "../types";

export type SubmitOutcome =
  | { kind: "idle" }
  | { kind: "sending" }
  | { kind: "sent"; id: string }
  | { kind: "queued" }
  | { kind: "failed"; message: string };

export function SubmitScreen({
  site,
  overall,
  overallLabel,
  answers,
  photoCount,
  outcome,
  pendingCount,
  onSubmit,
  onSyncNow,
  onBack,
  onRestart,
  onViewSite,
  clientId,
  scope,
  questCompleted,
}: {
  site: Site;
  overall: string;
  overallLabel: string;
  answers: AnswersState;
  photoCount: number;
  outcome: SubmitOutcome;
  pendingCount: number;
  onSubmit: (consent: boolean) => void;
  onSyncNow: () => void;
  onBack: () => void;
  onRestart: () => void;
  onViewSite?: () => void;
  clientId: string;
  scope: DataScope;
  questCompleted: string;
}) {
  const { t } = useTranslation();
  const [consent, setConsent] = useState(false);
  const [touched, setTouched] = useState(false);

  const [points, setPoints] = useState<MyPoints | null>(null);

  // Points are computed server-side from what was actually stored, so they are
  // fetched after the record lands rather than guessed here.
  useEffect(() => {
    if (outcome.kind !== "sent") return;
    let cancelled = false;
    returns
      .myPoints(scope, clientId)
      .then((result) => {
        if (!cancelled) setPoints(result);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [outcome.kind, scope, clientId]);

  const stats = agreementStats(answers);
  const answeredTotal = Object.values(answers).filter(
    (value) => value.codes.length > 0
  ).length;

  if (outcome.kind === "sent" || outcome.kind === "queued") {
    return (
      <div className="flex flex-col gap-4 py-6">
        <Notice
          tone={outcome.kind === "sent" ? "good" : "info"}
          title={
            outcome.kind === "sent" ? t("submit.sent") : t("submit.queuedTitle")
          }
        >
          {outcome.kind === "sent" ? (
            <p>
              {stats.rate != null
                ? t("submit.agreement", {
                    percent: Math.round(stats.rate * 100),
                  })
                : t("submit.noAgreement")}
            </p>
          ) : (
            <p>{t("submit.queued")}</p>
          )}
        </Notice>

        {outcome.kind === "sent" && points ? (
          <Card className="flex flex-col gap-2">
            <div className="flex items-baseline justify-between">
              <span className="font-semibold text-ink">Points</span>
              <span className="text-2xl font-bold tabular-nums text-brand">
                {points.total_points}
              </span>
            </div>
            {points.awards[0]?.awards.length ? (
              <ul className="flex flex-col gap-1 text-sm text-muted">
                {points.awards[0].awards.map((award) => (
                  <li key={award.rule_id}>
                    +{award.points} — {award.detail}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted">
                No points this time. Points come from photo quality, filling a
                gap, and agreeing with another visitor — never from how much you
                submit.
              </p>
            )}
            {questCompleted ? (
              <p className="text-xs text-muted">
                This visit filled the “{questCompleted.replace(/_/g, " ")}” gap.
              </p>
            ) : null}
          </Card>
        ) : null}

        {pendingCount > 0 ? (
          <Card>
            <p className="mb-3 text-sm font-medium">
              {t("submit.pending", { count: pendingCount })}
            </p>
            <Button variant="secondary" onClick={onSyncNow}>
              {t("submit.syncNow")}
            </Button>
          </Card>
        ) : null}

        <p className="text-xs text-muted">{t("submit.noMedicalClaim")}</p>

        {onViewSite ? (
          <Button full onClick={onViewSite}>
            See what this site now shows
          </Button>
        ) : null}
        <Button full variant={onViewSite ? "secondary" : "primary"} onClick={onRestart}>
          {t("submit.startAnother")}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h2 className="text-xl font-bold text-ink">{t("submit.title")}</h2>
      </header>

      <Card>
        <dl className="grid grid-cols-2 gap-y-3 text-sm">
          <dt className="font-semibold text-muted">{t("submit.site")}</dt>
          <dd className="text-right font-medium text-ink">
            {site.name}
            <span className="block text-xs text-muted">{site.city}</span>
          </dd>

          <dt className="font-semibold text-muted">{t("submit.rating")}</dt>
          <dd className="text-right font-bold text-ink">{overallLabel || overall}</dd>

          <dt className="font-semibold text-muted">{t("submit.answers")}</dt>
          <dd className="text-right font-medium text-ink">{answeredTotal}</dd>

          <dt className="font-semibold text-muted">{t("submit.photos")}</dt>
          <dd className="text-right font-medium text-ink">{photoCount}</dd>
        </dl>
      </Card>

      {stats.rate != null ? (
        <p className="text-sm text-muted">
          {t("submit.agreement", { percent: Math.round(stats.rate * 100) })}
        </p>
      ) : null}

      <label className="flex cursor-pointer items-start gap-3 rounded-2xl border-2 border-line bg-white p-4">
        <input
          type="checkbox"
          checked={consent}
          onChange={(event) => setConsent(event.target.checked)}
          className="mt-1 size-6 shrink-0 accent-[--color-brand]"
        />
        <span className="text-sm leading-relaxed text-ink">
          {t("submit.consent")}
        </span>
      </label>

      {touched && !consent ? (
        <Notice tone="warn">{t("submit.consentRequired")}</Notice>
      ) : null}

      {outcome.kind === "failed" ? (
        <Notice tone="danger" title={t("submit.failedTitle")}>
          {outcome.message}
        </Notice>
      ) : null}

      <p className="text-xs text-muted">{t("submit.noMedicalClaim")}</p>

      <div className="flex gap-2">
        <Button variant="secondary" onClick={onBack}>
          {t("common.back")}
        </Button>
        <Button
          full
          disabled={outcome.kind === "sending"}
          onClick={() => {
            setTouched(true);
            onSubmit(consent);
          }}
        >
          {outcome.kind === "sending" ? t("submit.sending") : t("submit.send")}
        </Button>
      </div>
    </div>
  );
}
