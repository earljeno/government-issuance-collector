document.addEventListener("DOMContentLoaded", () => {
    let currentPage = 1;
    const pageSize = 20;
    let previewedManualRecords = [];

    // Elements
    const globalTotalRecords = document.getElementById("global-total-records");
    const globalSystemStatus = document.getElementById("global-system-status");
    const progressCard = document.getElementById("progress-card");
    const progressStatusTitle = document.getElementById("progress-status-title");
    const progressMessage = document.getElementById("progress-message");
    const progDept = document.getElementById("prog-dept");
    const progCat = document.getElementById("prog-cat");
    const progPage = document.getElementById("prog-page");
    const progTotalPages = document.getElementById("prog-total-pages");
    const progRecords = document.getElementById("prog-records");
    const failedPagesBadge = document.getElementById("failed-pages-badge");

    // Table elements
    const issuancesTbody = document.getElementById("issuances-tbody");
    const pageSummary = document.getElementById("page-summary");
    const pageCurrent = document.getElementById("page-current");
    const pagePrev = document.getElementById("page-prev");
    const pageNext = document.getElementById("page-next");

    // Filter elements
    const tableSearch = document.getElementById("table-search");
    const tableFilterDept = document.getElementById("table-filter-dept");
    const tableFilterYear = document.getElementById("table-filter-year");
    const btnApplyFilters = document.getElementById("btn-apply-filters");
    const btnResetFilters = document.getElementById("btn-reset-filters");

    // Export elements
    const exportDeptSelect = document.getElementById("export-dept-select");
    const btnExportWordText = document.getElementById("btn-export-word-text");
    const btnExportExcelText = document.getElementById("btn-export-excel-text");

    // Actions
    const btnExtractAll = document.getElementById("btn-extract-all");
    const btnExtractSelected = document.getElementById("btn-extract-selected");
    const btnStopExtraction = document.getElementById("btn-stop-extraction");
    const btnCleanupDuplicates = document.getElementById("btn-cleanup-duplicates");
    const btnClearRecords = document.getElementById("btn-clear-records");
    const btnRetryFailed = document.getElementById("btn-retry-failed");

    // Modal elements
    const btnManualUrl = document.getElementById("btn-manual-url");
    const modalManual = document.getElementById("modal-manual");
    const modalManualClose = document.getElementById("modal-manual-close");
    const btnManualAnalyze = document.getElementById("btn-manual-analyze");
    const btnManualSave = document.getElementById("btn-manual-save");
    const manualDept = document.getElementById("manual-dept");
    const manualCat = document.getElementById("manual-cat");
    const manualUrlInput = document.getElementById("manual-url-input");
    const manualHtmlInput = document.getElementById("manual-html-input");
    const manualPreviewSection = document.getElementById("manual-preview-section");
    const manualStructInfo = document.getElementById("manual-struct-info");
    const manualPreviewTbody = document.getElementById("manual-preview-tbody");

    // Validation & Reconciliation Modal elements
    const btnValidateRecords = document.getElementById("btn-validate-records");
    const quarantineBadge = document.getElementById("quarantine-badge");
    const modalValidate = document.getElementById("modal-validate");
    const modalValidateClose = document.getElementById("modal-validate-close");
    const btnRunValidation = document.getElementById("btn-run-validation");
    const btnReconcileBackfill = document.getElementById("btn-reconcile-backfill");
    const tabBtnPortal = document.getElementById("tab-btn-portal");
    const tabBtnQuarantine = document.getElementById("tab-btn-quarantine");
    const panelPortal = document.getElementById("panel-portal-reconciliation");
    const panelQuarantine = document.getElementById("panel-quarantine-logs");
    const valIntegrityScore = document.getElementById("val-integrity-score");
    const valTotalRecords = document.getElementById("val-total-records");
    const valDetectedGaps = document.getElementById("val-detected-gaps");
    const valFailedPages = document.getElementById("val-failed-pages");
    const valLastChecked = document.getElementById("val-last-checked");
    const valPortalTbody = document.getElementById("val-portal-tbody");
    const valQuarantineTbody = document.getElementById("val-quarantine-tbody");
    const valQuarantineTabCount = document.getElementById("val-quarantine-tab-count");
    const quarantineSearchInput = document.getElementById("quarantine-search-input");
    const quarantineSearchClear = document.getElementById("quarantine-search-clear");
    const quarantineFilterCount = document.getElementById("quarantine-filter-count");
    let currentQuarantineLogs = [];

    // Toast helper
    function showToast(msg, duration = 3500) {
        const toast = document.getElementById("toast");
        toast.textContent = msg;
        toast.style.display = "block";
        setTimeout(() => {
            toast.style.display = "none";
        }, duration);
    }

    // Status polling
    async function pollStatus() {
        try {
            const res = await fetch("/api/status");
            const data = await res.json();
            const prog = data.progress || {};

            // Update stats
            globalTotalRecords.textContent = data.total_records.toLocaleString();
            failedPagesBadge.textContent = data.failed_pages_count;

            if (data.is_prod) {
                if (btnValidateRecords) {
                    btnValidateRecords.disabled = true;
                    btnValidateRecords.setAttribute("aria-disabled", "true");
                    btnValidateRecords.title = "Audit & Reconcile Data is disabled in production";
                }
                if (btnRunValidation) {
                    btnRunValidation.disabled = true;
                    btnRunValidation.setAttribute("aria-disabled", "true");
                    btnRunValidation.title = "Audit routines are disabled in production";
                }
                if (btnReconcileBackfill) {
                    btnReconcileBackfill.disabled = true;
                    btnReconcileBackfill.setAttribute("aria-disabled", "true");
                    btnReconcileBackfill.title = "Reconciliation is disabled in production";
                }
            }

            // Update Department Cards
            const codeMap = {
                "Department of Agriculture": "DA",
                "Department of Health": "DOH",
                "Department of Environment and Natural Resources": "DENR",
                "Department of Education": "DepEd"
            };

            for (const d of data.departments) {
                const code = codeMap[d.department];
                if (!code) continue;

                const countEl = document.getElementById(`count-${code}`);
                const lastEl = document.getElementById(`last-${code}`);
                const badgeEl = document.getElementById(`badge-${code}`);

                if (countEl) countEl.textContent = d.total_records.toLocaleString();
                if (lastEl) lastEl.textContent = d.last_extraction ? d.last_extraction.split(" ")[0] : "Never";

                if (badgeEl) {
                    badgeEl.textContent = d.status;
                    badgeEl.className = "dept-badge";
                    if (d.status === "Running") badgeEl.classList.add("badge-running");
                    else if (d.status === "Completed") badgeEl.classList.add("badge-completed");
                    else if (d.status === "Interrupted" || d.status === "Stopped") badgeEl.classList.add("badge-inaccessible");
                    else if (d.status === "Temporarily Inaccessible") badgeEl.classList.add("badge-inaccessible");
                    else if (d.status === "Error") badgeEl.classList.add("badge-error");
                    else badgeEl.classList.add("badge-idle");
                }
            }

            // Resume UI handling - Always visible, dynamically updated
            const checkpoints = data.checkpoints || {};
            const interruptedDepts = (data.departments || []).filter(d => d.status === "Interrupted" || d.status === "Stopped");
            const isRunning = prog && prog.is_running;
            const deptCodeMap = {
                "Department of Agriculture": "DA",
                "Department of Health": "DOH",
                "Department of Environment and Natural Resources": "DENR",
                "Department of Education": "DepEd"
            };

            const resumableDeptNames = new Set([
                ...Object.keys(checkpoints),
                ...interruptedDepts.map(d => d.department)
            ]);

            // Update individual card resume buttons
            Object.entries(deptCodeMap).forEach(([deptName, code]) => {
                const btn = document.getElementById(`resume-btn-${code}`);
                if (!btn) return;

                btn.style.display = "inline-flex";
                btn.disabled = isRunning;

                const cp = checkpoints[deptName];
                const isInterrupted = interruptedDepts.some(d => d.department === deptName);

                if (cp && cp.page && cp.page > 1) {
                    btn.className = "btn btn-sm btn-warning resume-single-btn";
                    btn.textContent = `Resume ${code} (p.${cp.page})`;
                    btn.title = `Resume ${deptName} from ${cp.category || 'checkpoint'} (Page ${cp.page})`;
                } else if (cp && cp.category) {
                    btn.className = "btn btn-sm btn-warning resume-single-btn";
                    btn.textContent = `Resume ${code} (${cp.category})`;
                    btn.title = `Resume ${deptName} from category: ${cp.category}`;
                } else if (isInterrupted) {
                    btn.className = "btn btn-sm btn-warning resume-single-btn";
                    btn.textContent = `Resume ${code}`;
                    btn.title = `Resume ${deptName} from last stopped point`;
                } else {
                    btn.className = "btn btn-sm btn-outline-warning resume-single-btn";
                    btn.textContent = `Resume ${code}`;
                    btn.title = `Continue / Resume ${deptName}`;
                }
            });

            // Update Global Resume Wrapper and Agency Selector
            const resumeWrapper = document.getElementById("resume-wrapper");
            const resumeAgencySelect = document.getElementById("resume-agency-select");
            const btnResumeAction = document.getElementById("btn-resume");

            if (resumeWrapper && resumeAgencySelect) {
                resumeWrapper.style.display = "inline-flex";
                if (btnResumeAction) btnResumeAction.disabled = isRunning;

                const prevVal = resumeAgencySelect.value;
                const options = [];

                if (resumableDeptNames.size > 1) {
                    options.push({ value: "all", label: "All Interrupted Agencies" });
                }

                Object.keys(deptCodeMap).forEach(dName => {
                    const shortName = dName.replace("Department of ", "");
                    const cp = checkpoints[dName];
                    const isInterrupted = interruptedDepts.some(d => d.department === dName);
                    let label = shortName;

                    if (cp && cp.page && cp.page > 1) {
                        label += ` (${cp.category ? cp.category + ' ' : ''}p.${cp.page} - Checkpoint)`;
                    } else if (cp && cp.category) {
                        label += ` (${cp.category} - Checkpoint)`;
                    } else if (isInterrupted) {
                        label += ` (Interrupted)`;
                    } else {
                        label += ` (Continue / Resume)`;
                    }
                    options.push({ value: dName, label: label });
                });

                const currentOptionsKey = options.map(o => `${o.value}:${o.label}`).join("|");
                if (resumeAgencySelect.dataset.optionsKey !== currentOptionsKey) {
                    resumeAgencySelect.innerHTML = "";
                    options.forEach(opt => {
                        const optEl = document.createElement("option");
                        optEl.value = opt.value;
                        optEl.textContent = opt.label;
                        resumeAgencySelect.appendChild(optEl);
                    });
                    resumeAgencySelect.dataset.optionsKey = currentOptionsKey;

                    const selectedRadio = document.querySelector('input[name="dept-select"]:checked');
                    if (selectedRadio && options.some(o => o.value === selectedRadio.value)) {
                        resumeAgencySelect.value = selectedRadio.value;
                    } else if (prevVal && options.some(o => o.value === prevVal)) {
                        resumeAgencySelect.value = prevVal;
                    }
                }
            }

            // Progress Banner handling
            if (prog && prog.is_running) {
                progressCard.style.display = "block";
                globalSystemStatus.textContent = "Running";
                globalSystemStatus.className = "stat-value";
                const deptCount = (prog.active_departments && prog.active_departments.length) || 1;
                progressStatusTitle.textContent = deptCount > 1
                    ? `Extracting ${deptCount} Agencies in Parallel...`
                    : `Extracting: ${prog.department || 'Processing'}...`;
                progressMessage.textContent = prog.message || "Extraction active in background.";
                progDept.textContent = prog.department || "-";
                progCat.textContent = prog.category || "-";
                progPage.textContent = prog.current_page || "-";
                progTotalPages.textContent = prog.total_pages || "-";
                progRecords.textContent = (prog.records_collected || 0).toLocaleString();
            } else {
                if (progressCard.style.display !== "none" && prog && prog.status !== "Running") {
                    // Just finished
                    progressStatusTitle.textContent = `Status: ${prog.status}`;
                    progressMessage.textContent = prog.message || "Process completed.";
                    setTimeout(() => {
                        progressCard.style.display = "none";
                    }, 4000);
                    loadRecords();
                }
                globalSystemStatus.textContent = prog ? prog.status : "Idle";
            }
        } catch (err) {
            console.error("Status polling error:", err);
        }
    }

    // Load records table
    async function loadRecords() {
        const dept = tableFilterDept.value;
        const year = tableFilterYear.value.trim();
        const search = tableSearch.value.trim();

        const params = new URLSearchParams({
            page: currentPage,
            page_size: pageSize
        });
        if (dept) params.append("department", dept);
        if (year) params.append("year", year);
        if (search) params.append("search", search);

        try {
            const res = await fetch(`/api/records?${params.toString()}`);
            const data = await res.json();

            issuancesTbody.innerHTML = "";
            if (data.records.length === 0) {
                issuancesTbody.innerHTML = `
                    <tr>
                        <td colspan="7" class="text-center text-muted" style="padding: 30px;">
                            No records found matching filters.
                        </td>
                    </tr>
                `;
            } else {
                data.records.forEach((rec, idx) => {
                    const row = document.createElement("tr");
                    const rowNum = (data.page - 1) * data.page_size + idx + 1;
                    const dateFormatted = rec.publication_date || "-";
                    const numFormatted = rec.issuance_number || '<span class="text-muted">Unnumbered</span>';
                    const linkMarkup = rec.source_url
                        ? `<a href="${rec.source_url}" target="_blank" class="dept-link">View &nearr;</a>`
                        : '<span class="text-muted">-</span>';

                    row.innerHTML = `
                        <td>${rowNum}</td>
                        <td><strong>${escapeHtml(rec.department)}</strong></td>
                        <td>${escapeHtml(rec.category)}</td>
                        <td><code>${escapeHtml(numFormatted)}</code></td>
                        <td>${escapeHtml(rec.title)}</td>
                        <td>${escapeHtml(dateFormatted)}</td>
                        <td>${linkMarkup}</td>
                    `;
                    issuancesTbody.appendChild(row);
                });
            }

            // Pagination UI
            pageSummary.textContent = `Showing ${(data.records.length > 0 ? (data.page - 1) * data.page_size + 1 : 0)} - ${(data.page - 1) * data.page_size + data.records.length} of ${data.total_count} records`;
            pageCurrent.textContent = `Page ${data.page} of ${data.total_pages}`;
            pagePrev.disabled = (data.page <= 1);
            pageNext.disabled = (data.page >= data.total_pages);

        } catch (err) {
            console.error("Error loading records:", err);
        }
    }

    function escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Helper: Collect categories for a department
    function getSelectedCategories(deptCode) {
        const checkboxes = document.querySelectorAll(`.cat-cb-${deptCode}:checked`);
        return Array.from(checkboxes).map(cb => cb.value);
    }

    // Start extraction trigger
    async function triggerExtraction(departmentsList) {
        const yearFilter = document.getElementById("filter-year").value;
        const maxPages = document.getElementById("filter-max-pages").value;

        const catMap = {};
        const codeMap = {
            "Department of Agriculture": "DA",
            "Department of Health": "DOH",
            "Department of Environment and Natural Resources": "DENR",
            "Department of Education": "DepEd"
        };

        for (const d of departmentsList) {
            const code = codeMap[d];
            if (code) {
                catMap[d] = getSelectedCategories(code);
            }
        }

        try {
            const res = await fetch("/api/extract", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    departments: departmentsList,
                    categories: catMap,
                    year: yearFilter,
                    max_pages: maxPages || null
                })
            });
            const data = await res.json();
            if (res.ok) {
                showToast(data.message);
                progressCard.style.display = "block";
            } else {
                showToast(data.message || "Failed to start extraction");
            }
        } catch (err) {
            showToast("Network error starting extraction");
        }
    }

    // Button Listeners
    btnExtractAll.addEventListener("click", () => {
        triggerExtraction([
            "Department of Agriculture",
            "Department of Education",
            "Department of Health",
            "Department of Environment and Natural Resources"
        ]);
    });

    btnExtractSelected.addEventListener("click", () => {
        const selectedRadio = document.querySelector('input[name="dept-select"]:checked');
        if (!selectedRadio) {
            alert("Please select a department radio option first.");
            return;
        }
        triggerExtraction([selectedRadio.value]);
    });

    async function resumeAgency(dept) {
        const yearEl = document.getElementById("filter-year");
        const maxPagesEl = document.getElementById("filter-max-pages");
        const year = yearEl ? yearEl.value.trim() : "";
        const maxPages = maxPagesEl ? maxPagesEl.value.trim() : "";

        const payload = {
            year: year,
            max_pages: maxPages ? parseInt(maxPages, 10) : null
        };
        if (dept && dept !== "all") {
            payload.department = dept;
        }

        try {
            const res = await fetch("/api/resume", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success) {
                showToast(data.message || "Resuming extraction...");
                pollStatus();
            } else {
                showToast(data.message || "Could not resume.", 4000);
            }
        } catch (err) {
            showToast("Failed to resume extraction: " + err, 4000);
        }
    }

    const btnResumeAction = document.getElementById("btn-resume");
    if (btnResumeAction) {
        btnResumeAction.addEventListener("click", async () => {
            btnResumeAction.disabled = true;
            try {
                const agencySelect = document.getElementById("resume-agency-select");
                const dept = agencySelect ? agencySelect.value : null;
                await resumeAgency(dept);
            } finally {
                btnResumeAction.disabled = false;
            }
        });
    }

    // Individual Department Card "Resume [DEPT]" buttons
    document.querySelectorAll(".resume-single-btn").forEach(btn => {
        btn.addEventListener("click", async (e) => {
            const dept = e.currentTarget.getAttribute("data-dept");
            if (dept) {
                e.currentTarget.disabled = true;
                try {
                    await resumeAgency(dept);
                } finally {
                    e.currentTarget.disabled = false;
                }
            }
        });
    });

    // Auto-select in resume dropdown when a department radio button is selected
    document.querySelectorAll('input[name="dept-select"]').forEach(radio => {
        radio.addEventListener("change", () => {
            const agencySelect = document.getElementById("resume-agency-select");
            if (agencySelect) {
                for (let i = 0; i < agencySelect.options.length; i++) {
                    if (agencySelect.options[i].value === radio.value) {
                        agencySelect.selectedIndex = i;
                        break;
                    }
                }
            }
        });
    });

    document.querySelectorAll(".extract-single-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            const dept = e.target.getAttribute("data-dept");
            if (dept) triggerExtraction([dept]);
        });
    });

    btnStopExtraction.addEventListener("click", async () => {
        try {
            const res = await fetch("/api/stop", { method: "POST" });
            const data = await res.json();
            showToast(data.message);
        } catch (err) {
            showToast("Error stopping extraction");
        }
    });

    btnCleanupDuplicates.addEventListener("click", async () => {
        if (!confirm("Scrub and deduplicate records across all departments?")) return;
        try {
            const res = await fetch("/api/records/cleanup-duplicates", { method: "POST" });
            const data = await res.json();
            showToast(data.message);
            loadRecords();
            pollStatus();
        } catch (err) {
            showToast("Error cleaning duplicates");
        }
    });

    btnClearRecords.addEventListener("click", async () => {
        if (!confirm("Are you sure you want to delete all extracted records from the local database?")) return;
        try {
            const res = await fetch("/api/records/delete", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({})
            });
            const data = await res.json();
            showToast(data.message);
            currentPage = 1;
            loadRecords();
            pollStatus();
        } catch (err) {
            showToast("Error deleting records");
        }
    });

    btnRetryFailed.addEventListener("click", async () => {
        try {
            const res = await fetch("/api/failed-pages");
            const data = await res.json();
            if (data.failed_pages.length === 0) {
                showToast("No failed pages on record.");
                return;
            }
            const deptsToRetry = Array.from(new Set(data.failed_pages.map(f => f.department)));
            showToast(`Retrying failed pages for: ${deptsToRetry.join(", ")}`);
            triggerExtraction(deptsToRetry);
        } catch (err) {
            showToast("Error checking failed pages");
        }
    });

    // Department abbreviation mapping for concise labels
    const deptAbbrMap = {
        "Department of Agriculture": "DA",
        "Department of Health": "DOH",
        "Department of Environment and Natural Resources": "DENR",
        "Department of Education": "DepEd"
    };

    function updateExportButtonLabels() {
        const selectedDept = (exportDeptSelect ? exportDeptSelect.value : "") || (tableFilterDept ? tableFilterDept.value : "");
        const abbr = deptAbbrMap[selectedDept] || (selectedDept ? selectedDept.substring(0, 15) : "");
        if (btnExportWordText) {
            btnExportWordText.textContent = abbr ? `Export ${abbr} (.docx)` : "Export Word (.docx)";
        }
        if (btnExportExcelText) {
            btnExportExcelText.textContent = abbr ? `Export ${abbr} (.xlsx)` : "Export Excel (.xlsx)";
        }
    }

    // Export Handler
    async function triggerExport(format, departmentOverride = null) {
        const dept = (departmentOverride !== null)
            ? departmentOverride
            : ((exportDeptSelect && exportDeptSelect.value) || (tableFilterDept && tableFilterDept.value) || "");

        const year = (departmentOverride === null && tableFilterYear) ? tableFilterYear.value.trim() : "";
        const search = (departmentOverride === null && tableSearch) ? tableSearch.value.trim() : "";

        // Pre-validate record availability to provide clear feedback
        const checkParams = new URLSearchParams({ page: 1, page_size: 1 });
        if (dept) checkParams.append("department", dept);
        if (year) checkParams.append("year", year);
        if (search) checkParams.append("search", search);

        try {
            const checkRes = await fetch(`/api/records?${checkParams.toString()}`);
            if (checkRes.ok) {
                const checkData = await checkRes.json();
                if (checkData.total_count === 0) {
                    const targetName = dept ? (deptAbbrMap[dept] || dept) : "selected filters";
                    showToast(`No records found for ${targetName} to export.`);
                    return;
                }
            }
        } catch (e) {
            console.warn("Count check failed before export:", e);
        }

        const exportParams = new URLSearchParams();
        if (dept) exportParams.append("department", dept);
        if (year) exportParams.append("year", year);
        if (search) exportParams.append("search", search);

        const qs = exportParams.toString();
        const downloadUrl = `/api/export/${encodeURIComponent(format)}${qs ? '?' + qs : ''}`;
        
        const labelDept = dept ? (deptAbbrMap[dept] || dept) : "All Departments";
        showToast(`Generating ${format.toUpperCase()} export for ${labelDept}...`);

        const link = document.createElement("a");
        link.href = downloadUrl;
        link.setAttribute("download", "");
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    // Export Buttons Click Listeners
    document.querySelectorAll(".export-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const fmt = btn.getAttribute("data-format");
            if (fmt) triggerExport(fmt);
        });
    });

    // Department Card Dropdown Triggers
    document.querySelectorAll(".dept-export-trigger").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const parentDropdown = btn.closest(".dept-export-dropdown");
            const menu = parentDropdown ? parentDropdown.querySelector(".dept-export-menu") : null;
            if (menu) {
                // Close all other open dropdown menus first
                document.querySelectorAll(".dept-export-menu.show").forEach(m => {
                    if (m !== menu) m.classList.remove("show");
                });
                menu.classList.toggle("show");
            }
        });
    });

    // Department Card Export Action Items
    document.querySelectorAll(".export-action-item").forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            e.stopPropagation();
            const dept = item.getAttribute("data-dept");
            const fmt = item.getAttribute("data-format");
            const menu = item.closest(".dept-export-menu");
            if (menu) menu.classList.remove("show");
            if (dept && fmt) triggerExport(fmt, dept);
        });
    });

    // Close any open dropdowns when clicking outside
    document.addEventListener("click", () => {
        document.querySelectorAll(".dept-export-menu.show").forEach(m => m.classList.remove("show"));
    });

    // Export department select change
    if (exportDeptSelect) {
        exportDeptSelect.addEventListener("change", () => {
            if (tableFilterDept) {
                tableFilterDept.value = exportDeptSelect.value;
            }
            updateExportButtonLabels();
            currentPage = 1;
            loadRecords();
        });
    }

    // Table filter department change sync
    if (tableFilterDept) {
        tableFilterDept.addEventListener("change", () => {
            if (exportDeptSelect) {
                exportDeptSelect.value = tableFilterDept.value;
            }
            updateExportButtonLabels();
        });
    }

    // Filters and Pagination
    btnApplyFilters.addEventListener("click", () => {
        currentPage = 1;
        loadRecords();
    });

    btnResetFilters.addEventListener("click", () => {
        tableSearch.value = "";
        tableFilterDept.value = "";
        tableFilterYear.value = "";
        if (exportDeptSelect) {
            exportDeptSelect.value = "";
        }
        updateExportButtonLabels();
        currentPage = 1;
        loadRecords();
    });

    pagePrev.addEventListener("click", () => {
        if (currentPage > 1) {
            currentPage--;
            loadRecords();
        }
    });

    pageNext.addEventListener("click", () => {
        currentPage++;
        loadRecords();
    });

    // Manual Modal logic
    btnManualUrl.addEventListener("click", () => {
        modalManual.style.display = "flex";
        manualPreviewSection.style.display = "none";
        previewedManualRecords = [];
    });

    modalManualClose.addEventListener("click", () => {
        modalManual.style.display = "none";
    });

    window.addEventListener("click", (e) => {
        if (e.target === modalManual) {
            modalManual.style.display = "none";
        }
    });

    btnManualAnalyze.addEventListener("click", async () => {
        const urlVal = manualUrlInput.value.trim();
        const htmlVal = manualHtmlInput.value.trim();
        const deptVal = manualDept.value;
        const catVal = manualCat.value.trim() || "General Issuances";

        if (!urlVal && !htmlVal) {
            alert("Please provide either a Webpage URL or paste HTML source.");
            return;
        }

        btnManualAnalyze.disabled = true;
        btnManualAnalyze.textContent = "Analyzing structure...";

        try {
            const res = await fetch("/api/manual-url/preview", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    url: urlVal,
                    html: htmlVal,
                    department: deptVal,
                    category: catVal
                })
            });
            const data = await res.json();
            btnManualAnalyze.disabled = false;
            btnManualAnalyze.textContent = "Analyze & Preview Structure";

            if (!data.success) {
                alert("Extraction failed: " + data.error);
                return;
            }

            previewedManualRecords = data.records;
            manualPreviewSection.style.display = "block";
            manualStructInfo.innerHTML = `<strong>Detected Structure:</strong> ${data.structure} | <strong>Records Found:</strong> ${data.total_found}`;

            manualPreviewTbody.innerHTML = "";
            data.records.slice(0, 10).forEach(r => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td>${escapeHtml(r.issuance_number || '-')}</td>
                    <td>${escapeHtml(r.title)}</td>
                    <td>${escapeHtml(r.publication_date || '-')}</td>
                    <td><a href="${r.source_url}" target="_blank">Link</a></td>
                `;
                manualPreviewTbody.appendChild(tr);
            });

            if (data.records.length > 10) {
                const tr = document.createElement("tr");
                tr.innerHTML = `<td colspan="4" class="text-center text-muted">... and ${data.records.length - 10} more records ready for import.</td>`;
                manualPreviewTbody.appendChild(tr);
            }
        } catch (err) {
            btnManualAnalyze.disabled = false;
            btnManualAnalyze.textContent = "Analyze & Preview Structure";
            alert("Error analyzing content: " + err.message);
        }
    });

    btnManualSave.addEventListener("click", async () => {
        if (previewedManualRecords.length === 0) return;
        btnManualSave.disabled = true;
        btnManualSave.textContent = "Saving...";

        try {
            const res = await fetch("/api/manual-url/save", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ records: previewedManualRecords })
            });
            const data = await res.json();
            btnManualSave.disabled = false;
            btnManualSave.textContent = "Approve & Save Records";

            if (res.ok) {
                showToast(data.message);
                modalManual.style.display = "none";
                manualUrlInput.value = "";
                manualHtmlInput.value = "";
                loadRecords();
                pollStatus();
            } else {
                alert("Failed to save: " + data.message);
            }
        } catch (err) {
            btnManualSave.disabled = false;
            btnManualSave.textContent = "Approve & Save Records";
            alert("Error saving records: " + err.message);
        }
    });

    // Validation & Reconciliation Modal Logic
    if (btnValidateRecords) {
        btnValidateRecords.addEventListener("click", () => {
            if (btnValidateRecords.disabled) {
                return;
            }
            modalValidate.style.display = "flex";
            loadValidationReport();
            loadQuarantineLogs();
        });
    }

    if (modalValidateClose) {
        modalValidateClose.addEventListener("click", () => {
            modalValidate.style.display = "none";
        });
    }

    window.addEventListener("click", (e) => {
        if (e.target === modalValidate) {
            modalValidate.style.display = "none";
        }
    });

    if (tabBtnPortal && tabBtnQuarantine) {
        tabBtnPortal.addEventListener("click", () => {
            if (panelPortal) panelPortal.style.display = "block";
            if (panelQuarantine) panelQuarantine.style.display = "none";
            tabBtnPortal.style.borderBottom = "2px solid var(--primary, #38bdf8)";
            tabBtnQuarantine.style.borderBottom = "none";
        });

        tabBtnQuarantine.addEventListener("click", () => {
            if (panelPortal) panelPortal.style.display = "none";
            if (panelQuarantine) panelQuarantine.style.display = "block";
            tabBtnQuarantine.style.borderBottom = "2px solid var(--primary, #38bdf8)";
            tabBtnPortal.style.borderBottom = "none";
            loadQuarantineLogs();
        });
    }

    async function fetchQuarantineSummary() {
        if (btnValidateRecords && btnValidateRecords.disabled) {
            if (quarantineBadge) quarantineBadge.style.display = "none";
            return;
        }
        try {
            const res = await fetch("/api/quarantine?status=Pending");
            const data = await res.json();
            if (data.success) {
                const count = data.count || 0;
                if (quarantineBadge) {
                    quarantineBadge.textContent = count;
                    quarantineBadge.style.display = count > 0 ? "inline-flex" : "none";
                }
                if (valQuarantineTabCount) {
                    valQuarantineTabCount.textContent = count;
                }
                if (valDetectedGaps) {
                    valDetectedGaps.textContent = count;
                }
            }
        } catch (err) {
            console.warn("Could not load quarantine summary badge:", err);
        }
    }

    function extractSearchKeyword(log) {
        const details = log.details || "";
        // 1. Missing issuance number: <number>
        const mNum = details.match(/Missing issuance number:\s*([^\s,;]+)/i);
        if (mNum) {
            return {
                keyword: mNum[1].trim(),
                fullQuery: `${log.category || ""} ${mNum[1].trim()}`.trim()
            };
        }
        // 2. Doc ID: <id>
        const mDoc = details.match(/Doc ID:\s*([^\s,;]+)/i);
        if (mDoc) {
            return {
                keyword: `Doc ID ${mDoc[1].trim()}`,
                fullQuery: `${log.category || ""} ${mDoc[1].trim()}`.trim()
            };
        }
        // 3. Number pattern like 2026-0003 or plain number
        const mCode = details.match(/\b(20\d{2}-\d{1,5}|\d{1,5})\b/);
        if (mCode) {
            return {
                keyword: mCode[1].trim(),
                fullQuery: `${log.category || ""} ${mCode[1].trim()}`.trim()
            };
        }
        // 4. Default: category name or department
        const fallback = (log.category || log.department || "Issuance").trim();
        return {
            keyword: fallback,
            fullQuery: fallback
        };
    }

    function buildGoogleSearchUrl(department, category, keyword, details) {
        const agencyDomains = {
            "Department of Health": "doh.gov.ph",
            "Department of Agriculture": "da.gov.ph",
            "Department of Education": "deped.gov.ph",
            "Department of Environment and Natural Resources": "denr.gov.ph"
        };
        const domain = agencyDomains[department] || "gov.ph";

        // Category singular cleaning
        let cleanCat = (category || "").trim();
        if (cleanCat.endsWith("s") && !cleanCat.endsWith("ies")) {
            cleanCat = cleanCat.slice(0, -1);
        } else if (cleanCat.endsWith("ies")) {
            cleanCat = cleanCat.slice(0, -3) + "y";
        }

        const cleanNum = (keyword || "").replace(/^Doc ID\s*/i, "").trim();
        const yearMatch = (details || "").match(/\b(20\d{2}|19\d{2})\b/) || cleanNum.match(/\b(20\d{2}|19\d{2})\b/);
        const yearQuery = yearMatch ? `"${yearMatch[1]}"` : "";

        // Build Google query with special operators:
        // - site:domain OR site:officialgazette.gov.ph (restricts to verified government portals)
        // - filetype:pdf (targets signed official issuance PDFs directly)
        // - exact quotes for category and number
        let queryParts = [
            `site:${domain} OR site:officialgazette.gov.ph`,
            `filetype:pdf`
        ];
        if (cleanCat) {
            queryParts.push(`"${cleanCat}"`);
        }
        if (cleanNum) {
            queryParts.push(`"${cleanNum}"`);
        }
        if (yearQuery && !cleanNum.includes(yearMatch[1])) {
            queryParts.push(yearQuery);
        }

        return `https://www.google.com/search?q=${encodeURIComponent(queryParts.join(" "))}`;
    }

    function renderQuarantineTable(logs) {
        if (!valQuarantineTbody) return;
        valQuarantineTbody.innerHTML = "";

        const query = (quarantineSearchInput ? quarantineSearchInput.value : "").trim().toLowerCase();
        const filtered = query
            ? logs.filter(log => {
                const kwInfo = extractSearchKeyword(log);
                const str = `${log.department} ${log.category} ${log.issue_type} ${log.details} ${kwInfo.keyword} ${kwInfo.fullQuery}`.toLowerCase();
                return str.includes(query);
            })
            : logs;

        if (quarantineFilterCount) {
            if (query) {
                quarantineFilterCount.textContent = `Showing ${filtered.length} of ${logs.length} logs`;
            } else {
                quarantineFilterCount.textContent = `${logs.length} pending items`;
            }
        }
        if (quarantineSearchClear) {
            quarantineSearchClear.style.display = query ? "inline-block" : "none";
        }

        if (filtered.length === 0) {
            valQuarantineTbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted, #94a3b8);">${query ? "No quarantine records match your search." : "No pending quarantine records. All extractions meet provenance standards."}</td></tr>`;
            return;
        }

        filtered.forEach(log => {
            const tr = document.createElement("tr");
            const kwInfo = extractSearchKeyword(log);
            const googleSearchUrl = buildGoogleSearchUrl(log.department, log.category, kwInfo.keyword, log.details);

            tr.innerHTML = `
                <td style="font-size: 0.8rem; color: var(--text-muted, #94a3b8); white-space: nowrap;">${log.created_at || "-"}</td>
                <td><strong>${escapeHtml(log.department)}</strong><br><span style="font-size: 0.8rem; color: var(--text-muted, #94a3b8);">${escapeHtml(log.category)}</span></td>
                <td><span class="badge-issue-type">${escapeHtml(log.issue_type)}</span></td>
                <td style="font-size: 0.82rem; word-break: break-word;">${escapeHtml(log.details)}</td>
                <td>
                    <div class="search-ready-cell">
                        <div class="drag-keyword-badge" draggable="true" title="Drag to any search input or click to copy" data-keyword="${escapeHtml(kwInfo.keyword)}" data-query="${escapeHtml(kwInfo.fullQuery)}">
                            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" class="drag-grip-icon" aria-hidden="true"><circle cx="9" cy="6" r="1.5"/><circle cx="9" cy="12" r="1.5"/><circle cx="9" cy="18" r="1.5"/><circle cx="15" cy="6" r="1.5"/><circle cx="15" cy="12" r="1.5"/><circle cx="15" cy="18" r="1.5"/></svg>
                            <span class="keyword-text">${escapeHtml(kwInfo.keyword)}</span>
                        </div>
                        <a href="${googleSearchUrl}" target="_blank" rel="noopener noreferrer" class="btn-quick-portal" title="Search official PDF on ${escapeHtml(log.department)} & Official Gazette via Google">
                            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                            <span>Google PDF</span>
                        </a>
                    </div>
                </td>
                <td style="text-align: center;">
                    <div class="quarantine-actions">
                        <button class="btn-paste-quarantine" data-id="${log.id}" data-dept="${escapeHtml(log.department)}" data-cat="${escapeHtml(log.category)}" data-url="${escapeHtml(log.source_url || '')}" data-details="${escapeHtml(log.details || '')}" type="button" title="Paste screen text & validate before saving">Paste & Review</button>
                        <button class="btn-resolve-quarantine" data-id="${log.id}" data-action="Resolved" type="button" title="Mark as resolved">Mark Resolved</button>
                        <button class="btn-ignore-quarantine" data-id="${log.id}" data-action="Ignored" type="button" title="Ignore this quarantine entry">Ignore</button>
                    </div>
                </td>
            `;
            valQuarantineTbody.appendChild(tr);
        });

        // Setup drag events on all keyword badges
        valQuarantineTbody.querySelectorAll(".drag-keyword-badge").forEach(badge => {
            badge.addEventListener("dragstart", (e) => {
                const kw = badge.getAttribute("data-keyword");
                const query = badge.getAttribute("data-query");
                badge.classList.add("dragging");
                e.dataTransfer.setData("text/plain", kw);
                e.dataTransfer.setData("text/search-query", query);
                e.dataTransfer.effectAllowed = "copyMove";
            });

            badge.addEventListener("dragend", () => {
                badge.classList.remove("dragging");
            });

            // Click to copy
            badge.addEventListener("click", () => {
                const kw = badge.getAttribute("data-keyword");
                navigator.clipboard.writeText(kw).then(() => {
                    showToast(`Copied keyword: "${kw}"`);
                }).catch(() => {
                    showToast(`Keyword: ${kw}`);
                });
            });
        });

        // Paste & Review button
        valQuarantineTbody.querySelectorAll(".btn-paste-quarantine").forEach(btn => {
            btn.addEventListener("click", () => {
                const log = {
                    id: btn.getAttribute("data-id"),
                    department: btn.getAttribute("data-dept"),
                    category: btn.getAttribute("data-cat"),
                    source_url: btn.getAttribute("data-url"),
                    details: btn.getAttribute("data-details")
                };
                openPasteModal(log);
            });
        });

        // Resolve & Ignore buttons
        valQuarantineTbody.querySelectorAll(".btn-resolve-quarantine, .btn-ignore-quarantine").forEach(btn => {
            btn.addEventListener("click", async (e) => {
                const id = e.target.getAttribute("data-id");
                const action = e.target.getAttribute("data-action");
                await resolveQuarantineItem(id, action);
            });
        });
    }

    async function loadQuarantineLogs() {
        if (!valQuarantineTbody) return;
        try {
            const res = await fetch("/api/quarantine?status=Pending");
            const data = await res.json();
            if (!data.success) {
                valQuarantineTbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--status-danger-text, #ef4444);">Failed to load quarantine logs.</td></tr>`;
                return;
            }

            const logs = data.logs || [];
            currentQuarantineLogs = logs;
            const count = logs.length;
            if (quarantineBadge) {
                quarantineBadge.textContent = count;
                quarantineBadge.style.display = count > 0 ? "inline-flex" : "none";
            }
            if (valQuarantineTabCount) {
                valQuarantineTabCount.textContent = count;
            }
            if (valDetectedGaps) {
                valDetectedGaps.textContent = count;
            }

            renderQuarantineTable(currentQuarantineLogs);

        } catch (err) {
            valQuarantineTbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted, #94a3b8);">Error loading quarantine: ${err.message}</td></tr>`;
        }
    }

    async function resolveQuarantineItem(logId, status) {
        try {
            const res = await fetch(`/api/quarantine/${logId}/resolve`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ status })
            });
            const data = await res.json();
            if (data.success) {
                showToast(data.message || `Quarantine entry #${logId} marked as ${status}.`);
                loadQuarantineLogs();
                fetchQuarantineSummary();
            } else {
                showToast("Action failed: " + (data.message || "Unknown error"));
            }
        } catch (err) {
            showToast("Error updating quarantine log: " + err.message);
        }
    }

    async function loadValidationReport() {
        if (!valPortalTbody) return;
        btnRunValidation.disabled = true;
        btnRunValidation.textContent = "Auditing live portals...";

        try {
            const res = await fetch("/api/validate");
            const data = await res.json();
            btnRunValidation.disabled = false;
            btnRunValidation.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg> <span>Re-scan Portals & Audit</span>`;

            if (!data.success) {
                showToast("Validation check failed: " + (data.error || "Unknown error"));
                valPortalTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted, #94a3b8);">${escapeHtml(data.error || "Validation check failed.")}</td></tr>`;
                return;
            }

            const r = data.report;
            valIntegrityScore.textContent = r.integrity_score || "100%";
            valTotalRecords.textContent = (r.total_records || 0).toLocaleString();
            valDetectedGaps.textContent = r.quality_metrics.pending_quarantine_count || r.quality_metrics.detected_gaps_count || 0;
            valFailedPages.textContent = r.quality_metrics.failed_pages_count || 0;
            valLastChecked.textContent = `Audited: ${r.timestamp}`;

            // Populate Portal Sync Table
            valPortalTbody.innerHTML = "";
            let hasPortalRows = false;

            (r.portal_reconciliation || []).forEach(dept => {
                (dept.categories || []).forEach(cat => {
                    hasPortalRows = true;
                    const tr = document.createElement("tr");

                    let badgeClass = "badge-completed";
                    if (cat.status === "New Records Available") badgeClass = "badge-running";
                    else if (cat.status === "Pending Extraction") badgeClass = "badge-idle";
                    else if (cat.status !== "In Sync") badgeClass = "badge-inaccessible";

                    tr.innerHTML = `
                        <td>
                            <strong>${dept.code}</strong> - ${cat.category}
                        </td>
                        <td><strong>${(cat.stored_records || 0).toLocaleString()}</strong></td>
                        <td>${cat.latest_portal_issuance || 'None'}</td>
                        <td>${cat.latest_portal_date || '-'}</td>
                        <td><span class="dept-badge ${badgeClass}">${cat.status}</span></td>
                    `;
                    valPortalTbody.appendChild(tr);
                });
            });

            if (!hasPortalRows) {
                valPortalTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted, #94a3b8);">No live portal reconciliation data available.</td></tr>`;
            }

            // Also reload quarantine logs
            loadQuarantineLogs();

        } catch (err) {
            btnRunValidation.disabled = false;
            btnRunValidation.textContent = "Re-scan Portals & Audit";
            showToast("Error running validation: " + err.message);
        }
    }

    if (btnRunValidation) {
        btnRunValidation.addEventListener("click", loadValidationReport);
    }

    if (btnReconcileBackfill) {
        btnReconcileBackfill.addEventListener("click", async () => {
            btnReconcileBackfill.disabled = true;
            btnReconcileBackfill.textContent = "Reconciling & backfilling...";

            try {
                const res = await fetch("/api/reconcile", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({})
                });
                const data = await res.json();
                btnReconcileBackfill.disabled = false;
                btnReconcileBackfill.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg> <span>Reconcile & Backfill Missing</span>`;

                if (data.success) {
                    showToast(data.message);
                    loadValidationReport();
                    loadRecords();
                    pollStatus();
                } else {
                    alert("Reconciliation failed: " + (data.error || "Unknown error"));
                }
            } catch (err) {
                btnReconcileBackfill.disabled = false;
                btnReconcileBackfill.textContent = "Reconcile & Backfill Missing";
                alert("Error during reconciliation: " + err.message);
            }
        });
    }

    // Quarantine Search Input & Drag-and-Drop Handlers
    if (quarantineSearchInput) {
        quarantineSearchInput.addEventListener("input", () => {
            renderQuarantineTable(currentQuarantineLogs);
        });

        quarantineSearchInput.addEventListener("dragover", (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = "copy";
            quarantineSearchInput.classList.add("drop-active");
        });

        quarantineSearchInput.addEventListener("dragleave", () => {
            quarantineSearchInput.classList.remove("drop-active");
        });

        quarantineSearchInput.addEventListener("drop", (e) => {
            e.preventDefault();
            quarantineSearchInput.classList.remove("drop-active");
            const droppedText = e.dataTransfer.getData("text/plain");
            if (droppedText) {
                quarantineSearchInput.value = droppedText;
                renderQuarantineTable(currentQuarantineLogs);
                quarantineSearchInput.focus();
                showToast(`Filtered quarantine by: "${droppedText}"`);
            }
        });
    }

    if (quarantineSearchClear) {
        quarantineSearchClear.addEventListener("click", () => {
            if (quarantineSearchInput) {
                quarantineSearchInput.value = "";
                renderQuarantineTable(currentQuarantineLogs);
                quarantineSearchInput.focus();
            }
        });
    }

    // Enable drag & drop target on Main Database table search input
    const tableSearchInput = document.getElementById("table-search");
    if (tableSearchInput) {
        tableSearchInput.addEventListener("dragover", (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = "copy";
            tableSearchInput.style.borderColor = "var(--border-focus, #1d4ed8)";
        });

        tableSearchInput.addEventListener("dragleave", () => {
            tableSearchInput.style.borderColor = "";
        });

        tableSearchInput.addEventListener("drop", (e) => {
            e.preventDefault();
            tableSearchInput.style.borderColor = "";
            const droppedText = e.dataTransfer.getData("text/plain");
            if (droppedText) {
                tableSearchInput.value = droppedText;
                currentPage = 1;
                loadRecords();
                tableSearchInput.focus();
                showToast(`Searching database for: "${droppedText}"`);
            }
        });
    }

    // Modal: Paste & Validate Quarantine Resolution Logic
    const modalPasteResolve = document.getElementById("modal-paste-resolve");
    const modalPasteClose = document.getElementById("modal-paste-close");
    const btnPasteCancel = document.getElementById("btn-paste-cancel");
    const pasteQuarantineId = document.getElementById("paste-quarantine-id");
    const pasteDeptInput = document.getElementById("paste-dept-input");
    const pasteCatInput = document.getElementById("paste-cat-input");
    const pasteUrlInput = document.getElementById("paste-url-input");
    const pasteOpenUrlBtn = document.getElementById("paste-open-url-btn");
    const pasteScreenText = document.getElementById("paste-screen-text");
    const btnParseScreenText = document.getElementById("btn-parse-screen-text");
    const btnClearPasteText = document.getElementById("btn-clear-paste-text");
    const pasteParseStatus = document.getElementById("paste-parse-status");
    const pasteValidationSection = document.getElementById("paste-validation-section");
    const pasteRecordCount = document.getElementById("paste-record-count");
    const btnAddPreviewRow = document.getElementById("btn-add-preview-row");
    const pastePreviewTbody = document.getElementById("paste-preview-tbody");
    const btnPasteConfirmSave = document.getElementById("btn-paste-confirm-save");
    const pasteSaveResult = document.getElementById("paste-save-result");
    const pasteModalSubtitle = document.getElementById("paste-modal-subtitle");

    function openPasteModal(log) {
        if (!modalPasteResolve) return;
        pasteQuarantineId.value = log.id || "";
        pasteDeptInput.value = log.department || "";
        pasteCatInput.value = log.category || "";
        pasteUrlInput.value = log.source_url || "";

        if (log.source_url && log.source_url.startsWith("http")) {
            pasteOpenUrlBtn.href = log.source_url;
            pasteOpenUrlBtn.style.display = "inline";
        } else {
            pasteOpenUrlBtn.style.display = "none";
        }

        if (pasteModalSubtitle) {
            pasteModalSubtitle.textContent = `Resolving Log #${log.id} • ${log.department} (${log.category}) • ${log.details || ""}`;
        }

        pasteScreenText.value = "";
        pasteParseStatus.textContent = "";
        pasteSaveResult.textContent = "";
        pastePreviewTbody.innerHTML = "";
        pasteValidationSection.style.display = "none";
        btnPasteConfirmSave.disabled = true;

        modalPasteResolve.style.display = "flex";
        setTimeout(() => pasteScreenText.focus(), 50);
    }

    function closePasteModal() {
        if (modalPasteResolve) {
            modalPasteResolve.style.display = "none";
        }
    }

    function updatePreviewRowCount() {
        if (!pastePreviewTbody) return;
        const rows = pastePreviewTbody.querySelectorAll("tr");
        if (pasteRecordCount) pasteRecordCount.textContent = rows.length;
        if (btnPasteConfirmSave) btnPasteConfirmSave.disabled = (rows.length === 0);
    }

    function addEditablePreviewRow(rec = {}) {
        if (!pastePreviewTbody) return;
        const tr = document.createElement("tr");
        const defaultUrl = pasteUrlInput ? pasteUrlInput.value.trim() : "";
        tr.innerHTML = `
            <td>
                <input type="text" class="paste-cell-input preview-field-num" value="${escapeHtml(rec.issuance_number || "")}" placeholder="e.g. 2026-0014">
            </td>
            <td>
                <input type="text" class="paste-cell-input preview-field-title" value="${escapeHtml(rec.title || "")}" placeholder="Issuance Title / Subject">
            </td>
            <td>
                <input type="text" class="paste-cell-input preview-field-date" value="${escapeHtml(rec.publication_date || "")}" placeholder="YYYY-MM-DD">
            </td>
            <td>
                <input type="url" class="paste-cell-input preview-field-url" value="${escapeHtml(rec.source_url || defaultUrl)}" placeholder="https://...">
            </td>
            <td style="text-align: center;">
                <button type="button" class="btn-del-preview-row" title="Remove this record">&times;</button>
            </td>
        `;
        tr.querySelector(".btn-del-preview-row").addEventListener("click", () => {
            tr.remove();
            updatePreviewRowCount();
        });
        pastePreviewTbody.appendChild(tr);
        updatePreviewRowCount();
    }

    if (modalPasteClose) modalPasteClose.addEventListener("click", closePasteModal);
    if (btnPasteCancel) btnPasteCancel.addEventListener("click", closePasteModal);
    if (btnClearPasteText) {
        btnClearPasteText.addEventListener("click", () => {
            pasteScreenText.value = "";
            pasteScreenText.focus();
        });
    }

    if (btnAddPreviewRow) {
        btnAddPreviewRow.addEventListener("click", () => {
            addEditablePreviewRow();
        });
    }

    if (btnParseScreenText) {
        btnParseScreenText.addEventListener("click", async () => {
            const rawText = pasteScreenText.value.trim();
            if (!rawText) {
                showToast("Please paste copied screen text or table first.");
                pasteScreenText.focus();
                return;
            }

            btnParseScreenText.disabled = true;
            btnParseScreenText.textContent = "Parsing text...";
            pasteParseStatus.textContent = "Analyzing structure...";

            try {
                const res = await fetch("/api/manual-url/preview", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        html: rawText,
                        url: pasteUrlInput.value.trim(),
                        department: pasteDeptInput.value.trim(),
                        category: pasteCatInput.value.trim()
                    })
                });
                const data = await res.json();
                btnParseScreenText.disabled = false;
                btnParseScreenText.textContent = "Parse & Preview Records";

                pastePreviewTbody.innerHTML = "";
                const records = data.records || [];

                if (records.length > 0) {
                    records.forEach(r => addEditablePreviewRow(r));
                    pasteValidationSection.style.display = "block";
                    pasteParseStatus.textContent = `Extracted ${records.length} record(s) via ${data.structure || "text heuristics"}.`;
                    pasteParseStatus.style.color = "var(--status-success-text, #15803d)";
                } else {
                    addEditablePreviewRow({
                        issuance_number: "",
                        title: rawText.split("\n")[0].substring(0, 100),
                        publication_date: "",
                        source_url: pasteUrlInput.value.trim()
                    });
                    pasteValidationSection.style.display = "block";
                    pasteParseStatus.textContent = "A template row was created below. Please check the fields.";
                    pasteParseStatus.style.color = "var(--status-warning-text, #b45309)";
                }
            } catch (err) {
                btnParseScreenText.disabled = false;
                btnParseScreenText.textContent = "Parse & Preview Records";
                pasteParseStatus.textContent = "Error parsing text: " + err.message;
                pasteParseStatus.style.color = "var(--status-danger-text, #b91c1c)";
            }
        });
    }

    if (btnPasteConfirmSave) {
        btnPasteConfirmSave.addEventListener("click", async () => {
            const rows = pastePreviewTbody.querySelectorAll("tr");
            if (rows.length === 0) {
                showToast("No records to save.");
                return;
            }

            const dept = pasteDeptInput.value.trim() || "Manual Import";
            const cat = pasteCatInput.value.trim() || "General Issuances";
            const recordsToSave = [];

            for (const r of rows) {
                const num = r.querySelector(".preview-field-num").value.trim();
                const title = r.querySelector(".preview-field-title").value.trim();
                const date = r.querySelector(".preview-field-date").value.trim();
                const url = r.querySelector(".preview-field-url").value.trim();

                if (!title && !num) continue;
                recordsToSave.push({
                    department: dept,
                    category: cat,
                    issuance_number: num,
                    title: title || num,
                    publication_date: date,
                    source_url: url
                });
            }

            if (recordsToSave.length === 0) {
                showToast("Every record must have at least an Issuance Number or Title.");
                return;
            }

            btnPasteConfirmSave.disabled = true;
            btnPasteConfirmSave.textContent = "Saving to Database...";

            try {
                const res = await fetch("/api/manual-url/save", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        records: recordsToSave,
                        quarantine_id: pasteQuarantineId.value || null
                    })
                });
                const data = await res.json();
                btnPasteConfirmSave.disabled = false;
                btnPasteConfirmSave.textContent = "Confirm & Save to Database";

                if (data.success) {
                    showToast(data.message || `Saved ${recordsToSave.length} record(s) and resolved quarantine!`);
                    closePasteModal();
                    loadQuarantineLogs();
                    fetchQuarantineSummary();
                    loadRecords();
                } else {
                    pasteSaveResult.textContent = "Save failed: " + (data.message || "Unknown error");
                    pasteSaveResult.style.color = "var(--status-danger-text, #b91c1c)";
                }
            } catch (err) {
                btnPasteConfirmSave.disabled = false;
                btnPasteConfirmSave.textContent = "Confirm & Save to Database";
                pasteSaveResult.textContent = "Error saving: " + err.message;
                pasteSaveResult.style.color = "var(--status-danger-text, #b91c1c)";
            }
        });
    }

    // Initial setup
    pollStatus();
    loadRecords();
    fetchQuarantineSummary();
    setInterval(pollStatus, 2000);
});
