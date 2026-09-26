import { useEffect, useState } from "react";

import {
  AlertCard,
  ForecastBar,
  Meter,
  MeasureCard,
  ScopeToggle,
  StatusPill,
} from "../components/insights";
import { Button, Card, Notice, Spinner } from "../components/ui";
import { returns, type Quest } from "../lib/returns";
import {
  insights,
  type DataScope,
  type HealthCard,
  type SiteActions,
  type SiteAlerts,
} from "../lib/insights";

/**
 * The site page: what people reported here, what the next 48 hours look like,
 * and what could be done about it. The demo centrepiece.
 */
export function SitePage({
  onStartQuest,
  siteId,
  scope,
  onScope,
  onBack,
}: {
  onStartQuest: (siteId: string, ruleId: string) => void;
  siteId: string;
  scope: DataScope;
  onScope: (scope: DataScope) => void;
  onBack: () => void;
}) {
  const [card, setCard] = useState<HealthCard | null>(null);
  const [alerts, setAlerts] = useState<SiteAlerts | null>(null);
  const [actions, setActions] = useState<SiteActions | null>(null);
  const [quests, setQuests] = useState<Quest[]>([]);
  const [latestObservation, setLatestObservation] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");

    Promise.all([
      insights.healthCard(siteId, scope),
      insights.siteAlerts(siteId, scope).catch(() => null),
      insights.siteActions(siteId, scope).catch(() => null),
      returns.siteQuests(siteId, scope).catch(() => null),
    ])
      .then(([healthCard, siteAlerts, siteActions, siteQuests]) => {
        if (cancelled) return;
        setCard(healthCard);
        setAlerts(siteAlerts);
        setActions(siteActions);
        setQuests(siteQuests?.quests ?? []);
        const history = healthCard.overall_history;
        setLatestObservation(
          history.length ? history[history.length - 1].observation_id : ""
        );
      })
      .catch((cause) => {
        if (!cancelled) setError(String(cause));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [siteId, scope]);

  if (loading) {
    return (
      <div className="py-10">
        <Spinner label="Loading this site…" />
      </div>
    );
  }

  if (error || !card) {
    return (
      <div className="flex flex-col gap-3">
        <Notice tone="danger" title="Could not load this site">
          {error || "No data came back."}
        </Notice>
        <Button variant="secondary" onClick={onBack}>
          Back
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <header>
        <button
          type="button"
          onClick={onBack}
          className="tap mb-2 text-sm font-semibold text-brand"
        >
          ← Back
        </button>
        <h2 className="text-xl font-bold text-ink">{card.site_name}</h2>
        <p className="text-sm text-muted">
          {card.city} · {card.visits} visit{card.visits === 1 ? "" : "s"}
          {card.last_visit
            ? ` · last ${new Date(card.last_visit).toLocaleDateString()}`
            : ""}
        </p>
      </header>

      <ScopeToggle
        scope={scope}
        onChange={onScope}
        syntheticCount={card.synthetic_count}
        realCount={card.real_count}
      />

      {card.visits === 0 ? (
        <Notice tone="info" title="Nobody has assessed this site yet">
          Be the first. Everything below fills in from citizen reports.
        </Notice>
      ) : null}

      {quests.length > 0 ? (
        <section className="flex flex-col gap-2">
          <h3 className="text-sm font-bold tracking-wide text-muted uppercase">
            Why this site is worth a visit
          </h3>
          {quests.map((quest) => (
            <Notice key={quest.rule_id} tone="info" title={quest.name}>
              <p>{quest.why}</p>
              <div className="mt-2">
                <Button onClick={() => onStartQuest(siteId, quest.rule_id)}>
                  Take this on
                </Button>
              </div>
              {quest.weather_synthetic ? (
                <span className="mt-2 inline-block rounded-full border border-amber-700/40 bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-900 uppercase">
                  ● demo forecast
                </span>
              ) : null}
            </Notice>
          ))}
        </section>
      ) : null}

      {/* --- alerts first: the time-sensitive thing ----------------------- */}
      {alerts ? (
        <section className="flex flex-col gap-3">
          <h3 className="text-sm font-bold tracking-wide text-muted uppercase">
            Next 48 hours
          </h3>
          <ForecastBar forecast={alerts.forecast} />
          {alerts.alerts.length === 0 ? (
            <Notice tone="good">
              No alerts for this site right now. {alerts.always_include}
            </Notice>
          ) : (
            alerts.alerts.map((alert) => (
              <AlertCard key={alert.rule_id} alert={alert} />
            ))
          )}
          <p className="text-xs text-muted">{alerts.never_a_diagnosis}</p>
        </section>
      ) : null}

      {/* --- the health card ---------------------------------------------- */}
      <section className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-bold tracking-wide text-muted uppercase">
            Stream health card
          </h3>
          {card.latest_overall ? (
            <span className="flex items-center gap-2 text-sm text-muted">
              Latest citizen rating <StatusPill status={card.latest_overall} />
            </span>
          ) : null}
        </div>

        <Notice tone="info">{card.disclaimer}</Notice>

        <Card>
          <ul className="flex flex-col divide-y divide-line">
            {card.sections.map((section) => (
              <li
                key={section.section_id}
                className="flex flex-wrap items-center justify-between gap-2 py-3 first:pt-0 last:pb-0"
              >
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-ink">{section.label}</p>
                  <p className="text-xs text-muted">{section.reason}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs tabular-nums text-muted">
                    {section.answered}/{section.total}
                  </span>
                  <StatusPill status={section.status} size="sm" />
                </div>
              </li>
            ))}
          </ul>
        </Card>

        <Card className="flex flex-col gap-4">
          <Meter
            value={card.completeness}
            label="Data completeness"
            caption={`${card.answered_questions} of ${card.total_questions} questions have ever been answered here — ${card.completeness_label}.`}
          />
          {Object.keys(card.emotions).length > 0 ? (
            <div>
              <p className="mb-1 text-sm font-semibold text-muted">
                How visitors felt here (average of {card.visits})
              </p>
              <div className="flex flex-wrap gap-3 text-sm">
                {Object.entries(card.emotions).map(([name, value]) => (
                  <span key={name} className="text-ink">
                    {name}: <strong className="tabular-nums">{value}</strong>/4
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </Card>

        {card.overall_history.length > 1 ? (
          <Card>
            <p className="mb-2 text-sm font-semibold text-muted">
              Citizen ratings over time
            </p>
            <ol className="flex flex-wrap items-end gap-1">
              {card.overall_history.map((entry) => (
                <li
                  key={entry.observation_id}
                  title={`${entry.overall} — ${new Date(
                    entry.recorded_at
                  ).toLocaleDateString()}${entry.synthetic ? " (demo)" : ""}`}
                  className={`h-8 w-3 rounded-sm ${
                    entry.overall === "GOOD"
                      ? "bg-[--color-good]"
                      : entry.overall === "MODERATE"
                        ? "bg-[--color-moderate]"
                        : "bg-[--color-poor]"
                  } ${entry.synthetic ? "opacity-70" : ""}`}
                />
              ))}
            </ol>
            <p className="mt-2 text-xs text-muted">
              Oldest first. {card.built_from}
            </p>
          </Card>
        ) : null}
      </section>

      {/* --- problems and what can be done -------------------------------- */}
      {actions && actions.problems.length > 0 ? (
        <section className="flex flex-col gap-3">
          <h3 className="text-sm font-bold tracking-wide text-muted uppercase">
            What visitors reported, and what helps
          </h3>

          <Card>
            <ul className="flex flex-col gap-3">
              {actions.problems.map((problem) => (
                <li key={problem.id}>
                  <p className="font-semibold text-ink">{problem.name}</p>
                  <p className="text-sm text-muted">{problem.why_it_matters}</p>
                  {problem.detection_note ? (
                    <p className="mt-1 text-xs italic text-muted">
                      {problem.detection_note}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          </Card>

          <h4 className="text-sm font-semibold text-ink">
            Measures from the OneAquaHealth catalogue
          </h4>
          <ul className="flex flex-col gap-3">
            {actions.measures.slice(0, 6).map((measure) => (
              <MeasureCard key={measure.id} measure={measure} />
            ))}
          </ul>

          <p className="text-xs text-muted">{actions.health_note}</p>
          <p className="text-xs text-muted">
            Source: {actions.catalogue.title} ({actions.catalogue.licence}),{" "}
            <a
              className="underline"
              href={actions.catalogue.url}
              target="_blank"
              rel="noreferrer"
            >
              {actions.catalogue.doi}
            </a>
          </p>
        </section>
      ) : null}

      {latestObservation ? (
        <section className="flex flex-col gap-2 border-t border-line pt-4">
          <h3 className="text-sm font-bold tracking-wide text-muted uppercase">
            For researchers
          </h3>
          <a
            href={returns.fhirUrl(latestObservation)}
            className="tap inline-flex w-fit items-center rounded-xl border-2 border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand hover:text-brand"
          >
            Export the latest assessment as FHIR
          </a>
          <p className="text-xs text-muted">
            FHIR R4 Bundle shaped against the OneAquaHealth IG: 0 errors and 0
            warnings from the official HL7 validator. See docs/fhir/ for the report.
          </p>
        </section>
      ) : null}
    </div>
  );
}
