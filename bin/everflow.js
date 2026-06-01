#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const scriptPath = join(dirname(dirname(fileURLToPath(import.meta.url))), "everflow_headless.py");
const candidates =
  process.platform === "win32"
    ? [
        ["py", ["-3", scriptPath]],
        ["python", [scriptPath]],
        ["python3", [scriptPath]],
      ]
    : [
        ["python3", [scriptPath]],
        ["python", [scriptPath]],
      ];

for (const [command, args] of candidates) {
  const result = spawnSync(command, args, { stdio: "inherit" });
  if (result.error?.code === "ENOENT") {
    continue;
  }
  if (result.error) {
    console.error(result.error.message);
    process.exit(1);
  }
  process.exit(result.status ?? 0);
}

console.error("Python 3 was not found. Install Python 3, then run this command again.");
process.exit(1);
