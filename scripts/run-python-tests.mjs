#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

function windowsPythonCandidates() {
  const candidates = [
    { command: ".\\.venv\\Scripts\\python.exe", args: [] },
  ];
  const localPrograms = process.env.LOCALAPPDATA
    ? path.join(process.env.LOCALAPPDATA, "Programs", "Python")
    : "";
  if (localPrograms && fs.existsSync(localPrograms)) {
    for (const entry of fs.readdirSync(localPrograms, { withFileTypes: true })) {
      if (!entry.isDirectory()) {
        continue;
      }
      const pythonPath = path.join(localPrograms, entry.name, "python.exe");
      if (fs.existsSync(pythonPath)) {
        candidates.push({ command: pythonPath, args: [] });
      }
    }
  }
  candidates.push(
    { command: "py", args: ["-3"] },
    { command: "python", args: [] },
    { command: "python3", args: [] },
  );
  return candidates;
}

const candidates = process.platform === "win32"
  ? windowsPythonCandidates()
  : [
      { command: ".venv/bin/python", args: [] },
      { command: "python3", args: [] },
      { command: "python", args: [] },
    ];

for (const candidate of candidates) {
  const result = spawnSync(
    candidate.command,
    [...candidate.args, "-m", "unittest", "discover", "-s", "tests/python", "-p", "test_*.py"],
    {
      cwd: process.cwd(),
      stdio: "pipe",
      shell: process.platform === "win32",
    },
  );
  if (result.error && result.error.code === "ENOENT") {
    continue;
  }
  const stderr = result.stderr?.toString?.() || "";
  const stdout = result.stdout?.toString?.() || "";
  if (result.status === 1 && /Access is denied|Erişim engellendi/i.test(stderr)) {
    continue;
  }
  if (result.status === 1 && !stdout && !stderr) {
    continue;
  }
  if (stdout) {
    process.stdout.write(stdout);
  }
  if (stderr) {
    process.stderr.write(stderr);
  }
  process.exit(result.status ?? 1);
}

console.error("Unable to find a Python interpreter to run Cheri's Python test suite.");
process.exit(1);
