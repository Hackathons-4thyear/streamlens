import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { SamplePicker } from "../components/SamplePicker";
import { Button, Notice } from "../components/ui";

export interface PhotoSlotValue {
  blob: Blob;
  url: string;
}

function PhotoSlot({
  role,
  label,
  hint,
  value,
  onChange,
}: {
  role: "upstream" | "downstream";
  label: string;
  hint: string;
  value: PhotoSlotValue | null;
  onChange: (value: PhotoSlotValue | null) => void;
}) {
  const { t } = useTranslation();
  const input = useRef<HTMLInputElement>(null);

  return (
    <div className="rounded-2xl border-2 border-line bg-white p-3">
      <h3 className="font-semibold text-ink">{label}</h3>
      <p className="mb-3 text-sm text-muted">{hint}</p>

      {value ? (
        <>
          <img
            src={value.url}
            alt={label}
            className="mb-3 aspect-4/3 w-full rounded-xl object-cover"
          />
          <div className="flex gap-2">
            <Button
              variant="secondary"
              className="flex-1"
              onClick={() => input.current?.click()}
            >
              {t("photos.retake")}
            </Button>
            <Button variant="danger" onClick={() => onChange(null)}>
              {t("photos.remove")}
            </Button>
          </div>
        </>
      ) : (
        <Button full variant="secondary" onClick={() => input.current?.click()}>
          📷 {t("photos.take")}
        </Button>
      )}

      <input
        ref={input}
        type="file"
        accept="image/*"
        capture="environment"
        className="sr-only"
        aria-label={`${label}. ${t("photos.take")}`}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onChange({ blob: file, url: URL.createObjectURL(file) });
          event.target.value = "";
        }}
        data-testid={`photo-input-${role}`}
      />
    </div>
  );
}

export function PhotosScreen({
  upstream,
  downstream,
  onUpstream,
  onDownstream,
  onBack,
  onNext,
  useAi,
  onChangeAiChoice,
}: {
  upstream: PhotoSlotValue | null;
  downstream: PhotoSlotValue | null;
  onUpstream: (value: PhotoSlotValue | null) => void;
  onDownstream: (value: PhotoSlotValue | null) => void;
  onBack: () => void;
  onNext: () => void;
  useAi: boolean;
  onChangeAiChoice: () => void;
}) {
  const { t } = useTranslation();
  const [touched, setTouched] = useState(false);
  const hasOne = Boolean(upstream || downstream);

  // Object URLs are revoked when the component unmounts, not on every change,
  // so a preview never points at a released blob.
  useEffect(
    () => () => {
      if (upstream) URL.revokeObjectURL(upstream.url);
      if (downstream) URL.revokeObjectURL(downstream.url);
    },
    [upstream, downstream]
  );

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h2 className="text-xl font-bold text-ink">{t("photos.title")}</h2>
        <p className="text-sm text-muted">{t("photos.lead")}</p>
      </header>

      <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border-2 border-line bg-white p-3">
        <span className="text-sm font-semibold text-ink">
          {useAi ? t("aiChoice.usingAi") : t("aiChoice.manualOnly")}
        </span>
        <button
          type="button"
          onClick={onChangeAiChoice}
          className="tap text-sm font-semibold text-brand underline"
        >
          {t("aiChoice.change")}
        </button>
      </div>

      <Notice tone="info">{t("photos.privacy")}</Notice>

      <SamplePicker
        onPick={(role, blob) => {
          const value = { blob, url: URL.createObjectURL(blob) };
          if (role === "upstream") onUpstream(value);
          else onDownstream(value);
        }}
        onPickPair={(up, down) => {
          onUpstream({ blob: up, url: URL.createObjectURL(up) });
          onDownstream({ blob: down, url: URL.createObjectURL(down) });
        }}
      />

      <PhotoSlot
        role="upstream"
        label={t("photos.upstream")}
        hint={t("photos.upstreamHint")}
        value={upstream}
        onChange={onUpstream}
      />
      <PhotoSlot
        role="downstream"
        label={t("photos.downstream")}
        hint={t("photos.downstreamHint")}
        value={downstream}
        onChange={onDownstream}
      />

      <p className="text-sm text-muted">{t("photos.tips")}</p>

      {touched && !hasOne ? (
        <Notice tone="warn">{t("photos.needOne")}</Notice>
      ) : null}

      <div className="flex gap-2">
        <Button variant="secondary" onClick={onBack}>
          {t("common.back")}
        </Button>
        <Button
          full
          onClick={() => {
            setTouched(true);
            if (hasOne) onNext();
          }}
          disabled={!hasOne}
        >
          {t("common.next")}
        </Button>
      </div>
    </div>
  );
}
