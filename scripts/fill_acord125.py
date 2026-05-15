#!/usr/bin/env python3
"""Fill an official ACORD 125 AcroForm template from an AMS CSV export."""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


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
    "prior_carrier": "Prior carrier",
    "prior_policy_number": "Prior policy number",
    "prior_policy_expiration": "Prior policy expiration",
    "prior_premium": "Prior premium",
    "general_liability_limit": "General liability limit",
    "property_limit": "Property limit",
    "business_auto_limit": "Business auto limit",
    "workers_comp_estimated_payroll": "Workers comp estimated payroll",
    "workers_comp_premium": "Workers compensation premium",
    "umbrella_limit": "Umbrella limit",
}

LINE_FIELD_TRIGGERS = {
    "general_liability_limit": ("general liability",),
    "property_limit": ("property",),
    "business_auto_limit": ("business auto", "commercial auto"),
    "workers_comp_estimated_payroll": ("workers compensation", "workers comp"),
    "workers_comp_premium": ("workers compensation", "workers comp"),
    "umbrella_limit": ("umbrella",),
}

OPTIONAL_FIELDS = {
    "llc_member_manager_count": "LLC member / manager count",
    "website": "Website",
    "transaction_type": "Transaction type",
    "requested_expiration_date": "Requested expiration date",
    "business_type": "Business type",
    "operations_description": "Operations description",
    "primary_contact_phone": "Insured primary contact phone",
    "primary_contact_phone_type": "Insured primary contact phone type",
    "agency_name": "Agency",
    "agency_street": "Agency street",
    "agency_city": "Agency city",
    "agency_state": "Agency state",
    "agency_zip": "Agency ZIP",
    "producer_name": "Producer",
    "producer_phone": "Producer phone",
    "producer_email": "Producer email",
    "producer_fax": "Producer fax",
    "csr_name": "CSR / account manager",
    "carrier_name": "Carrier",
    "carrier_naic_code": "Carrier NAIC code",
    "program_name": "Program name",
    "program_code": "Program code",
    "underwriter_name": "Underwriter",
    "underwriter_office": "Underwriter office",
    "target_market_id": "Target market ID",
    "market_notes": "Target market notes",
    "general_liability_premium": "General liability premium",
    "property_premium": "Property premium",
    "business_auto_premium": "Business auto premium",
    "umbrella_premium": "Umbrella premium",
    "notes": "Submission notes",
}

