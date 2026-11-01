// Landing page: prioritized queue of OPEN detections. Only analysts can claim.
import { useEffect, useState } from "react";
import { useActive } from "../active";
import { api } from "../api";
import { isAnalyst, useAuth } from "../auth";
import { PriorityBadge } from "../components/PriorityBadge";

export default function Queue() {
  const { user } = useAuth();
  const { active, refresh } = useActive();
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      setRows(await api.queue());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function claim(id) {
    setError("");
    try {
      await api.claim(id);
      await Promise.all([load(), refresh()]);
    } catch (err) {
      // 409 => lost the race or already have an active detection.
      setError(err.message);
      await load();
    }
  }

  return (
    <div>
      <div className="page-head">
        <h2>Queue</h2>
        <div className="muted">Open detections, most urgent first.</div>
      </div>
      {error && <div className="error">{error}</div>}
      {loading ? (
        <p>Loading…</p>
      ) : rows.length === 0 ? (
        <p className="muted">The queue is empty. 🎉</p>
      ) : (
        <table className="grid">
          <thead>
            <tr>
              <th>ID</th>
              <th>Priority</th>
              <th>Signature</th>
              <th>Customer</th>
              <th>Created</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((d) => (
              <tr key={d.id}>
                <td>#{d.id}</td>
                <td>
                  <PriorityBadge value={d.priority} />
                </td>
                <td>{d.signature_id}</td>
                <td>{d.customer_id}</td>
                <td>{new Date(d.created_at).toLocaleString()}</td>
                <td>
                  {isAnalyst(user) && (
                    <button
                      disabled={!!active}
                      title={active ? "Close your active detection first" : "Claim"}
                      onClick={() => claim(d.id)}
                    >
                      Claim
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
