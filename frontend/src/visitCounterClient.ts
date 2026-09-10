declare const __VISITS_ENDPOINT__: string;
export const visitsEndpoint = typeof __VISITS_ENDPOINT__ === "undefined" ? "" : __VISITS_ENDPOINT__;
const sessionKey = "shiva.portal.visit-session.v1";
let memorySession: string | undefined;

export function visitSession(storage: Pick<Storage, "getItem" | "setItem"> | null, createId: () => string): string {
  try {
    const stored = storage?.getItem(sessionKey);
    if (stored && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(stored)) return stored;
  } catch { /* Storage can be unavailable in private browsing. */ }
  memorySession ??= createId();
  try { storage?.setItem(sessionKey, memorySession); } catch { /* Keep the in-memory session. */ }
  return memorySession;
}

export async function requestVisits(endpoint: string, sessionId?: string, fetcher: typeof fetch = fetch): Promise<number> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetcher(endpoint, {
      method: sessionId ? "POST" : "GET",
      headers: sessionId ? { "Content-Type": "application/json" } : undefined,
      body: sessionId ? JSON.stringify({ session_id: sessionId }) : undefined,
      credentials: "omit",
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) throw new Error("Visit counter unavailable");
    const data = await response.json();
    if (!Number.isSafeInteger(data.total) || data.total < 0) throw new Error("Invalid visit total");
    return data.total;
  } finally {
    clearTimeout(timeout);
  }
}

let initialVisit: Promise<number> | undefined;
export async function registerVisit(): Promise<number> {
  // Share the request across React Strict Mode's effect remounts.
  if (!initialVisit) {
    let storage: Storage | null = null;
    try { storage = window.sessionStorage; } catch { /* No persistent session storage. */ }
    const id = visitSession(storage, () => crypto.randomUUID());
    initialVisit = requestVisits(visitsEndpoint, id).catch((error) => {
      initialVisit = undefined;
      throw error;
    });
  }
  return initialVisit;
}
