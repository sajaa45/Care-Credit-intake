import { useState } from "react";

import { HOUSEHOLD_LABELS, STATUS_LABELS, dateTime, euro } from "../format.js";
import ScheduleTable from "./ScheduleTable.jsx";

const EMPLOYEE_KEY = "employee-name";

function readSavedName() {
  try {
    return localStorage.getItem(EMPLOYEE_KEY) ?? "";
  } catch {
    return "";
  }
}

function Answers({ application: a }) {
  return (
    <section>
      <h3>Applicant's answers</h3>
      <dl className="summary">
        <dt>Household</dt>
        <dd>{HOUSEHOLD_LABELS[a.household] ?? a.household}</dd>
        <dt>Net income</dt>
        <dd>{euro(a.income)}</dd>
        {a.partner_income !== null && (
          <>
            <dt>Partner's net income</dt>
            <dd>{euro(a.partner_income)}</dd>
          </>
        )}
        <dt>Housing costs</dt>
        <dd>{euro(a.housing_cost)}</dd>
        <dt>Existing obligations</dt>
        <dd>{euro(a.existing_obligations)}</dd>
      </dl>
    </section>
  );
}

export function Calculation({ assessment }) {
  if (!assessment) {
    return (
      <section>
        <h3>System assessment</h3>
        <p className="muted">This application was submitted before assessments existed.</p>
      </section>
    );
  }
  const { steps, constants } = assessment.calculation;
  const share = (Number(steps.income_share) * 100).toFixed(2);
  return (
    <section>
      <h3>
        System assessment: <span className={`badge badge-${assessment.outcome}`}>{STATUS_LABELS[assessment.outcome]}</span>
      </h3>
      <p>{assessment.reason}</p>
      <table className="calc">
        <tbody>
          <tr><th>Applicant's share of household income</th><td>{share}%</td></tr>
          <tr><th>Net income</th><td>{euro(assessment.calculation.inputs.income)}</td></tr>
          <tr><th>− Housing share</th><td>{euro(steps.housing_share)}</td></tr>
          <tr><th>− Existing obligations</th><td>{euro(assessment.calculation.inputs.existing_obligations)}</td></tr>
          <tr><th>− Living standard norm share (of {euro(constants.living_standard_norm)})</th><td>{euro(steps.norm_share)}</td></tr>
          <tr className="total"><th>= Available room</th><td>{euro(steps.available_room)}</td></tr>
          <tr><th>Instalment ({assessment.term} months, {(Number(constants.annual_interest_rate) * 100).toFixed(1)}%)</th><td>{euro(steps.instalment)}</td></tr>
          <tr><th>Refer limit (room + {(Number(constants.refer_margin) * 100).toFixed(0)}%)</th><td>{euro(steps.refer_limit)}</td></tr>
        </tbody>
      </table>
      {assessment.total_repayable && (
        <p>
          Total repayable {euro(assessment.total_repayable)} ({euro(assessment.calculation.inputs.cost)} principal +{" "}
          {euro(assessment.total_interest)} interest).
        </p>
      )}
      <ScheduleTable schedule={assessment.schedule} summary={`Repayment schedule (${assessment.term} months)`} />
      {assessment.suggested_term && (
        <p className="muted">
          Shortest term that would be accepted: {assessment.suggested_term} months at{" "}
          {euro(assessment.suggested_instalment)}.
        </p>
      )}
      <p className="muted small">Rule version {assessment.rule_version} · {dateTime(assessment.created_at)}</p>
    </section>
  );
}

