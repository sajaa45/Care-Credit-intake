import { useEffect, useState } from "react";

import { Calculation, FreeTextReview, History } from "../components/ApplicationReview.jsx";
import { STATUS_LABELS, dateTime, euro } from "../format.js";

function ApplicationList({ applications, onOpen }) {
  if (!applications) return <p className="muted">Loading…</p>;
  if (applications.length === 0) return <p className="muted">No applications found.</p>;
  return (
    <ul className="app-list">
      {applications.map((a) => (
        <li key={a.id} className="app-card">
          <button type="button" className="app-row" onClick={() => onOpen(a.id)}>
            <span className={`badge badge-${a.status}`}>{STATUS_LABELS[a.status] ?? a.status}</span>
            <span className="app-main">
              <strong>{a.treatment}</strong> · {euro(a.cost)} over {a.requested_term} months
            </span>
            <span className="app-meta">
              Applicant {a.applicant_id.slice(0, 8)} · #{a.application_number} · {dateTime(a.created_at)}
              {a.decided_by_employee && " · decided by employee"}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

function Record({ id, onBack }) {
  const [record, setRecord] = useState(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetch(`/api/compliance/applications/${id}/record`)
      .then((res) => (res.ok ? res.json() : Promise.reject(res)))
      .then(setRecord)
      .catch(() => setFailed(true));
  }, [id]);

  const back = (
    <button type="button" className="button secondary" onClick={onBack}>
      ← Back to the list
    </button>
  );
  if (failed) return <>{back}<p className="form-error">Couldn't load this record.</p></>;
  if (!record) return <p className="muted">Loading…</p>;

  const a = record.application;
  return (
    <>
      {back}
      <header className="record-header">
        <h2>
          {a.treatment} · {euro(a.cost)}{" "}
          <span className={`badge badge-${a.status}`}>{STATUS_LABELS[a.status] ?? a.status}</span>
        </h2>
        <p className="muted">
          Application #{a.application_number} of applicant {a.applicant_id.slice(0, 8)} · received{" "}
          {dateTime(a.created_at)} · reference {a.id}
        </p>
      </header>

      <section className="record-section">
        <h3>1. What we asked, and what the applicant answered</h3>
        <p className="muted small">
          Form version {record.form_version} · form id {record.form_id.slice(0, 12)}: the wording below is exactly
          what the applicant saw.
        </p>
        <table className="qa">
          <thead>
            <tr><th scope="col">Question</th><th scope="col">Answer</th></tr>
          </thead>
          <tbody>
            {record.answers.map((qa) => (
              <tr key={qa.field}>
                <th scope="row">{qa.question}</th>
                <td>
                  {qa.answer !== null && <span className="free-text">{qa.answer}</span>}
                  {qa.note && <span className="muted small qa-note">{qa.note}</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="record-section">
        <h3>2. What the system concluded, and on what basis</h3>
        {record.assessments.length === 0 && <p className="muted">No assessment on record.</p>}
        {record.assessments.map((assessment) => (
          <Calculation key={assessment.created_at} assessment={assessment} />
        ))}
        <FreeTextReview review={record.free_text_review} />
      </section>

      <section className="record-section">
        <h3>3. What employees did afterwards</h3>
        {record.decisions.length === 0 ? (
          <p className="muted">No employee changed this outcome.</p>
        ) : (
          <History decisions={record.decisions} />
        )}
      </section>

      <section className="record-section">
        <h3>Timeline</h3>
        <ol className="timeline">
          {record.timeline.map((event, i) => (
            <li key={i}>
              <span className="muted small">{dateTime(event.at)}</span>
              <strong>{event.event}</strong>
              <span>{event.detail}</span>
            </li>
          ))}
        </ol>
      </section>
    </>
  );
}

export default function CompliancePage() {
  const [applications, setApplications] = useState(null);
  const [idNumber, setIdNumber] = useState("");
  const [searchedFor, setSearchedFor] = useState(null);
  const [error, setError] = useState(null);
  const [openId, setOpenId] = useState(null);

  function loadAll() {
    setApplications(null);
    setSearchedFor(null);
    setError(null);
    fetch("/api/compliance/applications")
      .then((res) => (res.ok ? res.json() : Promise.reject(res)))
      .then(setApplications)
      .catch(() => setError("Couldn't load applications. Is the backend running on port 8000?"));
  }

  useEffect(loadAll, []);

  async function search(event) {
    event.preventDefault();
    if (!idNumber) return loadAll();
    setError(null);
    setApplications(null);
    try {
      const res = await fetch("/api/compliance/applications/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ applicant_number: idNumber }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.errors?.[0]?.message ?? "Search failed.");
      setApplications(data);
      setSearchedFor(idNumber);
    } catch (e) {
      setError(e.message);
      setApplications([]);
    }
  }

  if (openId) return <Record id={openId} onBack={() => setOpenId(null)} />;

  return (
    <>
      <h1>Compliance</h1>
      <p className="lede">Open any application to see what we asked, what was answered, what we concluded and why, and what employees did.</p>

      <form className="search" onSubmit={search}>
        <label htmlFor="id-number">Find by ID number</label>
        <div className="search-row">
          <div className="input-wrap">
            <input
              id="id-number"
              type="text"
              inputMode="numeric"
              autoComplete="off"
              maxLength={20}
              value={idNumber}
              onChange={(e) => setIdNumber(e.target.value.replace(/\D/g, ""))}
            />
          </div>
          <button type="submit" className="button">Search</button>
          {searchedFor !== null && (
            <button type="button" className="button secondary" onClick={() => { setIdNumber(""); loadAll(); }}>
              Show all
            </button>
          )}
        </div>
      </form>

      {error && <p className="form-error">{error}</p>}
      {searchedFor !== null && !error && (
        <p className="muted">Applications for ID number {searchedFor}:</p>
      )}
      <ApplicationList applications={applications} onOpen={setOpenId} />
    </>
  );
}