ACROFORM_FIELD_TARGETS = {
    "account_id": [
        "F[0].P1[0].Producer_CustomerIdentifier_A[0]",
        "F[0].P2[0].Producer_CustomerIdentifier_A[0]",
        "F[0].P3[0].Producer_CustomerIdentifier_A[0]",
        "F[0].P4[0].Producer_CustomerIdentifier_A[0]",
    ],
    "target_market_id": ["F[0].P1[0].Insurer_ProducerIdentifier_A[0]"],
    "named_insured": ["F[0].P1[0].NamedInsured_FullName_A[0]"],
    "llc_member_manager_count": [
        "F[0].P1[0].NamedInsured_LegalEntity_MemberManagerCount_A[0]"
    ],
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
    "agency_street": ["F[0].P1[0].Producer_MailingAddress_LineOne_A[0]"],
    "agency_city": ["F[0].P1[0].Producer_MailingAddress_CityName_A[0]"],
    "agency_state": ["F[0].P1[0].Producer_MailingAddress_StateOrProvinceCode_A[0]"],
    "agency_zip": ["F[0].P1[0].Producer_MailingAddress_PostalCode_A[0]"],
    "producer_name": ["F[0].P1[0].Producer_ContactPerson_FullName_A[0]"],
    "producer_phone": ["F[0].P1[0].Producer_ContactPerson_PhoneNumber_A[0]"],
    "producer_email": ["F[0].P1[0].Producer_ContactPerson_EmailAddress_A[0]"],
    "producer_fax": ["F[0].P1[0].Producer_FaxNumber_A[0]"],
    "carrier_name": ["F[0].P1[0].Insurer_FullName_A[0]"],
    "carrier_naic_code": ["F[0].P1[0].Insurer_NAICCode_A[0]"],
    "program_name": ["F[0].P1[0].Insurer_ProductDescription_A[0]"],
    "program_code": ["F[0].P1[0].Insurer_ProductCode_A[0]"],
    "underwriter_name": ["F[0].P1[0].Insurer_Underwriter_FullName_A[0]"],
    "underwriter_office": ["F[0].P1[0].Insurer_Underwriter_OfficeIdentifier_A[0]"],
    "website": ["F[0].P1[0].NamedInsured_Primary_WebsiteAddress_A[0]"],
    "requested_effective_date": [
        "F[0].P1[0].Policy_EffectiveDate_A[0]",
        "F[0].P1[0].Policy_Status_EffectiveDate_A[0]",
    ],
    "requested_expiration_date": ["F[0].P1[0].Policy_ExpirationDate_A[0]"],
    "annual_revenue": ["F[0].P2[0].CommercialStructure_AnnualRevenueAmount_A[0]"],
    "employee_count": ["F[0].P2[0].BusinessInformation_FullTimeEmployeeCount_A[0]"],
    "operations_description": ["F[0].P2[0].CommercialPolicy_OperationsDescription_A[0]"],
    "general_liability_premium": [
        "F[0].P1[0].GeneralLiabilityLineOfBusiness_TotalPremiumAmount_A[0]"
    ],
    "property_premium": ["F[0].P1[0].CommercialPropertyLineOfBusiness_PremiumAmount_A[0]"],
    "business_auto_premium": [
        "F[0].P1[0].CommercialVehicleLineOfBusiness_PremiumAmount_A[0]"
    ],
    "workers_comp_premium": [
        "F[0].P1[0].Policy_SectionAttached_OtherPremiumAmount_A[0]"
    ],
    "umbrella_premium": [
        "F[0].P1[0].CommercialUmbrellaLineOfBusiness_PremiumAmount_A[0]"
    ],
    "prior_carrier": ["F[0].P3[0].PriorCoverage_GeneralLiability_InsurerFullName_A[0]"],
    "prior_policy_number": [
        "F[0].P3[0].PriorCoverage_GeneralLiability_PolicyNumberIdentifier_A[0]"
    ],
    "prior_policy_expiration": ["F[0].P3[0].PriorCoverage_GeneralLiability_ExpirationDate_A[0]"],
    "prior_premium": ["F[0].P3[0].PriorCoverage_GeneralLiability_TotalPremiumAmount_A[0]"],
}

STATUS_FIELD_TARGETS = {
    "quote": "F[0].P1[0].Policy_Status_QuoteIndicator_A[0]",
    "renew": "F[0].P1[0].Policy_Status_RenewIndicator_A[0]",
    "renewal": "F[0].P1[0].Policy_Status_RenewIndicator_A[0]",
    "issue": "F[0].P1[0].Policy_Status_IssueIndicator_A[0]",
    "bound": "F[0].P1[0].Policy_Status_BoundIndicator_A[0]",
    "change": "F[0].P1[0].Policy_Status_ChangeIndicator_A[0]",
    "cancel": "F[0].P1[0].Policy_Status_CancelIndicator_A[0]",
}

BUSINESS_TYPE_TARGETS = {
    "contractor": "F[0].P2[0].BusinessInformation_BusinessType_ContractorIndicator_A[0]",
    "restaurant": "F[0].P2[0].BusinessInformation_BusinessType_RestaurantIndicator_A[0]",
    "retail": "F[0].P2[0].BusinessInformation_BusinessType_RetailIndicator_A[0]",
    "service": "F[0].P2[0].BusinessInformation_BusinessType_ServiceIndicator_A[0]",
    "manufacturing": "F[0].P2[0].BusinessInformation_BusinessType_ManufacturingIndicator_A[0]",
}

CONTACT_PHONE_TYPE_TARGETS = {
    "business": "F[0].P2[0].NamedInsured_Contact_PrimaryBusinessPhoneIndicator_A[0]",
    "bus": "F[0].P2[0].NamedInsured_Contact_PrimaryBusinessPhoneIndicator_A[0]",
    "cell": "F[0].P2[0].NamedInsured_Contact_PrimaryCellPhoneIndicator_A[0]",
    "mobile": "F[0].P2[0].NamedInsured_Contact_PrimaryCellPhoneIndicator_A[0]",
    "home": "F[0].P2[0].NamedInsured_Contact_PrimaryHomePhoneIndicator_A[0]",
}


