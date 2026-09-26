import { useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip } from "react-leaflet";

import { ScopeToggle } from "../components/insights";
import { Button, Card, Notice, Spinner } from "../components/ui";
import { getIdentity } from "../lib/identity";
import type { DataScope } from "../lib/insights";
import {
  returns,
  type Coverage,
  type Leaderboard,
  type MyPoints,
  type Wellbeing,
} from "../lib/returns";

/** The coverage map: which sites got a visit this month. Opens the video. */
export function CoverageMap({
  coverage,
  onOpenSite,
}: {
  coverage: Coverage;
  onOpenSite: (siteId: string) => void;
}) {
  const withPosition = coverage.sites.filter((s) => s.lat != null && s.lon != null);
  const centre = useMemo<[number, number]>(() => {
    if (!withPosition.length) return [45.5, 5.0];
    const lat = withPosition.reduce((sum, s) => sum + (s.lat ?? 0), 0) / withPosition.length;
    const lon = withPosition.reduce((sum, s) => sum + (s.lon ?? 0), 0) / withPosition.length;
    return [lat, lon];
  }, [withPosition]);

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h3 className="font-semibold text-ink">Covered this month</h3>
          <p className="text-sm text-muted">
            {coverage.covered} of {coverage.total_sites} research sites visited in
            the last {coverage.days} days.
          </p>
        </div>
        <span className="text-2xl font-bold tabular-nums text-brand">
          {Math.round(coverage.share * 100)}%
        </span>
      </div>

      <div className="h-72 overflow-hidden rounded-xl border border-line">
        <MapContainer
          center={centre}
          zoom={coverage.city ? 10 : 4}
          className="h-full w-full"
          scrollWheelZoom
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {withPosition.map((site) => (
            <CircleMarker
              key={site.site_id}
              center={[site.lat!, site.lon!]}
              radius={site.visited ? 8 : 4}
              pathOptions={{
                color: site.visited ? "#15803d" : "#94a3b8",
                fillColor: site.visited ? "#15803d" : "#cbd5e1",
                fillOpacity: site.visited ? 0.9 : 0.5,
                weight: site.visited ? 2 : 1,
              }}
              eventHandlers={{ click: () => onOpenSite(site.site_id) }}
            >
              <Tooltip>
                {site.site_name} — {site.visited ? "visited" : "not visited"}
              </Tooltip>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>

      <p className="flex flex-wrap gap-4 text-xs text-muted">
        <span className="flex items-center gap-1">
          <span className="inline-block size-3 rounded-full bg-[--color-good]" />
          visited
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block size-2 rounded-full bg-slate-400" />
          not yet
        </span>
      </p>
    </Card>
  );
}

/** Return: what the community got back. Coverage, teams, and your own mirror. */
export function ReturnScreen({
  cities,
  scope,
  onScope,
  onOpenSite,
}: {
  cities: string[];
  scope: DataScope;
  onScope: (scope: DataScope) => void;
  onOpenSite: (siteId: string) => void;
}) {
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [board, setBoard] = useState<Leaderboard | null>(null);
  const [mirror, setMirror] = useState<Wellbeing | null>(null);
  const [community, setCommunity] = useState<Wellbeing | null>(null);
  const [points, setPoints] = useState<MyPoints | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  // Empty means every city. Coverage and the team standings follow it
  // together, so the map and the table always describe the same place.
  const [city, setCity] = useState("");

  const identity = getIdentity();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");

    Promise.all([
      returns.coverage(scope, 30, city || null),
      returns.leaderboard(scope, city || null),
      returns.wellbeing(scope, identity.clientId, false).catch(() => null),
      returns.wellbeing(scope, identity.clientId, true).catch(() => null),
      returns.myPoints(scope, identity.clientId).catch(() => null),
    ])
      .then(([c, b, m, cm, p]) => {
        if (cancelled) return;
        setCoverage(c);
        setBoard(b);
        setMirror(m);
        setCommunity(cm);
        setPoints(p);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load this. You may be offline.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [scope, city, identity.clientId]);

  if (loading) {
    return (
      <div className="py-10">
        <Spinner label="Loading…" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <header>
        <h2 className="text-xl font-bold text-ink">What we found together</h2>
        <p className="text-sm text-muted">
          Coverage, teams, and what people recorded feeling.
        </p>
      </header>

      <ScopeToggle scope={scope} onChange={onScope} />

      <div className="flex flex-wrap items-center gap-2">
        <label
          className="text-sm font-semibold text-muted"
          htmlFor="return-city"
        >
          City
        </label>
        <select
          id="return-city"
          value={city}
          onChange={(event) => setCity(event.target.value)}
          className="tap rounded-xl border-2 border-line bg-white px-3 py-2 text-sm"
        >
          <option value="">All cities</option>
          {cities.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </div>
      {error ? <Notice tone="warn">{error}</Notice> : null}

      {coverage ? <CoverageMap coverage={coverage} onOpenSite={onOpenSite} /> : null}

      {/* --- your own points ------------------------------------------- */}
      {points ? (
        <Card className="flex flex-col gap-2">
          <div className="flex items-baseline justify-between">
            <h3 className="font-semibold text-ink">
              {identity.nickname ? `${identity.nickname}'s points` : "Your points"}
            </h3>
            <span className="text-2xl font-bold tabular-nums text-brand">
              {points.total_points}
            </span>
          </div>
          <p className="text-sm text-muted">
            From {points.observations} assessment
            {points.observations === 1 ? "" : "s"}. Daily cap {points.daily_cap}.
          </p>
          <details className="text-sm">
            <summary className="tap cursor-pointer font-semibold text-brand">
              Why there are no points for volume
            </summary>
            <div className="mt-2 flex flex-col gap-2 text-muted">
              {points.why_not_volume.map((line) => (
                <p key={line.slice(0, 24)}>{line}</p>
              ))}
              <p>
                <strong>Never rewarded:</strong>{" "}
                {points.never_awarded_for.join(", ")}.
              </p>
            </div>
          </details>
        </Card>
      ) : null}

      {/* --- teams ------------------------------------------------------ */}
      {board ? (
        <section className="flex flex-col gap-2">
          <h3 className="text-sm font-bold tracking-wide text-muted uppercase">
            Teams
          </h3>
          {board.teams.length === 0 ? (
            <Notice tone="info">
              {city
                ? `No teams have assessed a site in ${city} yet.`
                : "No teams yet. Add a team code in Settings and your assessments will count towards it."}
            </Notice>
          ) : (
            <Card>
              <ol className="flex flex-col divide-y divide-line">
                {board.teams.slice(0, 8).map((team, index) => (
                  <li
                    key={team.team}
                    className="flex items-center gap-3 py-2 first:pt-0 last:pb-0"
                  >
                    <span className="w-6 text-sm font-bold tabular-nums text-muted">
                      {index + 1}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block font-medium text-ink">{team.team}</span>
                      <span className="block text-xs text-muted">
                        {team.sites_covered} site
                        {team.sites_covered === 1 ? "" : "s"} · {team.members} people
                        {team.cities.length ? ` · ${team.cities.join(", ")}` : ""}
                      </span>
                    </span>
                    <span className="text-lg font-bold tabular-nums text-brand">
                      {team.points}
                    </span>
                  </li>
                ))}
              </ol>
            </Card>
          )}
          <p className="text-xs text-muted">{board.why_teams_only}</p>
          {board.teams_withheld_too_small > 0 ? (
            <p className="text-xs text-muted">
              {board.teams_withheld_too_small} team
              {board.teams_withheld_too_small === 1 ? " is" : "s are"} not shown:{" "}
              {board.why_withheld}
            </p>
          ) : null}
        </section>
      ) : null}

      {/* --- wellbeing mirror ------------------------------------------ */}
      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-bold tracking-wide text-muted uppercase">
          Wellbeing mirror
        </h3>

        {mirror?.available && mirror.headline ? (
          <Card>
            <p className="mb-2 font-medium text-ink">{mirror.headline}</p>
            <div className="flex flex-wrap gap-3 text-sm text-muted">
              {Object.entries(mirror.by_rating).map(([rating, data]) => (
                <span key={rating}>
                  {rating}: {data.visits} visit{data.visits === 1 ? "" : "s"},{" "}
                  {Math.round(data.positive_share * 100)}% calm or joyful
                </span>
              ))}
            </div>
          </Card>
        ) : (
          <Notice tone="info">
            Record how a few more streams made you feel and your own mirror appears
            here.
          </Notice>
        )}

        {community ? (
          community.available ? (
            <Card>
              <p className="mb-1 text-sm font-semibold text-muted">
                Everyone ({community.people} people)
              </p>
              <p className="text-ink">{community.headline}</p>
            </Card>
          ) : (
            <Notice tone="info" title="Community view not shown">
              {community.caveat}
            </Notice>
          )
        ) : null}

        <p className="text-xs text-muted">
          {mirror?.caveat ?? community?.caveat}
        </p>
        <p className="text-xs text-muted">
          {mirror?.not_a_health_measure ?? community?.not_a_health_measure}{" "}
          {(mirror ?? community)?.research_link ? (
            <a
              className="underline"
              href={(mirror ?? community)!.research_link.url}
              target="_blank"
              rel="noreferrer"
            >
              {(mirror ?? community)!.research_link.text}
            </a>
          ) : null}
        </p>
      </section>
    </div>
  );
}

/** First-run prompt: a nickname and an optional team. Neither is an account. */
export function IdentityCard({
  onSaved,
  onSkip,
}: {
  onSaved: (nickname: string, team: string) => void;
  onSkip: () => void;
}) {
  const [nickname, setNickname] = useState("");
  const [team, setTeam] = useState("");

  return (
    <Card className="flex flex-col gap-3">
      {/* An h2: this card is the first thing on the page after the app
          title, so an h3 here skips a level for a screen reader. */}
      <h2 className="font-semibold text-ink">What should we call you?</h2>
      <p className="text-sm text-muted">
        Only so the app can say "your points". Your nickname stays on this phone
        and is never sent anywhere. There is no account and no password.
      </p>

      <label className="flex flex-col gap-1">
        <span className="text-sm font-semibold text-muted">Nickname</span>
        <input
          value={nickname}
          onChange={(event) => setNickname(event.target.value)}
          maxLength={40}
          className="tap rounded-xl border-2 border-line bg-white px-4 py-3 text-base"
          placeholder="e.g. Ana"
        />
      </label>

      <label className="flex flex-col gap-1">
        <span className="text-sm font-semibold text-muted">
          Team or school code <span className="font-normal">(optional)</span>
        </span>
        <input
          value={team}
          onChange={(event) => setTeam(event.target.value.toUpperCase())}
          maxLength={40}
          className="tap rounded-xl border-2 border-line bg-white px-4 py-3 text-base"
          placeholder="e.g. ESC-COIMBRA-7B"
        />
        <span className="text-xs text-muted">
          Sent with your assessments so your team appears on the leaderboard.
          Teams are ranked; people never are.
        </span>
      </label>

      <div className="flex gap-2">
        <Button variant="secondary" onClick={onSkip}>
          Not now
        </Button>
        <Button full onClick={() => onSaved(nickname, team)}>
          Save
        </Button>
      </div>
    </Card>
  );
}
