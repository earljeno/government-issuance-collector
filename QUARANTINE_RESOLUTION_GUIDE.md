# Quarantine Resolution & Verification Guide

## 1. Overview & Purpose

This guide establishes the standard operating procedures (SOP) for auditing, researching, and resolving records in the `quarantine_logs` database table.

The quarantine system captures potential data-quality issues identified during government issuance scraping and validation, including:

- Missing or inconsistent issuance numbers.
- Missing publication dates or metadata.
- Potential gaps in sequential issuance numbering.
- Extraction failures and incomplete records.
- Invalid, inaccessible, or non-authoritative source URLs.
- Other anomalies detected during automated validation.

The objective is to maintain data integrity while avoiding two problems:

1. **False positives:** Treating valid records or expected numbering gaps as extraction errors.
2. **False negatives:** Dismissing genuine issuances that were missed during scraping or data collection.

**Core principle:** A sequence gap is an indication that further investigation may be necessary. It is not, by itself, proof that a government issuance exists.

---

## 2. Issue Classification Taxonomy

### Category 1: National Cross-Cutting Enactments

**Categories:**
- `Republic Acts`
- `Executive Orders`
- `Presidential Decrees`

**Nature:**

These instruments are issued at the national level, rather than generated exclusively by individual line agencies. Government departments may archive or reference only those instruments relevant to their respective mandates.

**Integrity Rule:**

Continuous numbering should not be expected within an individual agency's archive for these categories. A missing number in an agency-specific collection does not automatically indicate an extraction failure.

**Resolution Action:**

- If the quarantine entry was generated solely because of an expected sequence gap, mark it as `Ignored`.
- Record a note explaining that the numbering belongs to a national-level issuance series and is not expected to be continuous within the agency archive.
- Use the `NATIONAL_CROSS_CUTTING_CATEGORIES` classification rule where applicable.
- Do not ignore other issues involving missing metadata, invalid URLs, or incomplete extraction merely because the record belongs to one of these categories.

### Category 2: Agency-Specific Sequential Issuances

**Categories may include:**
- `DepEd Orders (DO)`
- `DepEd Memoranda (DM)`
- `DepEd Advisories (DA)`
- `DOH Administrative Orders (AO)`
- `DOH Department Circulars (DC)`
- `DA Administrative Orders`
- `DENR Administrative Orders (DAO)`

**Nature:**

These issuance categories commonly use agency-specific numbering systems, often organized by calendar year and issuance type.

**Integrity Rule:**

A missing number between two recorded issuances should be treated as a potential gap requiring investigation.

Possible explanations include:

1. The issuance exists on an official agency website or another authoritative government archive but was missed during extraction.
2. The number was reserved, unused, cancelled, withdrawn, or otherwise never formally issued.
3. The document was published under another issuance category or series.
4. The document is temporarily unavailable, unindexed, or inaccessible through the available public archives.
5. The numbering convention or archive structure changed during the relevant period.

These are possible explanations, not established facts. Each gap must be evaluated independently.

**Resolution Action:**

- **Found and verified:** Retrieve the official document, validate its metadata, ingest or backfill the record, and mark the quarantine entry as `Resolved`.
- **Confirmed unused, cancelled, or withdrawn:** Mark as `Resolved` only when supported by an authoritative source or reliable official confirmation. Record the evidence in the resolution note.
- **Reclassified issuance:** Verify the alternate category or series, ensure the record is correctly represented in the database, and mark the original gap as `Resolved`.
- **Unconfirmed or not found:** Keep the entry as `Pending`.
- **Insufficient evidence:** Do not assume that an issuance was never published simply because it cannot be found through a search engine or current agency archive.

### Category 3: Agency Number Blocks & Reservation Gaps

**Example:**

An agency publishes `AO 2026-0031` while numbers `2026-0014` through `2026-0030` are not present in the currently collected dataset.

**Nature:**

Issuance numbers may be reserved, assigned in batches, released at different times, or used according to internal agency procedures. Publicly accessible archives may also be incomplete or delayed.

**Integrity Rule:**

A later issuance number does not establish that all preceding numbers were formally issued. Similarly, an absent number does not establish that it was reserved or cancelled.

**Resolution Action:**

- Keep unexplained numbering gaps as `Pending`.
- Investigate the relevant official agency archive and other authoritative government sources.
- Do not mark gaps as resolved solely because the calendar year has ended.
- If an official source confirms that a number was unused, cancelled, withdrawn, or otherwise not issued, document that evidence and mark it as `Resolved`.
- If no definitive evidence is available, retain the pending status for future reconciliation.

### Category 4: Scraper Quarantine — Missing Metadata & Invalid Source URLs

**Nature:**

The scraper encountered a record with one or more extraction or validation problems, such as:

- Missing issuance number.
- Missing or unparseable publication date.
- Missing document title.
- Missing direct document link.
- Invalid or inaccessible source URL.
- Non-official or unrelated external domain.
- Navigation links or archive-page URLs incorrectly identified as document records.
- Incomplete or malformed extracted content.

**Integrity Rule:**

A missing field does not automatically mean the record is invalid. The original source must be examined to determine whether the information is genuinely absent or was simply not extracted correctly.

**Resolution Action:**

- **Valid document recovered:** Retrieve the document, verify its metadata, and save it through `/api/manual-url/save` with the corresponding `quarantine_id` to trigger automatic resolution.
- **Valid record with unavailable metadata:** Preserve the record where possible and document which fields could not be verified. Do not invent missing values.
- **Confirmed irrelevant navigation link or placeholder:** Mark as `Ignored` with an explanatory note.
- **Confirmed dead or inaccessible link:** Mark as `Resolved` only if the record has been independently determined to be invalid or an alternative authoritative source confirms its status. Otherwise, retain it as `Pending`.
- **Unverified external domain:** Investigate whether the domain belongs to an authoritative government source before accepting or rejecting it.

