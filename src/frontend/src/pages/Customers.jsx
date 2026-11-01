// View customers; admins can edit importance (and add customers). Readonly sees data.
import { useEffect, useState } from "react";
import { api } from "../api";
import { isAdmin, useAuth } from "../auth";

export default function Customers() {
  const { user } = useAuth();
  const admin = isAdmin(user);
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [newCustomer, setNewCustomer] = useState({ name: "", importance: 3 });

  async function load() {
    setError("");
    try {
      setRows(await api.customers());
    } catch (err) {
      setError(err.message);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function changeImportance(c, importance) {
    try {
      await api.updateCustomer(c.id, { importance });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function addCustomer(e) {
    e.preventDefault();
    try {
      await api.createCustomer({
        name: newCustomer.name,
        importance: Number(newCustomer.importance),
      });
      setNewCustomer({ name: "", importance: 3 });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div>
      <div className="page-head">
        <h2>Customers</h2>
        <div className="muted">Importance (1–5) feeds detection priority.</div>
      </div>
      {error && <div className="error">{error}</div>}
      <table className="grid">
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Importance</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.id}>
              <td>#{c.id}</td>
              <td>{c.name}</td>
              <td>
                {admin ? (
                  <select
                    value={c.importance}
                    onChange={(e) => changeImportance(c, Number(e.target.value))}
                  >
                    {[1, 2, 3, 4, 5].map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                ) : (
                  c.importance
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {admin && (
        <form className="card inline-form" onSubmit={addCustomer}>
          <h3>Add customer</h3>
          <input
            placeholder="Name"
            value={newCustomer.name}
            onChange={(e) => setNewCustomer({ ...newCustomer, name: e.target.value })}
            required
          />
          <select
            value={newCustomer.importance}
            onChange={(e) =>
              setNewCustomer({ ...newCustomer, importance: e.target.value })
            }
          >
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>
                importance {n}
              </option>
            ))}
          </select>
          <button>Add</button>
        </form>
      )}
    </div>
  );
}
