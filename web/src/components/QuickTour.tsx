import { useState } from "react";

const DISMISSED = "streamlens.tour";

/** The five steps, in the order a visitor actually walks them. */
const STEPS: { title: string; body: string }[] = [
  {
    title: "1. Pick a site",
    body:
      "The list is the OneAquaHealth / ENORA research sites in Benevento, Coimbra, Oslo and Toulouse. " +
      "Sorting by distance needs your location; choosing from the list does not.",
  },
  {
    title: "2. Decide whether the AI helps",
    body:
      "Use AI suggestions and a shrunk, EXIF-stripped copy of your photographs goes to Google Gemini " +
      "under its free-tier terms. Answer yourself and nothing is sent. Both paths ask the same questions " +
      "and record the same data.",
  },
  {
    title: "3. Photograph upstream and downstream",
    body:
      "Two views let a reviewer see the reach rather than one framing of it. No stream to hand? " +
      "Open \"Try with sample photos\" for six Creative Commons photographs, one of which has no water in it.",
  },
  {
    title: "4. Confirm every answer",
    body:
      "The AI drafts; you accept, change or reject each chip, and the overall rating is yours alone. " +
      "Where you disagree with the AI, both answers are kept, so the two can be compared later.",
  },
  {
    title: "5. Read what came back",
    body:
      "Explore holds the health card, the 48-hour alerts and the restoration measures for a site. " +
      "Community holds coverage, team standings, the wellbeing mirror and the FHIR R4 export.",
  },
];

function wasDismissed(): boolean {
  try {
    return localStorage.getItem(DISMISSED) === "yes";
  } catch {
    return false;
  }
}

/**
 * A five-step orientation for a first-time visitor, and for a judge with four
 * minutes and thirty other entries to see.
 */
export function QuickTour() {
  const [hidden, setHidden] = useState(wasDismissed);
  const [open, setOpen] = useState(false);

  const dismiss = () => {
    try {
      localStorage.setItem(DISMISSED, "yes");
    } catch {
      // Storage blocked: the tour simply comes back next time.
    }
    setHidden(true);
  };

  if (hidden) {
    return (
      <button
        type="button"
        onClick={() => {
          setHidden(false);
          setOpen(true);
        }}
        className="tap self-start text-sm font-semibold text-brand underline"
      >
        Show the quick tour
      </button>
    );
  }

  return (
    <section className="rounded-2xl border-2 border-brand/30 bg-brand-light/30 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="font-bold text-ink">Quick tour</h2>
          <p className="text-sm text-muted">
            Five steps, about four minutes. Everything works without signing in.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            className="tap rounded-xl bg-brand px-3 py-1.5 text-sm font-semibold text-white"
          >
            {open ? "Hide" : "Show"}
          </button>
          <button
            type="button"
            onClick={dismiss}
            className="tap rounded-xl border-2 border-line bg-white px-3 py-1.5 text-sm font-semibold text-muted"
          >
            Dismiss
          </button>
        </div>
      </div>

      {open ? (
        <ol className="mt-3 flex flex-col gap-3">
          {STEPS.map((step) => (
            <li key={step.title}>
              <h3 className="text-sm font-bold text-ink">{step.title}</h3>
              <p className="text-sm text-muted">{step.body}</p>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
