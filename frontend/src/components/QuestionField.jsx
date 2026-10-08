// One input per question type from GET /applicant/form.

const euro = new Intl.NumberFormat("nl-NL", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

export function formatAmount(question, value) {
  return question.unit === "EUR" ? euro.format(value) : `${value} ${question.unit}`;
}

const HINTS = {
  applicant_number: "Numbers only. Use the same ID every time you apply, so we can keep your applications together.",
  treatment_other: "For example skin surgery or a hearing aid.",
  cost: "The amount on the quote from your clinic, in whole euros.",
  requested_term: "How many months you'd like to repay over. If it doesn't fit your budget we'll suggest another term.",
  income: "What you receive each month after tax.",
  housing_cost: "Rent or mortgage. Enter 0 if you don't pay any.",
  existing_obligations: "Monthly payments on other loans, credit cards or lease contracts. Enter 0 if none.",
  partner_income: "What your partner receives each month after tax. Enter 0 if they have no income.",
  additional_information:
    "For example a temporary contract, an expected change in income, or a partner going on leave. You don't need to share medical details.",
};

function hintFor(question) {
  const parts = [HINTS[question.field]];
  // Only show a range when it's a real product limit, not the sanity ceiling on monthly amounts.
  if (question.type === "integer" && question.unit === "months") {
    parts.push(`Between ${question.min} and ${question.max} months.`);
  } else if (question.type === "integer" && question.field === "cost") {
    parts.push(`Between ${formatAmount(question, question.min)} and ${formatAmount(question, question.max)}.`);
  }
  return parts.filter(Boolean).join(" ");
}

const onlyDigits = (text) => text.replace(/\D/g, "");

export default function QuestionField({ question, value, error, onChange }) {
  const { field, label, type } = question;
  const hintId = `${field}-hint`;
  const errorId = `${field}-error`;
  const describedBy = `${hintId} ${errorId}`;
  const hint = hintFor(question);

  let control;
  if (type === "choice") {
    control = (
      <div className="options" role="radiogroup" aria-describedby={describedBy}>
        {question.options.map((option) => (
          <label key={option.value} className="option">
            <input
              type="radio"
              name={field}
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
            />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
    );
  } else if (type === "integer" || type === "digits") {
    const maxLength = type === "digits" ? question.max_length : String(question.max).length;
    control = (
      <div className="input-wrap">
        {question.unit === "EUR" && <span className="affix">€</span>}
        <input
          id={field}
          type="text"
          inputMode="numeric"
          autoComplete="off"
          maxLength={maxLength}
          value={value}
          aria-describedby={describedBy}
          aria-invalid={Boolean(error)}
          onChange={(e) => onChange(onlyDigits(e.target.value))}
        />
        {question.unit === "months" && <span className="affix">months</span>}
      </div>
    );
  } else if (type === "short_text") {
    control = (
      <div className="input-wrap wide">
        <input
          id={field}
          type="text"
          maxLength={question.max_length}
          value={value}
          aria-describedby={describedBy}
          aria-invalid={Boolean(error)}
          onChange={(e) => onChange(e.target.value)}
        />
      </div>
    );
  } else {
    control = (
      <>
        <textarea
          id={field}
          maxLength={question.max_length}
          value={value}
          aria-describedby={describedBy}
          aria-invalid={Boolean(error)}
          onChange={(e) => onChange(e.target.value)}
        />
        <p className="counter">{value.length} / {question.max_length}</p>
      </>
    );
  }

  const Wrapper = type === "choice" ? "fieldset" : "div";
  const Title = type === "choice" ? "legend" : "label";

  return (
    <Wrapper className={`field${error ? " invalid" : ""}`}>
      <Title {...(type === "choice" ? {} : { htmlFor: field })}>
        {label} {!question.required && <span className="optional">(optional)</span>}
      </Title>
      {hint && <p className="hint" id={hintId}>{hint}</p>}
      {control}
      <p className="error" id={errorId}>{error}</p>
    </Wrapper>
  );
}
