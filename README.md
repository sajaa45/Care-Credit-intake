# Care credit intake and assessment

A prototype of the online intake and affordability assessment for medical treatment financing (€500–€25,000, repaid over 6–60 months). An applicant fills in a form and gets a decision. An employee reviews referred applications and can overturn any outcome. A compliance officer can open any application and see the full record of what happened.

It covers three roles, each with its own screen in the React frontend and its own group of endpoints in the API (documented in Swagger).

- **Applicant**: fills in the intake form. Gets an accept, refer or decline with the instalment, the total to repay and the full schedule. If the requested term doesn't fit, they're offered one that does.
- **Employee**: sees every application with the system's calculation and the screened free-text answer, and records accept or decline decisions with a required comment.
- **Compliance**: looks up applications, searching by ID number. Sees what was asked, what was answered, what the system concluded and why, and what employees did, as one record with a timeline.

---

## Running it

Requirements: Python 3.10+ (developed on 3.14) and Node.js 22+ (developed on 24).

### Backend (FastAPI + SQLite)

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env          
uvicorn main:app --reload --env-file .env
```

- API and Swagger UI: http://localhost:8000/docs (`/` redirects there)
- The SQLite database (`backend/intake.db`) is created on first start. It's git-ignored, so everyone gets their own. After a schema change, delete it and restart.

Environment variables (`backend/.env`, git-ignored; see `.env.example`):

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY` | Key for the free-text screening call. Without it, every free-text answer fails screening: the text is deleted and the application is flagged for an employee. |
| `GROQ_MODEL` | Optional, defaults to `openai/gpt-oss-120b`. |
| `APPLICANT_ID_KEY` | Secret used to hash applicant ID numbers. Falls back to a dev-only key. Set it once and keep it, because changing it unlinks earlier applications. |

### Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The dev server forwards `/api/*` to the backend on port 8000, so there's nothing else to configure.

### Tests

```bash
cd backend
python3 -m unittest discover -s tests
```

### Trying the API without the UI

Use Swagger at `/docs`, where the submit endpoint has ready-made examples in a dropdown, or `backend/requests.http` (VS Code REST Client / JetBrains HTTP client).

---

## How it works

### 1. Intake

The form definition lives in one place (`backend/applicant/form.py`): the questions, labels, options and number ranges. `GET /applicant/form` serves it, and the React form is drawn from it, so the frontend can't drift from what the API accepts.

| Field | Rules |
|---|---|
| ID number | Digits only, sent as a string so leading zeros are kept. Stored only as a keyed hash (see below). |
| Treatment | `dental`, `eye`, `orthodontic` or `other`. With `other`, a short description is required and is stored as the treatment. |
| Cost | Whole euros, €500–€25,000 |
| Preferred term | Whole months, 6–60 |
| Net monthly income, housing costs, existing obligations | Whole euros, 0–1,000,000 (a ceiling against typos, not a business rule) |
| Household | Single, single with children, couple, couple with children |
| Partner's net income | Required for couples (0 allowed), ignored and stored as null otherwise |
| Anything else we should know | Optional, up to 2,000 characters (see "Free-text screening") |

All amounts must be real JSON integers. `3500.5`, `3500.0`, `"3500"` and `true` are rejected. Validation errors come back as `422` with one `{field, message}` per problem, written so the form can show each message next to its input.

**Repeat applicants.** The ID number is hashed with HMAC-SHA256 and a secret key, so the same person always gets the same `applicant_id` but the number itself is never stored. Each submission is a new application, numbered 1, 2, 3… per applicant. Earlier applications are never changed. The number is assigned inside the `INSERT` and backed by a unique constraint, so two simultaneous submissions can't get the same number.

### 2. Affordability assessment

`backend/assessment/rules.py`, pure functions using `Decimal`, with no web or database code mixed in:

```
share          = income / (income + partner_income)        (1 without a partner)
available room = income − housing × share − existing obligations − norm × share

instalment ≤ room           → accept
instalment ≤ room × 1.10    → refer (an employee reviews it)
otherwise                   → decline
```

Living standard norms: single €1,150, single with children €1,400, couple €1,600, couple with children €1,850.

