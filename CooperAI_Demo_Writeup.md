# ACORDingly. Cooper AI Sales Engineer Take-Home Write-Up

ACORDingly is a small, working MVP for a mid-market commercial P&C brokerage pilot. It ingests a structured AMS-style CSV export and an optional target-market CSV, then generates one output package per account and carrier or program target. Each package includes a draft PDF application, a markdown review report, and a machine-readable JSON payload. When a fillable ACORD 125 AcroForm template is supplied locally, the same normalized payload can also populate the official PDF template. The goal is not to replace CSR or producer review. The goal is to remove the first pass of repetitive re-keying and make missing data explicit before a submission moves forward.

## 1. Discovery Questions and Assumptions

### Walk me through how a commercial submission gets prepared today, from account data gathering through sending an application to market.

I open here because it forces the customer to describe their actual workflow before I propose anything. I want the order of operations, the systems and people involved, and which steps the team treats as routine versus painful. For the MVP, I assumed the first-pass workflow starts with core account data in the AMS and ends with a CSR preparing an ACORD 125 package for producer review. The script mirrors that step.

### Where does the process slow down or create rework for CSRs, account managers, or producers?

I want to surface where the team loses hours and where the same data gets typed more than once. That tells me which form or workflow to prove time savings on first. For the MVP, I assumed the highest-volume pain is repetitive re-keying of applicant-level data on common ACORD applications. I chose ACORD 125 as the pilot form because it captures reusable applicant data that later feeds line-specific forms and carrier supplementals.

### When someone fills an application today, where do they actually go to find the facts they need?

I want to understand source-of-truth and where the friction lives. Account data can sit in the AMS, a declaration page, a current policy PDF, a quote, an email thread, or broker notes. Knowing which sources are clean and which are scattered tells me where deterministic code is enough and where AI extraction earns its keep. For the MVP, I assumed the AMS is the cleanest single source and can export a CSV with named insured, address, FEIN, NAICS, contacts, requested lines, limits, premiums, and prior coverage. I deferred declaration pages, policies, emails, and loss runs to the next extraction adapter.

### What information most often causes an application to get stuck, sent back, or held for review?

I want to learn which missing data is genuinely blocking and which is cosmetic, because those two cases should be handled differently. The product proposal is that the tool should generate a draft even when data is incomplete, but should make the gap visible and prevent the package from being treated as submission-ready when a blocking field is missing. For the MVP, I assumed missing legal and account identity data such as FEIN is typically blocking. That model drives the review_report.md output. The Birchwood sample intentionally omits FEIN to show this behavior end-to-end.

### How does the team decide which markets or carrier programs should receive a submission?

I want to understand whether one account routinely goes to multiple carriers and whether each carrier needs its own version of the application. If a tool only produces one generic application per account, it misses where the time savings compound. For the MVP, I assumed the same account is typically shopped to multiple markets, each needing its own copy with carrier-specific identifiers and underwriter details. I added target_markets.csv as an optional input. The script produces one package per account and market combination with carrier, NAIC, program, underwriter, and market notes attached.

### After a trial user runs this, what would make them say the workflow saved meaningful time?

I want to understand what "done" looks like for the CSR. Some teams want a finished PDF they can email out. Others want a draft plus visibility into what was filled, what's missing, and what an auditor would need to verify. For the MVP, I assumed producers and CSRs at a mid-market brokerage want auditability and review surface area rather than a black box. I shipped three artifacts per package. The PDF and review report are the human-facing artifacts. The JSON is the production bridge for downstream official-form rendering.

### Summary of assumptions

- **Pilot workflow.** Start the pilot on a high-volume common ACORD application (ACORD 125) because it captures reusable applicant data that later feeds line-specific forms and carrier supplementals.
- **Source data.** AMS is the cleanest current source and can export a structured CSV with named insured, address, FEIN, NAICS, contacts, requested lines, limits, premiums, and prior coverage. Declaration pages, policies, emails, and loss runs are deferred to the next extraction adapter.
- **Workflow roles.** CSR or account manager prepares the first draft. Producer or account executive reviews before submission. The tool sits between those roles, not in place of them.
- **Completeness model.** Drafts are generated even with missing data, but blocking missing fields prevent the package from being marked ready. The review report makes the gap explicit.
- **Multi-market submissions.** The same account is typically sent to multiple carriers, each needing its own copy with carrier-specific fields. The optional target_markets.csv input produces one carrier or program-specific package per account.
- **Output expectations.** Pilot users receive a filled draft PDF, a markdown review report, and a JSON payload for auditability and downstream rendering, not a black box or auto-submission.

## 2. What I Chose To Build and What I Cut

I intentionally optimized for one complete, inspectable workflow rather than broad form coverage. The MVP proves the highest-risk path. Structured account data can be transformed into a reviewable submission package, and when an official AcroForm template is available, into a real filled ACORD PDF.

**Built**