@dataclass(frozen=True)
class ReviewIssue:
    """A missing or incomplete field that should be shown to the reviewer."""

    field: str
    label: str
    severity: str


def clean(value: str | None) -> str:
    """Normalize nullable CSV values before validation or rendering."""
    return (value or "").strip()


def slugify(value: str) -> str:
    """Create stable folder names for generated account/carrier packages."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug or "account"


def normalize_row(row: dict[str, str]) -> dict[str, str]:
    """Strip CSV header and value whitespace for one input row."""
    return {key.strip(): clean(value) for key, value in row.items()}


def read_accounts(csv_path: Path) -> list[dict[str, str]]:
    """Load account rows from the AMS export CSV."""
    with csv_path.open(newline="", encoding="utf-8-sig") as file:
        rows = [normalize_row(row) for row in csv.DictReader(file)]
    if not rows:
        raise ValueError(f"No account rows found in {csv_path}")
    return rows


def read_markets(markets_path: Path | None) -> list[dict[str, str]]:
    """Load optional carrier/program target rows."""
    if not markets_path:
        return []
    with markets_path.open(newline="", encoding="utf-8-sig") as file:
        rows = [normalize_row(row) for row in csv.DictReader(file)]
    if not rows:
        raise ValueError(f"No target market rows found in {markets_path}")
    return rows


def select_accounts(
    accounts: Iterable[dict[str, str]], account_id: str | None
) -> list[dict[str, str]]:
    """Apply the optional account-id filter from the CLI."""
    selected = [
        account
        for account in accounts
        if account_id is None or account.get("account_id") == account_id
    ]
    if not selected:
        raise ValueError(f"No account found with account_id={account_id!r}")
    return selected


def account_market_variants(
    account: dict[str, str], markets: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Merge one account with each target market for carrier-specific outputs."""
    if not markets:
        return [account]
    variants = []
    for market in markets:
        variant = account.copy()
        variant.update({key: value for key, value in market.items() if value})
        variants.append(variant)
    return variants


def validate_account(account: dict[str, str]) -> list[ReviewIssue]:
    """Return blocking and recommended gaps for the reviewer."""
    issues: list[ReviewIssue] = []
    for field, label in BLOCKING_FIELDS.items():
        if not clean(account.get(field)):
            issues.append(ReviewIssue(field, label, "blocking"))
    for field, label in RECOMMENDED_FIELDS.items():
        if is_recommended_field_applicable(account, field) and not clean(account.get(field)):
            issues.append(ReviewIssue(field, label, "recommended"))
    return issues


def is_recommended_field_applicable(account: dict[str, str], field: str) -> bool:
    """Skip line-specific recommendations when that line was not requested."""
    triggers = LINE_FIELD_TRIGGERS.get(field)
    if not triggers:
        return True
    requested_lines = clean(account.get("requested_lines")).lower()
    return any(trigger in requested_lines for trigger in triggers)


def format_pdf_date(value: str) -> str:
    """Convert supported input date formats to ACORD's MM/DD/YYYY style."""
    for date_format in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, date_format).strftime("%m/%d/%Y")
        except ValueError:
            continue
    return value


def truncate(value: str, max_length: int) -> str:
    """Trim long values before placing them into small AcroForm fields."""
    return value if len(value) <= max_length else value[: max_length - 3].rstrip() + "..."


def value(account: dict[str, str], field: str) -> str:
    """Read a display value and mark missing data visibly."""
    return clean(account.get(field)) or "MISSING"


