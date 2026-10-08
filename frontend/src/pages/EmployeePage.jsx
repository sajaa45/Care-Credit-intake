import { useEffect, useState } from "react";

import ApplicationReview from "../components/ApplicationReview.jsx";
import { STATUS_LABELS, euro } from "../format.js";

const FILTERS = [
  { value: "", label: "All" },
  { value: "refer", label: "To review" },
  { value: "accept", label: "Accepted" },
  { value: "decline", label: "Declined" },
];

export default function EmployeePage() {
  const [filter, setFilter] = useState("refer");
  const [applications, setApplications] = useState(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [openId, setOpenId] = useState(null);

  useEffect(() => {
    setApplications(null);
    setLoadFailed(false);
    fetch(`/api/employee/applications${filter ? `?status=${filter}` : ""}`)
      .then((res) => (res.ok ? res.json() : Promise.reject(res)))
      .then(setApplications)
      .catch(() => setLoadFailed(true));
  }, [filter]);

  function replaceApplication(updated) {
    setApplications((list) => list.map((a) => (a.id === updated.id ? updated : a)));
  }

  return (
    <>
      <h1>Applications</h1>
      <p className="lede">The system's assessment and calculation for every application, and your decisions.</p>

      <div className="tabs" role="tablist" aria-label="Filter by status">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            role="tab"
            aria-selected={filter === f.value}
            className="tab"
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loadFailed && <p className="form-error">Couldn't load applications. Is the backend running on port 8000?</p>}
      {!applications && !loadFailed && <p className="muted">Loading…</p>}
      {applications?.length === 0 && <p className="muted">No applications here.</p>}

      <ul className="app-list">
        {applications?.map((a) => {
          const open = openId === a.id;
          return (
            <li key={a.id} className={`app-card${open ? " open" : ""}`}>
              <button
                type="button"
                className="app-row"
                aria-expanded={open}
                onClick={() => setOpenId(open ? null : a.id)}
              >
                <span className={`badge badge-${a.status}`}>{STATUS_LABELS[a.status] ?? a.status}</span>
                <span className="app-main">
                  <strong>{a.treatment}</strong> · {euro(a.cost)} over {a.requested_term} months
                </span>
                <span className="app-meta">
                  Applicant {a.applicant_id.slice(0, 8)} · #{a.application_number} ·{" "}
                  {new Date(a.created_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}
                  {a.decisions.length > 0 && " · decided by employee"}
                </span>
              </button>
              {open && <ApplicationReview application={a} onUpdated={replaceApplication} />}
            </li>
          );
        })}
      </ul>
    </>
  );
}
