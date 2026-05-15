# ACORDingly - Cooper AI Sales Engineer Demo

ACORDingly is a small deterministic Claude Skill MVP for a mid-market commercial P&C brokerage. It ingests an AMS-style CSV export for one or more accounts and produces one output package per account/carrier combination:

- a filled official ACORD 125 PDF when a template is supplied, otherwise an ACORD 125-style draft PDF
- a markdown review report showing missing blocking and recommended fields
- a JSON payload that can feed a production official-form renderer

The goal is not to replace producer/CSR review. The goal is to remove the first pass of repetitive re-keying and make the review work explicit.

## Suggested Demo Flow

1. Run the Acme Mechanical example to show a complete draft package.
2. Open the generated carrier-specific folder and show the filled PDF, review report, and JSON payload.
3. Run the Birchwood Hospitality example to show how the skill handles missing blocking data.
4. Open Birchwood's review report and point out that the form is generated, but the package is not marked ready because FEIN is missing.
5. If an official ACORD template is available locally, rerun Acme with `--template` to show the same normalized payload filling a real AcroForm PDF.

## Demo Command

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Generate the Acme Mechanical example:

```bash
python3 scripts/fill_acord125.py \
  --input-dir sample_inputs/acme_mechanical \
  --out outputs/demo
```

Generate the Birchwood Hospitality example, which intentionally has a missing blocking field:

```bash
python3 scripts/fill_acord125.py \
  --input-dir sample_inputs/birchwood_hospitality \
  --out outputs/demo
```

The Birchwood sample intentionally omits FEIN to demonstrate how the skill flags blocking missing fields while still generating a draft package for review.

If you have a fillable ACORD 125 PDF template locally, generate official filled drafts as well:

```bash
python3 scripts/fill_acord125.py \
  --input-dir sample_inputs/acme_mechanical \
  --template ../Acord125_Template.pdf \
  --out outputs/demo
```

When `--template` is supplied, the CLI prints a short verification summary for the highest-value official ACORD fields, including completion date, website, prior carrier, repeated customer IDs, transaction status, policy dates, business type, operations, attachment indicators, umbrella, and premium fields.

Each example folder contains:

- `ams_export.csv`: one account's structured AMS export
- `target_markets.csv`: optional carrier/program targets used to generate one ACORD copy per market

You can also pass files directly:

```bash
python3 scripts/fill_acord125.py \
  --csv sample_inputs/acme_mechanical/ams_export.csv \
  --markets sample_inputs/acme_mechanical/target_markets.csv \
  --template ../Acord125_Template.pdf \
  --out outputs/demo
```

## What I Chose To Build

I built the narrow deterministic version of the skill:

I intentionally optimized for one complete, inspectable workflow rather than broad form coverage. The MVP proves the highest-risk path: structured account data can be transformed into a reviewable submission package and, when an official AcroForm template is available, into a real filled ACORD PDF.

```text
AMS CSV export
  -> optional target market CSV
  -> deterministic parser
  -> explicit validation rules
  -> ACORD 125-style field mapping
  -> filled PDF draft
  -> machine-readable form payload
  -> optional official ACORD 125 AcroForm fill
  -> missing-field review report
```

For the MVP, I assumed the pilot users are retail commercial P&C producers and CSRs preparing submission drafts for carrier markets. I also assumed the brokerage can export structured account data from an AMS such as Applied Epic, AMS360, or a similar agency management system.

The output is intentionally a human-reviewable draft rather than an auto-submitted final application because insurance applications create E&O and compliance risk.

The JSON output is included as the production bridge. If a fillable ACORD 125 template is provided, the script also fills the mapped subset of official AcroForm fields directly. If target markets are provided, it generates one carrier-specific copy per market.

An AcroForm is the fillable-field layer inside a PDF: text boxes, checkboxes, dates, and other controls with internal field names. If an official ACORD template exposes those fields, code can set values by field name instead of asking an LLM to rewrite the document layout.

## Discovery Questions And Assumptions

**Which submission workflow should we prioritize for the pilot: high-volume common ACORD forms, lower-volume supplemental forms that take longer because the data is scattered, or a specific line of business where re-keying creates the most operational pain?**

Assumption: I prioritized a high-volume commercial P&C submission using an ACORD 125-style application because it captures reusable account-level data that can later feed line-specific ACORD forms and carrier supplementals.

**For that workflow, where does the data live today?**