def write_review_report(account: dict[str, str], issues: list[ReviewIssue], output_path: Path) -> None:
    """Write the CSR-facing checklist for one account/carrier package."""
    blocking = [issue for issue in issues if issue.severity == "blocking"]
    recommended = [issue for issue in issues if issue.severity == "recommended"]
    status = "Needs CSR review" if blocking else "Ready for review"

    lines = [
        f"# Review Report: {value(account, 'named_insured')}",
        "",
        f"- Account ID: `{value(account, 'account_id')}`",
        f"- Status: **{status}**",
        "- Source: AMS CSV export",
    ]
    if clean(account.get("target_market_id")):
        lines.append(f"- Target Market: `{clean(account.get('target_market_id'))}`")
    if clean(account.get("carrier_name")):
        lines.append(f"- Carrier: {clean(account.get('carrier_name'))}")
    if clean(account.get("program_name")):
        lines.append(f"- Program: {clean(account.get('program_name'))}")
    if clean(account.get("market_notes")):
        lines.append(f"- Market Notes: {clean(account.get('market_notes'))}")
    lines.extend(["", "## Blocking Missing Fields"])
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
    """Format missing-field lists for the markdown report."""
    if not issues:
        return ["- None"]
    return [f"- {issue.label} (`{issue.field}`)" for issue in issues]


def required_level(field: str) -> str:
    """Expose each normalized field's validation level in the JSON payload."""
    if field in BLOCKING_FIELDS:
        return "blocking"
    if field in RECOMMENDED_FIELDS:
        return "recommended"
    return "optional"


def field_label(field: str) -> str:
    """Return a human-readable label for a normalized schema key."""
    labels = {**BLOCKING_FIELDS, **RECOMMENDED_FIELDS, **OPTIONAL_FIELDS}
    return labels.get(field, field.replace("_", " ").title())


def build_acroform_fields(
    account: dict[str, str], generated_at: datetime
) -> dict[str, str | bool]:
    """Map normalized account fields onto official ACORD AcroForm names."""
    acroform_fields: dict[str, str | bool] = {}
    acroform_fields["F[0].P1[0].Form_CompletionDate_A[0]"] = generated_at.strftime(
        "%m/%d/%Y"
    )
    transaction_type = clean(account.get("transaction_type")).lower() or "quote"
    status_target = STATUS_FIELD_TARGETS.get(transaction_type)
    if status_target:
        acroform_fields[status_target] = True

    for schema_key, targets in ACROFORM_FIELD_TARGETS.items():
        field_value = clean(account.get(schema_key))
        if not field_value:
            continue
        if schema_key in {
            "requested_effective_date",
            "requested_expiration_date",
            "prior_policy_expiration",
        }:
            field_value = format_pdf_date(field_value)
        elif schema_key == "operations_description":
            field_value = truncate(field_value, 180)
        for target in targets:
            acroform_fields[target] = field_value

    entity_type = clean(account.get("entity_type")).lower()
    if "llc" in entity_type or "limited liability" in entity_type:
        acroform_fields[
            "F[0].P1[0].NamedInsured_LegalEntity_LimitedLiabilityCorporationIndicator_A[0]"
        ] = True
    elif "corp" in entity_type:
        acroform_fields["F[0].P1[0].NamedInsured_LegalEntity_CorporationIndicator_A[0]"] = True

    business_type = clean(account.get("business_type")).lower()
    if business_type:
        business_type_target = BUSINESS_TYPE_TARGETS.get(business_type)
        if business_type_target:
            acroform_fields[business_type_target] = True
        else:
            acroform_fields[
                "F[0].P2[0].BusinessInformation_BusinessType_OtherIndicator_A[0]"
            ] = True
            acroform_fields[
                "F[0].P2[0].BusinessInformation_BusinessType_OtherDescription_A[0]"
            ] = truncate(clean(account.get("business_type")), 40)

    contact_phone_type = clean(account.get("primary_contact_phone_type")).lower()
    contact_phone_type_target = CONTACT_PHONE_TYPE_TARGETS.get(contact_phone_type)
    if contact_phone_type_target:
        acroform_fields[contact_phone_type_target] = True

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
    if "property" in requested_lines:
        acroform_fields[
            "F[0].P1[0].CommercialPolicy_Attachment_StatementOfValuesIndicator_A[0]"
        ] = True
    if "business auto" in requested_lines or "commercial auto" in requested_lines:
        acroform_fields[
            "F[0].P1[0].Policy_SectionAttached_VehicleScheduleIndicator_A[0]"
        ] = True
    if business_type == "contractor":
        acroform_fields[
            "F[0].P1[0].CommercialPolicy_Attachment_ContractorsSupplementIndicator_A[0]"
        ] = True
    if business_type in {"hotel", "motel", "hotel/motel"}:
        acroform_fields[
            "F[0].P1[0].CommercialPolicy_Attachment_HotelMotelSupplementIndicator_A[0]"
        ] = True

    return acroform_fields


