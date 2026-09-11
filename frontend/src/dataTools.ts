declare const __LOCAL_DATA_TOOLS__: boolean;

// Enabled by the local Vite dev server only; every build is public/read-only.
export const localDataTools = typeof __LOCAL_DATA_TOOLS__ !== "undefined" && __LOCAL_DATA_TOOLS__;
