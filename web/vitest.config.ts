import { defineConfig, mergeConfig, configDefaults } from "vitest/config";
import viteConfig from "./vite.config.ts";

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test/setup.ts"],
      css: false,
      // web/e2e/ son specs de Playwright (Task 22), no de Vitest.
      exclude: [...configDefaults.exclude, "e2e/**"],
    },
  }),
);