def build_field_payload(account: dict[str, str]) -> list[dict[str, object]]:
    """Build the normalized field list used by downstream integrations."""
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
    generated_at: datetime,
) -> None:
    """Write the machine-readable payload for form filling and audit review."""
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
            "generated_at": generated_at.isoformat(timespec="seconds"),
            "source_type": "ams_csv",
            "source_file": source_csv.name,
            "account_id": value(account, "account_id"),
            "review_status": status,
            "target_market_id": clean(account.get("target_market_id")) or None,
            "carrier_name": clean(account.get("carrier_name")) or None,
            "program_name": clean(account.get("program_name")) or None,
        },
        "normalized_account": account,
        "validation": {
            "blocking_missing": [issue.field for issue in blocking],
            "recommended_missing": [issue.field for issue in recommended],
        },
        "field_payload": build_field_payload(account),
        "acroform_fields": build_acroform_fields(account, generated_at),
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def fill_official_acord_template(
    template_path: Path,
    account: dict[str, str],
    output_path: Path,
    generated_at: datetime,
) -> tuple[int, list[str]]:
    """Fill the official ACORD template and report skipped candidate fields."""
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import BooleanObject, NameObject

    reader = PdfReader(str(template_path))
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)

    available_fields = set((reader.get_fields() or {}).keys())
    candidate_fields = build_acroform_fields(account, generated_at)
    fillable_fields = {
        field_name: pdf_field_value(field_value)
        for field_name, field_value in candidate_fields.items()
        if field_name in available_fields
    }
    unmapped_fields = sorted(set(candidate_fields) - available_fields)

    for page in writer.pages:
        writer.update_page_form_field_values(page, fillable_fields, auto_regenerate=True)

    try:
        if "/AcroForm" in writer._root_object:
            writer._root_object["/AcroForm"].update(
                {NameObject("/NeedAppearances"): BooleanObject(True)}
            )
    except (AttributeError, KeyError, TypeError):
        # pypdf's `_root_object` is a private attribute; if a future release
        # renames or restructures it, skip the NeedAppearances flag instead of
        # crashing. Most viewers still render filled fields without it.
        pass

    with output_path.open("wb") as file:
        writer.write(file)

    return len(fillable_fields), unmapped_fields


def pdf_field_value(field_value: str | bool) -> str:
    """Convert Python values to the strings expected by pypdf AcroForm writes."""
    if field_value is True:
        return "/1"
    if field_value is False:
        return "/Off"
    return field_value