export function FreeTextReview({ review }) {
  if (!review || review.status === "skipped") return null;
  if (review.status === "stubbed") {
    return (
      <section className="free-text-review stubbed">
        <h3>
          Free-text answer <span className="badge">Not screened: no API key</span>
        </h3>
        <p>{review.summary}</p>
        <p>{review.reason}</p>
        {review.raw_text_deleted_at && (
          <p className="muted">The applicant's own words were deleted ({dateTime(review.raw_text_deleted_at)}).</p>
        )}
      </section>
    );
  }
  return (
    <section className={`free-text-review${review.needs_review ? " flagged" : ""}`}>
      <h3>
        Free-text answer{" "}
        <span className={`badge ${review.needs_review ? "badge-refer" : "badge-accept"}`}>
          {review.needs_review ? "Needs a look" : "Nothing flagged"}
        </span>
      </h3>
      {review.summary && <p><strong>Summary:</strong> {review.summary}</p>}
      <p><strong>{review.needs_review ? "Why:" : "Reason:"}</strong> {review.reason}</p>
      {review.raw_text_deleted_at && (
        <p className="muted">
          The applicant's own words were deleted after screening ({dateTime(review.raw_text_deleted_at)}); only this
          summary and reason are kept.
        </p>
      )}
      {review.referred_by_flag && (
        <p className="muted">The rule accepted this application; the flag sent it to review instead.</p>
      )}
      <p className="muted small">
        {review.status === "failed" ? "Screening failed" : "Screened"} by {review.model} · prompt{" "}
        {review.prompt_version} · {dateTime(review.created_at)}
      </p>
    </section>
  );
}

export function History({ decisions }) {
  if (decisions.length === 0) return null;
  return (
    <section>
      <h3>Decisions</h3>
      <ol className="history">
        {decisions.map((d) => (
          <li key={d.id}>
            <p>
              <strong>{d.employee}</strong> changed {STATUS_LABELS[d.previous_status]} →{" "}
              <span className={`badge badge-${d.outcome}`}>{STATUS_LABELS[d.outcome]}</span>
              <span className="muted small"> · {dateTime(d.created_at)}</span>
            </p>
            <p className="free-text">{d.comment}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}

function DecisionForm({ application, title, onSaved, onCancel }) {
  const [outcome, setOutcome] = useState("");
  const [comment, setComment] = useState("");
  const [employee, setEmployee] = useState(readSavedName);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!outcome || !comment.trim() || !employee.trim()) {
      setError("Choose accept or decline, and fill in your name and a comment.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`/api/employee/applications/${application.id}/decisions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ outcome, comment, employee }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.errors?.map((e) => `${e.field}: ${e.message}`).join(" ") ?? data.detail ?? "Saving failed.");
        return;
      }
      try {
        localStorage.setItem(EMPLOYEE_KEY, employee.trim());
      } catch {
        // Remembering the name is only a convenience.
      }
      onSaved(data);
    } catch {
      setError("Couldn't reach the server. Nothing was saved.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="decision-form" onSubmit={handleSubmit} noValidate>
      <h3>{title}</h3>
      <div className="options two">
        {["accept", "decline"].map((value) => (
          <label key={value} className="option">
            <input
              type="radio"
              name={`outcome-${application.id}`}
              value={value}
              checked={outcome === value}
              onChange={() => setOutcome(value)}
            />
            <span>{value === "accept" ? "Accept" : "Decline"}</span>
          </label>
        ))}
      </div>
      <label htmlFor={`comment-${application.id}`}>Why? (required)</label>
      <textarea
        id={`comment-${application.id}`}
        value={comment}
        maxLength={2000}
        onChange={(e) => setComment(e.target.value)}
      />
      <label htmlFor={`employee-${application.id}`}>Your name</label>
      <div className="input-wrap">
        <input
          id={`employee-${application.id}`}
          type="text"
          value={employee}
          maxLength={100}
          onChange={(e) => setEmployee(e.target.value)}
        />
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="actions">
        <button type="submit" className="button" disabled={saving}>
          {saving ? "Saving…" : "Save decision"}
        </button>
        <button type="button" className="button secondary" onClick={onCancel} disabled={saving}>
          Cancel
        </button>
      </div>
    </form>
  );
}

export default function ApplicationReview({ application, onUpdated }) {
  // The decision form only appears when the employee chooses to act.
  const [deciding, setDeciding] = useState(false);
  const title = application.decisions.length > 0 ? "Change the decision" : "Add a decision";
  return (
    <div className="review">
      <div className="review-columns">
        <Answers application={application} />
        <Calculation assessment={application.assessment} />
      </div>
      <FreeTextReview review={application.free_text_review} />
      <History decisions={application.decisions} />
      {deciding ? (
        <DecisionForm
          application={application}
          title={title}
          onSaved={(updated) => {
            onUpdated(updated);
            setDeciding(false);
          }}
          onCancel={() => setDeciding(false)}
        />
      ) : (
        <button type="button" className="button" onClick={() => setDeciding(true)}>
          {title}
        </button>
      )}
    </div>
  );
}
