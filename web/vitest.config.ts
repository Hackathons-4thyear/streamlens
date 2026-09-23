import { defineConfig } from "vitest/config";

/**
 * Kept separate from vite.config.ts on purpose: vitest ships its own copy of
 * Vite, and importing `defineConfig` from "vitest/config" in the same file as
 * the Vite plugins makes TypeScript compare two different Vite type trees.
 *
 * JSX is handled by esbuild (tsconfig sets jsx: react-jsx), so component tests
 * work here without the React plugin.
 */
export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