def verification_targets(account: dict[str, str]) -> list[tuple[str, str]]:
    """List high-value PDF fields to confirm after official template generation."""
    targets = [
        ("form completion date", "F[0].P1[0].Form_CompletionDate_A[0]"),
        ("website address", "F[0].P1[0].NamedInsured_Primary_WebsiteAddress_A[0]"),
        ("prior carrier", "F[0].P3[0].PriorCoverage_GeneralLiability_InsurerFullName_A[0]"),
        ("customer ID page 1", "F[0].P1[0].Producer_CustomerIdentifier_A[0]"),
        ("customer ID page 2", "F[0].P2[0].Producer_CustomerIdentifier_A[0]"),
        ("customer ID page 3", "F[0].P3[0].Producer_CustomerIdentifier_A[0]"),
        ("customer ID page 4", "F[0].P4[0].Producer_CustomerIdentifier_A[0]"),
        ("policy effective date", "F[0].P1[0].Policy_EffectiveDate_A[0]"),
        ("status effective date", "F[0].P1[0].Policy_Status_EffectiveDate_A[0]"),
        ("policy expiration date", "F[0].P1[0].Policy_ExpirationDate_A[0]"),
        ("operations description", "F[0].P2[0].CommercialPolicy_OperationsDescription_A[0]"),
    ]

    if clean(account.get("llc_member_manager_count")):
        targets.append(
            (
                "LLC member / manager count",
                "F[0].P1[0].NamedInsured_LegalEntity_MemberManagerCount_A[0]",
            )
        )

    contact_phone_type = clean(account.get("primary_contact_phone_type")).lower()
    contact_phone_type_target = CONTACT_PHONE_TYPE_TARGETS.get(contact_phone_type)
    if contact_phone_type_target:
        targets.append((f"{contact_phone_type} phone type", contact_phone_type_target))

    transaction_type = clean(account.get("transaction_type")).lower() or "quote"
    status_target = STATUS_FIELD_TARGETS.get(transaction_type)
    if status_target:
        targets.append((f"{transaction_type} status checkbox", status_target))

    business_type = clean(account.get("business_type")).lower()
    if business_type:
        targets.extend(business_type_verification_targets(business_type))

    requested_lines = clean(account.get("requested_lines")).lower()
    if "property" in requested_lines:
        targets.append(
            (
                "statement of values attachment",
                "F[0].P1[0].CommercialPolicy_Attachment_StatementOfValuesIndicator_A[0]",
            )
        )
    if "business auto" in requested_lines or "commercial auto" in requested_lines:
        targets.append(
            (
                "vehicle schedule attachment",
                "F[0].P1[0].Policy_SectionAttached_VehicleScheduleIndicator_A[0]",
            )
        )
    if "umbrella" in requested_lines:
        targets.append(
            ("umbrella line checkbox", "F[0].P1[0].Policy_LineOfBusiness_UmbrellaIndicator_A[0]")
        )

    for source_key, label, field_name in [
        (
            "general_liability_premium",
            "general liability premium",
            "F[0].P1[0].GeneralLiabilityLineOfBusiness_TotalPremiumAmount_A[0]",
        ),
        (
            "property_premium",
            "property premium",
            "F[0].P1[0].CommercialPropertyLineOfBusiness_PremiumAmount_A[0]",
        ),
        (
            "business_auto_premium",
            "business auto premium",
            "F[0].P1[0].CommercialVehicleLineOfBusiness_PremiumAmount_A[0]",
        ),
        (
            "workers_comp_premium",
            "workers compensation premium",
            "F[0].P1[0].Policy_SectionAttached_OtherPremiumAmount_A[0]",
        ),
        (
            "umbrella_premium",
            "umbrella premium",
            "F[0].P1[0].CommercialUmbrellaLineOfBusiness_PremiumAmount_A[0]",
        ),
    ]:
        if clean(account.get(source_key)):
            targets.append((label, field_name))

    return targets


def business_type_verification_targets(business_type: str) -> list[tuple[str, str]]:
    """Return verification checks driven by business type mappings."""
    target = BUSINESS_TYPE_TARGETS.get(business_type)
    if target:
        targets = [(f"{business_type} business type", target)]
    else:
        targets = [
            (
                "other business type",
                "F[0].P2[0].BusinessInformation_BusinessType_OtherIndicator_A[0]",
            ),
            (
                "other business type description",
                "F[0].P2[0].BusinessInformation_BusinessType_OtherDescription_A[0]",
            ),
        ]
    if business_type == "contractor":
        targets.append(
            (
                "contractors supplement attachment",
                "F[0].P1[0].CommercialPolicy_Attachment_ContractorsSupplementIndicator_A[0]",
            )
        )
    if business_type in {"hotel", "motel", "hotel/motel"}:
        targets.append(
            (
                "hotel/motel supplement attachment",
                "F[0].P1[0].CommercialPolicy_Attachment_HotelMotelSupplementIndicator_A[0]",
            )
        )
    return targets


def print_official_pdf_verification(output_path: Path, account: dict[str, str]) -> None:
    """Print a concise confirmation that expected fields landed in the PDF."""
    from pypdf import PdfReader

    fields = PdfReader(str(output_path)).get_fields() or {}
    ok_labels = []
    missing_labels = []
    for label, field_name in verification_targets(account):
        field_value = fields.get(field_name, {}).get("/V")
        if field_value in (None, "", "/Off"):
            missing_labels.append(label)
        else:
            ok_labels.append(label)

    total = len(ok_labels) + len(missing_labels)
    print(f"Verification targets: {len(ok_labels)}/{total} populated")
    print(f"  OK: {', '.join(ok_labels) if ok_labels else 'none'}")
    if missing_labels:
        print(f"  Missing: {', '.join(missing_labels)}")


