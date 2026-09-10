declare const __PORTAL_VERSION__: string;

// Vite supplies the package version for both development and production builds.
export const portalVersion = typeof __PORTAL_VERSION__ === "undefined"
  ? "development"
  : __PORTAL_VERSION__;
