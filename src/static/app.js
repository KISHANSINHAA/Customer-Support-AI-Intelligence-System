// ==============================================================================
// Support Ticket AI Intelligence System - Frontend Controller
// ==============================================================================

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initQueryConsole();
    initAnomaliesCenter();
    initDatasetExplorer();
    loadAnalyticsKPIs();
});

// ------------------------------------------------------------------------------
// 1. Tab Navigation
// ------------------------------------------------------------------------------
function initTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            const target = btn.getAttribute('data-tab');
            const pane = document.getElementById(target);
            if (pane) pane.classList.add('active');

            if (target === 'tab-anomalies') loadAnomalies();
            if (target === 'tab-tickets') loadTickets(1);
        });
    });
}

// ------------------------------------------------------------------------------
// 2. Natural Language Query Console
// ------------------------------------------------------------------------------
function initQueryConsole() {
    const form = document.getElementById('nlQueryForm');
    const input = document.getElementById('queryInput');
    const submitBtn = document.getElementById('querySubmitBtn');
    const spinner = submitBtn.querySelector('.btn-spinner');
    const btnText = submitBtn.querySelector('.btn-text');

    const resultsArea = document.getElementById('queryResultsArea');
    const summaryText = document.getElementById('querySummaryText');
    const execTiming = document.getElementById('execTimingBadge');
    const sqlCode = document.getElementById('querySqlCode');
    const copySqlBtn = document.getElementById('copySqlBtn');
    const resultsCount = document.getElementById('resultsCountLabel');
    const tableHead = document.getElementById('queryTableHead');
    const tableBody = document.getElementById('queryTableBody');

    // Sample query chips
    document.querySelectorAll('.query-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const query = chip.getAttribute('data-query');
            input.value = query;
            executeQuery(query);
        });
    });

    // Form submit
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const query = input.value.trim();
        if (query) executeQuery(query);
    });

    // Copy SQL button
    copySqlBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(sqlCode.textContent).then(() => {
            copySqlBtn.textContent = 'Copied!';
            setTimeout(() => { copySqlBtn.textContent = 'Copy SQL'; }, 2000);
        });
    });

    async function executeQuery(userQuery) {
        // UI loading state
        submitBtn.disabled = true;
        spinner.classList.remove('hidden');
        btnText.textContent = 'Synthesizing...';
        resultsArea.classList.remove('hidden');
        summaryText.textContent = 'Generating safe SQL and querying database...';
        sqlCode.textContent = '-- Compiling query...';
        tableHead.innerHTML = '';
        tableBody.innerHTML = '<tr><td colspan="10" class="text-center">Query in progress...</td></tr>';

        try {
            const resp = await fetch('/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: userQuery })
            });

            if (!resp.ok) {
                const errData = await resp.json();
                throw new Error(errData.detail || 'Query execution failed');
            }

            const data = await resp.json();

            // Populate summary & timing
            summaryText.textContent = data.summary || 'Query executed successfully.';
            execTiming.textContent = `${data.execution_time_ms} ms (${data.provider})`;
            sqlCode.textContent = data.sql || '-- No SQL generated';
            resultsCount.textContent = `${data.row_count} records returned`;

            // Populate table
            renderDataTable(data.columns, data.results, tableHead, tableBody);

        } catch (err) {
            summaryText.textContent = `Error: ${err.message}`;
            execTiming.textContent = 'Failed';
            sqlCode.textContent = '-- Execution failed';
            tableHead.innerHTML = '';
            tableBody.innerHTML = `<tr><td colspan="10" class="text-center" style="color:#EF4444;">${err.message}</td></tr>`;
        } finally {
            submitBtn.disabled = false;
            spinner.classList.add('hidden');
            btnText.textContent = 'Execute Query';
        }
    }
}

function renderDataTable(columns, rows, headElem, bodyElem) {
    headElem.innerHTML = '';
    bodyElem.innerHTML = '';

    if (!columns || columns.length === 0 || !rows || rows.length === 0) {
        bodyElem.innerHTML = '<tr><td class="text-center" colspan="10">No records found.</td></tr>';
        return;
    }

    // Render Headers
    const trHead = document.createElement('tr');
    columns.forEach(col => {
        const th = document.createElement('th');
        th.textContent = col.replace(/_/g, ' ');
        trHead.appendChild(th);
    });
    headElem.appendChild(trHead);

    // Render Rows
    rows.forEach(row => {
        const tr = document.createElement('tr');
        columns.forEach(col => {
            const td = document.createElement('td');
            let val = row[col];
            if (val === null || val === undefined) {
                td.innerHTML = '<span style="color:#64748B;">null</span>';
            } else if (col === 'status') {
                td.innerHTML = `<span class="status-tag status-${val.toLowerCase()}">${val}</span>`;
            } else if (col === 'priority') {
                td.innerHTML = `<span class="badge badge-${val.toLowerCase()}">${val}</span>`;
            } else {
                td.textContent = val;
            }
            tr.appendChild(td);
        });
        bodyElem.appendChild(tr);
    });
}

// ------------------------------------------------------------------------------
// 3. Operational Anomaly Center
// ------------------------------------------------------------------------------
function initAnomaliesCenter() {
    const sevFilter = document.getElementById('severityFilter');
    const typeFilter = document.getElementById('typeFilter');
    const refreshBtn = document.getElementById('refreshAnomaliesBtn');

    sevFilter.addEventListener('change', () => loadAnomalies());
    typeFilter.addEventListener('change', () => loadAnomalies());
    refreshBtn.addEventListener('click', () => loadAnomalies());
}

