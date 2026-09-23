import { spawn } from "node:child_process";

import { venvPython } from "./venv.mjs";

const child = spawn(venvPython(), ["-m", "pytest"], {
  stdio: "inherit",
  cwd: "api",
});
child.on("exit", (code) => process.exit(code ?? 0));
