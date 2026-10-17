import path from "node:path"
import { fileURLToPath } from "node:url"

import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

const root = fileURLToPath(new URL(".", import.meta.url))

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@vectors": path.resolve(root, "../../tests/proofcheck/vectors"),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": process.env.MEMOPOPS_API_ORIGIN ?? "http://127.0.0.1:8010",
    },
  },
  preview: {
    host: "127.0.0.1",
    port: 4173,
    proxy: {
      "/api": process.env.MEMOPOPS_API_ORIGIN ?? "http://127.0.0.1:8010",
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
})
