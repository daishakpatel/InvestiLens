import { defineConfig } from "vitest/config";

// Unit tests target pure modules (schemas, citations, formatting) + a source guard, so a plain
// Node environment is enough — no jsdom/React renderer dependency (keeps the toolchain minimal).
export default defineConfig({
  test: {
    include: ["src/**/*.test.ts"],
    environment: "node",
  },
});
