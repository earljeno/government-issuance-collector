# Terms of Service

**Last Updated: November 1, 2026**
**Effective Date: November 1, 2026**

These Terms of Service ("Terms", "Agreement") govern your access to and use of the **Philippine Government Issuance Title Collector** web application, tools, and associated documentation (collectively, the "Service" or "Application"), maintained by the Project Operations Team ("Operator", "we", "us", or "our").

By accessing the Application, entering the access PIN, or checking the agreement box on the authentication gateway, you ("User", "you", or "your") acknowledge that you have read, understood, and agreed to be bound by these Terms. If you do not agree with any part of these Terms, do not access or use the Service.

---

## 1. Description of Service

The Application is a specialized administrative data-aggregation and research tool designed to collect, index, audit, and compile public titles and publication metadata of laws, orders, and circulars from official Philippine national government department portals:

1. **Department of Agriculture (DA)** (`https://www.da.gov.ph/`)
2. **Department of Education (DepEd)** (`https://www.deped.gov.ph/`)
3. **Department of Health (DOH)** (`https://doh.gov.ph/`)
4. **Department of Environment and Natural Resources (DENR)** (`https://denr.gov.ph/`)

The Service formats and compiles gathered metadata into academic Microsoft Word (`.docx`), Microsoft Excel (`.xlsx`), Comma-Separated Values (`.csv`), and plain text (`.txt`) documents for scholarly, administrative, and legal research.

---

## 2. Disclaimer of Government Affiliation

**IMPORTANT NOTICE:** The Application is an independent administrative software utility. The Operator is not an agency, instrumentality, or official representative of the Government of the Republic of the Philippines. 

The Service is **NOT** affiliated with, endorsed by, sponsored by, or operated in partnership with the Department of Agriculture, Department of Education, Department of Health, Department of Environment and Natural Resources, or any other government office. All government department names, logos, official seals, and portal URLs referenced within the Application belong exclusively to their respective government agencies and are used strictly for identification and descriptive reference.

---

## 3. Public Domain and Intellectual Property

### 3.1 Government Works
Pursuant to **Section 176 of Republic Act No. 8293** (Intellectual Property Code of the Philippines):

> *"No copyright shall subsist in any work of the Government of the Philippines. However, prior approval of the government agency or office wherein the work is created shall be necessary for exploitation of such work for profit."*

Official government issuance titles, reference numbers, publication dates, and administrative circular texts extracted from public government portals are public records. The Service does not claim proprietary copyright over raw government issuance metadata.

### 3.2 Software Intellectual Property
The Application codebase, scraper architecture, database schemas, user interface design, export generators, and documentation are proprietary works owned by the Project Maintainers and licensed contributors. You may not decompile, reverse-engineer, distribute, or create unauthorized derivative works of the proprietary codebase without prior written consent.

---

## 4. Access Control and Single-Session Policy

1. **Access Gate:** The Service is protected by an administrative PIN verification gateway. Access is restricted to authorized administrative users possessing a valid PIN.
2. **Single Global Session:** The Service enforces a single active session architecture. Authenticating from a new browser or device automatically supersedes and invalidates any existing active session.
3. **Credential Confidentiality:** You are solely responsible for maintaining the confidentiality of the access PIN. You agree to notify the Operator immediately upon becoming aware of any unauthorized access.
4. **Rate Limiting:** The authentication gateway employs automated rate limiting (10 attempts per 60-second window per IP address). Excessive failed attempts will trigger temporary IP throttling to protect system integrity.

---

## 5. Acceptable Use Policy

You agree to use the Service in compliance with all applicable Philippine laws, including but not limited to **Republic Act No. 10175 (Cybercrime Prevention Act of 2012)** and **Republic Act No. 10173 (Data Privacy Act of 2012)**.

### Prohibited Conduct
You agree not to:
1. Conduct denial-of-service attacks, flood requests, or artificially bypass polite crawl delays (`REQUEST_DELAY_SECONDS`) configured in the scrapers.
2. Interfere with or bypass Cloudflare Web Application Firewalls (WAF), bot mitigation systems, or server security mechanisms of government target portals.
3. Use the Service for any fraudulent, unlawful, or malicious purpose.
4. Attempt to gain unauthorized access to underlying PostgreSQL database servers, host environments, or server credentials.
5. Resell, rent, or lease access to the Service to third parties without authorization.

---

## 6. External Government Portals and Digitization Disclaimers

