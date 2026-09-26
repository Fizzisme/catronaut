import { defineConfig } from "vite";

// Fixtures live next to the harness (../fixtures); allow Vite to read them at build time.
export default defineConfig({
  server: { fs: { allow: [".."] } },
  build: { outDir: "dist", emptyOutDir: true },
});
