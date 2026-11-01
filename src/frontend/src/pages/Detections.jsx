// Full, filterable history of ALL detections (open, assigned, closed).
// Deliberately distinct from the queue: this is the record, the queue is the worklist.
import { useEffect, useState } from "react";
import { api } from "../api";
import { PriorityBadge } from "../components/PriorityBadge";

const STATUSES = ["", "open", "assigned", "closed"];

export default function Detections() {
  const [rows, setRows] = useState([]);
  const [status, setStatus] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      setRows(
        await api.listDetections({ status, customer_id: customerId || undefined })
      );
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, customerId]);

  return (
    <div>
      <div className="page-head">
        <h2>Detections</h2>
        <div className="muted">All detections — historical and active.</div>
      </div>
      <div className="filters">
        <label>
          Status:
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s || "all"}
              </option>
            ))}
          </select>
        </label>
        <label>
          Customer ID:
          <input
            type="number"
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
            placeholder="any"
          />
        </label>
      </div>
      {error && <div className="error">{error}</div>}
      <table className="grid">
        <thead>
          <tr>
            <th>ID</th>
            <th>Priority</th>
            <th>Status</th>
            <th>Signature</th>
            <th>Customer</th>
            <th>Assignee</th>
            <th>Resolution</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((d) => (
            <tr key={d.id}>
              <td>#{d.id}</td>
              <td>
                <PriorityBadge value={d.priority} />
              </td>
              <td>
                <span className={`status status-${d.status}`}>{d.status}</span>
              </td>
              <td>{d.signature_id}</td>
              <td>{d.customer_id}</td>
              <td>{d.assignee_id ?? "—"}</td>
              <td className="resolution">{d.resolution ?? "—"}</td>
              <td>{new Date(d.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && <p className="muted">No detections match the filters.</p>}
    </div>
  );
}
