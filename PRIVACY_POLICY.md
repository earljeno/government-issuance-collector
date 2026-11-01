# Privacy Policy

**Last Updated: November 1, 2026**
**Effective Date: November 1, 2026**

The **Philippine Government Issuance Title Collector** ("Service", "Application", "we", "us", or "our"), operated by the Project Operations Team ("Operator"), is committed to transparency and responsible handling of digital information. 

This Privacy Policy explains how information is processed when you access and use the administrative dashboard, API endpoints, and export features of the Application. We adhere to the principles of transparency, legitimate purpose, and proportionality established by the **Data Privacy Act of 2012 (Republic Act No. 10173)** of the Republic of the Philippines.

---

## 1. Scope and Nature of Processed Data

The Application functions primarily as an administrative metadata indexing tool for public government legal records. The categories of information processed by the Service fall into two distinct groups:

### 1.1 Public Government Records (Non-Personal Information)
The Application crawls and compiles public legal records from official national government department portals (Department of Agriculture, Department of Education, Department of Health, Department of Environment and Natural Resources).

Under **Section 4(c) of Republic Act No. 10173**, the Data Privacy Act does not apply to:
> *"Information relating to any function or position of an officer or employee of the Philippine government, or information about an individual that is performing a service under contract for a government institution."*

All collected issuance titles, reference numbers (e.g. Administrative Order numbers, Memorandum Circular numbers), signing dates, and public download links are public government domain information accessible to all citizens and are not private personal data.

### 1.2 Administrative Security and Session Data
When you access the administrative web interface, we process minimal technical data necessary to operate and secure the Service:

1. **Access Verification (PIN):** The 6-digit access PIN you submit is verified using cryptographic constant-time comparison (`hmac.compare_digest`). The PIN is not logged or stored alongside individual identities.
2. **Session Cookie:** Upon successful verification, the server issues an encrypted random UUID session identifier stored in an `HttpOnly`, `SameSite=Lax` browser cookie (`session_access_token`). This cookie contains no personal identity, email address, or tracking information.
3. **Client IP Address (Security Throttling):** Client IP addresses are stored temporarily in volatile server memory solely to enforce rate limiting (maximum 10 failed login attempts per 60-second sliding window). IP records are automatically purged and are never persisted to the permanent database.
4. **Temporary System Logs:** Standard web server operational logs (HTTP method, route accessed, HTTP status code, timestamp) generated for debugging and error diagnosis.

---

## 2. Purpose and Legal Basis for Processing

We process technical data solely based on legitimate administrative interest and system security:

| Category | Purpose | Legal Basis under RA 10173 | Retention Period |
| :--- | :--- | :--- | :--- |
| **Session Cookie (`session_access_token`)** | Maintaining single active administrative session and blocking unauthorized access | Legitimate security interest; contractual necessity | Cleared upon logout or superseded by a new session |
| **Client IP Address** | Mitigating brute-force PIN attacks and distributed denial-of-service attempts | Legitimate security interest | Cleared after 60-second sliding window |
| **Public Government Metadata** | Aggregating and compiling public legal records into academic documents | Public interest and open governance research | Maintained in PostgreSQL database until administrative reset |

We do not engage in profiling, automated behavioral scoring, or behavioral marketing.

---

## 3. Cookies and Local Storage

The Service uses only **strictly necessary technical cookies**:

- **Cookie Name:** `session_access_token`
- **Type:** First-party, HTTP-only, secure session cookie
- **Purpose:** Identifies the single globally active administrative user
- **Duration:** Session duration (invalidated upon logout or new session authentication)

We **DO NOT** use:
- Third-party tracking or advertising cookies (e.g. Google AdSense, Meta Pixel);
- Cross-site analytics trackers;
- Behavioral profiling tools.

---

## 4. Third-Party Services and Data Sharing

We do not sell, rent, lease, or monetize any user information or collected records. Data is transferred only to infrastructure providers strictly necessary to host the Application:

| Provider | Purpose | Nature of Data Shared | Privacy Reference |
| :--- | :--- | :--- | :--- |
| **Supabase / PostgreSQL** | Relational database hosting for public government issuance records | Scraped public issuance titles, dates, reference codes | `https://supabase.com/privacy` |
| **Cloud Hosting (Vercel / Render / Self-Hosted)** | Web server execution and runtime hosting | Transient HTTP request logs and encrypted session cookies | Respective hosting privacy policies |

We do not share any data with marketing networks, data brokers, or commercial aggregators.

---

## 5. Security Safeguards

We implement appropriate technical, organizational, and physical safeguards to prevent unauthorized access, loss, or destruction of information:

1. **Cryptographic Protection:** Single active session tokens are randomly generated 128-bit UUIDs. PIN comparison utilizes timing-safe constant comparison to prevent side-channel timing attacks.
2. **Access Gate:** Unauthorized requests to private dashboard views and extraction APIs are rejected with HTTP 401 Unauthorized responses.
3. **Isolated Memory Architecture:** Rate-limiting structures reside exclusively in transient memory locks, minimizing exposure to disk exploits.
4. **Export Sandboxing:** Exported Word, Excel, CSV, and TXT files are compiled into isolated temporary directories and served with sanitized file headers.

---

## 6. Data Subject Rights (RA 10173 Compliance)

In accordance with Republic Act No. 10173 (Data Privacy Act of 2012), authorized users possess specific rights regarding their personal data:

1. **Right to be Informed:** The right to understand whether personal data is being processed, as articulated in this Privacy Policy.
2. **Right to Access:** The right to request confirmation of any personal information held by the Operator.
3. **Right to Rectification:** The right to dispute any inaccurate or incomplete data.
4. **Right to Erasure or Blocking:** The right to request the deletion or removal of personal information upon legitimate grounds.
5. **Right to Damages:** The right to be indemnified for damages sustained due to inaccurate, false, unlawfully obtained, or unauthorized use of personal data.

To exercise any of these rights, please contact the Operator using the details in Section 9.

---

## 7. Children's Privacy

The Service is an administrative and legal research platform intended strictly for adult professionals, legal researchers, and system administrators. We do not knowingly collect, request, or maintain data from individuals under 18 years of age.

---

## 8. Updates to this Policy

We reserve the right to amend this Privacy Policy to reflect modifications in our data practices, regulatory requirements, or Application features. Any revisions will be posted directly to this page with an updated "Last Updated" date. We encourage users to periodically review this document.

---

## 9. Contact Information

For inquiries, concerns, or requests relating to this Privacy Policy or data privacy compliance, please direct communications to:

- **Data Protection / Administration:** System Operations & Privacy Team
- **Application:** Philippine Government Issuance Title Collector
- **Jurisdiction:** Republic of the Philippines
