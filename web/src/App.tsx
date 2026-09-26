import { useCallback, useEffect, useMemo, useReducer, useState } from "react";
import { useTranslation } from "react-i18next";

import { QuickTour } from "./components/QuickTour";
import { Button, Notice, Spinner } from "./components/ui";
import { LANGUAGES, setLanguage, type LanguageCode } from "./i18n";
import { ApiError, api } from "./lib/api";
import { cacheGet, cacheSet, pendingCount, queueObservation } from "./lib/db";
import type { Position } from "./lib/geo";
import { flushOutbox, startAutoSync } from "./lib/sync";
import { CityScreen, ExploreScreen } from "./screens/ExploreScreen";
import { PhotosScreen, type PhotoSlotValue } from "./screens/PhotosScreen";
import { AiChoiceScreen } from "./screens/AiChoiceScreen";
import { IdentityCard, ReturnScreen } from "./screens/ReturnScreen";
import { SitePage } from "./screens/SitePage";
import { getIdentity, markIntroduced, needsIntroduction, setIdentity } from "./lib/identity";
import type { DataScope } from "./lib/insights";
import { RatingScreen } from "./screens/RatingScreen";
import { ReviewScreen } from "./screens/ReviewScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import { SiteScreen } from "./screens/SiteScreen";
import { SubmitScreen, type SubmitOutcome } from "./screens/SubmitScreen";
import {
  answersReducer,
  toPayloadAnswers,
  type AnswersState,
} from "./state/answers";
import type {
  Emotion,
  ObservationPayload,
  QuestionSet,
  Site,
  SitesResponse,
  SuggestResponse,
} from "./types";

const STEPS = ["site", "aiChoice", "photos", "review", "rating", "submit"] as const;
type Step = (typeof STEPS)[number];

/** The two halves of the product: record an assessment, or read what is there. */
type Mode = "observe" | "explore" | "return";
type ExploreView =
  | { kind: "home" }
  | { kind: "site"; siteId: string }
  | { kind: "city"; city: string };

function useOnline(): boolean {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  return online;
}