def resolve_input_paths(args: argparse.Namespace) -> tuple[Path, Path | None]:
    """Resolve the folder convention or explicit CSV paths from CLI args."""
    if args.input_dir:
        csv_path = args.csv or args.input_dir / "ams_export.csv"
        default_markets_path = args.input_dir / "target_markets.csv"
        markets_path = args.markets or (
            default_markets_path if default_markets_path.exists() else None
        )
    else:
        if not args.csv:
            raise ValueError("Provide --csv or --input-dir.")
        csv_path = args.csv
        markets_path = args.markets

    if not csv_path.exists():
        raise FileNotFoundError(f"AMS CSV not found: {csv_path}")
    if markets_path and not markets_path.exists():
        raise FileNotFoundError(f"Target markets CSV not found: {markets_path}")
    return csv_path, markets_path


def process_account(
    account: dict[str, str],
    source_csv: Path,
    output_dir: Path,
    template_path: Path,
) -> tuple[Path, Path, Path, Path]:
    """Generate all artifacts for one normalized account/carrier variant."""
    issues = validate_account(account)
    generated_at = datetime.now()
    market_slug = clean(account.get("target_market_id")) or clean(account.get("carrier_name"))
    account_slug_source = f"{value(account, 'account_id')}-{value(account, 'named_insured')}"
    if market_slug:
        account_slug_source = f"{account_slug_source}-{market_slug}"
    account_slug = slugify(account_slug_source)
    package_dir = output_dir / account_slug
    package_dir.mkdir(parents=True, exist_ok=True)

    report_path = package_dir / "review_report.md"
    json_path = package_dir / "form_payload.json"
    official_pdf_path = package_dir / "official_acord125.pdf"

    write_review_report(account, issues, report_path)
    write_json_payload(account, issues, source_csv, json_path, generated_at)
    filled_count, unmapped_fields = fill_official_acord_template(
        template_path, account, official_pdf_path, generated_at
    )
    target = market_slug or "generic market"
    print(
        f"Filled {filled_count} official ACORD fields "
        f"for {value(account, 'account_id')} / {target}"
    )
    print_official_pdf_verification(official_pdf_path, account)
    if unmapped_fields:
        print(
            f"Skipped {len(unmapped_fields)} candidate fields not present in template"
        )
    return package_dir, report_path, json_path, official_pdf_path


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for local runs or Claude Skill execution."""
    parser = argparse.ArgumentParser(
        description="Fill an official ACORD 125 AcroForm template from an AMS CSV export."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        help="Example folder containing ams_export.csv and optional target_markets.csv.",
    )
    parser.add_argument("--csv", type=Path, help="Path to the AMS CSV export.")
    parser.add_argument("--markets", type=Path, help="Optional path to target markets CSV.")
    parser.add_argument(
        "--account-id",
        help="Optional account_id to process. If omitted, every row in the CSV is processed.",
    )
    parser.add_argument(
        "--template",
        type=Path,
        required=True,
        help="Path to a fillable ACORD 125 PDF template supplied locally.",
    )
    parser.add_argument("--out", default=Path("outputs/demo"), type=Path, help="Output directory.")
    return parser.parse_args()


def main() -> None:
    """Run the full CSV-to-form workflow from the command line."""
    args = parse_args()
    if not args.template.exists():
        raise FileNotFoundError(f"Template not found: {args.template}")

    csv_path, markets_path = resolve_input_paths(args)
    args.out.mkdir(parents=True, exist_ok=True)
    accounts = select_accounts(read_accounts(csv_path), args.account_id)
    markets = read_markets(markets_path)

    for account in accounts:
        for variant in account_market_variants(account, markets):
            package_dir, report_path, json_path, official_pdf_path = process_account(
                variant, csv_path, args.out, args.template
            )
            print(f"Wrote package {package_dir}")
            print(f"Wrote {report_path}")
            print(f"Wrote {json_path}")
            print(f"Wrote {official_pdf_path}")


if __name__ == "__main__":
    main()
