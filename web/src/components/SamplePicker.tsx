import { useState } from "react";

import { Button, Notice, Spinner } from "./ui";
import {
  fetchSampleBlob,
  loadSamples,
  sampleUrl,
  type SamplePhoto,
} from "../lib/samples";

/**
 * "Try with sample photos": the demo path for anyone with no stream to hand.
 *
 * Nothing is fetched until the panel is opened, so the photographs cost a
 * first-time visitor nothing. Each card carries its author and licence next to
 * the image, because that is the condition on which they may be used at all.
 */
export function SamplePicker({
  onPick,
  onPickPair,
}: {
  onPick: (role: "upstream" | "downstream", blob: Blob) => void;
  onPickPair: (upstream: Blob, downstream: Blob) => void;
}) {
  const [open, setOpen] = useState(false);
  const [samples, setSamples] = useState<SamplePhoto[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const expand = () => {
    setOpen((wasOpen) => !wasOpen);
    if (samples || error) return;
    loadSamples()
      .then(setSamples)
      .catch(() => setError("The sample photographs could not be loaded."));
  };

  const pick = async (
    sample: SamplePhoto,
    role: "upstream" | "downstream"
  ) => {
    setBusy(`${sample.id}-${role}`);
    try {
      onPick(role, await fetchSampleBlob(sample));
    } catch {
      setError("That sample could not be loaded.");
    } finally {
      setBusy("");
    }
  };

  const pickPair = async () => {
    if (!samples) return;
    const up = samples.find((s) => s.id === "benevento-upstream");
    const down = samples.find((s) => s.id === "benevento-downstream");
    if (!up || !down) return;
    setBusy("pair");
    try {
      const [a, b] = await Promise.all([
        fetchSampleBlob(up),
        fetchSampleBlob(down),
      ]);
      onPickPair(a, b);
    } catch {
      setError("Those samples could not be loaded.");
    } finally {
      setBusy("");
    }
  };

  return (
    <section className="rounded-2xl border-2 border-dashed border-line bg-white p-3">
      <button
        type="button"
        onClick={expand}
        aria-expanded={open}
        className="tap flex w-full items-center justify-between gap-2 text-left"
      >
        <span>
          <span className="block font-semibold text-ink">
            No stream nearby? Try with sample photos
          </span>
          <span className="block text-sm text-muted">
            Six Creative Commons photographs, including one with no water in it.
          </span>
        </span>
        <span aria-hidden="true" className="text-lg text-muted">
          {open ? "▴" : "▾"}
        </span>
      </button>

      {open ? (
        <div className="mt-3 flex flex-col gap-3">
          {error ? <Notice tone="warn">{error}</Notice> : null}
          {!samples && !error ? <Spinner label="Loading samples…" /> : null}

          {samples ? (
            <>
              <Button
                full
                variant="secondary"
                onClick={() => void pickPair()}
                disabled={busy === "pair"}
              >
                {busy === "pair"
                  ? "Loading…"
                  : "Fill both slots with one river (Benevento)"}
              </Button>

              <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {samples.map((sample) => (
                  <li
                    key={sample.id}
                    className="flex flex-col gap-2 rounded-xl border-2 border-line p-2"
                  >
                    <img
                      src={sampleUrl(sample)}
                      alt={sample.shows}
                      loading="lazy"
                      width={sample.width}
                      height={sample.height}
                      className="aspect-4/3 w-full rounded-lg object-cover"
                    />
                    <p className="text-sm text-ink">{sample.purpose}</p>
                    <div className="flex gap-2">
                      <Button
                        variant="secondary"
                        className="flex-1 text-sm"
                        onClick={() => void pick(sample, "upstream")}
                        disabled={busy === `${sample.id}-upstream`}
                      >
                        Use upstream
                      </Button>
                      <Button
                        variant="secondary"
                        className="flex-1 text-sm"
                        onClick={() => void pick(sample, "downstream")}
                        disabled={busy === `${sample.id}-downstream`}
                      >
                        Use downstream
                      </Button>
                    </div>
                    <p className="text-xs text-muted">
                      {sample.author} ·{" "}
                      {sample.licence_url ? (
                        <a
                          className="underline"
                          href={sample.licence_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          {sample.licence}
                        </a>
                      ) : (
                        sample.licence
                      )}{" "}
                      ·{" "}
                      <a
                        className="underline"
                        href={sample.source_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Wikimedia Commons
                      </a>
                    </p>
                  </li>
                ))}
              </ul>

              <p className="text-xs text-muted">
                Sample photographs are used under their own licences, which are
                not the licence of this project. They are resized copies; the
                originals are linked above.
              </p>
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
