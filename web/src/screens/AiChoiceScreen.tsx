import { useTranslation } from "react-i18next";

import { Button, Card, Notice } from "../components/ui";

/**
 * The choice that has to come before the camera.
 *
 * Opting out is not a degraded mode: the same questions, the same help, the
 * same record. The only difference is that nobody has filled anything in, and
 * that the photographs never leave for Google.
 *
 * The wording names Google, says human reviewers may read the images, and says
 * so before the photograph exists rather than after. Google's own free-tier
 * terms instruct users not to send personal information, so a citizen deserves
 * to know that before pointing a camera at anything.
 */
export function AiChoiceScreen({
  onChoose,
  onBack,
}: {
  onChoose: (useAi: boolean) => void;
  onBack: () => void;
}) {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h2 className="text-xl font-bold text-ink">{t("aiChoice.title")}</h2>
        <p className="text-sm text-muted">{t("aiChoice.lead")}</p>
      </header>

      <button
        type="button"
        onClick={() => onChoose(true)}
        className="tap rounded-2xl border-2 border-brand bg-white p-4 text-left hover:bg-brand-light/30"
      >
        <span className="block text-base font-bold text-ink">
          {t("aiChoice.yesTitle")}
        </span>
        <span className="mt-1 block text-sm text-muted">{t("aiChoice.yesBody")}</span>
        <ul className="mt-2 list-disc pl-5 text-sm text-muted">
          <li>{t("aiChoice.yesPoint1")}</li>
          <li>{t("aiChoice.yesPoint2")}</li>
          <li>{t("aiChoice.yesPoint3")}</li>
        </ul>
      </button>

      <button
        type="button"
        onClick={() => onChoose(false)}
        className="tap rounded-2xl border-2 border-line bg-white p-4 text-left hover:border-brand/60"
      >
        <span className="block text-base font-bold text-ink">
          {t("aiChoice.noTitle")}
        </span>
        <span className="mt-1 block text-sm text-muted">{t("aiChoice.noBody")}</span>
        <ul className="mt-2 list-disc pl-5 text-sm text-muted">
          <li>{t("aiChoice.noPoint1")}</li>
          <li>{t("aiChoice.noPoint2")}</li>
        </ul>
      </button>

      <Notice tone="warn" title={t("aiChoice.peopleTitle")}>
        {t("aiChoice.peopleBody")}
      </Notice>

      <Card>
        <p className="text-xs text-muted">
          {t("aiChoice.termsQuote")}{" "}
          <a
            className="underline"
            href="https://ai.google.dev/gemini-api/terms"
            target="_blank"
            rel="noreferrer"
          >
            {t("aiChoice.termsLink")}
          </a>
        </p>
      </Card>

      <Button variant="secondary" onClick={onBack}>
        {t("common.back")}
      </Button>
    </div>
  );
}
