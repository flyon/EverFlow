#!/usr/bin/env node

import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const scriptPath = join(dirname(dirname(fileURLToPath(import.meta.url))), "everflow_headless.py");
const candidates =
  process.platform === "win32"
    ? [
        ["python", []],
        ["python3", []],
        ["py", ["-3"]],
        ["py", []],
      ]
    : [
        ["python3", []],
        ["python", []],
      ];

for (const [command, prefixArgs] of candidates) {
  const check = spawnSync(
    command,
    [...prefixArgs, "-c", "import sys; raise SystemExit(0 if sys.version_info[0] == 3 else 1)"],
    { stdio: "ignore" },
  );
  if (check.error?.code === "ENOENT" || check.status !== 0) {
    continue;
  }

  const result = spawnSync(command, [...prefixArgs, scriptPath], { stdio: "inherit" });
  if (result.error) {
    console.error(result.error.message);
    process.exit(1);
  }
  process.exit(result.status ?? 0);
}

console.error("Python 3 was not found. Install Python 3, then run this command again.");
process.exit(1);
