#!/usr/bin/env python3
"""Generate an ACORD 125-style draft application from an AMS CSV export."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


BLOCKING_FIELDS = {
    "account_id": "Account ID",
    "named_insured": "Named insured",
    "entity_type": "Business entity type",
    "fein": "FEIN",
    "naics": "NAICS",
    "mailing_street": "Mailing street",
    "mailing_city": "Mailing city",
    "mailing_state": "Mailing state",
    "mailing_zip": "Mailing ZIP",
    "physical_street": "Physical street",
    "physical_city": "Physical city",
    "physical_state": "Physical state",
    "physical_zip": "Physical ZIP",
    "primary_contact_name": "Insured primary contact",
    "primary_contact_email": "Insured primary contact email",
    "requested_effective_date": "Requested effective date",
    "requested_lines": "Requested coverage lines",
}

RECOMMENDED_FIELDS = {
    "annual_revenue": "Annual revenue",
    "employee_count": "Employee count",
    "years_in_business": "Years in business",
    "prior_carrier": "Prior carrier",
    "prior_policy_number": "Prior policy number",
    "prior_policy_expiration": "Prior policy expiration",
    "prior_premium": "Prior premium",
    "general_liability_limit": "General liability limit",
    "property_limit": "Property limit",
    "business_auto_limit": "Business auto limit",
    "workers_comp_estimated_payroll": "Workers comp estimated payroll",
    "umbrella_limit": "Umbrella limit",
}

LINE_FIELD_TRIGGERS = {
    "general_liability_limit": ("general liability",),
    "property_limit": ("property",),
    "business_auto_limit": ("business auto", "commercial auto"),
    "workers_comp_estimated_payroll": ("workers compensation", "workers comp"),
    "umbrella_limit": ("umbrella",),
}

DISPLAY_FIELDS = [
    ("named_insured", "Named Insured"),
    ("dba", "DBA"),
    ("entity_type", "Entity Type"),
    ("fein", "FEIN"),
    ("naics", "NAICS"),
    ("years_in_business", "Years in Business"),
    ("annual_revenue", "Annual Revenue"),
    ("employee_count", "Employee Count"),
    ("website", "Website"),
]

COVERAGE_FIELDS = [
    ("general_liability_limit", "General Liability"),
    ("property_limit", "Property"),
    ("business_auto_limit", "Business Auto"),
    ("workers_comp_estimated_payroll", "Workers Compensation"),
    ("umbrella_limit", "Umbrella"),
]

OPTIONAL_FIELDS = {
    "dba": "DBA",
    "website": "Website",
    "primary_contact_phone": "Insured primary contact phone",
    "agency_name": "Agency",
    "producer_name": "Producer",
    "csr_name": "CSR / account manager",
    "notes": "Submission notes",
}

ACROFORM_FIELD_TARGETS = {
    "account_id": ["F[0].P1[0].Producer_CustomerIdentifier_A[0]"],
    "named_insured": ["F[0].P1[0].NamedInsured_FullName_A[0]"],
    "fein": ["F[0].P1[0].NamedInsured_TaxIdentifier_A[0]"],
    "naics": ["F[0].P1[0].NamedInsured_NAICSCode_A[0]"],
    "mailing_street": ["F[0].P1[0].NamedInsured_MailingAddress_LineOne_A[0]"],
    "mailing_city": ["F[0].P1[0].NamedInsured_MailingAddress_CityName_A[0]"],
    "mailing_state": ["F[0].P1[0].NamedInsured_MailingAddress_StateOrProvinceCode_A[0]"],
    "mailing_zip": ["F[0].P1[0].NamedInsured_MailingAddress_PostalCode_A[0]"],
    "physical_street": ["F[0].P2[0].CommercialStructure_PhysicalAddress_LineOne_A[0]"],
    "physical_city": ["F[0].P2[0].CommercialStructure_PhysicalAddress_CityName_A[0]"],
    "physical_state": ["F[0].P2[0].CommercialStructure_PhysicalAddress_StateOrProvinceCode_A[0]"],
    "physical_zip": ["F[0].P2[0].CommercialStructure_PhysicalAddress_PostalCode_A[0]"],
    "primary_contact_name": ["F[0].P2[0].NamedInsured_Contact_FullName_A[0]"],
    "primary_contact_email": ["F[0].P2[0].NamedInsured_Contact_PrimaryEmailAddress_A[0]"],
    "primary_contact_phone": [
        "F[0].P1[0].NamedInsured_Primary_PhoneNumber_A[0]",
        "F[0].P2[0].NamedInsured_Contact_PrimaryPhoneNumber_A[0]",
    ],
    "agency_name": ["F[0].P1[0].Producer_FullName_A[0]"],
    "producer_name": ["F[0].P1[0].Producer_ContactPerson_FullName_A[0]"],
    "requested_effective_date": ["F[0].P1[0].Policy_EffectiveDate_A[0]"],
    "annual_revenue": ["F[0].P2[0].CommercialStructure_AnnualRevenueAmount_A[0]"],
    "employee_count": ["F[0].P2[0].BusinessInformation_FullTimeEmployeeCount_A[0]"],
    "prior_policy_number": [
        "F[0].P3[0].PriorCoverage_GeneralLiability_PolicyNumberIdentifier_A[0]"
    ],
    "prior_policy_expiration": ["F[0].P3[0].PriorCoverage_GeneralLiability_ExpirationDate_A[0]"],
    "prior_premium": ["F[0].P3[0].PriorCoverage_GeneralLiability_TotalPremiumAmount_A[0]"],
}


@dataclass(frozen=True)
class ReviewIssue:
    field: str
    label: str
    severity: str


def clean(value: str | None) -> str:
    return (value or "").strip()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug or "account"


def normalize_row(row: dict[str, str]) -> dict[str, str]:
    return {key.strip(): clean(value) for key, value in row.items()}


def read_accounts(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8-sig") as file:
        rows = [normalize_row(row) for row in csv.DictReader(file)]
    if not rows:
        raise ValueError(f"No account rows found in {csv_path}")
    return rows


def select_accounts(
    accounts: Iterable[dict[str, str]], account_id: str | None
) -> list[dict[str, str]]:
    selected = [
        account
        for account in accounts
        if account_id is None or account.get("account_id") == account_id
    ]
    if not selected:
        raise ValueError(f"No account found with account_id={account_id!r}")
    return selected


def validate_account(account: dict[str, str]) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    for field, label in BLOCKING_FIELDS.items():
        if not clean(account.get(field)):
            issues.append(ReviewIssue(field, label, "blocking"))
    for field, label in RECOMMENDED_FIELDS.items():
        if is_recommended_field_applicable(account, field) and not clean(account.get(field)):
            issues.append(ReviewIssue(field, label, "recommended"))
    return issues


def is_recommended_field_applicable(account: dict[str, str], field: str) -> bool:
    triggers = LINE_FIELD_TRIGGERS.get(field)
    if not triggers:
        return True
    requested_lines = clean(account.get("requested_lines")).lower()
    return any(trigger in requested_lines for trigger in triggers)


def format_address(account: dict[str, str], prefix: str) -> str:
    street = clean(account.get(f"{prefix}_street"))
    city = clean(account.get(f"{prefix}_city"))
    state = clean(account.get(f"{prefix}_state"))
    zip_code = clean(account.get(f"{prefix}_zip"))
    line_two = ", ".join(part for part in [city, state] if part)
    if zip_code:
        line_two = f"{line_two} {zip_code}".strip()
    return "\n".join(part for part in [street, line_two] if part)


def value(account: dict[str, str], field: str) -> str:
    return clean(account.get(field)) or "MISSING"


def paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(html.escape(text).replace("\n", "<br/>"), style)


def build_key_value_table(
    account: dict[str, str],
    rows: list[tuple[str, str]],
    body_style: ParagraphStyle,
) -> Table:
    table_data = [
        [paragraph(label, body_style), paragraph(value(account, field), body_style)]
        for field, label in rows
    ]
    table = Table(table_data, colWidths=[2.1 * inch, 4.8 * inch])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#b8c1cc")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#edf2f7")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def build_section_heading(text: str, styles) -> Paragraph:
    return Paragraph(text, styles["section"])


def generate_pdf(account: dict[str, str], issues: list[ReviewIssue], output_path: Path) -> None:
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="section",
            parent=styles["Heading2"],
            fontSize=11,
            leading=14,
            spaceBefore=10,
            spaceAfter=6,
            textColor=colors.HexColor("#1f2937"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="small",
            parent=styles["BodyText"],
            fontSize=8,
            leading=10,
        )
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.45 * inch,
        bottomMargin=0.45 * inch,
    )

    status = (
        "Ready for review"
        if not any(i.severity == "blocking" for i in issues)
        else "Needs CSR review"
    )
    title = f"ACORD 125-Style Commercial Application Draft: {value(account, 'named_insured')}"
    story = [
        paragraph(title, styles["Title"]),
        Paragraph(
            "Generated from an AMS CSV export. This is a human-reviewable draft, not an automatically submitted final application.",
            styles["small"],
        ),
        Spacer(1, 8),
        build_key_value_table(
            {
                "account_id": value(account, "account_id"),
                "status": status,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            },
            [
                ("account_id", "Account ID"),
                ("status", "Review Status"),
                ("generated_at", "Generated At"),
            ],
            styles["BodyText"],
        ),
        build_section_heading("Applicant Information", styles),
        build_key_value_table(account, DISPLAY_FIELDS, styles["BodyText"]),
        build_section_heading("Addresses", styles),
        build_key_value_table(
            {
                "mailing": format_address(account, "mailing") or "MISSING",
                "physical": format_address(account, "physical") or "MISSING",
            },
            [("mailing", "Mailing Address"), ("physical", "Primary Physical Location")],
            styles["BodyText"],
        ),
        build_section_heading("Insured Contact And Brokerage Team", styles),
        build_key_value_table(
            account,
            [
                ("primary_contact_name", "Insured Primary Contact"),
                ("primary_contact_email", "Insured Contact Email"),
                ("primary_contact_phone", "Insured Contact Phone"),
                ("agency_name", "Agency"),
                ("producer_name", "Producer"),
                ("csr_name", "CSR / Account Manager"),
            ],
            styles["BodyText"],
        ),
        build_section_heading("Requested Coverage", styles),
        build_key_value_table(
            account,
            [
                ("requested_effective_date", "Requested Effective Date"),
                ("requested_lines", "Requested Lines"),
                *COVERAGE_FIELDS,
            ],
            styles["BodyText"],
        ),
        build_section_heading("Prior Coverage", styles),
        build_key_value_table(
            account,
            [
                ("prior_carrier", "Prior Carrier"),
                ("prior_policy_number", "Prior Policy Number"),
                ("prior_policy_expiration", "Prior Expiration"),
                ("prior_premium", "Prior Premium"),
            ],
            styles["BodyText"],
        ),
        build_section_heading("Submission Notes", styles),
        paragraph(clean(account.get("notes")) or "No notes provided.", styles["BodyText"]),
        build_section_heading("Review Flags", styles),
    ]

    if issues:
        issue_rows = [
            [
                paragraph(issue.severity.title(), styles["BodyText"]),
                paragraph(issue.label, styles["BodyText"]),
                paragraph(issue.field, styles["small"]),
            ]
            for issue in issues
        ]
        issue_table = Table(
            [["Severity", "Missing Field", "Schema Key"], *issue_rows],
            colWidths=[1.2 * inch, 3.1 * inch, 2.6 * inch],
        )
        issue_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#b8c1cc")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(issue_table)
    else:
        story.append(Paragraph("No blocking or recommended field gaps found.", styles["BodyText"]))

    doc.build(story)


def write_review_report(account: dict[str, str], issues: list[ReviewIssue], output_path: Path) -> None:
    blocking = [issue for issue in issues if issue.severity == "blocking"]
    recommended = [issue for issue in issues if issue.severity == "recommended"]
    status = "Needs CSR review" if blocking else "Ready for review"

    lines = [
        f"# Review Report: {value(account, 'named_insured')}",
        "",
        f"- Account ID: `{value(account, 'account_id')}`",
        f"- Status: **{status}**",
        "- Source: AMS CSV export",
        "",
        "## Blocking Missing Fields",
    ]
    lines.extend(format_issue_lines(blocking))
    lines.extend(["", "## Recommended Missing Fields"])
    lines.extend(format_issue_lines(recommended))
    lines.extend(
        [
            "",
            "## Scope Note",
            "This deterministic MVP fills mapped fields from structured AMS data and flags gaps for human review. It does not auto-submit applications.",
            "",
        ]
    )
    output_path.write_text("\n".join(lines), encoding="utf-8")


def format_issue_lines(issues: list[ReviewIssue]) -> list[str]:
    if not issues:
        return ["- None"]
    return [f"- {issue.label} (`{issue.field}`)" for issue in issues]


def required_level(field: str) -> str:
    if field in BLOCKING_FIELDS:
        return "blocking"
    if field in RECOMMENDED_FIELDS:
        return "recommended"
    return "optional"


def field_label(field: str) -> str:
    labels = {**BLOCKING_FIELDS, **RECOMMENDED_FIELDS, **OPTIONAL_FIELDS}
    return labels.get(field, field.replace("_", " ").title())


def build_acroform_fields(account: dict[str, str]) -> dict[str, str | bool]:
    acroform_fields: dict[str, str | bool] = {}
    for schema_key, targets in ACROFORM_FIELD_TARGETS.items():
        field_value = clean(account.get(schema_key))
        if not field_value:
            continue
        for target in targets:
            acroform_fields[target] = field_value

    entity_type = clean(account.get("entity_type")).lower()
    if "llc" in entity_type or "limited liability" in entity_type:
        acroform_fields[
            "F[0].P1[0].NamedInsured_LegalEntity_LimitedLiabilityCorporationIndicator_A[0]"
        ] = True
    elif "corp" in entity_type:
        acroform_fields["F[0].P1[0].NamedInsured_LegalEntity_CorporationIndicator_A[0]"] = True

    requested_lines = clean(account.get("requested_lines")).lower()
    line_targets = {
        "general liability": "F[0].P1[0].Policy_LineOfBusiness_CommercialGeneralLiability_A[0]",
        "property": "F[0].P1[0].Policy_LineOfBusiness_CommercialProperty_A[0]",
        "business auto": "F[0].P1[0].Policy_LineOfBusiness_BusinessAutoIndicator_A[0]",
        "commercial auto": "F[0].P1[0].Policy_LineOfBusiness_BusinessAutoIndicator_A[0]",
        "umbrella": "F[0].P1[0].Policy_LineOfBusiness_UmbrellaIndicator_A[0]",
        "liquor": "F[0].P1[0].Policy_LineOfBusiness_LiquorLiabilityIndicator_A[0]",
    }
    for line_name, target in line_targets.items():
        if line_name in requested_lines:
            acroform_fields[target] = True
    if "workers compensation" in requested_lines or "workers comp" in requested_lines:
        acroform_fields["F[0].P1[0].Policy_LineOfBusiness_OtherIndicator_A[0]"] = True
        acroform_fields[
            "F[0].P1[0].Policy_LineOfBusiness_OtherLineOfBusinessDescription_A[0]"
        ] = "Workers Compensation"

    return acroform_fields


def build_field_payload(account: dict[str, str]) -> list[dict[str, object]]:
    fields = sorted({*BLOCKING_FIELDS, *RECOMMENDED_FIELDS, *OPTIONAL_FIELDS})
    payload = []
    for field in fields:
        raw_value = clean(account.get(field))
        applicable = (
            is_recommended_field_applicable(account, field)
            if field in RECOMMENDED_FIELDS
            else True
        )
        payload.append(
            {
                "schema_key": field,
                "label": field_label(field),
                "value": raw_value or None,
                "required_level": required_level(field),
                "applicable": applicable,
                "source": f"ams_csv:{field}" if raw_value else None,
                "acroform_targets": ACROFORM_FIELD_TARGETS.get(field, []),
            }
        )
    return payload


def write_json_payload(
    account: dict[str, str],
    issues: list[ReviewIssue],
    source_csv: Path,
    output_path: Path,
) -> None:
    blocking = [issue for issue in issues if issue.severity == "blocking"]
    recommended = [issue for issue in issues if issue.severity == "recommended"]
    status = "needs_review" if blocking else "ready_for_review"
    payload = {
        "form": {
            "id": "ACORD_125_STYLE_DRAFT",
            "description": "Machine-readable payload generated from structured AMS data.",
            "production_note": "The acroform_fields object can feed a PDF AcroForm filler when mapped to an official template's internal field names.",
        },
        "metadata": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source_type": "ams_csv",
            "source_file": str(source_csv),
            "account_id": value(account, "account_id"),
            "review_status": status,
        },
        "normalized_account": account,
        "validation": {
            "blocking_missing": [issue.field for issue in blocking],
            "recommended_missing": [issue.field for issue in recommended],
        },
        "field_payload": build_field_payload(account),
        "acroform_fields": build_acroform_fields(account),
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def fill_official_acord_template(
    template_path: Path,
    account: dict[str, str],
    output_path: Path,
) -> tuple[int, list[str]]:
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import BooleanObject, NameObject

    reader = PdfReader(str(template_path))
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)

    available_fields = set((reader.get_fields() or {}).keys())
    candidate_fields = build_acroform_fields(account)
    fillable_fields = {
        field_name: pdf_field_value(field_value)
        for field_name, field_value in candidate_fields.items()
        if field_name in available_fields
    }
    unmapped_fields = sorted(set(candidate_fields) - available_fields)

    for page in writer.pages:
        writer.update_page_form_field_values(page, fillable_fields, auto_regenerate=True)

    if "/AcroForm" in writer._root_object:
        writer._root_object["/AcroForm"].update(
            {NameObject("/NeedAppearances"): BooleanObject(True)}
        )

    with output_path.open("wb") as file:
        writer.write(file)

    return len(fillable_fields), unmapped_fields


def pdf_field_value(field_value: str | bool) -> str:
    if field_value is True:
        return "/1"
    if field_value is False:
        return "/Off"
    return field_value


def process_account(
    account: dict[str, str],
    source_csv: Path,
    output_dir: Path,
    template_path: Path | None,
) -> tuple[Path, Path, Path, Path | None]:
    issues = validate_account(account)
    account_slug = slugify(f"{value(account, 'account_id')}-{value(account, 'named_insured')}")
    pdf_path = output_dir / f"{account_slug}_application_draft.pdf"
    report_path = output_dir / f"{account_slug}_review_report.md"
    json_path = output_dir / f"{account_slug}_form_payload.json"
    official_pdf_path = (
        output_dir / f"{account_slug}_official_acord125.pdf" if template_path else None
    )
    generate_pdf(account, issues, pdf_path)
    write_review_report(account, issues, report_path)
    write_json_payload(account, issues, source_csv, json_path)
    if template_path and official_pdf_path:
        filled_count, unmapped_fields = fill_official_acord_template(
            template_path, account, official_pdf_path
        )
        print(
            f"Filled {filled_count} official ACORD fields for {value(account, 'account_id')}"
        )
        if unmapped_fields:
            print(
                f"Skipped {len(unmapped_fields)} candidate fields not present in template"
            )
    return pdf_path, report_path, json_path, official_pdf_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fill an ACORD 125-style commercial application draft from an AMS CSV export."
    )
    parser.add_argument("--csv", required=True, type=Path, help="Path to the AMS CSV export.")
    parser.add_argument(
        "--account-id",
        help="Optional account_id to process. If omitted, every row in the CSV is processed.",
    )
    parser.add_argument(
        "--template",
        type=Path,
        help="Optional path to a fillable ACORD 125 PDF template.",
    )
    parser.add_argument("--out", default=Path("outputs/demo"), type=Path, help="Output directory.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.template and not args.template.exists():
        raise FileNotFoundError(f"Template not found: {args.template}")

    args.out.mkdir(parents=True, exist_ok=True)
    accounts = select_accounts(read_accounts(args.csv), args.account_id)

    for account in accounts:
        pdf_path, report_path, json_path, official_pdf_path = process_account(
            account, args.csv, args.out, args.template
        )
        print(f"Wrote {pdf_path}")
        print(f"Wrote {report_path}")
        print(f"Wrote {json_path}")
        if official_pdf_path:
            print(f"Wrote {official_pdf_path}")


if __name__ == "__main__":
    main()
