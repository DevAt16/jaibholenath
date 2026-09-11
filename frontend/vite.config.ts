import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";

const { version } = JSON.parse(
  readFileSync(new URL("./package.json", import.meta.url), "utf8"),
);

export default defineConfig(({ mode, command }) => ({
  plugins: [react()],
  define: {
    __LOCAL_DATA_TOOLS__: JSON.stringify(command === "serve"),
    __PORTAL_VERSION__: JSON.stringify(version),
    __VISITS_ENDPOINT__: JSON.stringify(loadEnv(mode, process.cwd(), "VITE_").VITE_VISITS_API_URL || ""),
  },
}));
