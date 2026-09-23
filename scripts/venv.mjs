import { platform } from "node:process";

export const isWindows = platform === "win32";

/** Path to the API virtualenv's Python interpreter. */
export function venvPython() {
  return isWindows ? "api/.venv/Scripts/python.exe" : "api/.venv/bin/python";
}

/** The interpreter used to CREATE the virtualenv. */
export function systemPython() {
  return isWindows ? "py" : "python3.11";
}

export function systemPythonArgs() {
  return isWindows ? ["-3.11"] : [];
}
