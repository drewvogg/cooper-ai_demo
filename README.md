# Accordingly

Accordingly is a small deterministic Claude Skill MVP for a mid-market commercial P&C brokerage. It ingests an AMS-style CSV export for one or more accounts and produces:

- a filled ACORD 125-style commercial application draft PDF
- a markdown review report showing missing blocking and recommended fields
- a JSON payload that can feed a production official-form renderer

The goal is not to replace producer/CSR review. The goal is to remove the first pass of repetitive re-keying and make the review work explicit.

## Demo Command

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Generate one clean application:

```bash
python3 scripts/fill_acord125.py \
  --csv sample_inputs/applied_epic_ams_export.csv \
  --account-id ACME-001 \
  --out outputs/demo
```

Generate every sample account, including one with missing blocking data:

```bash
python3 scripts/fill_acord125.py \
  --csv sample_inputs/applied_epic_ams_export.csv \
  --out outputs/demo
```

## What I Chose To Build

I built the narrow deterministic version of the skill:

```text
AMS CSV export
  -> deterministic parser
  -> explicit validation rules
  -> ACORD 125-style field mapping
  -> filled PDF draft
  -> machine-readable form payload
  -> missing-field review report
```

For the MVP, I assumed the pilot users are retail commercial P&C producers and CSRs preparing submission drafts for carrier markets. I also assumed the brokerage can export structured account data from an AMS such as Applied Epic, AMS360, or a similar agency management system.

The output is intentionally a human-reviewable draft rather than an auto-submitted final application because insurance applications create E&O and compliance risk.

The JSON output is included as the production bridge. A real pilot would use the same normalized payload to fill an official ACORD 125 template through an AcroForm filler or coordinate overlay renderer.

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

This MVP only renders an ACORD 125-style draft, but the structure is intentionally split into source parsing, validation, and form rendering. More forms can be added by creating new field groups and renderers that consume the same normalized account data.

**Machine-readable payload as the integration contract**

Each run writes a `*_form_payload.json` file containing normalized account data, validation results, mapped field payloads, and candidate AcroForm field values. The PDF is the human-facing demo output; the JSON is the handoff point for filling an official form template in a production pilot.

**Draft output, not auto-submission**

The skill generates a draft PDF and a review report. It does not submit to a carrier, wholesale broker, or portal. Direct submission would require customer-specific approval workflow, audit logging, carrier integration support, and legal/compliance review.

## What I Cut

- Official ACORD PDF overlay or AcroForm filling. This is important for production but coordinate/field mapping work is time-consuming and not the highest-value proof point for the MVP.
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

I used AI to understand the assignment, research insurance workflow terminology, scope the MVP, generate realistic sample data, and accelerate implementation. I intentionally did not use AI for deterministic CSV parsing or final document rendering because those steps should be controlled, testable, and easy to audit.

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
