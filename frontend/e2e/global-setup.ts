import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { join } from "node:path";

/**
 * Prepare the browser suite's database — locked 47.1.3 r3, 55.3, 54.6.
 *
 * Delegates to `backend/tools/e2e_bootstrap.py`, which is the only step the API
 * cannot perform: locked 47.1.3 r3 says LegalMind never self-provisions an account,
 * so `POST /users` cannot set a credential and the first administrator must be created
 * outside the API — exactly as a real installation does it.
 *
 * The bootstrap also **recreates the database**. A browser suite that inherited the
 * previous run's Reviews would let one run change another's assertions, which is the
 * `F-4` failure class the backend harness was rebuilt to eliminate. It runs against
 * the dedicated e2e database only, never the development one.
 *
 * Everything else the specs need is built through the real HTTP endpoints, so the
 * suite exercises the API rather than a fixture loader.
 */

export const FIXTURE_PATH = join(__dirname, ".fixture.json");

export default function globalSetup(): void {
  const databaseUrl =
    process.env.LEGALMIND_E2E_DATABASE_URL ??
    "postgresql+psycopg2://legalmind:legalmind@127.0.0.1/legalmind_v1_e2e";

  const stdout = execFileSync(
    "python3",
    ["-m", "tools.e2e_bootstrap", "--recreate"],
    {
      cwd: join(__dirname, "..", "..", "backend"),
      env: { ...process.env, LEGALMIND_DATABASE_URL: databaseUrl },
      encoding: "utf8",
      // Alembic logs to stderr; only stdout is the contract.
      stdio: ["ignore", "pipe", "inherit"],
    },
  );

  // Parsed before writing, so a malformed bootstrap fails here rather than inside a
  // spec where the error would look like a product defect.
  const fixture = JSON.parse(stdout);
  if (!fixture.accounts?.admin || !fixture.document?.path) {
    throw new Error("bootstrap did not emit the expected fixture description");
  }
  writeFileSync(FIXTURE_PATH, JSON.stringify(fixture, null, 2));
}
