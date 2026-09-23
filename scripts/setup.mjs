// One-time setup: create the API virtualenv, install both dependency trees.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";

import { repoRoot, systemPython, systemPythonArgs, venvPython } from "./venv.mjs";

function run(command, args, label) {
  console.log(`\n> ${label}`);
  const result = spawnSync(command, args, {
    stdio: "inherit",
    shell: false,
    cwd: repoRoot,
  });
  if (result.status !== 0) {
    console.error(`\nFailed: ${label}`);
    process.exit(result.status ?? 1);
  }
}

if (!existsSync(venvPython())) {
  run(
    systemPython(),
    [...systemPythonArgs(), "-m", "venv", "api/.venv"],
    "creating the API virtualenv (Python 3.11)"
  );
} else {
  console.log("\n> virtualenv already exists, reusing it");
}

run(venvPython(), ["-m", "pip", "install", "--upgrade", "pip"], "upgrading pip");
run(
  venvPython(),
  ["-m", "pip", "install", "-r", "api/requirements.txt"],
  "installing API dependencies"
);
run("npm", ["--prefix", "web", "install"], "installing web dependencies");

console.log("\nSetup complete. Start both apps with:  npm run dev\n");
