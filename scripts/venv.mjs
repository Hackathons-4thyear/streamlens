import { dirname, join, resolve } from "node:path";
import { platform } from "node:process";
import { fileURLToPath } from "node:url";

export const isWindows = platform === "win32";

/** The repository root, derived from this file rather than from cwd. */
export const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

/**
 * Absolute path to the API virtualenv's Python interpreter.
 *
 * Absolute on purpose: run-pytest.mjs spawns with cwd set to api/, so a path
 * relative to the repository root would resolve to api/api/.venv there.
 */
export function venvPython() {
  return isWindows
    ? join(repoRoot, "api", ".venv", "Scripts", "python.exe")
    : join(repoRoot, "api", ".venv", "bin", "python");
}

/** The interpreter used to CREATE the virtualenv. */
export function systemPython() {
  return isWindows ? "py" : "python3.11";
}

export function systemPythonArgs() {
  return isWindows ? ["-3.11"] : [];
}
