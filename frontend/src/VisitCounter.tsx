import { useEffect, useRef, useState } from "react";
import { Footprints } from "lucide-react";
import { formatNumber } from "./reportLogic";
import { registerVisit, requestVisits, visitsEndpoint } from "./visitCounterClient";

export function VisitCounter() {
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [total, setTotal] = useState<number | null>(null);
  const [failed, setFailed] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!visitsEndpoint) return;
    let active = true;
    registerVisit().then((value) => { if (active) setTotal(value); })
      .catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (!open) return;
    let active = true;
    if (visitsEndpoint) {
      registerVisit().then(() => requestVisits(visitsEndpoint)).then((value) => {
        if (active) { setTotal(value); setFailed(false); }
      }).catch(() => { if (active) setFailed(true); });
    }
    const dismiss = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) { setOpen(false); setPinned(false); }
    };
    document.addEventListener("pointerdown", dismiss);
    return () => { active = false; document.removeEventListener("pointerdown", dismiss); };
  }, [open]);
  return (
    <div
      className="visit-counter"
      ref={root}
      onPointerEnter={(event) => { if (event.pointerType === "mouse") setOpen(true); }}
      onPointerLeave={(event) => { if (event.pointerType === "mouse" && !pinned) setOpen(false); }}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) { setOpen(false); setPinned(false); }
      }}
      onKeyDown={(event) => {
        if (event.key === "Escape") { setOpen(false); setPinned(false); event.stopPropagation(); }
      }}
    >
      <button
        type="button"
        className="visit-counter-button"
        aria-label="Portal visits"
        aria-expanded={open}
        aria-describedby={open ? "visit-counter-tooltip" : undefined}
        onFocus={(event) => { if (event.currentTarget.matches(":focus-visible")) setOpen(true); }}
        onClick={() => { setPinned(!pinned); setOpen(!pinned); }}
      >
        <span className="visit-counter-mark" aria-hidden="true">
          <Footprints size={16} strokeWidth={1.75} />
        </span>
      </button>
      {open && (
        <div className="visit-counter-tooltip" role="tooltip" id="visit-counter-tooltip">
          <span className="eyebrow">FOOTPRINTS HERE</span>
          <strong>{!visitsEndpoint ? "Not connected yet" : failed ? "Visits unavailable" : total === null ? "Counting visits…" : formatNumber(total)}</strong>
          <span>{!visitsEndpoint ? "The shared visit count will appear once the counter is connected." : failed ? "The counter could not be reached. Try opening this again later." : "Total recorded portal visits"}</span>
          <small>Browser tab sessions, not unique people. Refreshes reuse the session when browser storage is available.</small>
        </div>
      )}
    </div>
  );
}
