import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./__tests__/setup.ts"],
    include: ["__tests__/**/*.test.{ts,tsx}"],
    pool: "threads",
    testTimeout: 15000,
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      include: ["app/**", "components/**", "lib/**", "context/**", "middleware.ts"],
      exclude: [
        "node_modules",
        ".next",
        "__tests__",
        // Server-only modules that cannot be exercised in jsdom
        "lib/proxy.ts",
        "app/api/**",
        // Next.js layout/metadata shells with no testable logic
        "app/layout.tsx",
        "app/**/layout.tsx",
        "app/robots.ts",
        "app/sitemap.ts",
      ],
      thresholds: {
        lines: 70,
        functions: 70,
        branches: 70,
        statements: 70,
      },
    },
  },
});