export default function App() {
  const { t, i18n } = useTranslation();
  const online = useOnline();

  const [mode, setMode] = useState<Mode>("observe");
  const [explore, setExplore] = useState<ExploreView>({ kind: "home" });
  const [scope, setScope] = useState<DataScope>("all");
  const [identity, setIdentityState] = useState(getIdentity);
  const [askName, setAskName] = useState(needsIntroduction);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [step, setStep] = useState<Step>("site");
  const [catalogueError, setCatalogueError] = useState("");
  const [sites, setSites] = useState<SitesResponse | null>(null);
  const [questionSet, setQuestionSet] = useState<QuestionSet | null>(null);

  const [site, setSite] = useState<Site | null>(null);
  const [position, setPosition] = useState<Position | null>(null);
  const [upstream, setUpstream] = useState<PhotoSlotValue | null>(null);
  const [downstream, setDownstream] = useState<PhotoSlotValue | null>(null);

  // Null until the citizen has chosen. Never defaulted to true: sending a
  // photograph to Google is their decision, not one we make for them.
  const [useAi, setUseAi] = useState<boolean | null>(null);
  // Set when the citizen started from a quest, so the record can say which
  // gap this visit filled and the points can be awarded for filling it.
  const [quest, setQuest] = useState<{ siteId: string; ruleId: string } | null>(
    null
  );
  const [suggestion, setSuggestion] = useState<SuggestResponse | null>(null);
  const [suggestLoading, setSuggestLoading] = useState(false);
  const [suggestError, setSuggestError] = useState("");

  const [answers, dispatch] = useReducer(answersReducer, {} as AnswersState);
  const [overall, setOverall] = useState("");
  const [emotions, setEmotions] = useState<Partial<Record<Emotion, number>>>({});
  const [note, setNote] = useState("");

  const [outcome, setOutcome] = useState<SubmitOutcome>({ kind: "idle" });
  const [queued, setQueued] = useState(0);

  // --- catalogue, cached so a cold start with no signal still works --------

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setCatalogueError("");
      const lang = i18n.language;
      try {
        const [freshSites, freshQuestions] = await Promise.all([
          api.sites(),
          api.questions(lang),
        ]);
        if (cancelled) return;
        setSites(freshSites);
        setQuestionSet(freshQuestions);
        void cacheSet("sites", freshSites);
        void cacheSet(`questions.${lang}`, freshQuestions);
      } catch {
        const [cachedSites, cachedQuestions] = await Promise.all([
          cacheGet<SitesResponse>("sites"),
          cacheGet<QuestionSet>(`questions.${lang}`),
        ]);
        if (cancelled) return;
        if (cachedSites && cachedQuestions) {
          setSites(cachedSites);
          setQuestionSet(cachedQuestions);
        } else {
          setCatalogueError(t("errors.sites"));
        }
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, [i18n.language, t]);

  // --- outbox --------------------------------------------------------------

  const refreshQueued = useCallback(async () => {
    setQueued(await pendingCount());
  }, []);

  useEffect(() => {
    void refreshQueued();
    return startAutoSync(() => {
      void refreshQueued();
    });
  }, [refreshQueued]);

  // --- suggestions ---------------------------------------------------------

  const fetchSuggestions = useCallback(async () => {
    if (!site) return;
    if (!useAi) {
      // The manual path never calls the API, so "your photos are not sent
      // to Google" is true by construction rather than by promise.
      setSuggestion(null);
      setSuggestError("");
      dispatch({ type: "reset" });
      return;
    }
    setSuggestLoading(true);
    setSuggestError("");
    setSuggestion(null);
    try {
      const result = await api.suggest({
        siteId: site.id,
        upstream: upstream?.blob,
        downstream: downstream?.blob,
        lat: position?.lat ?? null,
        lon: position?.lon ?? null,
        clientId: identity.clientId,
      });
      setSuggestion(result);
      dispatch({ type: "init", chips: result.suggestions });
    } catch (error) {
      const offline = error instanceof ApiError && error.status === 0;
      setSuggestError(
        offline ? t("errors.offlineSuggest") : t("errors.suggest")
      );
      dispatch({ type: "reset" });
    } finally {
      setSuggestLoading(false);
    }
  }, [site, upstream, downstream, position, t, useAi, identity.clientId]);

  // --- submit --------------------------------------------------------------

  const buildPayload = (): ObservationPayload | null => {
    if (!site || !questionSet) return null;
    return {
      site_id: site.id,
      overall,
      answers: toPayloadAnswers(answers, questionSet.questions),
      emotions,
      lang: i18n.language,
      lat: position?.lat ?? null,
      lon: position?.lon ?? null,
      accuracy_m: position?.accuracy ?? null,
      note,
      consent_given: true,
      synthetic: false,
      client_id: identity.clientId,
      team: identity.team,
      completed_quest:
        quest && site && quest.siteId === site.id ? quest.ruleId : "",
      recorded_at: new Date().toISOString(),
      ai_provider: useAi ? suggestion?.provider ?? "" : "",
      ai_model: useAi ? suggestion?.model ?? "" : "",
    };
  };

  const submit = async (consent: boolean) => {
    if (!consent) return;
    const payload = buildPayload();
    if (!payload) return;

    const photos = { upstream: upstream?.blob, downstream: downstream?.blob };
    setOutcome({ kind: "sending" });

    if (!navigator.onLine) {
      await queueObservation({ payload, ...photos });
      await refreshQueued();
      setOutcome({ kind: "queued" });
      return;
    }

    try {
      const saved = await api.createObservation(payload, photos);
      setOutcome({ kind: "sent", id: saved.id });
    } catch (error) {
      const apiError =
        error instanceof ApiError ? error : new ApiError(String(error), 0);
      if (apiError.isRetryable) {
        // The server is unreachable rather than unhappy: keep the visit.
        await queueObservation({ payload, ...photos });
        await refreshQueued();
        setOutcome({ kind: "queued" });
      } else {
        setOutcome({ kind: "failed", message: apiError.message });
      }
    }
  };

  /** Jump from a quest straight into assessing that site. */
  const startQuest = (siteId: string, ruleId: string) => {
    const target = sites?.sites.find((s) => s.id === siteId) ?? null;
    if (!target) return;
    setSite(target);
    setQuest({ siteId, ruleId });
    setUpstream(null);
    setDownstream(null);
    setSuggestion(null);
    setUseAi(null);
    dispatch({ type: "reset" });
    setOverall("");
    setOutcome({ kind: "idle" });
    setMode("observe");
    setStep("aiChoice");
  };

  const restart = () => {
    setSite(null);
    setUpstream(null);
    setDownstream(null);
    setSuggestion(null);
    setSuggestError("");
    setUseAi(null);
    setQuest(null);
    dispatch({ type: "reset" });
    setOverall("");
    setEmotions({});
    setNote("");
    setOutcome({ kind: "idle" });
    setStep("site");
  };

  const overallLabel = useMemo(() => {
    const question = questionSet?.questions.find((q) => q.id === "overall");
    return question?.options.find((o) => o.code === overall)?.label ?? "";
  }, [questionSet, overall]);

  const stepIndex = STEPS.indexOf(step);

  // --- render --------------------------------------------------------------

  if (catalogueError) {
    return (
      <main className="mx-auto max-w-2xl p-4">
        <Notice tone="danger" title={t("errors.generic")}>
          {catalogueError}
        </Notice>
        <div className="mt-4">
          <Button onClick={() => window.location.reload()}>
            {t("common.retry")}
          </Button>
        </div>
      </main>
    );
  }

  if (!sites || !questionSet) {
    return (
      <main className="mx-auto flex max-w-2xl justify-center p-10">
        <Spinner label={t("common.loading")} />
      </main>
    );
  }

  return (
    <div className="min-h-full">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-2xl flex-wrap items-center justify-between gap-2 px-4 py-3">
          <div>
            <h1 className="text-lg font-bold text-brand-dark">
              {t("app.title")}
            </h1>
            <p className="text-xs text-muted">{t("app.tagline")}</p>
          </div>

          <div className="flex items-center gap-2">
            <span
              className={`rounded-full px-2 py-1 text-xs font-bold ${
                online
                  ? "bg-emerald-100 text-emerald-900"
                  : "bg-slate-200 text-slate-700"
              }`}
            >
              {online ? t("common.online") : t("common.offline")}
            </span>

            {queued > 0 ? (
              <button
                type="button"
                onClick={() => {
                  void flushOutbox().then(() => refreshQueued());
                }}
                className="tap rounded-full bg-amber-100 px-3 py-1 text-xs font-bold text-amber-900"
              >
                {t("submit.pending", { count: queued })}
              </button>
            ) : null}

            <button
              type="button"
              onClick={() => setSettingsOpen(true)}
              aria-label={t("app.settings")}
              className="tap rounded-xl border-2 border-line bg-white px-2 py-1 text-sm"
            >
              <span aria-hidden="true">⚙</span>
            </button>

            <label className="sr-only" htmlFor="lang">
              {t("app.language")}
            </label>
            <select
              id="lang"
              value={i18n.language}
              onChange={(event) =>
                setLanguage(event.target.value as LanguageCode)
              }
              className="tap rounded-xl border-2 border-line bg-white px-2 py-1 text-sm"
            >
              {LANGUAGES.map((language) => (
                <option key={language.code} value={language.code}>
                  {language.label}
                  {language.city ? ` · ${language.city}` : ""}
                </option>
              ))}
            </select>
          </div>
        </div>

        <nav className="mx-auto flex max-w-2xl gap-2 px-4 pb-2">
          {(["observe", "explore", "return"] as Mode[]).map((name) => (
            <button
              key={name}
              type="button"
              onClick={() => setMode(name)}
              aria-current={mode === name ? "page" : undefined}
              className={`tap flex-1 rounded-xl px-3 py-2 text-sm font-semibold transition-colors ${
                mode === name
                  ? "bg-brand text-white"
                  : "bg-slate-100 text-slate-600 hover:text-brand"
              }`}
            >
              {name === "observe"
                ? t("nav.observe")
                : name === "explore"
                  ? t("nav.explore")
                  : t("nav.return")}
            </button>
          ))}
        </nav>

        {mode === "observe" && !settingsOpen ? (
        <ol className="mx-auto flex max-w-2xl gap-1 px-4 pb-3 text-xs">
          {STEPS.map((name, index) => (
            <li
              key={name}
              className={`flex-1 rounded-full px-2 py-1 text-center font-semibold ${
                index === stepIndex
                  ? "bg-brand text-white"
                  : index < stepIndex
                    ? "bg-brand-light text-brand-dark"
                    : "bg-slate-100 text-slate-500"
              }`}
              aria-current={index === stepIndex ? "step" : undefined}
            >
              {t(`steps.${name}`)}
            </li>
          ))}
        </ol>
        ) : null}
      </header>

      <main className="mx-auto max-w-2xl px-4 py-5 pb-[calc(2rem+var(--safe-bottom))]">
        {i18n.language !== "en" ? (
          <p className="mb-3 text-xs text-muted">{t("app.translationWarning")}</p>
        ) : null}

        {settingsOpen ? (
          <SettingsScreen
            onSaved={setIdentityState}
            onBack={() => setSettingsOpen(false)}
          />
        ) : (
        <>
        {askName ? (
          <div className="mb-4">
            <IdentityCard
              onSaved={(nickname, team) => {
                setIdentityState(setIdentity(nickname, team));
                markIntroduced();
                setAskName(false);
              }}
              onSkip={() => {
                markIntroduced();
                setAskName(false);
              }}
            />
          </div>
        ) : null}

        {mode === "return" ? (
          <ReturnScreen
            cities={sites.cities}
            scope={scope}
            onScope={setScope}
            onOpenSite={(siteId) => {
              setExplore({ kind: "site", siteId });
              setMode("explore");
            }}
          />
        ) : null}

        {mode === "explore" && explore.kind === "home" ? (
          <ExploreScreen
            sites={sites.sites}
            cities={sites.cities}
            scope={scope}
            onScope={setScope}
            position={position}
            onPosition={setPosition}
            onOpenSite={(siteId) => setExplore({ kind: "site", siteId })}
            onOpenCity={(city) => setExplore({ kind: "city", city })}
            onStartQuest={startQuest}
          />
        ) : null}

        {mode === "explore" && explore.kind === "site" ? (
          <SitePage
            onStartQuest={startQuest}
            siteId={explore.siteId}
            scope={scope}
            onScope={setScope}
            onBack={() => setExplore({ kind: "home" })}
          />
        ) : null}

        {mode === "explore" && explore.kind === "city" ? (
          <CityScreen
            city={explore.city}
            scope={scope}
            onScope={setScope}
            onOpenSite={(siteId) => setExplore({ kind: "site", siteId })}
            onBack={() => setExplore({ kind: "home" })}
          />
        ) : null}

        {mode === "observe" && step === "site" ? (
          <div className="mb-4 flex flex-col">
            <QuickTour />
          </div>
        ) : null}

        {mode === "observe" && step === "site" ? (
          <SiteScreen
            sites={sites.sites}
            cities={sites.cities}
            attribution={sites.attribution}
            selected={site}
            position={position}
            onPosition={setPosition}
            onSelect={setSite}
            onNext={() => setStep("aiChoice")}
          />
        ) : null}

        {mode === "observe" && step === "aiChoice" ? (
          <AiChoiceScreen
            onChoose={(choice) => {
              setUseAi(choice);
              setStep("photos");
            }}
            onBack={() => setStep("site")}
          />
        ) : null}

        {mode === "observe" && step === "photos" ? (
          <PhotosScreen
            upstream={upstream}
            downstream={downstream}
            onUpstream={setUpstream}
            onDownstream={setDownstream}
            onBack={() => setStep("aiChoice")}
            useAi={useAi === true}
            onChangeAiChoice={() => setStep("aiChoice")}
            onNext={() => {
              setStep("review");
              void fetchSuggestions();
            }}
          />
        ) : null}

        {mode === "observe" && step === "review" ? (
          <ReviewScreen
            loading={suggestLoading}
            error={suggestError}
            suggestion={suggestion}
            useAi={useAi === true}
            questionSet={questionSet}
            answers={answers}
            dispatch={dispatch}
            onBack={() => setStep("photos")}
            onNext={() => setStep("rating")}
          />
        ) : null}

        {mode === "observe" && step === "rating" ? (
          <RatingScreen
            questionSet={questionSet}
            overall={overall}
            emotions={emotions}
            note={note}
            onOverall={setOverall}
            onEmotion={(emotion, level) =>
              setEmotions((current) => ({ ...current, [emotion]: level }))
            }
            onNote={setNote}
            onBack={() => setStep("review")}
            onNext={() => setStep("submit")}
          />
        ) : null}

        {mode === "observe" && step === "submit" && site ? (
          <SubmitScreen
            site={site}
            overall={overall}
            overallLabel={overallLabel}
            answers={answers}
            photoCount={[upstream, downstream].filter(Boolean).length}
            outcome={outcome}
            pendingCount={queued}
            onSubmit={(consent) => void submit(consent)}
            onSyncNow={() => {
              void flushOutbox().then(() => refreshQueued());
            }}
            onBack={() => setStep("rating")}
            clientId={identity.clientId}
            scope={scope}
            questCompleted={
              quest && quest.siteId === site.id ? quest.ruleId : ""
            }
            onRestart={restart}
            onViewSite={() => {
              setExplore({ kind: "site", siteId: site.id });
              setMode("explore");
            }}
          />
        ) : null}
        </>
        )}
      </main>
    </div>
  );
}
