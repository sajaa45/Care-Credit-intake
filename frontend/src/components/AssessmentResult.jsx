// What the applicant sees once their application has been assessed.
// The applicant gets the outcome and their instalment, not the internal numbers
// (available room, norms); those are for the employee.

import { euro as money } from "../format.js";
import ScheduleTable from "./ScheduleTable.jsx";

function TermAlternative({ assessment, onChangeTerm }) {
  if (!assessment.suggested_term) return null;
  return (
    <div className="alternative">
      <p>
        <strong>We could finance it over {assessment.suggested_term} months</strong> instead, at{" "}
        {money(assessment.suggested_instalment)} per month.
      </p>
      <button type="button" className="button" onClick={() => onChangeTerm(assessment.suggested_term)}>
        Apply with {assessment.suggested_term} months
      </button>
    </div>
  );
}

function Accepted({ assessment }) {
  const schedule = assessment.schedule;
  const finalInstalment = schedule?.[schedule.length - 1].instalment;
  return (
    <>
      <h2>Good news: we can finance your treatment</h2>
      <dl className="summary">
        <dt>Monthly instalment</dt>
        <dd>
          <strong>{money(assessment.instalment)}</strong>
          {finalInstalment && finalInstalment !== assessment.instalment && (
            <span className="muted"> (final instalment {money(finalInstalment)})</span>
          )}
        </dd>
        <dt>Term</dt>
        <dd>{assessment.term} months</dd>
        <dt>Interest</dt>
        <dd>8.9% per year, fixed</dd>
        {assessment.total_repayable && (
          <>
            <dt>Total interest</dt>
            <dd>{money(assessment.total_interest)}</dd>
            <dt>Total you'll repay</dt>
            <dd><strong>{money(assessment.total_repayable)}</strong></dd>
          </>
        )}
      </dl>
      <ScheduleTable schedule={schedule} />
      <p>We'll send you the agreement to sign.</p>
    </>
  );
}

function Referred({ assessment, onChangeTerm }) {
  return (
    <>
      <h2>One of our colleagues will look at your application</h2>
      <p>
        The monthly instalment of {money(assessment.instalment)} over {assessment.term} months is just above what
        your budget leaves room for. Rather than saying no, we'd like a person to look at your situation. We'll
        let you know the outcome.
      </p>
      <TermAlternative assessment={assessment} onChangeTerm={onChangeTerm} />
    </>
  );
}

function Declined({ assessment, onChangeTerm }) {
  if (assessment.suggested_term) {
    return (
      <>
        <h2>We can't finance it over {assessment.term} months, but there is another way</h2>
        <p>
          Over {assessment.term} months the instalment would be {money(assessment.instalment)}, which is more than
          your budget leaves room for after your fixed costs and everyday living.
        </p>
        <TermAlternative assessment={assessment} onChangeTerm={onChangeTerm} />
      </>
    );
  }

  return (
    <>
      <h2>We're not able to finance this treatment right now</h2>
      <p>
        We know this isn't the answer you were hoping for, especially when it's about your health, and we're sorry.
      </p>
      <p>
        <strong>Why:</strong> based on the income and costs you gave us, a monthly repayment, even spread over the
        longest term we offer, would leave you with less than you need for everyday living. We don't want to lend
        you money that would make things harder for you.
      </p>
      <p>This is not a judgement about you, and it doesn't stop you from applying again.</p>
      <h3>What you can do</h3>
      <ul className="steps">
        <li>
          <strong>Ask your clinic</strong> whether you can pay in instalments, or whether the treatment can be done
          in stages.
        </li>
        <li>
          <strong>Check with your health insurer</strong> whether part of it is covered, or whether a supplementary
          policy would cover it from next year.
        </li>
        <li>
          <strong>Apply again</strong> if something in your situation is different from what you entered, or
          changes, such as a new job or lower housing costs.
        </li>
        <li>
          <strong>Get free help with money matters</strong> from your municipality (gemeente) or at geldfit.nl.
          It's confidential and free.
        </li>
      </ul>
      <p className="muted">
        This decision was made automatically using a fixed rule. If you think something went wrong, or you'd like
        a person to look at it, contact us and one of our colleagues will review it.
      </p>
    </>
  );
}

export default function AssessmentResult({ assessment, onChangeTerm }) {
  const Outcome = { accept: Accepted, refer: Referred, decline: Declined }[assessment.outcome];
  return (
    <section className={`result result-${assessment.outcome}`} aria-live="polite">
      <Outcome assessment={assessment} onChangeTerm={onChangeTerm} />
    </section>
  );
}
