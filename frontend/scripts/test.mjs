import {
  mkdtempSync,
  readdirSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const output = mkdtempSync(join(tmpdir(), "shiva-ui-tests-"));
try {
  writeFileSync(join(output, "package.json"), '{"type":"commonjs"}');
  symlinkSync(
    join(root, "node_modules"),
    join(output, "node_modules"),
    "junction",
  );
  const compile = spawnSync(
    process.execPath,
    [
      join(root, "node_modules/typescript/bin/tsc"),
      "--ignoreConfig",
      "src/App.tsx",
      "src/reportData.ts",
      "src/reportLogic.ts",
      "--outDir",
      output,
      "--module",
      "commonjs",
      "--target",
      "ES2020",
      "--jsx",
      "react-jsx",
      "--lib",
      "ES2020,DOM",
      "--strict",
      "--skipLibCheck",
      "--esModuleInterop",
    ],
    { cwd: root, stdio: "inherit" },
  );
  if (compile.status !== 0) process.exitCode = compile.status || 1;
  else {
    const tests = readdirSync(join(root, "tests"))
      .filter((file) => file.endsWith(".test.cjs"))
      .map((file) => join(root, "tests", file));
    const result = spawnSync(process.execPath, ["--test", ...tests], {
      cwd: root,
      stdio: "inherit",
      env: { ...process.env, SHIVA_UI_TEST_BUILD: output },
    });
    process.exitCode = result.status || (result.error ? 1 : 0);
  }
} finally {
  rmSync(output, { recursive: true, force: true });
}
