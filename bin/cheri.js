#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");
const cliPath = path.join(repoRoot, "cli.py");
const args = process.argv.slice(2);

const candidates = process.platform === "win32"
  ? [
      { command: "py", args: ["-3"] },
      { command: "python", args: [] },
      { command: "python3", args: [] },
    ]
  : [
      { command: "python3", args: [] },
      { command: "python", args: [] },
    ];

for (const candidate of candidates) {
  const result = spawnSync(candidate.command, [...candidate.args, cliPath, ...args], {
    cwd: process.cwd(),
    stdio: "inherit",
  });
  if (result.error && result.error.code === "ENOENT") {
    continue;
  }
  process.exit(result.status ?? 1);
}

console.error(
  "Cheri requires Python 3. Install Python and run `python -m pip install .` from this repository before using the npm launcher."
);
process.exit(1);
