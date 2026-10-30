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

            // Update stats
            globalTotalRecords.textContent = data.total_records.toLocaleString();
            failedPagesBadge.textContent = data.failed_pages_count;

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
                    else if (d.status === "Temporarily Inaccessible") badgeEl.classList.add("badge-inaccessible");
                    else if (d.status === "Error") badgeEl.classList.add("badge-error");
                    else badgeEl.classList.add("badge-idle");
                }
            }

            // Progress Banner handling
            const prog = data.progress;
            if (prog && prog.is_running) {
                progressCard.style.display = "block";
                globalSystemStatus.textContent = "Running";
                globalSystemStatus.className = "stat-value";
                progressStatusTitle.textContent = `Extracting: ${prog.department || 'Processing'}...`;
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

    // Initial setup
    pollStatus();
    loadRecords();
    setInterval(pollStatus, 2000);
});
