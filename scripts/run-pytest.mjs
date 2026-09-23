import { spawn } from "node:child_process";
import { join } from "node:path";

import { repoRoot, venvPython } from "./venv.mjs";

const child = spawn(venvPython(), ["-m", "pytest"], {
  stdio: "inherit",
  cwd: join(repoRoot, "api"),
});
child.on("exit", (code) => process.exit(code ?? 0));