For couples, housing costs and the norm are split by the applicant's share of household income (see decision 1). A partner with no income means the applicant carries everything. Zero household income doesn't divide by zero.

**The preferred term is a preference.** If the requested term isn't accepted, the result also contains the shortest longer term that would be, with its instalment. Shortest, because each extra month costs the applicant more interest. The applicant sees "we can't finance it over 12 months, but we could over 22 months at €247.16". One button takes them back to the form with every answer kept and only the term changed.

**Traceability.** Every assessment is stored with its outcome, a reason written out with the numbers, a `rule_version`, and a `calculation` JSON holding every input, constant and intermediate step (income share, housing share, norm share, room, instalment, refer limit), enough to redo the decision by hand. Money is stored as text decimals, never floats.

### 3. Repayment schedule

8.9% per year, fixed, standard annuity: `instalment = P × r / (1 − (1 + r)^−n)` with `r = 0.089 / 12`, rounded to the cent.

Each month, interest = balance × r rounded to the cent, repayment = instalment − interest, and the new balance = old balance − repayment. **The final instalment absorbs the rounding** by paying exactly what's left plus that month's interest. So:

- the closing balance after the last instalment is exactly €0.00;
- the instalments add up to exactly principal + interest charged, to the cent.

For example, €3,500 over 24 months is 23 × €159.74 plus a final €159.65, for €3,833.67 in total (€3,500 + €333.67 interest).

`tests/test_schedule.py` checks this for 111 amounts (boundaries, awkward amounts and a fixed random sample) across all 55 terms, about 6,000 schedules. It covers the closing balance, the sums, continuity between months, whole cents everywhere, and that only the final instalment differs (by less than a cent per month of term).

The schedule is stored with the assessment when it's made, so years later the record shows exactly what the applicant was offered, even if the rate changes.

### 4. Free-text screening (one model call)

`backend/assessment/free_text.py`. The prompt is at the top of the file.

```
Applicant submits free text
  → raw text stored temporarily (its own table, apart from the application)
  → one call to Groq (openai/gpt-oss-120b, temperature 0, JSON output)
  → model returns: summary, needs_review, reason (no medical detail)
  → summary and reason stored; raw text deleted, in the same transaction
  → employee works from the summary and reason
  → compliance record shows the summary, the reason and when the raw text was deleted
```

- **One call, no frameworks.** Python's standard library makes the HTTPS request. The answer is validated against a strict schema.
- **What gets flagged.** The memo's examples (temporary contract, partner on unpaid leave, expected drop in income) plus benefits ending, arrears or new debts, separation, irregular income, being unable to work (never the condition), and signs of pressure from someone else.
- **Medical detail.** The model is told never to put medical specifics in the summary or reason, and the raw text is deleted right after screening. If the server stops between storing and screening, any leftover raw text is deleted and flagged at the next startup.
- **The model can only escalate.** A flag on an application the rule accepted turns it into "refer", so a person looks before the applicant is told yes. The model never accepts or declines anything, and the rule's own result stays on record.
- **Failure is safe.** With no key, a network error or an unusable answer, the raw text is deleted anyway and the application is flagged with "ask the applicant about their situation". The reason for the failure is logged (never the text).
- **Prompt injection.** The applicant's text is marked as data. If it tries to give instructions, it gets flagged ("The text contains instructions aimed at the screening system").
- Every screening stores the model and a `PROMPT_VERSION`.

### 5. What the applicant sees

After submitting: "We've received your application", then after a short pause (3 seconds) the result.

- **Accept**: instalment (and final instalment if it differs), term, rate, total interest, total to repay, and the full schedule.
- **Refer**: a colleague will look at it. There are two versions: just over budget, or "the repayments fit, but something you told us is worth a closer look" when the free text was flagged. Shows the alternative term if there is one.
- **Decline with an alternative**: the longer term that would work, with a one-click retry.
- **Decline with no alternative**: a message written for someone who just learned they can't get their treatment paid for. It acknowledges that, explains why in plain words (no internal numbers), says it's not a judgement and doesn't stop them from reapplying, and lists concrete next steps: ask the clinic about instalments or doing it in stages, check the health insurer, reapply if things change, and get free money advice from the municipality or geldfit.nl. It also says the decision was automatic and that they can ask for a person to review it.

