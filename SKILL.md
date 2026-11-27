---
name: ACORDingly
description: Fill an official ACORD 125 commercial application from structured AMS CSV exports.
---

# ACORDingly

Use this skill when a user uploads or points to an AMS-style CSV export for a commercial P&C account and asks for a filled insurance application draft. The repo includes sample inputs and the Python workflow. The official ACORD 125 PDF template is licensed, required for PDF generation, and must be supplied separately, usually at `templates/Acord125_Template.pdf`.

## What This Skill Does

This MVP handles one deterministic path:

1. Read a structured AMS CSV export.
2. Select one account row or process every row.
3. Validate required and recommended fields for an ACORD 125-style commercial application draft.
4. Fill a locally supplied ACORD 125 AcroForm template.
5. Generate a markdown review report and a machine-readable JSON payload.

The generated application is a human-reviewable draft. It is not automatically submitted to a carrier or market.

## Inputs

Expected account CSV columns are shown in `sample_inputs/acme_mechanical/ams_export.csv`.
Each example folder can also include `target_markets.csv` to generate carrier-specific ACORD copies.
The official PDF template is not committed. Before running the demo, place the licensed PDF at `templates/Acord125_Template.pdf` or use the uploaded file path in the `--template` argument.

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
python3 -m pip install -r requirements.txt
```

If the ACORD template was uploaded separately, either place it at `templates/Acord125_Template.pdf` or substitute the uploaded file path anywhere the commands below use `--template`.

To generate complete carrier-specific official ACORD outputs for Acme:

```bash
python3 scripts/fill_acord125.py \
  --input-dir sample_inputs/acme_mechanical \
  --template templates/Acord125_Template.pdf \
  --out outputs/demo
```

To run the incomplete-data review scenario for Birchwood:

```bash
python3 scripts/fill_acord125.py \
  --input-dir sample_inputs/birchwood_hospitality \
  --template templates/Acord125_Template.pdf \
  --out outputs/demo
```

Birchwood intentionally omits FEIN. The skill should still generate the PDF package, but the review report should mark the account as not ready because a blocking field is missing.

To generate a generic pre-market ACORD draft without carrier/program fields, pass the account CSV directly and omit `--markets`:

```bash
python3 scripts/fill_acord125.py \
  --csv sample_inputs/acme_mechanical/ams_export.csv \
  --template templates/Acord125_Template.pdf \
  --out outputs/generic
```

When filling an official template, review the printed verification summary to confirm the target fields landed in the AcroForm.

To override the folder convention, pass explicit paths:

```bash
python3 scripts/fill_acord125.py \
  --csv sample_inputs/acme_mechanical/ams_export.csv \
  --markets sample_inputs/acme_mechanical/target_markets.csv \
  --template templates/Acord125_Template.pdf \
  --out outputs/demo
```

## Outputs

For each account/carrier combination, the script writes one folder named from the account and target market. The folder contains:

- `official_acord125.pdf`: filled official ACORD 125 template
- `review_report.md`: missing-field report for CSR/producer review
- `form_payload.json`: normalized account data, validation state, and candidate AcroForm field values for a production PDF filler

For the standard demo, inspect:

- `outputs/demo/acme-001-acme-mechanical-llc-trv-glprop/`
- `outputs/demo/acme-001-acme-mechanical-llc-hart-cpkg/`
- `outputs/demo/acme-001-acme-mechanical-llc-lib-umbrella/`
- `outputs/demo/brch-002-birchwood-hospitality-group-inc-hart-hotel/`
- `outputs/demo/brch-002-birchwood-hospitality-group-inc-amwins-hosp/`

## Operating Rules

- Do not infer missing account facts.
- Do not mark an application ready if any blocking field is missing.
- Treat the PDF as a draft for human review.
- Treat the JSON payload as the integration contract for downstream official-form rendering.
- If the CSV has unrecognized fields, preserve the existing workflow and only map fields explicitly supported by the script.

## Future Hybrid Extension

For unstructured artifacts such as declaration pages, current policy PDFs, or broker notes, Claude should extract facts into the same normalized field names used by the CSV before calling the Python script. The deterministic validation and rendering path should remain unchanged so output behavior stays testable and auditable.
