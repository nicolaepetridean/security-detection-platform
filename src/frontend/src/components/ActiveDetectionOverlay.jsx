// Persistent panel pinned to the bottom-right showing the analyst's single active
// detection. Always accessible; lets them close it with a written resolution.
import { useState } from "react";
import { useActive } from "../active";
import { api } from "../api";
import { isAnalyst, useAuth } from "../auth";

export default function ActiveDetectionOverlay() {
  const { user } = useAuth();
  const { active, refresh } = useActive();
  const [resolution, setResolution] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (!isAnalyst(user)) return null;
  if (!active) {
    return (
      <div className="overlay overlay-empty">
        <strong>No active detection</strong>
        <div className="muted">Claim one from the queue to start working.</div>
      </div>
    );
  }

  async function onClose(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api.close(active.id, resolution);
      setResolution("");
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="overlay">
      <div className="overlay-head">
        <strong>Active detection #{active.id}</strong>
        <span className={`prio prio-${bucket(active.priority)}`}>
          priority {active.priority}
        </span>
      </div>
      <div className="muted">
        signature {active.signature_id} · customer {active.customer_id}
      </div>
      <pre className="payload">{JSON.stringify(active.raw_payload?.fields, null, 2)}</pre>
      <form onSubmit={onClose}>
        <textarea
          placeholder="Write a resolution to close this detection…"
          value={resolution}
          onChange={(e) => setResolution(e.target.value)}
          required
        />
        {error && <div className="error">{error}</div>}
        <button disabled={busy || !resolution.trim()}>Close detection</button>
      </form>
    </div>
  );
}

function bucket(p) {
  if (p >= 15) return "high";
  if (p >= 6) return "med";
  return "low";
}