1. **Third-Party Availability:** The Service relies on the public availability and website structures of third-party Philippine government web servers. Government portals may experience downtime, structural redesigns, network latency, or anti-bot protections (e.g. Cloudflare challenges).
2. **Incomplete Government Digitization & Physical Archives:** You expressly acknowledge that the Service can only collect issuances that government departments have actively scanned, digitized, and published on their public websites. Philippine government agencies have not digitized all historical, existing, or local administrative orders. Many valid issuances exist solely in physical paper format, internal department filing cabinets, or non-public agency repositories.
3. **Absence Does Not Equal Inexistence:** The absence of a particular law, order, circular, or advisory within this Application does NOT mean that such issuance was never enacted or does not exist in Philippine jurisprudence. Users must never assume an issuance does not exist simply because it was not returned by this tool.
4. **Official Legal Verification Required:** For binding legal, academic, or judicial proceedings, users must verify records through authoritative sources: the Office of the National Administrative Register (ONAR) at the UP Law Center, the Official Gazette of the Republic of the Philippines (`https://www.officialgazette.gov.ph/`), the National Archives of the Philippines, or certified physical copies from agency records officers.
5. **No Scraping Guarantees:** The Operator does not warrant that target government websites will remain accessible, complete, uninterrupted, or error-free. Government portals frequently contain broken download links, missing PDF attachments, un-indexed years, or altered URL structures.
6. **External Hyperlinks:** Exported documents contain hyperlinks pointing directly to official government file downloads (e.g. `.pdf` documents hosted on `da.gov.ph`, `deped.gov.ph`, etc.). We do not control or endorse the content, safety, or availability of third-party external files.

---

## 7. Warranty Disclaimer

THE SERVICE IS PROVIDED ON AN **"AS IS"** AND **"AS AVAILABLE"** BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED. TO THE FULLEST EXTENT PERMISSIBLE UNDER APPLICABLE LAW, THE OPERATOR EXPRESSLY DISCLAIMS ALL WARRANTIES, INCLUDING BUT NOT LIMITED TO:

1. MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.
2. ACCURACY, COMPLETENESS, TIMELINESS, OR RELIABILITY OF GATHERED GOVERNMENT RECORDS.
3. UNINTERRUPTED OR ERROR-FREE OPERATION OF CRAWLERS AND EXPORT PIPELINES.

Official legal research must always be cross-referenced with certified true copies published in the Official Gazette of the Republic of the Philippines (`https://www.officialgazette.gov.ph/`) or official department repositories. The Application is a research aid, not an official legal gazette.

---

## 8. Limitation of Liability

TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, IN NO EVENT SHALL THE OPERATOR, DEVELOPERS, OR CONTRIBUTORS BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, EXEMPLARY, OR PUNITIVE DAMAGES, INCLUDING BUT NOT LIMITED TO:

- LOSS OF DATA, REPUTATION, OR BUSINESS OPPORTUNITIES;
- LEGAL PENALTIES OR DISPUTES ARISING FROM ACTIONS TAKEN IN RELIANCE ON COMPILED TITLES;
- SYSTEM DOWNTIME, NETWORK TIMEOUTS, OR HARDWARE FAILURE;
- SERVER OVERLOAD OR ACTIONS TAKEN BY THIRD-PARTY HOSTS OR GOVERNMENT FIREWALLS.

OUR TOTAL AGGREGATE LIABILITY FOR ALL CLAIMS ARISING OUT OF OR RELATING TO THE SERVICE SHALL NOT EXCEED ONE HUNDRED UNITED STATES DOLLARS (USD $100.00) OR THE EQUIVALENT IN PHILIPPINE PESOS (PHP).

---

## 9. Indemnification

You agree to defend, indemnify, and hold harmless the Operator, its affiliates, and maintainers against any claims, liabilities, damages, losses, and expenses (including reasonable legal fees) arising out of or in any way connected with:
1. Your breach of these Terms;
2. Your violation of any applicable law or third-party rights;
3. Your misuse of compiled records or execution of crawler extractions against government portals.

---

## 10. Modifications and Termination

1. **Right to Modify Terms:** We reserve the right to revise or replace these Terms at any time. Changes become effective immediately upon posting to the Application. Your continued use of the Application following any updates signifies acceptance of the revised Terms.
2. **Termination:** We reserve the right to terminate or suspend access to the Service immediately, without prior notice or liability, for any violation of these Terms or misuse of system resources.

---

## 11. Dispute Resolution and Governing Law

These Terms shall be governed by, construed, and enforced in accordance with the laws of the **Republic of the Philippines**, without regard to conflict of law principles. Any dispute, claim, or controversy arising out of or relating to these Terms or the Service shall be subject to the exclusive jurisdiction of the competent courts of the Republic of the Philippines.

---

## 12. Severability and Entire Agreement

If any provision of these Terms is found to be unlawful, void, or unenforceable by a court of competent jurisdiction, that provision shall be enforced to the maximum extent permissible, and the remaining provisions shall continue in full force and effect. These Terms constitute the entire agreement between you and the Operator regarding your use of the Application.

---

## 13. Contact Information

If you have questions, inquiries, or legal notices concerning these Terms of Service, please contact:

- **Entity / Maintainer:** Philippine Government Issuance Title Collector Operations
- **Project:** Philippine Government Issuance Title Collector
- **Contact:** System Administrator
- **Website:** Administrative Access Portal
