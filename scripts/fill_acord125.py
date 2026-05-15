#!/usr/bin/env python3
"""Generate an ACORD 125-style draft application from an AMS CSV export."""

from __future__ import annotations

import argparse
import csv
import html
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
        if not clean(account.get(field)):
            issues.append(ReviewIssue(field, label, "recommended"))
    return issues


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
        Paragraph(title, styles["Title"]),
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
        Paragraph(clean(account.get("notes")) or "No notes provided.", styles["BodyText"]),
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


def process_account(account: dict[str, str], output_dir: Path) -> tuple[Path, Path]:
    issues = validate_account(account)
    account_slug = slugify(f"{value(account, 'account_id')}-{value(account, 'named_insured')}")
    pdf_path = output_dir / f"{account_slug}_application_draft.pdf"
    report_path = output_dir / f"{account_slug}_review_report.md"
    generate_pdf(account, issues, pdf_path)
    write_review_report(account, issues, report_path)
    return pdf_path, report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fill an ACORD 125-style commercial application draft from an AMS CSV export."
    )
    parser.add_argument("--csv", required=True, type=Path, help="Path to the AMS CSV export.")
    parser.add_argument(
        "--account-id",
        help="Optional account_id to process. If omitted, every row in the CSV is processed.",
    )
    parser.add_argument("--out", default=Path("outputs/demo"), type=Path, help="Output directory.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    accounts = select_accounts(read_accounts(args.csv), args.account_id)

    for account in accounts:
        pdf_path, report_path = process_account(account, args.out)
        print(f"Wrote {pdf_path}")
        print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