Assumption: The AMS is the system of record for core account and policy metadata, but supporting evidence may still live in emails, declaration pages, current policies, loss runs, and attachments. For this MVP, I used a structured AMS CSV export as the source of truth and cut document extraction.

**Who prepares the application today, and who reviews or approves the draft before it is sent to a carrier or market?**

Assumption: A CSR or account manager prepares the first draft by re-keying account data. A producer or account executive reviews the draft before it is sent to carriers.

**What level of completeness is acceptable before a CSR sends the draft for review?**

Assumption: The workflow should distinguish blocking missing fields from recommended missing fields. A draft can still be generated with missing data, but the review report should prevent the team from treating an incomplete application as submission-ready.

**What output should the pilot user receive?**

Assumption: The pilot user needs a filled draft plus a review report, not a black-box answer. The report gives the CSR a short checklist of what must be confirmed before the application can move forward.

## Key Architecture Decisions

**Deterministic field handling for structured data**

Structured AMS exports are parsed with code, not an LLM. The CSV headers map directly to supported schema keys. This keeps the easiest part of the workflow auditable and avoids using AI where basic code is more reliable.

**Explicit validation rules**

The script separates blocking fields from recommended fields. That makes the review state explainable and allows future customer-specific rules without changing the renderer.

**Form-specific mapper behind a normalized schema**

This MVP renders an ACORD 125-style draft by default and can optionally fill a real ACORD 125 AcroForm template. The structure is intentionally split into source parsing, validation, and form rendering. More forms can be added by creating new field groups and renderers that consume the same normalized account data.

**Machine-readable payload as the integration contract**

Each account/carrier run writes a folder containing `form_payload.json`, `review_report.md`, and either `official_acord125.pdf` when an AcroForm template is supplied or `application_draft.pdf` when running without a template. The PDF is the human-facing demo output; the JSON is the handoff point for filling an official form template in a production pilot.

**Official template fill as an optional renderer**

The script can also fill a real ACORD 125 AcroForm template when supplied with `--template`. I kept the template out of the repo and made this opt-in so the deterministic skill still runs anywhere, while the onsite demo can show the same payload landing in an actual ACORD artifact. When `target_markets.csv` is present, the skill creates carrier-specific official drafts with carrier, NAIC, program, underwriter, and quote-status fields populated.

**Draft output, not auto-submission**

The skill generates a PDF package and a review report. It does not submit to a carrier, wholesale broker, or portal. Direct submission would require customer-specific approval workflow, audit logging, carrier integration support, and legal/compliance review.

## What I Cut

- Full official ACORD 125 field coverage. The template contains hundreds of fields; this MVP fills the high-value account/submission fields available from the sample AMS export.
- Unstructured document extraction from declaration pages, current policies, and emails.
- Carrier-specific supplemental applications.
- Portal/API submission.
- Authentication, persistence, and customer-specific AMS integrations.

## How This Scales

**More forms**

Add form-specific mappers/renderers for ACORD 126, ACORD 130, carrier supplementals, and schedules. The parser and validation layer can stay shared while each form owns its own required fields, JSON payload mapping, and output layout.

**More lines**

Extend the normalized schema with line-specific groups such as general liability exposures, workers compensation class codes/payroll, vehicle schedules, property locations, and liquor liability operations.

**More carriers**

Add carrier-specific validation profiles and supplemental form mappings. A Hartford contractors supplemental, for example, may reuse common applicant data but require contractor operations, subcontractor usage, and safety-program fields.

**More input types**

Add adapters in front of the same normalized schema:

- deterministic adapters for AMS exports and structured spreadsheets
- AI extraction adapters for declaration pages, current policy PDFs, broker notes, and emails
- source citations and confidence flags for any value extracted from unstructured documents

## Where I Used AI

I used AI heavily to scope the workflow, generate realistic sample data, inspect ACORD field behavior, and accelerate implementation. I intentionally did not use runtime AI for CSV parsing or final form rendering because those steps should be deterministic, testable, and auditable. In a production Cooper workflow, the next AI layer would extract structured facts from declaration pages, policies, emails, and broker notes into the same normalized schema used here.

## What I Would Build Next

The next version would be the hybrid skill:

```text
AMS CSV
  -> deterministic parser

declaration pages / policy PDFs / broker notes
  -> Claude extraction into the same schema with source citations

normalized account data
  -> deterministic validation and form generation
```

That would let the skill handle real-world brokerage artifacts while preserving a deterministic final output path.
