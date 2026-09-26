# Privacy, and what happens to your photographs

Written for: anyone using StreamLens, and the judges. Plain language, no
euphemisms.

Last checked: **26 September 2026.**

## The short version

- StreamLens never asks for your name, your email or a password. There is no
  account.
- **AI help is optional.** You choose, before you take a photograph, whether to
  use it. If you say no, your photographs are never sent to Google.
- If you say yes, your photographs go to Google's Gemini API on its **free
  tier**, and Google's own terms say that human reviewers may read them and that
  Google may use them to improve its products. The exact wording is quoted below.
- Photographs have their hidden metadata, including any GPS the camera recorded,
  destroyed before they go anywhere.
- On the public demo, photographs are **not stored at all** once they have been
  measured.

## Choosing AI help

Before the photo step, StreamLens asks you to choose:

| Choice | What happens to your photographs |
|---|---|
| **Use AI suggestions** | A copy, shrunk to at most 1024 pixels and stripped of metadata, is sent to Google Gemini. Google's free-tier terms apply — see below. You get draft answers to check. |
| **Answer myself** | **Nothing is sent to Google.** Your photographs go only to StreamLens, which measures whether they are sharp and bright enough, and on the public demo does not keep them. |

**The manual path asks exactly the same questions and records exactly the same
data.** The only difference is that nobody has filled anything in for you. The
plain-language help, the glossary and the photo checks all work the same.

## What Google's free-tier terms actually say

StreamLens has no billing account with Google. It runs on the unpaid quota,
which Google's terms call **Unpaid Services**. Quoted from the
[Gemini API Additional Terms of Service](https://ai.google.dev/gemini-api/terms),
effective **23 March 2026**:

> "When you use Unpaid Services, including, for example, Google AI Studio and
> the unpaid quota on Gemini API, Google uses the content you submit to the
> Services and any generated responses to provide, improve, and develop Google
> products and services and machine learning technologies, including Google's
> enterprise features, products, and services, consistent with our Privacy
> Policy."

> "To help with quality and improve our products, human reviewers may read,
> annotate, and process your API input and output."

> "Do not submit sensitive, confidential, or personal information to the Unpaid
> Services."

Google states that it disconnects this data from the Google Account, API key and
Cloud project before reviewers see it.

**Read that third line again, because it governs how you should use this app.**
Google is telling you not to send personal information through the free tier. A
photograph of a stream is not personal information. A photograph with your
children in it, or your neighbour's car number plate, or a recognisable house,
might be.

So:

- **Photograph the water and the banks, not people.** The assessment does not
  need people in it, and the prompt explicitly instructs the model to refuse
  images that mainly show people.
- If somebody has wandered into the frame, retake it, or choose **Answer
  myself** for that visit.
- On a paid tier Google does not use prompts to improve its products. StreamLens
  is not on one, and this project will not add a payment method. If you deploy
  StreamLens for real use, with real volunteers, **paying for the API is the
  right call**, and this page should be rewritten to say so.

## What StreamLens itself holds

| Thing | Where it goes | How long |
|---|---|---|
| Your nickname | This device only. Never transmitted. | Until you clear it |
| Your team code | Sent with an assessment, so a school can find itself on the board. Free text you typed; not verified, not an account. | With the record |
| A random device id | Generated on your phone. Sent with an assessment so two visits can be told apart and so the rate limit works. Not linked to anything else. | With the record |
| Your location | Only if you tap to share it, and only as coordinates in their own field. | With the record |
| Your answers and rating | Sent and stored. This is the point of the app. | With the record |
| Your photographs | See below. | See below |
| Your emotion sliders | Stored, and only ever reported in groups of at least ten people. | With the record |

### Photographs, precisely

1. When you take one, StreamLens applies the rotation the camera recorded, then
   **rebuilds the image from raw pixels**, which destroys every piece of
   metadata including GPS.
2. It is shrunk to at most 1600 pixels on the long edge.
3. Sharpness and brightness are measured.
4. If you chose AI help, **a second, smaller copy — at most 1024 pixels — is
   what is sent to Google.** The larger one never leaves the server.
5. On the public demo, `STORE_PHOTOS` is off: the measurements are kept and the
   image itself is discarded. Nothing to leak, nothing to delete.
6. Where storage is switched on, photographs are deleted after 14 days and are
   never shown publicly — no gallery, no public URL, no listing endpoint.

## Rate limits

The demo runs on a free allowance, so AI suggestions are capped at 10 per person
per hour and 300 per day across everybody. When a cap is reached the app keeps
working: the offline demo helper fills in drafts instead, clearly badged, and
your own answers are unaffected. It never shows an error and there is no bill to
run up.

## What StreamLens never does

- No medical or health claim about anyone, ever. It describes streams.
- No AI-chosen rating: the Good / Moderate / Poor verdict is always yours.
- No individual leaderboard, so there is nothing to be ranked on personally.
- No tracking, no analytics, no advertising, no third-party scripts beyond the
  map tiles (OpenStreetMap) and the fonts already in your browser.

## Clearing your data

**Settings → Clear my data on this device** removes the nickname, team code and
device id from this browser. Assessments already submitted stay in the research
record — they carry no name, and there is no way to work backwards from them to
you, which also means there is no way for us to find and delete "yours".

If you want an assessment withdrawn, open an issue on the repository with its id
and the date, and it will be removed.
