/**
 * Identity, kept as light as it can be.
 *
 * The nickname and the team code live on this phone and are never sent to the
 * server. What the server receives is a random id generated here once, which
 * identifies the device and nothing else: no name, no email, no account, no way
 * to work backwards to a person.
 *
 * The nickname exists so the app can say "your points"; the team code exists so
 * a school can see itself on a leaderboard. Both are the citizen's own words and
 * neither is verified.
 */

const CLIENT_KEY = "streamlens.client";
const NICKNAME_KEY = "streamlens.nickname";
const TEAM_KEY = "streamlens.team";

export interface Identity {
  /** Random, generated on this device. The only part the server ever sees. */
  clientId: string;
  /** Shown in this app only. Never transmitted. */
  nickname: string;
  /** Optional free-text team or school code. Sent with an observation. */
  team: string;
}

function read(key: string): string {
  try {
    return localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

function write(key: string, value: string): void {
  try {
    if (value) localStorage.setItem(key, value);
    else localStorage.removeItem(key);
  } catch {
    // Private browsing, or storage blocked. The app still works; the phone
    // simply forgets the nickname between sessions.
  }
}

export function clientId(): string {
  const existing = read(CLIENT_KEY);
  if (existing) return existing;
  const created =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `anon-${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
  write(CLIENT_KEY, created);
  return created;
}

export function getIdentity(): Identity {
  return {
    clientId: clientId(),
    nickname: read(NICKNAME_KEY),
    team: read(TEAM_KEY),
  };
}

export function setIdentity(nickname: string, team: string): Identity {
  write(NICKNAME_KEY, nickname.trim().slice(0, 40));
  write(TEAM_KEY, team.trim().toUpperCase().slice(0, 40));
  return getIdentity();
}

/** True until the citizen has been asked once, so we only ask once. */
export function needsIntroduction(): boolean {
  return !read(NICKNAME_KEY) && !read(TEAM_KEY) && read("streamlens.asked") !== "yes";
}

export function markIntroduced(): void {
  write("streamlens.asked", "yes");
}
