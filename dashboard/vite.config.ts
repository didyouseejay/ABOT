import path from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
import { abotBundle } from "./vite/bundlePlugin.ts";

const here = path.dirname(fileURLToPath(import.meta.url));
/** Written by `abot export-dashboard`; read-only for the dashboard. */
export const BUNDLE_DIR = path.resolve(here, "../data/processed/dashboard/v1");

export default defineConfig({
  base: "./",
  plugins: [react(), abotBundle({ bundleDir: BUNDLE_DIR, urlPrefix: "/data/v1/" })],
  build: { outDir: "dist", emptyOutDir: true, sourcemap: true },
  test: {
    environment: "node",
    include: ["test/**/*.test.ts"],
  },
});