The applicant never sees the reference ID, the available room, the norms or the screening summary.

### 6. Employee dashboard

- Tabs: **To review** (referred), All, Accepted, Declined. Each row shows status, treatment, amount, term, the applicant hash prefix, the application number, and markers for "decided by employee" and "⚑ free text flagged".
- Expanding a row shows the answers, the calculation line by line, the schedule, the free-text summary and reason, and the decision history.
- **Add a decision**: accept or decline, a required comment and the employee's name. It works in either direction and on any status. Decisions are append-only (`decisions` table). Each stores who made it, the previous status, the new outcome, the comment and the time, and the application's status becomes the latest decision.

### 7. Compliance

- List of all applications, plus **search by ID number**. The number is hashed the same way and sent in the request body, not the URL, so it doesn't end up in server logs or browser history.
- **Full record** of one application, in the memo's order:
  1. **What we asked and what was answered.** Each question in its exact original wording, next to the stored answer. Questions that didn't apply are marked "not asked", the ID number "not stored", and the free text "raw text deleted at …".
  2. **What the system concluded, and on what basis.** Every assessment with its calculation and schedule, plus the free-text screening.
  3. **What employees did afterwards.** Every decision, from → to, who, why and when.
  4. **Timeline**: submitted → system outcome → free text screened → raw text deleted → each employee decision.
- **"What we asked" is exact.** Every form version is stored in a `forms` table word for word, keyed by a hash of its content. Each application points to the exact form it answered, so an old record can never show today's wording, even if someone edits a question and forgets to bump `FORM_VERSION`.
- **Retention**: `POST /compliance/retention/purge` deletes applications older than 7 years. Their assessments, decisions and screening go with them. It's a **dry run by default** and only deletes with `?dry_run=false`.

---

## API overview

| Method | Path | What it does |
|---|---|---|
| GET | `/applicant/form` | The form: questions, options, ranges, form id and version |
| POST | `/applicant/applications` | Submit, assess and screen; returns the application with its assessment |
| GET | `/applicant/applications/{id}` | One application with its latest assessment |
| GET | `/employee/applications?status=refer` | All applications (optionally by status) with assessment, screening and decisions |
| POST | `/employee/applications/{id}/decisions` | Record an accept or decline with a comment |
| GET | `/compliance/applications` | All applications, summarised |
| POST | `/compliance/applications/search` | Applications for one ID number |
| GET | `/compliance/applications/{id}/record` | The full compliance record with timeline |
| POST | `/compliance/retention/purge?dry_run=true` | List (or with `false`, delete) applications past retention |

## Project layout

```
backend/
  main.py                  app setup, error format, startup
  db.py                    SQLite schema and connection
  applicant/               form definition, ID hashing, intake endpoints
  assessment/              affordability rule + schedule, storing assessments, free-text screening
  employee/                dashboard list and decisions
  compliance/              record, search, retention
  tests/                   rule and schedule tests
  requests.http            example requests
frontend/src/
  pages/                   Home, Applicant, Employee, Compliance
  components/              form fields, result screens, review panels, schedule table
```

---

## Five decisions

**1. Couples: housing and the living norm are split by the applicant's share of household income.**
The memo's formula takes "net income" without saying whose. I assess the applicant's own share of the household: housing and the norm are both multiplied by `income / (income + partner_income)`. Applying the full couple norm against only the applicant's income would decline nearly every couple, and adding both incomes would make the applicant responsible for a partner's money they don't control. *Given up:* the plainest reading of the memo and a one-line formula. It also ignores the partner's own debts, which we don't ask about.

**2. The raw free text is deleted straight after screening, and the model can only escalate.**
The memo wants medical specifics gone once the assessment is done. The raw text is held in a separate table only for the model call, then deleted in the same transaction that stores the summary and reason. If screening fails, it's deleted anyway and the application is flagged. The model's only power is to turn an accept into a refer. It can't accept or decline anything. *Given up:* nobody, including compliance, can later read the applicant's exact words, and the quality of what's kept depends on the model's summary.

