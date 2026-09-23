// Start the API using the virtualenv's Python, on any platform.
// Node's spawn handles forward slashes on Windows, which cmd.exe does not.
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";

import { venvPython } from "./venv.mjs";

const python = venvPython();

if (!existsSync(python)) {
  console.error(
    `\nNo virtualenv found at ${python}.\nRun 'npm run setup' first.\n`
  );
  process.exit(1);
}

const child = spawn(
  python,
  ["-m", "uvicorn", "app.main:app", "--reload", "--port", "8000", "--app-dir", "api"],
  { stdio: "inherit" }
);

child.on("exit", (code) => process.exit(code ?? 0));
