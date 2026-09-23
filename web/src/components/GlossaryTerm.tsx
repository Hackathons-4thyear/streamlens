import { useEffect, useId, useRef, useState } from "react";

/**
 * A glossary term the citizen can tap for a plain-language explanation.
 *
 * Built as a button with a popover rather than a CSS tooltip: hover does not
 * exist on a phone, and a tooltip that only appears on hover is unusable in the
 * field and invisible to a screen reader.
 */
export function GlossaryTerm({
  term,
  explanation,
  title,
}: {
  term: string;
  explanation: string;
  title: string;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const wrapper = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!wrapper.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <span className="relative inline-block" ref={wrapper}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls={id}
        className="cursor-help rounded border-b-2 border-dotted border-brand px-0.5 font-medium text-brand-dark"
      >
        {term}
        <span className="sr-only"> — {title}</span>
      </button>
      {open ? (
        <span
          id={id}
          role="tooltip"
          className="absolute bottom-full left-0 z-30 mb-2 block w-64 rounded-xl border border-line bg-white p-3 text-sm font-normal text-ink shadow-lg"
        >
          <span className="mb-1 block text-xs font-bold tracking-wide text-muted uppercase">
            {title}
          </span>
          {explanation}
        </span>
      ) : null}
    </span>
  );
}

/**
 * Wraps any glossary term found in `text` with a tappable explanation.
 * Longest terms first, so "impervious surface" wins over "surface".
 */
export function withGlossary(
  text: string,
  glossary: Record<string, string>,
  title: string
) {
  const terms = Object.keys(glossary).sort((a, b) => b.length - a.length);
  if (terms.length === 0) return text;

  const escaped = terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const pattern = new RegExp(`\\b(${escaped.join("|")})\\b`, "gi");

  const parts: (string | React.ReactElement)[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = pattern.exec(text)) !== null) {
    const found = match[0];
    const definition = glossary[found.toLowerCase()];
    if (!definition) continue;
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
    parts.push(
      <GlossaryTerm
        key={`${found}-${key++}`}
        term={found}
        explanation={definition}
        title={title}
      />
    );
    lastIndex = match.index + found.length;
  }

  if (lastIndex === 0) return text;
  parts.push(text.slice(lastIndex));
  return parts;
}
