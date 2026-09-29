import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";
import { readFile } from "node:fs/promises";

const pilotFiles = new Set([
  "national_summary.csv", "state_counts.csv", "district_counts.csv", "candidate_review.csv",
]);
const pilotDirectory = new URL("../tmp/phase_1_2_pilot/reclassified_results/", import.meta.url);
const pilotReports = {
  name: "local-up-pilot-reports",
  configureServer(server: { middlewares: { use: (handler: (req: { url?: string }, res: { statusCode: number; setHeader: (key: string, value: string) => void; end: (body?: string) => void }, next: () => void) => void) => void } }) {
    server.middlewares.use((req, res, next) => {
      const prefix = "/local-up-pilot/";
      const path = req.url?.split("?", 1)[0] || "";
      if (!path.startsWith(prefix)) return next();
      const file = path.slice(prefix.length);
      if (!pilotFiles.has(file)) { res.statusCode = 404; res.end(); return; }
      readFile(new URL(file, pilotDirectory), "utf8")
        .then(content => {
          res.setHeader("Content-Type", "text/csv; charset=utf-8");
          res.setHeader("Cache-Control", "no-store");
          res.end(content);
        })
        .catch(() => { res.statusCode = 404; res.end(); });
    });
  },
};

const { version } = JSON.parse(
  readFileSync(new URL("./package.json", import.meta.url), "utf8"),
);

export default defineConfig(({ mode, command }) => ({
  plugins: [react(), ...(command === "serve" ? [pilotReports] : [])],
  define: {
    __LOCAL_DATA_TOOLS__: JSON.stringify(command === "serve"),
    __PORTAL_VERSION__: JSON.stringify(version),
    __VISITS_ENDPOINT__: JSON.stringify(loadEnv(mode, process.cwd(), "VITE_").VITE_VISITS_API_URL || ""),
  },
}));
