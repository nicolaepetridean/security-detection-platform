// View signatures; admins can add. Each signature carries one or more field/value
// pairs (entered as JSON) used for matching, plus a priority.
import { useEffect, useState } from "react";
import { api } from "../api";
import { isAdmin, useAuth } from "../auth";

export default function Signatures() {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    name: "",
    priority: 3,
    match_fields: '{"event_type": "auth_fail"}',
  });

  async function load() {
    setError("");
    try {
      setRows(await api.signatures());
    } catch (err) {
      setError(err.message);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function addSignature(e) {
    e.preventDefault();
    setError("");
    let fields;
    try {
      fields = JSON.parse(form.match_fields);
    } catch {
      setError("match_fields must be valid JSON, e.g. {\"service\": \"ssh\"}");
      return;
    }
    try {
      await api.createSignature({
        name: form.name,
        priority: Number(form.priority),
        match_fields: fields,
      });
      setForm({ name: "", priority: 3, match_fields: '{"event_type": "auth_fail"}' });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div>
      <div className="page-head">
        <h2>Signatures</h2>
        <div className="muted">
          A signature matches when all its field/value pairs are present in an incident.
        </div>
      </div>
      {error && <div className="error">{error}</div>}
      <table className="grid">
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Priority</th>
            <th>Match fields</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.id}>
              <td>#{s.id}</td>
              <td>{s.name}</td>
              <td>{s.priority}</td>
              <td>
                <code>{JSON.stringify(s.match_fields)}</code>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {admin && (
        <form className="card inline-form" onSubmit={addSignature}>
          <h3>Add signature</h3>
          <input
            placeholder="Name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
          />
          <select
            value={form.priority}
            onChange={(e) => setForm({ ...form, priority: e.target.value })}
          >
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>
                priority {n}
              </option>
            ))}
          </select>
          <input
            className="wide"
            placeholder='{"field": "value"}'
            value={form.match_fields}
            onChange={(e) => setForm({ ...form, match_fields: e.target.value })}
          />
          <button>Add</button>
        </form>
      )}
    </div>
  );
}
