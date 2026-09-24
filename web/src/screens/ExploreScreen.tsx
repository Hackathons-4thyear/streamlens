import { useCallback, useEffect, useState } from "react";

import { ScopeToggle, StatusPill } from "../components/insights";
import { Button, Card, Notice, Spinner } from "../components/ui";
import { getPosition, type Position } from "../lib/geo";
import { insights, type DataScope, type SiteAlerts } from "../lib/insights";
import { returns, type Quest } from "../lib/returns";
import type { Site } from "../types";

/** Home for Understand & Act: what needs attention near you. */
export function ExploreScreen({
  sites,
  cities,
  scope,
  onScope,
  position,
  onPosition,
  onOpenSite,
  onOpenCity,
}: {
  sites: Site[];
  cities: string[];
  scope: DataScope;
  onScope: (scope: DataScope) => void;
  position: Position | null;
  onPosition: (position: Position) => void;
  onOpenSite: (siteId: string) => void;
  onOpenCity: (city: string) => void;
}) {
  const [near, setNear] = useState<SiteAlerts[] | null>(null);
  const [quests, setQuests] = useState<Quest[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [locating, setLocating] = useState(false);

  const load = useCallback(
    async (lat: number, lon: number) => {
      setLoading(true);
      setError("");
      try {
        const result = await insights.alertsNear(lat, lon, scope, 400);
        setNear(result.results);
      } catch {
        setError("Could not load alerts. You may be offline.");
      } finally {
        setLoading(false);
      }
    },
    [scope]
  );

  useEffect(() => {
    if (position) void load(position.lat, position.lon);
  }, [position, load]);

  useEffect(() => {
    let cancelled = false;
    returns
      .quests(scope, position?.lat, position?.lon)
      .then((result) => {
        if (!cancelled) setQuests(result.quests);
      })
      .catch(() => {
        if (!cancelled) setQuests([]);
      });
    return () => {
      cancelled = true;
    };
  }, [scope, position]);

  const locate = async () => {
    setLocating(true);
    setError("");
    try {
      onPosition(await getPosition());
    } catch {
      setError("Location is off, so we cannot sort by distance. Pick a city instead.");
    } finally {
      setLocating(false);
    }
  };

  const withAlerts = (near ?? []).filter((entry) => entry.alerts.length > 0);
  const quiet = (near ?? []).filter((entry) => entry.alerts.length === 0);

  return (
    <div className="flex flex-col gap-5">
      <header>
        <h2 className="text-xl font-bold text-ink">Alerts near you</h2>
        <p className="text-sm text-muted">
          Advisory notes for the next 48 hours, from the forecast and what people
          have reported.
        </p>
      </header>

      <ScopeToggle scope={scope} onChange={onScope} />

      {!position ? (
        <Card className="flex flex-col gap-3">
          <p className="text-sm text-muted">
            Share your location to see the nearest monitored sites, or pick a city.
          </p>
          <Button onClick={locate} disabled={locating}>
            {locating ? "Finding you…" : "Use my location"}
          </Button>
        </Card>
      ) : null}

      {error ? <Notice tone="warn">{error}</Notice> : null}
      {loading ? <Spinner label="Checking sites near you…" /> : null}

      {withAlerts.length > 0 ? (
        <section className="flex flex-col gap-3">
          <h3 className="text-sm font-bold tracking-wide text-muted uppercase">
            Needs attention
          </h3>
          {withAlerts.map((entry) => (
            <button
              key={entry.site_id}
              type="button"
              onClick={() => onOpenSite(entry.site_id)}
              className="tap rounded-2xl border-2 border-[--color-poor]/40 bg-[--color-danger-bg] p-4 text-left"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold text-ink">{entry.site_name}</span>
                <span className="text-xs text-muted">
                  {entry.city}
                  {entry.distance_km != null ? ` · ${entry.distance_km} km` : ""}
                </span>
              </div>
              <ul className="mt-1 flex flex-col gap-1">
                {entry.alerts.map((alert) => (
                  <li key={alert.rule_id} className="text-sm text-[--color-danger-ink]">
                    {alert.name}
                  </li>
                ))}
              </ul>
              {entry.forecast.synthetic ? (
                <span className="mt-2 inline-block rounded-full border border-amber-700/40 bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-900 uppercase">
                  ● demo forecast
                </span>
              ) : null}
            </button>
          ))}
        </section>
      ) : null}

      {near && withAlerts.length === 0 && !loading ? (
        <Notice tone="good" title="Nothing needs attention right now">
          {quiet.length} nearby site{quiet.length === 1 ? "" : "s"} checked. Check
          official local advice.
        </Notice>
      ) : null}

      {quiet.length > 0 ? (
        <section className="flex flex-col gap-2">
          <h3 className="text-sm font-bold tracking-wide text-muted uppercase">
            Quiet sites nearby
          </h3>
          {quiet.map((entry) => (
            <button
              key={entry.site_id}
              type="button"
              onClick={() => onOpenSite(entry.site_id)}
              className="tap flex items-center justify-between rounded-xl border-2 border-line bg-white p-3 text-left"
            >
              <span className="font-medium text-ink">{entry.site_name}</span>
              <span className="text-xs text-muted">
                {entry.distance_km != null ? `${entry.distance_km} km` : entry.city}
              </span>
            </button>
          ))}
        </section>
      ) : null}

      {quests && quests.length > 0 ? (
        <section className="flex flex-col gap-2">
          <h3 className="text-sm font-bold tracking-wide text-muted uppercase">
            Worth a visit
          </h3>
          <p className="text-sm text-muted">
            Each of these points at a real gap in the record.
          </p>
          {quests.slice(0, 6).map((quest) => (
            <button
              key={`${quest.site_id}-${quest.rule_id}`}
              type="button"
              onClick={() => onOpenSite(quest.site_id)}
              className="tap rounded-2xl border-2 border-brand/30 bg-brand-light/30 p-4 text-left"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold text-ink">{quest.site_name}</span>
                <span className="text-xs text-muted">
                  {quest.city}
                  {quest.distance_km != null ? ` · ${quest.distance_km} km` : ""}
                </span>
              </div>
              <p className="mt-1 text-sm text-muted">{quest.why}</p>
              <div className="mt-2 flex flex-wrap gap-2">
                <span className="rounded-full bg-brand px-2 py-0.5 text-xs font-bold text-white">
                  {quest.name}
                </span>
                {quest.weather_synthetic ? (
                  <span className="rounded-full border border-amber-700/40 bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-900 uppercase">
                    ● demo forecast
                  </span>
                ) : null}
              </div>
            </button>
          ))}
        </section>
      ) : null}

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-bold tracking-wide text-muted uppercase">
          Browse by city
        </h3>
        <div className="flex flex-wrap gap-2">
          {cities.map((city) => (
            <button
              key={city}
              type="button"
              onClick={() => onOpenCity(city)}
              className="tap rounded-full border-2 border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand hover:text-brand"
            >
              {city}
            </button>
          ))}
        </div>
        <p className="text-xs text-muted">
          {sites.length} research sites. The city view is built for municipal users
          and works best on a laptop.
        </p>
      </section>
    </div>
  );
}

/** The city overview: a sortable table for someone with a desk. */
export function CityScreen({
  city,
  scope,
  onScope,
  onOpenSite,
  onBack,
}: {
  city: string;
  scope: DataScope;
  onScope: (scope: DataScope) => void;
  onOpenSite: (siteId: string) => void;
  onBack: () => void;
}) {
  const [data, setData] = useState<Awaited<
    ReturnType<typeof insights.cityOverview>
  > | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sortKey, setSortKey] = useState<
    "site_name" | "visits" | "alert_count" | "completeness" | "latest_overall"
  >("alert_count");
  const [ascending, setAscending] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    insights
      .cityOverview(city, scope)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load this city.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [city, scope]);

  const sort = (key: typeof sortKey) => {
    if (key === sortKey) setAscending((value) => !value);
    else {
      setSortKey(key);
      setAscending(key === "site_name");
    }
  };

  const rows = [...(data?.rows ?? [])].sort((a, b) => {
    const left = a[sortKey] ?? "";
    const right = b[sortKey] ?? "";
    const result =
      typeof left === "number" && typeof right === "number"
        ? left - right
        : String(left).localeCompare(String(right));
    return ascending ? result : -result;
  });

  const header = (key: typeof sortKey, label: string, numeric = false) => (
    <th
      scope="col"
      className={`cursor-pointer px-3 py-2 text-xs font-bold tracking-wide uppercase ${
        numeric ? "text-right" : "text-left"
      }`}
      onClick={() => sort(key)}
      aria-sort={sortKey === key ? (ascending ? "ascending" : "descending") : "none"}
    >
      {label}
      {sortKey === key ? (ascending ? " ▲" : " ▼") : ""}
    </th>
  );

  return (
    <div className="flex flex-col gap-4">
      <header>
        <button
          type="button"
          onClick={onBack}
          className="tap mb-2 text-sm font-semibold text-brand"
        >
          ← Back
        </button>
        <h2 className="text-xl font-bold text-ink">{city}</h2>
        {data ? (
          <p className="text-sm text-muted">
            {data.site_count} sites · {data.visited} visited · {data.with_alerts} with
            alerts
          </p>
        ) : null}
      </header>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <ScopeToggle scope={scope} onChange={onScope} />
        <div className="flex gap-2">
          <a
            href={insights.cityCsvUrl(city, scope)}
            className="tap inline-flex items-center rounded-xl border-2 border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand hover:text-brand"
          >
            Download CSV
          </a>
          <a
            href={returns.cityFhirUrl(city, scope)}
            className="tap inline-flex items-center rounded-xl border-2 border-line bg-white px-4 py-2 text-sm font-semibold text-ink hover:border-brand hover:text-brand"
            title="FHIR R4 Bundle, validated against the OneAquaHealth IG"
          >
            Export FHIR
          </a>
        </div>
      </div>

      {data ? <Notice tone="info">{data.disclaimer}</Notice> : null}
      {error ? <Notice tone="danger">{error}</Notice> : null}
      {loading ? <Spinner label="Loading…" /> : null}

      {data ? (
        <div className="overflow-x-auto rounded-2xl border border-line bg-white">
          <table className="w-full min-w-[46rem] border-collapse text-sm">
            <thead className="border-b border-line bg-slate-50 text-muted">
              <tr>
                {header("site_name", "Site")}
                {header("latest_overall", "Latest rating")}
                {header("visits", "Visits", true)}
                {header("alert_count", "Alerts", true)}
                {header("completeness", "Complete", true)}
                <th scope="col" className="px-3 py-2 text-left text-xs font-bold tracking-wide uppercase">
                  Top problems
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.site_id}
                  className="cursor-pointer border-b border-line last:border-0 hover:bg-brand-light/30"
                  onClick={() => onOpenSite(row.site_id)}
                >
                  <td className="px-3 py-2">
                    <span className="font-medium text-ink">{row.site_name}</span>
                    <span className="block text-xs text-muted">
                      {row.site_id}
                      {row.synthetic_count > 0 ? " · includes demo data" : ""}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    {row.latest_overall ? (
                      <StatusPill status={row.latest_overall} size="sm" />
                    ) : (
                      <span className="text-xs text-muted">No visits</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{row.visits}</td>
                  <td className="px-3 py-2 text-right">
                    {row.alert_count > 0 ? (
                      <span className="rounded-full bg-[--color-danger-bg] px-2 py-0.5 text-xs font-bold text-[--color-danger-ink]">
                        {row.alert_count}
                      </span>
                    ) : (
                      <span className="text-xs text-muted">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {Math.round(row.completeness * 100)}%
                  </td>
                  <td className="px-3 py-2 text-xs text-muted">
                    {row.top_problems.join(", ") || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