async function loadAnomalies() {
    const tableBody = document.getElementById('anomaliesTableBody');
    const sevFilter = document.getElementById('severityFilter').value;
    const typeFilter = document.getElementById('typeFilter').value;

    tableBody.innerHTML = '<tr><td colspan="7" class="text-center">Detecting operational anomalies...</td></tr>';

    try {
        const params = new URLSearchParams();
        if (sevFilter) params.append('severity', sevFilter);
        if (typeFilter) params.append('anomaly_type', typeFilter);
        params.append('limit', '60');

        const res = await fetch(`/anomalies?${params.toString()}`);
        if (!res.ok) throw new Error('Failed to retrieve anomalies');

        const data = await res.json();
        tableBody.innerHTML = '';

        if (!data.anomalies || data.anomalies.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="7" class="text-center">No anomalies match the current filters.</td></tr>';
            return;
        }

        data.anomalies.forEach(a => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><span class="badge badge-${a.severity.toLowerCase()}">${a.severity}</span></td>
                <td><strong>${a.ticket_id}</strong></td>
                <td><code style="font-size:11px;color:#A5B4FC;">${a.anomaly_type.replace(/_/g, ' ')}</code></td>
                <td>${a.category} / <span class="badge badge-${a.priority.toLowerCase()}">${a.priority}</span></td>
                <td><strong>${a.metric_value}</strong> <span style="color:#64748B;">(Thresh: ${a.threshold})</span></td>
                <td style="max-width:320px;">${a.explanation}</td>
                <td style="max-width:280px;color:#34D399;font-size:12px;">${a.recommended_action}</td>
            `;
            tableBody.appendChild(tr);
        });

    } catch (err) {
        tableBody.innerHTML = `<tr><td colspan="7" class="text-center" style="color:#EF4444;">${err.message}</td></tr>`;
    }
}

// ------------------------------------------------------------------------------
// 4. Dataset Explorer
// ------------------------------------------------------------------------------
let currentTicketPage = 1;

function initDatasetExplorer() {
    const statusSelect = document.getElementById('ticketStatusFilter');
    const catSelect = document.getElementById('ticketCategoryFilter');
    const prevBtn = document.getElementById('prevPageBtn');
    const nextBtn = document.getElementById('nextPageBtn');

    statusSelect.addEventListener('change', () => loadTickets(1));
    catSelect.addEventListener('change', () => loadTickets(1));

    prevBtn.addEventListener('click', () => {
        if (currentTicketPage > 1) loadTickets(currentTicketPage - 1);
    });

    nextBtn.addEventListener('click', () => {
        loadTickets(currentTicketPage + 1);
    });
}

async function loadTickets(page = 1) {
    currentTicketPage = page;
    const tableBody = document.getElementById('rawTicketsBody');
    const pageLabel = document.getElementById('pageInfoLabel');
    const prevBtn = document.getElementById('prevPageBtn');
    const nextBtn = document.getElementById('nextPageBtn');

    const status = document.getElementById('ticketStatusFilter').value;
    const cat = document.getElementById('ticketCategoryFilter').value;

    tableBody.innerHTML = '<tr><td colspan="10" class="text-center">Loading ticket records...</td></tr>';

    try {
        const params = new URLSearchParams({ page: page, page_size: 20 });
        if (status) params.append('status', status);
        if (cat) params.append('category', cat);

        const res = await fetch(`/tickets?${params.toString()}`);
        if (!res.ok) throw new Error('Failed to load tickets');
        const data = await res.json();

        pageLabel.textContent = `Page ${data.page} of ${data.total_pages || 1} (${data.total_records} tickets)`;
        prevBtn.disabled = data.page <= 1;
        nextBtn.disabled = data.page >= data.total_pages;

        tableBody.innerHTML = '';
        data.tickets.forEach(t => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${t.ticket_id}</strong></td>
                <td style="font-size:11px;color:#94A3B8;">${t.created_at}</td>
                <td>${t.category}</td>
                <td><span class="badge badge-${t.priority.toLowerCase()}">${t.priority}</span></td>
                <td><span class="status-tag status-${t.status.toLowerCase()}">${t.status}</span></td>
                <td>${t.response_time_hrs}</td>
                <td>${t.resolution_time_hrs !== null ? t.resolution_time_hrs : '<span style="color:#64748B;">--</span>'}</td>
                <td>${t.agent_id}</td>
                <td>${t.customer_rating !== null ? `${t.customer_rating} ★` : '<span style="color:#64748B;">--</span>'}</td>
                <td style="max-width:260px;font-size:12px;">${t.issue_summary}</td>
            `;
            tableBody.appendChild(tr);
        });

    } catch (err) {
        tableBody.innerHTML = `<tr><td colspan="10" class="text-center" style="color:#EF4444;">${err.message}</td></tr>`;
    }
}

// ------------------------------------------------------------------------------
// 5. Load Analytics KPIs
// ------------------------------------------------------------------------------
async function loadAnalyticsKPIs() {
    try {
        const res = await fetch('/analytics/summary');
        if (!res.ok) return;
        const data = await res.json();

        const countElem = document.getElementById('kpiAnomaliesCount');
        const breakdownElem = document.getElementById('kpiAnomaliesBreakdown');

        if (countElem) countElem.textContent = data.anomalies_count;
        if (breakdownElem && data.anomalies_by_severity) {
            const sev = data.anomalies_by_severity;
            breakdownElem.textContent = `${sev.CRITICAL || 0} Critical, ${sev.HIGH || 0} High, ${sev.MEDIUM || 0} Medium`;
        }
    } catch (e) {
        console.error('Failed to load KPIs:', e);
    }
}