---

## 3. Search & Verification Protocols

When investigating a quarantined issuance number or incomplete record, follow these steps.

### Step 1: Search Official Agency Sources

Prioritize the issuing agency's official website and document archive.

**DepEd**

Suggested search queries:

- `site:deped.gov.ph "DO [N], s. [YYYY]"`
- `site:deped.gov.ph "DM [N], s. [YYYY]"`
- `site:deped.gov.ph filetype:pdf "[issuance number]"`

**DOH**

Suggested search queries:

- `site:doh.gov.ph "[YYYY]-[NNNN]"`
- `site:doh.gov.ph "[issuance number]" filetype:pdf`

Also examine the official DOH policy and issuance repositories where available.

**DA and DENR**

Suggested search queries:

- `site:da.gov.ph "[issuance number]" filetype:pdf`
- `site:denr.gov.ph "[issuance number]" filetype:pdf`

Check the relevant agency issuance archives and official publication pages.

### Step 2: Search Other Authoritative Government Sources

If the issuing agency's website does not provide sufficient information, consult other authoritative sources, where applicable:

- Official Gazette: `officialgazette.gov.ph`
- Supreme Court E-Library: `elibrary.judiciary.gov.ph`
- Lawphil: `lawphil.net`
- Other official government repositories or publications.

**Important:** A search result, third-party index, or document-sharing website may help locate a record, but it should not automatically be treated as proof of official issuance. Verify the document against an authoritative source whenever possible.

### Step 3: Verify the Retrieved Record

Before marking an entry as `Resolved`, check the following:

1. **Issuing Agency:** Does the document originate from the correct government agency?
2. **Issuance Category:** Does it belong to the expected series, such as an Administrative Order, Department Order, or Memorandum?
3. **Issuance Number:** Does the document's number match the quarantined number?
4. **Publication Year:** Is the year consistent with the expected issuance series?
5. **Document Title:** Does the title accurately represent the document?
6. **Publication Date:** Is the date supported by the official document or publication record?
7. **Source URL:** Does the link lead to the actual document or an authoritative record?
8. **Database Status:** Has the verified record been successfully ingested or backfilled, where applicable?
9. **Evidence:** Is there sufficient supporting evidence for the selected resolution status?

### Step 4: Apply the Resolution Standard

**Strict verification principle:**

If the search results are ambiguous, the source is unreliable, or no definitive evidence can be found, **leave the quarantine entry as `Pending`.**

Never fabricate issuance numbers, dates, titles, cancellation reasons, or publication details to fill a sequence gap.

---

## 4. Resolution Status Definitions

| Status | Meaning | When to Use |
|---|---|---|
| `Pending` | Requires further investigation | Evidence is incomplete, ambiguous, or unavailable |
| `Resolved` | The underlying issue has been addressed | Record recovered, metadata corrected, or issue conclusively explained |
| `Ignored` | The alert is not applicable or is an established false positive | Expected sequence gap or confirmed irrelevant entry |

**Status distinction:**

- `Resolved` means the issue was investigated and addressed with sufficient evidence.
- `Ignored` means the alert does not require further action because it is not applicable.
- `Pending` means the issue remains unresolved and must not be treated as verified.

Every manual resolution should include a concise explanation and supporting source reference whenever available.

---

## 5. Execution Workflow Summary

```text
                    [Quarantine Record]
                            |
                  [Identify Issue Type]
                            |
          ---------------------------------------
          |                  |                  |
   National-Level       Agency-Specific     Scraper / Metadata
   Issuance Gap         Issuance Gap         Extraction Issue
          |                  |                  |
   Check whether       Search official      Inspect original
   gap is expected     agency sources       source and metadata
          |                  |                  |
   ----------------    ----------------    ----------------
   |              |    |              |    |              |
Expected       Other  Document      No      Record       Invalid /
Gap           Issue   Found       Evidence  Recovered    Irrelevant
   |              |    |              |    |              |
 Ignored     Investigate Backfill /  Pending  Verify      Verify
                         Ingest                and Save    and Classify
                            |                     |           |
                         Resolved              Resolved   Resolved /
                                                          Ignored
```

---

## 6. Audit Trail & Documentation Requirements

Every manually resolved or ignored quarantine entry should include enough information for another reviewer to understand the decision.

Recommended resolution notes should contain:

- **Resolution reason:** Why the entry was resolved or ignored.
- **Verification source:** Official URL or document reference.
- **Verified issuance number:** Where applicable.
- **Verified issuance category:** Where applicable.
- **Verification date:** When the investigation was performed.
- **Action taken:** Backfilled, corrected, confirmed unused, classified as false positive, or another applicable action.

Do not mark an entry as resolved without recording the reason for the decision.

---

## 7. Final Data Integrity Principles

1. A numbering gap is a signal for investigation, not proof of a missing issuance.
2. Official agency documents and authoritative government repositories take priority over search snippets and third-party references.
3. Missing metadata must be investigated before being treated as an invalid record.
4. Unconfirmed gaps must remain `Pending`.
5. A record should only be marked `Resolved` when the underlying issue has been addressed and adequately documented.
6. `Ignored` should be reserved for non-applicable alerts and established false positives.
7. Never fabricate metadata or infer cancellation, withdrawal, or non-issuance without supporting evidence.
8. Preserve source URLs and verification notes to maintain traceability and support future audits.

**Final rule: When evidence is insufficient, preserve the uncertainty rather than forcing a resolution.**