- A Claude-runnable Python skill with SKILL.md, README.md, sample inputs, requirements.txt, and scripts/fill_acord125.py.
- Input folders under sample_inputs for Acme Mechanical (a complete account) and Birchwood Hospitality (an intentionally incomplete account).
- A parser for AMS-style CSV data and optional target market data.
- Validation that separates blocking fields from recommended fields and marks packages as Ready for review or Needs CSR review.
- One output folder per account and carrier combination, containing application_draft.pdf, review_report.md, and form_payload.json.
- Optional official ACORD 125 AcroForm filling when a local template is supplied with --template.

**Cut or deferred**

- An AI extraction adapter for declaration pages, current policies, quotes, emails, and broker notes. I scoped this as the next layer in the architecture after proving the schema, validation, and form-rendering path.
- Full official ACORD 125 field coverage. The MVP fills the high-value applicant, brokerage, policy, line, prior coverage, and target-market fields available from the sample export.
- ACORD 126, ACORD 130, schedules, and carrier-specific supplemental forms.
- A hosted web UI, authentication, persistence, carrier portal submission, and customer-specific AMS integrations.

## 3. Key Architecture Decisions and Scaling Plan

**Python executes, outputs designed for handoff.** Python owns CSV parsing, validation, mapping, and form rendering. The script produces three artifacts per package and exits. Those artifacts are intentionally structured for downstream work: the JSON payload is the integration contract for an official-form renderer, and the markdown review report is something a producer, CSR, or LLM can read directly. Keeping execution simple and outputs clean is what makes the rest of the architecture scale.

**Deterministic handling for structured data.** CSV parsing, validation, and final form rendering are implemented in Python instead of routed through an LLM. Structured AMS exports do not need an LLM to parse or fill into form fields. Runtime AI earns its keep on the unstructured side, where extraction from dec pages, policies, and broker notes is genuinely hard. The MVP builds the stable schema and form-rendering spine that an AI extraction layer can plug into next.

**Normalized payload as the integration contract.** The form_payload.json output contains normalized account data, validation status, field-level source metadata, and candidate AcroForm targets. The PDF is the human-facing artifact. The JSON is the production bridge.

**Explicit validation before rendering.** The skill does not hide gaps. If blocking fields are missing, the PDF can still be created as a draft, but the review report prevents the package from being treated as submission-ready.

**Mapping-driven official form fill.** When a fillable ACORD 125 template is supplied, the script maps normalized fields to known AcroForm field names. This avoids asking an LLM to rewrite a regulated form layout.

**Target markets as data, not code.** Carrier and program variations come from target_markets.csv, allowing one account to produce multiple market-specific packages without changing the core script.

On scaling: more forms would be added through new form-specific mappers and renderers that consume the same normalized account model. More lines would add line-specific schema groups, validators, and schedules such as workers compensation payroll and class codes, vehicle schedules, property locations, and liquor liability operations. More carriers would add carrier-specific validation profiles, supplement mappings, appetite rules, and required-field profiles. More input types would be added as adapters in front of the same schema, including AI extraction adapters for PDFs, emails, and broker notes with source citations and confidence flags.

## 4. Where AI Shows Up

I used AI heavily to scope the workflow, generate realistic synthetic account and market data, reason through architecture tradeoffs, inspect ACORD field behavior, accelerate Python implementation, and polish the README and SKILL documentation.

The MVP is also designed so its outputs are clean handoff points for AI work on top. The review report is plain markdown and the form payload is structured JSON, both of which Claude or another model can read directly. That keeps the door open for next-step uses such as summarizing a stack of reports for a producer, drafting a CSR follow-up to the insured listing only the blocking missing fields, or comparing two packages side by side. None of that is wired into the MVP. The point is that the output shape does not have to change for those uses to be added, which keeps the same architecture viable as the workflow grows.

The next AI layer in the architecture is extraction. In a production Cooper workflow, AI would extract structured facts from declaration pages, policies, quotes, emails, broker notes, and loss runs into the same normalized schema used here, attaching source snippets and confidence signals to each extracted value. Validation would then decide whether a value can be filled, should be shown as a candidate for CSR review, or should be treated as missing. That is where AI has the most leverage in this workflow, and the schema already exists for it to target.

## 5. What I Would Build Next

- Add AI extraction adapters for declaration pages, policy PDFs, quotes, broker notes, emails, and loss runs, all producing the same normalized schema.
- Add field-level source attribution, confidence, and review thresholds so low-confidence values are not silently written into forms.
- Build a lightweight human review UI where CSRs can approve, edit, or reject extracted values before final form generation.
- Expand to ACORD 126, ACORD 130, vehicle schedules, property schedules, and carrier-specific supplementals such as contractors and hotel or motel applications.
- Add customer deployment features such as tenant-specific mappings, audit logs, permissions, persistence, and eventually integrations with AMS exports and carrier submission workflows.
