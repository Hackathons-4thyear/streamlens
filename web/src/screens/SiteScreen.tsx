import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { CircleMarker, MapContainer, TileLayer, Tooltip } from "react-leaflet";

import { Button, Notice } from "../components/ui";
import { formatDistance, getPosition, haversineM, type Position } from "../lib/geo";
import type { Site } from "../types";

const CITY_CENTRES: Record<string, [number, number]> = {
  Coimbra: [40.2033, -8.4103],
  Benevento: [41.1291, 14.7868],
  Toulouse: [43.6045, 1.4442],
  Ghent: [51.0543, 3.7174],
  Oslo: [59.9139, 10.7522],
};

export function SiteScreen({
  sites,
  cities,
  attribution,
  selected,
  position,
  onPosition,
  onSelect,
  onNext,
}: {
  sites: Site[];
  cities: string[];
  attribution: string;
  selected: Site | null;
  position: Position | null;
  onPosition: (position: Position) => void;
  onSelect: (site: Site) => void;
  onNext: () => void;
}) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [city, setCity] = useState("");
  const [locating, setLocating] = useState(false);
  const [locationError, setLocationError] = useState("");

  const withDistance = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return sites
      .filter((site) => (city ? site.city === city : true))
      .filter(
        (site) =>
          !needle ||
          site.name.toLowerCase().includes(needle) ||
          site.city.toLowerCase().includes(needle) ||
          site.id.toLowerCase().includes(needle)
      )
      .map((site) => ({
        site,
        distance:
          position && site.lat != null && site.lon != null
            ? haversineM(position.lat, position.lon, site.lat, site.lon)
            : null,
      }))
      .sort((a, b) => {
        if (a.distance != null && b.distance != null) return a.distance - b.distance;
        return a.site.name.localeCompare(b.site.name);
      });
  }, [sites, query, city, position]);

  const centre = useMemo<[number, number]>(() => {
    if (selected?.lat != null && selected.lon != null) {
      return [selected.lat, selected.lon];
    }
    if (position) return [position.lat, position.lon];
    if (city && CITY_CENTRES[city]) return CITY_CENTRES[city];
    return [45.5, 5.0]; // wide enough to hold all five cities
  }, [selected, position, city]);

  const locate = async () => {
    setLocating(true);
    setLocationError("");
    try {
      onPosition(await getPosition());
    } catch {
      setLocationError(t("site.locationDenied"));
    } finally {
      setLocating(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h2 className="text-xl font-bold text-ink">{t("site.title")}</h2>
        <p className="text-sm text-muted">{t("site.lead")}</p>
      </header>

      <div className="h-56 overflow-hidden rounded-2xl border border-line">
        <MapContainer
          center={centre}
          zoom={selected ? 14 : city ? 11 : 4}
          key={`${centre[0]}-${centre[1]}-${city}`}
          className="h-full w-full"
          scrollWheelZoom
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {withDistance.slice(0, 200).map(({ site }) =>
            site.lat != null && site.lon != null ? (
              <CircleMarker
                key={site.id}
                center={[site.lat, site.lon]}
                radius={selected?.id === site.id ? 11 : 7}
                pathOptions={{
                  color: selected?.id === site.id ? "#115e59" : "#0f766e",
                  fillColor: selected?.id === site.id ? "#0f766e" : "#5eead4",
                  fillOpacity: 0.9,
                  weight: 2,
                }}
                eventHandlers={{ click: () => onSelect(site) }}
              >
                <Tooltip>
                  {site.name} ({site.city})
                </Tooltip>
              </CircleMarker>
            ) : null
          )}
        </MapContainer>
      </div>

      <div className="flex flex-col gap-3">
        <label className="flex flex-col gap-1">
          <span className="text-sm font-semibold text-muted">
            {t("site.search")}
          </span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="tap rounded-xl border-2 border-line bg-white px-4 py-3 text-base"
            placeholder={t("site.search")}
          />
        </label>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setCity("")}
            aria-pressed={city === ""}
            className={`tap rounded-full border-2 px-4 py-2 text-sm font-semibold ${
              city === ""
                ? "border-brand bg-brand text-white"
                : "border-line bg-white text-ink"
            }`}
          >
            {t("site.allCities")}
          </button>
          {cities.map((name) => (
            <button
              key={name}
              type="button"
              onClick={() => setCity(name === city ? "" : name)}
              aria-pressed={city === name}
              className={`tap rounded-full border-2 px-4 py-2 text-sm font-semibold ${
                city === name
                  ? "border-brand bg-brand text-white"
                  : "border-line bg-white text-ink"
              }`}
            >
              {name}
            </button>
          ))}
        </div>

        <Button variant="secondary" onClick={locate} disabled={locating}>
          {locating ? t("site.locating") : t("site.useLocation")}
        </Button>
        {locationError ? <Notice tone="warn">{locationError}</Notice> : null}
      </div>

      <ul className="flex max-h-96 flex-col gap-2 overflow-y-auto">
        {withDistance.length === 0 ? (
          <li className="py-6 text-center text-muted">{t("site.noResults")}</li>
        ) : null}
        {withDistance.slice(0, 60).map(({ site, distance }) => (
          <li key={site.id}>
            <button
              type="button"
              onClick={() => onSelect(site)}
              aria-pressed={selected?.id === site.id}
              className={`tap flex w-full items-center justify-between gap-3 rounded-xl border-2 p-3 text-left transition-colors ${
                selected?.id === site.id
                  ? "border-brand bg-brand-light/50"
                  : "border-line bg-white hover:border-brand/60"
              }`}
            >
              <span>
                <span className="block font-semibold text-ink">{site.name}</span>
                <span className="block text-sm text-muted">
                  {site.city} · {site.id}
                </span>
              </span>
              {distance != null ? (
                <span className="shrink-0 text-sm font-semibold text-brand-dark">
                  {t("site.away", { distance: formatDistance(distance) })}
                </span>
              ) : null}
            </button>
          </li>
        ))}
      </ul>

      <p className="text-xs text-muted">{attribution || t("site.attribution")}</p>

      <Button full disabled={!selected} onClick={onNext}>
        {selected ? `${t("common.next")}: ${selected.name}` : t("common.next")}
      </Button>
    </div>
  );
}