**3. Applicants are identified by a keyed hash of their ID number, and every submission is a new linked application.**
Linking repeat applications helps the employee and compliance, but an ID number is sensitive, so only an HMAC-SHA256 hash is stored. Plain SHA-256 of a short number can be reversed by trying every number. Earlier applications are never overwritten. *Given up:* the number can't be shown back, a typo creates a "new" applicant, and losing or changing the key unlinks the history. In production the key belongs in a secrets manager.

**4. Money is exact: whole-euro inputs, `Decimal` throughout, and the final instalment absorbs rounding.**
Inputs are strict integers. All calculations use `Decimal` rounded half-up to the cent, money is stored as text, and the schedule is stored as it was offered. Putting the rounding difference in the final instalment makes the schedule close at exactly €0.00 and add up to the cent. *Given up:* the final instalment differs from the others by a few cents. That needs to be stated in the agreement, and the finance team should confirm they round interest monthly the same way.

**5. SQLite with plain SQL, no ORM and no migrations.**
For a prototype this keeps every query visible and the setup at zero. The database is local and git-ignored, created on startup, and rebuilt after a schema change. *Given up:* migrations, concurrent writers and a realistic path to production. A real system would need Postgres, a migration tool and proper transactions around the external model call.

Other choices worth knowing:
- **The refer band** is read as 10% of the *room* (`instalment ≤ room × 1.10`), not 10% of the instalment.
- **Retention** counts 7 years from `created_at`, because loan closing isn't modelled.
- **The 3-second pause** before the result is deliberate UX. The assessment itself is instant.

## What I added that wasn't asked for

**An exact, permanent record of the questions asked.** Every version of the intake form (labels, options and limits) is stored, keyed by a hash of its content, and each application points to the form it answered. The compliance record shows each answer next to the question exactly as the applicant saw it. "What we asked" was the one part of the compliance requirement with nothing behind it, and versioning by content means it stays right even if someone rewords a question and forgets to bump the version.

Smaller additions: linking repeat applicants (decision 3), the one-click retry with the suggested term, the dry-run-by-default retention purge, and deleting leftover raw text at startup.

## What I'd raise before building this for real

- **Proving the record wasn't changed (not built).** The record is complete, but someone with database access could still edit it without a trace. How I'd do it:
  1. Write every event (submitted, assessed, screened, raw text deleted, decided, purged) to an append-only log, where each entry stores the SHA-256 of its content plus the previous entry's hash. Changing or removing any entry breaks every hash after it.
  2. Block `UPDATE` and `DELETE` on that table at the database level (triggers or permissions).
  3. Regularly publish the latest hash somewhere the company can't rewrite, such as an RFC 3161 timestamping service, WORM storage or a periodic statement to the auditor. That stops someone from quietly rebuilding the whole chain.
  4. Give compliance a "verify" action that recomputes the chain and compares it to the published hashes. That's what turns "we say it wasn't changed" into something a regulator can check.
  5. For retention, keep the personal data in a separate table that can be deleted, and keep only hashes in the chain. Old records can then be erased without breaking verification, and the purge itself becomes an entry.
- **The free text goes to Groq unredacted.** It may contain health data (special category under GDPR), sent to a US provider. Production needs a data processing agreement and a transfer assessment, or an EU-hosted model.
- **Compliance loses the applicant's exact words.** That's by design (decision 2). Compliance should confirm that a summary and reason are an acceptable record.
- **No authentication.** Employee names are typed in, so "what any employee did" is self-reported. The retention purge can be called by anyone. Both need real identities and roles.
- **Retention start date.** The memo says 7 years after the loan is *closed*. That needs a loan lifecycle, and the clock should start there.
- **Business confirmation needed on the rule**: the couple split (decision 1), the refer band (10% of room vs. of instalment), and whether a partner's debts should be asked.
- **Applicants aren't told about employee decisions.** An overturned outcome changes the status, but nothing notifies the applicant.
- **The decline text** promises a human review on request. There needs to be a real channel for that, and legal should review the wording.

## Status

Built: everything in the memo, including both optional parts (the UI, and handling more than one application), except the tamper-evident log, which is described above.

Next steps I'd take:
- When no term up to 60 months fits but there is some room, offer a smaller amount the applicant could borrow.
- Tests for the intake validation and the decision and compliance endpoints. Today's tests cover the rule and the schedule.
- The tamper-evident log described above.
