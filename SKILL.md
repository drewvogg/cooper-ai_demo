---
name: accordingly
description: Fill an ACORD 125-style commercial application draft from a structured AMS CSV export.
---

# Accordingly

Use this skill when a user uploads or points to an AMS-style CSV export for a commercial P&C account and asks for a filled insurance application draft.

## What This Skill Does

This MVP handles one deterministic path:

1. Read a structured AMS CSV export.
2. Select one account row or process every row.
3. Validate required and recommended fields for an ACORD 125-style commercial application draft.
4. Generate a filled PDF draft, a markdown review report, and a machine-readable JSON payload.
5. Optionally fill a real ACORD 125 AcroForm template if the user supplies one.

The generated application is a human-reviewable draft. It is not automatically submitted to a carrier or market.

## Inputs

Expected account CSV columns are shown in `sample_inputs/acme_mechanical/ams_export.csv`.
Each example folder can also include `target_markets.csv` to generate carrier-specific ACORD copies.

The important fields include:

- `account_id`
- `named_insured`
- `entity_type`
- `fein`
- `naics`
- mailing and physical address fields
- insured primary contact fields
- requested effective date and requested lines
- current/prior policy fields where available
- requested limits by line of business

## How To Run

From the repository root, run:

```bash
python3 scripts/fill_acord125.py \
  --input-dir sample_inputs/acme_mechanical \
  --out outputs/demo
```

To run the incomplete-data review scenario:

```bash
python3 scripts/fill_acord125.py \
  --input-dir sample_inputs/birchwood_hospitality \
  --out outputs/demo
```

If a fillable ACORD 125 template is available locally, pass it with `--template`:

```bash
python3 scripts/fill_acord125.py \
  --input-dir sample_inputs/acme_mechanical \
  --template ../Acord125_Template.pdf \
  --out outputs/demo
```

When filling an official template, review the printed verification summary to confirm the target fields landed in the AcroForm.

To override the folder convention, pass explicit paths:

```bash
python3 scripts/fill_acord125.py \
  --csv sample_inputs/acme_mechanical/ams_export.csv \
  --markets sample_inputs/acme_mechanical/target_markets.csv \
  --template ../Acord125_Template.pdf \
  --out outputs/demo
```

## Outputs

For each account/carrier combination, the script writes one folder named from the account and target market. The folder contains:

- `official_acord125.pdf`: filled official ACORD 125 template when `--template` is supplied
- `application_draft.pdf`: fallback ACORD 125-style draft application when no template is supplied
- `review_report.md`: missing-field report for CSR/producer review
- `form_payload.json`: normalized account data, validation state, and candidate AcroForm field values for a production PDF filler

## Operating Rules

- Do not infer missing account facts.
- Do not mark an application ready if any blocking field is missing.
- Treat the PDF as a draft for human review.
- Treat the JSON payload as the integration contract for downstream official-form rendering.
- If the CSV has unrecognized fields, preserve the existing workflow and only map fields explicitly supported by the script.

## Future Hybrid Extension

For unstructured artifacts such as declaration pages, current policy PDFs, or broker notes, Claude should extract facts into the same normalized field names used by the CSV before calling the Python script. The deterministic validation and rendering path should remain unchanged so output behavior stays testable and auditable.
