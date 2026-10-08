import { useState } from "react";
import { Link } from "react-router-dom";

import AssessmentResult from "../components/AssessmentResult.jsx";
import ReceivedCard from "../components/ReceivedCard.jsx";
import { dateTime, euro } from "../format.js";

// Worded for the applicant, not with the internal status names.
const STATUS_TEXT = {
  submitted: { label: "Received", text: "We've received it and are assessing it." },
  accept: { label: "Accepted", text: "We can finance this treatment." },
  refer: { label: "Being reviewed", text: "A colleague is looking at it. We'll let you know the outcome." },
  decline: { label: "Not approved", text: "We're not able to finance this one." },
};

export default function ApplicantStatusPage() {
  const [idNumber, setIdNumber] = useState("");
  const [applications, setApplications] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [openNumber, setOpenNumber] = useState(null);

  async function lookup(event) {
    event.preventDefault();
    if (!idNumber) {
      setError("Please enter your ID number.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/api/applicant/applications/lookup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ applicant_number: idNumber }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.errors?.[0]?.message ?? "Something went wrong.");
      setApplications(data);
      setOpenNumber(null);
    } catch (e) {
      setError(e.message === "Failed to fetch" ? "We couldn't reach the server. Please try again." : e.message);
      setApplications(null);
    } finally {
      setLoading(false);
    }
  }

  const opened = applications?.find((a) => a.application_number === openNumber);
  if (opened) {
    return (
      <>
        <button type="button" className="button secondary back" onClick={() => setOpenNumber(null)}>
          ← All my applications
        </button>
        <ReceivedCard applicationNumber={opened.application_number} receivedAt={opened.submitted_at} />
        {opened.reviewed_by_employee && (
          <p className="muted">A colleague reviewed this application on {dateTime(opened.updated_at)}.</p>
        )}
        {opened.offer ? (
          <AssessmentResult
            assessment={opened.offer}
            status={opened.status}
            reviewedByEmployee={opened.reviewed_by_employee}
          />
        ) : (
          <p className="muted">This application hasn't been assessed yet.</p>
        )}
      </>
    );
  }

  return (
    <>
      <h1>Your applications</h1>
      <p className="lede">Enter the ID number you applied with to see the status of your applications.</p>

      <form className="search" onSubmit={lookup} noValidate>
        <label htmlFor="lookup-id">Your ID number</label>
        <div className="search-row">
          <div className="input-wrap">
            <input
              id="lookup-id"
              type="text"
              inputMode="numeric"
              autoComplete="off"
              maxLength={20}
              value={idNumber}
              onChange={(e) => setIdNumber(e.target.value.replace(/\D/g, ""))}
            />
          </div>
          <button type="submit" className="button" disabled={loading}>
            {loading ? "Looking up…" : "Show my applications"}
          </button>
        </div>
      </form>

      {error && <p className="form-error" role="alert">{error}</p>}

      {applications?.length === 0 && (
        <p className="muted">
          We found no applications for this ID number. Check that it's the same number you applied with, including
          any leading zeros.
        </p>
      )}

      {applications?.length > 0 && (
        <ul className="app-list">
          {applications.map((a) => {
            const status = STATUS_TEXT[a.status];
            return (
              <li key={a.application_number} className="app-card">
                <button type="button" className="status-card" onClick={() => setOpenNumber(a.application_number)}>
                  <span className="status-head">
                    <strong>Application {a.application_number}</strong>
                    <span className={`badge badge-${a.status}`}>{status.label}</span>
                  </span>
                  <span className="status-line">
                    {a.treatment} · {euro(a.cost)} over {a.requested_term} months
                  </span>
                  <span className="status-line">{status.text}</span>
                  <span className="status-line muted small">
                    Submitted {dateTime(a.submitted_at)}
                    {a.reviewed_by_employee && ` · reviewed by a colleague ${dateTime(a.updated_at)}`}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <p>
        <Link to="/applicant">Start a new application</Link>
      </p>
    </>
  );
}
