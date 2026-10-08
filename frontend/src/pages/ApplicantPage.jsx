import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import AssessmentResult from "../components/AssessmentResult.jsx";
import QuestionField, { formatAmount } from "../components/QuestionField.jsx";
import ReceivedCard from "../components/ReceivedCard.jsx";

// The assessment itself is instant; the applicant first sees that their
// application arrived, and the result follows after this pause.
const PROCESSING_MS = 3000;

// The form is drawn from GET /applicant/form, so the options and limits always
// match what the API accepts. The API stays the authority: the checks here only
// give feedback before a round trip.

function isVisible(question, values) {
  const rule = question.show_when;
  return !rule || rule.values.includes(values[rule.field]);
}

function validate(question, value) {
  if (value === "") {
    if (!question.required) return null;
    return question.type === "choice" ? "Please choose an option." : "Please fill this in.";
  }
  if (question.type === "integer") {
    const number = Number(value);
    if (number < question.min) return `Please enter at least ${formatAmount(question, question.min)}.`;
    if (number > question.max) return `Please enter at most ${formatAmount(question, question.max)}.`;
  }
  return null;
}

function toRequestBody(questions, values) {
  const body = {};
  for (const question of questions) {
    if (!isVisible(question, values)) continue;
    const value = values[question.field];
    body[question.field] = question.type === "integer" ? Number(value) : value;
  }
  return body;
}

export default function ApplicantPage() {
  const [questions, setQuestions] = useState(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [values, setValues] = useState({});
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [received, setReceived] = useState(null);
  const [processing, setProcessing] = useState(false);
  const formRef = useRef(null);

  useEffect(() => {
    fetch("/api/applicant/form")
      .then((res) => (res.ok ? res.json() : Promise.reject(res)))
      .then((form) => {
        setQuestions(form.questions);
        setValues(Object.fromEntries(form.questions.map((q) => [q.field, ""])));
      })
      .catch(() => setLoadFailed(true));
  }, []);

  useEffect(() => {
    if (!received) return;
    setProcessing(true);
    const timer = setTimeout(() => setProcessing(false), PROCESSING_MS);
    return () => clearTimeout(timer);
  }, [received]);

  // After errors are shown, move focus to the first one so it isn't missed.
  useEffect(() => {
    formRef.current?.querySelector(".field.invalid input, .field.invalid textarea")?.focus();
  }, [errors]);

  function setValue(field, value) {
    setValues((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: null }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setFormError(null);

    const visible = questions.filter((q) => isVisible(q, values));
    const clientErrors = Object.fromEntries(visible.map((q) => [q.field, validate(q, values[q.field])]));
    if (Object.values(clientErrors).some(Boolean)) {
      setErrors(clientErrors);
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch("/api/applicant/applications", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(toRequestBody(questions, values)),
      });
      const data = await res.json();
      if (res.status === 422) {
        const known = new Set(questions.map((q) => q.field));
        setErrors(Object.fromEntries(data.errors.filter((e) => known.has(e.field)).map((e) => [e.field, e.message])));
        const other = data.errors.filter((e) => !known.has(e.field));
        if (other.length) setFormError(other.map((e) => e.message).join(" "));
        return;
      }
      if (!res.ok) throw new Error(res.statusText);
      setReceived(data);
      window.scrollTo({ top: 0 });
    } catch {
      setFormError("Something went wrong sending your application. Your answers are still here, please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  function startOver() {
    setValues(Object.fromEntries(questions.map((q) => [q.field, ""])));
    setErrors({});
    setReceived(null);
  }

  // Back to the form with every answer kept, only the term changed; submitting
  // it creates a new application under the same ID.
  function changeTerm(term) {
    setValues((current) => ({ ...current, requested_term: String(term) }));
    setErrors({});
    setReceived(null);
    window.scrollTo({ top: 0 });
  }

  if (received) {
    return (
      <>
        <ReceivedCard applicationNumber={received.application_number} receivedAt={received.created_at} />

        {processing ? (
          <section className="result processing" aria-live="polite">
            <span className="spinner" aria-hidden="true" />
            <p>We're assessing your application. This takes a few seconds…</p>
          </section>
        ) : (
          <>
            {received.assessment && <AssessmentResult assessment={received.assessment} status={received.status} onChangeTerm={changeTerm} />}
            <div className="actions">
              <button type="button" className="button secondary" onClick={startOver}>
                Start a new application
              </button>
              <Link to="/applicant/status" className="button secondary">
                Check my applications later
              </Link>
            </div>
          </>
        )}
      </>
    );
  }

  return (
    <>
      <h1>Apply for treatment financing</h1>
      <p className="lede">
        A few questions about the treatment and your monthly budget. It takes about five minutes.
      </p>
      <p>
        Already applied? <Link to="/applicant/status">Check the status of your applications</Link>
      </p>

      {loadFailed && <p className="form-error">We couldn't load the form. Is the backend running on port 8000?</p>}
      {!questions && !loadFailed && <p className="muted">Loading form…</p>}

      {questions && (
        <form ref={formRef} onSubmit={handleSubmit} noValidate>
          {questions
            .filter((q) => isVisible(q, values))
            .map((q) => (
              <QuestionField
                key={q.field}
                question={q}
                value={values[q.field]}
                error={errors[q.field]}
                onChange={(value) => setValue(q.field, value)}
              />
            ))}
          {formError && <p className="form-error" role="alert">{formError}</p>}
          <button type="submit" className="button" disabled={submitting}>
            {submitting ? "Submitting…" : "Submit application"}
          </button>
        </form>
      )}
    </>
  );
}
