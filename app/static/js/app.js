/**
 * FinSight Agent - Frontend JavaScript
 * Handles UI interactions, API calls, and response rendering
 */

// State management
const state = {
    currentMode: 'agentic',
    currentRole: 'analyst',
    selectedDocs: [],
    isLoading: false,
    lastResponse: null,
    lastQuestion: '',
};

// DOM Elements
const questionInput = document.getElementById('question-input');
const submitButton = document.getElementById('submit-button');
const modeSelect = document.getElementById('mode-select');
const modelSelect = document.getElementById('model-select');
const loadingSpinner = document.getElementById('loading-spinner');

const responseSection = document.getElementById('response-section');
const emptyState = document.querySelector('.empty-state-container');
const errorState = document.getElementById('error-state');
const errorMessage = document.getElementById('error-message');
const errorDismiss = document.getElementById('error-dismiss');

const answerText = document.getElementById('answer-text');
const confidenceBadge = document.getElementById('confidence-badge');
const confidenceValue = document.getElementById('confidence-value');
const decisionState = document.getElementById('decision-state');
const decisionReason = document.getElementById('decision-reason');
const citationsList = document.getElementById('citations-list');
const citationCount = document.getElementById('citation-count');
const chunksList = document.getElementById('chunks-list');
const chunksCount = document.getElementById('chunks-count');
const executionTime = document.getElementById('execution-time');

const clearButton = document.getElementById('clear-button');
const documentsList = document.getElementById('documents-list');

// Research Brief + Role Desk elements
const briefButton = document.getElementById('brief-button');
const roleSelect = document.getElementById('role-select');
const analystView = document.getElementById('analyst-view');
const reviewerView = document.getElementById('reviewer-view');
const auditorView = document.getElementById('auditor-view');
const reviewQueueEl = document.getElementById('review-queue');
const auditLogEl = document.getElementById('audit-log');
const clearAuditButton = document.getElementById('clear-audit-button');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadDocuments();
});

function setupEventListeners() {
    submitButton.addEventListener('click', handleSubmit);
    questionInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && e.ctrlKey) {
            handleSubmit();
        }
    });

    modeSelect.addEventListener('change', (e) => {
        state.currentMode = e.target.value;
    });

    errorDismiss.addEventListener('click', hideError);
    clearButton.addEventListener('click', clearHistory);

    // Research Brief export
    if (briefButton) briefButton.addEventListener('click', generateBrief);

    // Role-based desk: Analyst / Reviewer / Auditor
    if (roleSelect) roleSelect.addEventListener('change', (e) => switchRole(e.target.value));
    if (clearAuditButton) clearAuditButton.addEventListener('click', clearAuditLog);

    // Upload area
    setupUploadArea();
}

/**
 * Set up PDF upload area (click + drag/drop)
 */
function setupUploadArea() {
    const uploadArea = document.getElementById('upload-area');
    const fileInput = document.getElementById('file-upload');
    const uploadStatus = document.getElementById('upload-status');

    if (!uploadArea || !fileInput) return;

    fileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (file) await uploadFile(file);
    });

    // Drag-drop
    ['dragenter', 'dragover'].forEach(ev => {
        uploadArea.addEventListener(ev, (e) => {
            e.preventDefault();
            e.stopPropagation();
            uploadArea.classList.add('drag-active');
        });
    });
    ['dragleave', 'drop'].forEach(ev => {
        uploadArea.addEventListener(ev, (e) => {
            e.preventDefault();
            e.stopPropagation();
            uploadArea.classList.remove('drag-active');
        });
    });
    uploadArea.addEventListener('drop', async (e) => {
        const file = e.dataTransfer.files[0];
        if (file) await uploadFile(file);
    });

    async function uploadFile(file) {
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            showUploadStatus('Only PDF files are supported', 'error');
            return;
        }

        showUploadStatus(`Uploading ${file.name}...`, 'loading');

        const formData = new FormData();
        formData.append('file', file);

        try {
            const resp = await fetch('/upload', { method: 'POST', body: formData });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.detail || 'Upload failed');
            showUploadStatus(
                `✓ ${file.name}: ${data.chunks_ingested} chunks added`,
                'success'
            );
            // Reload documents list
            setTimeout(loadDocuments, 500);
        } catch (err) {
            showUploadStatus(`✗ ${err.message}`, 'error');
        }
    }

    function showUploadStatus(msg, type) {
        uploadStatus.textContent = msg;
        uploadStatus.className = `upload-status ${type}`;
        uploadStatus.classList.remove('hidden');
    }
}

/**
 * Load and display available documents
 */
async function loadDocuments() {
    try {
        // TODO: Fetch list of available documents from backend
        // For now, show placeholder
        const documents = ['Apple_2023_10K.pdf', 'Microsoft_2023_AR.pdf', 'Tesla_2023_10K.pdf'];

        documentsList.innerHTML = documents
            .map(
                (doc) => `
            <div class="document-item">
                <input type="checkbox" id="doc-${doc}" value="${doc}" checked>
                <label for="doc-${doc}">${doc}</label>
            </div>
        `
            )
            .join('');

        // Add change listeners
        document.querySelectorAll('.document-item input').forEach((checkbox) => {
            checkbox.addEventListener('change', updateSelectedDocs);
        });

        updateSelectedDocs();
    } catch (error) {
        console.error('Error loading documents:', error);
    }
}

/**
 * Update selected documents state
 */
function updateSelectedDocs() {
    const checkboxes = document.querySelectorAll('.document-item input:checked');
    state.selectedDocs = Array.from(checkboxes).map((cb) => cb.value);
}

/**
 * Handle query submission
 */
async function handleSubmit() {
    const question = questionInput.value.trim();

    if (!question) {
        showError('Please enter a question.');
        return;
    }

    if (state.isLoading) return;

    state.isLoading = true;
    submitButton.disabled = true;
    loadingSpinner.classList.remove('hidden');
    hideError();

    try {
        const response = await fetch('/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                question,
                mode: state.currentMode,
                selected_docs: state.selectedDocs,
            }),
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        const data = await response.json();
        state.lastResponse = data;
        state.lastQuestion = question;
        displayResponse(data);
    } catch (error) {
        console.error('Error:', error);
        showError(`Failed to get response: ${error.message}`);
    } finally {
        state.isLoading = false;
        submitButton.disabled = false;
        loadingSpinner.classList.add('hidden');
    }
}

/**
 * Display response in UI
 */
function displayResponse(response) {
    // Hide empty state and show response section
    emptyState.classList.add('hidden');
    responseSection.classList.remove('hidden');

    // Answer — render with markdown for richer formatting
    if (typeof marked !== 'undefined') {
        answerText.innerHTML = marked.parse(response.answer || '', {
            breaks: true,
            gfm: true,
        });
    } else {
        answerText.textContent = response.answer;
    }

    // Confidence
    const confidence = response.confidence;
    const confidencePercent = (confidence * 100).toFixed(0);
    confidenceValue.textContent = `${confidencePercent}%`;
    updateConfidenceBadge(confidence);

    // Decision (legacy 4-state)
    decisionState.textContent = response.decision;
    decisionState.className = `decision-badge ${response.decision}`;
    decisionReason.textContent = response.reason;

    // Extended recommendation (7-state, when different from legacy decision)
    renderRecommendation(response.recommendation, response.recommendation_description, response.decision);

    // FinSight Trust Score (composite 0-100 + 6 component breakdown)
    renderTrustScore(response.trust_score);

    // Temporal scope badges (FinSight novel: temporal-aware retrieval)
    renderTemporalContext(response.temporal_context);

    // Cross-doc conflicts (FinSight novel: conflict detection)
    renderConflictReport(response.conflict_report);

    // Citations
    renderCitations(response.citations);

    // Chunks
    renderChunks(response.chunks);

    // Multi-agent trace (if present)
    renderAgentTrace(response.multi_agent_trace);

    // Execution time
    executionTime.textContent = response.execution_time_ms
        ? response.execution_time_ms.toFixed(2)
        : '--';

    // Record this query in the audit log (powers the Reviewer + Auditor views)
    appendAuditRecord(response);

    // Scroll to response
    setTimeout(() => {
        responseSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
}

/**
 * Render multi-agent trace (only for multi_agent mode)
 */
function renderAgentTrace(trace) {
    const card = document.getElementById('agent-trace-card');
    const content = document.getElementById('agent-trace-content');

    if (!trace) {
        card.classList.add('hidden');
        return;
    }

    card.classList.remove('hidden');

    const planner = `
        <div class="agent-step planner">
            <div class="agent-step-header">
                <span class="agent-emoji">🎯</span>
                <strong>Planner Agent</strong>
                <span class="complexity-badge">Complexity: ${trace.complexity_score}/5</span>
            </div>
            <p class="agent-decision"><strong>Decision:</strong> ${trace.planner_decision}</p>
            <p class="agent-reasoning">${escapeHtml(trace.planner_reasoning || '')}</p>
        </div>
    `;

    let subQueriesHtml = '';
    if (trace.sub_queries && trace.sub_queries.length > 0) {
        subQueriesHtml = `
            <div class="agent-step decomposer">
                <div class="agent-step-header">
                    <span class="agent-emoji">🔨</span>
                    <strong>Decomposer Agent</strong>
                    <span class="count-badge">${trace.sub_queries.length} sub-queries</span>
                </div>
                <ol class="sub-queries-list">
                    ${trace.sub_queries.map((sq, i) => `
                        <li class="sub-query-item">
                            <div class="sub-q-question"><strong>Q:</strong> ${escapeHtml(sq.question)}</div>
                            <div class="sub-q-answer"><strong>A:</strong> ${escapeHtml(sq.answer)}</div>
                            <div class="sub-q-meta">📄 ${sq.chunks_count} chunks retrieved</div>
                        </li>
                    `).join('')}
                </ol>
            </div>
        `;
    }

    let synthHtml = '';
    if (trace.synthesis_reasoning && trace.sub_queries.length > 0) {
        synthHtml = `
            <div class="agent-step synthesizer">
                <div class="agent-step-header">
                    <span class="agent-emoji">🧬</span>
                    <strong>Synthesizer Agent</strong>
                </div>
                <p class="agent-reasoning">${escapeHtml(trace.synthesis_reasoning)}</p>
            </div>
        `;
    }

    let validationHtml = '';
    if (trace.validation_report && Object.keys(trace.validation_report).length > 0) {
        const v = trace.validation_report;
        const issuesHtml = v.issues && v.issues.length > 0
            ? `<ul class="issues-list">${v.issues.map(i => `<li>${escapeHtml(i)}</li>`).join('')}</ul>`
            : '<p class="no-issues">No issues found ✓</p>';
        validationHtml = `
            <div class="agent-step validator">
                <div class="agent-step-header">
                    <span class="agent-emoji">✅</span>
                    <strong>Validator Agent</strong>
                    <span class="support-badge ${v.supported || ''}">${v.supported || ''}</span>
                </div>
                <p class="validation-score"><strong>Validation Score:</strong> ${(v.validation_score || 0).toFixed(2)}/1.0</p>
                <p class="agent-reasoning">${escapeHtml(v.summary || '')}</p>
                <div class="issues-section">
                    <strong>Issues:</strong>
                    ${issuesHtml}
                </div>
            </div>
        `;
    }

    let timingHtml = '';
    if (trace.execution_time_per_agent && Object.keys(trace.execution_time_per_agent).length > 0) {
        const timings = Object.entries(trace.execution_time_per_agent)
            .map(([agent, t]) => `<span class="timing-pill"><strong>${agent}:</strong> ${t}s</span>`)
            .join('');
        timingHtml = `
            <div class="agent-timing">
                <strong>⏱️ Agent Timing:</strong>
                <div class="timing-pills">${timings}</div>
                ${trace.total_time_seconds ? `<p class="total-time">Total: ${trace.total_time_seconds}s</p>` : ''}
            </div>
        `;
    }

    content.innerHTML = planner + subQueriesHtml + synthHtml + validationHtml + timingHtml;
}

/**
 * Render the extended 7-state recommendation chip next to the legacy
 * decision. Hidden when the extended recommendation is identical to the
 * legacy decision (e.g. plain ANSWER).
 */
function renderRecommendation(recommendation, description, baseDecision) {
    const chip = document.getElementById('recommendation-state');
    const descRow = document.getElementById('recommendation-description-row');
    const descEl = document.getElementById('recommendation-description');
    if (!chip || !recommendation || recommendation === baseDecision) {
        if (chip) chip.classList.add('hidden');
        if (descRow) descRow.classList.add('hidden');
        return;
    }
    chip.textContent = recommendation;
    chip.className = `recommendation-badge ${recommendation}`;
    chip.classList.remove('hidden');
    if (description && descEl && descRow) {
        descEl.textContent = description;
        descRow.classList.remove('hidden');
    }
}

/**
 * Render the FinSight Trust Score card — composite headline + 6 weighted
 * components shown as horizontal bars with detail text.
 */
function renderTrustScore(trust) {
    const card = document.getElementById('trust-card');
    if (!card || !trust) {
        if (card) card.classList.add('hidden');
        return;
    }
    card.classList.remove('hidden');

    document.getElementById('trust-composite').textContent = trust.composite;
    const bandEl = document.getElementById('trust-band');
    bandEl.textContent = trust.band.replace(/_/g, ' ');
    bandEl.className = `trust-band-badge band-${trust.band}`;
    document.getElementById('trust-band-desc').textContent = trust.band_description || '';

    const compsEl = document.getElementById('trust-components');
    if (!compsEl) return;

    const rows = (trust.components || []).map((c) => {
        const pct = Math.round((c.value || 0) * 100);
        const weightPct = Math.round((c.weight || 0) * 100);
        const contribPct = Math.round((c.weighted || 0) * 100);
        return `
            <div class="trust-component-row">
                <div class="trust-component-header">
                    <span class="trust-component-name">${escapeHtml(c.name)}</span>
                    <span class="trust-component-meta">
                        <span class="trust-component-value">${pct}%</span>
                        <span class="trust-component-weight">× ${weightPct}% weight</span>
                        <span class="trust-component-contrib">= +${contribPct} pts</span>
                    </span>
                </div>
                <div class="trust-component-bar">
                    <div class="trust-component-fill" style="width: ${pct}%"></div>
                </div>
                ${c.detail ? `<div class="trust-component-detail">${escapeHtml(c.detail)}</div>` : ''}
            </div>
        `;
    });

    compsEl.innerHTML = rows.join('');
}

/**
 * Render detected temporal/company scope as a set of badges.
 * Surfaces FinSight's temporal-aware retrieval to the user.
 */
function renderTemporalContext(contextList) {
    const card = document.getElementById('temporal-card');
    const content = document.getElementById('temporal-content');
    const countEl = document.getElementById('temporal-count');
    if (!card || !content) return;

    if (!contextList || contextList.length === 0) {
        card.classList.add('hidden');
        return;
    }
    card.classList.remove('hidden');
    countEl.textContent = contextList.length;

    content.innerHTML = contextList.map((tc) => {
        const labelParts = [];
        if (tc.company) labelParts.push(`<span class="temporal-pill company">🏢 ${escapeHtml(tc.company)}</span>`);
        if (tc.year) {
            const qtr = tc.quarter ? ` ${escapeHtml(tc.quarter)}` : '';
            labelParts.push(`<span class="temporal-pill year">📅 FY${tc.year}${qtr}</span>`);
        } else if (tc.quarter) {
            labelParts.push(`<span class="temporal-pill year">📅 ${escapeHtml(tc.quarter)}</span>`);
        }
        if (tc.doc_type) labelParts.push(`<span class="temporal-pill doctype">📋 ${escapeHtml(tc.doc_type)}</span>`);
        if (tc.freshness) labelParts.push(`<span class="temporal-pill freshness">⚡ ${escapeHtml(tc.freshness)}</span>`);

        const subQ = tc.sub_question ? `<div class="temporal-subq">${escapeHtml(tc.sub_question)}</div>` : '';
        const note = tc.note ? `<div class="temporal-note">${escapeHtml(tc.note)}</div>` : '';
        return `
            <div class="temporal-item">
                ${subQ}
                <div class="temporal-pills">${labelParts.join('')}</div>
                ${note}
            </div>
        `;
    }).join('');
}

/**
 * Render cross-document conflict report.
 * FinSight novel feature: surface contradictions across filings/companies.
 */
function renderConflictReport(report) {
    const card = document.getElementById('conflict-card');
    const content = document.getElementById('conflict-content');
    const countEl = document.getElementById('conflict-count');
    if (!card || !content) return;

    if (!report) {
        card.classList.add('hidden');
        return;
    }
    const conflicts = report.conflicts || [];

    if (conflicts.length === 0) {
        // Suppress card entirely when nothing to report
        if (report.skipped || report.pairs_checked === 0) {
            card.classList.add('hidden');
            return;
        }
        // Otherwise show a green "no conflicts" pill
        card.classList.remove('hidden');
        countEl.textContent = '0';
        content.innerHTML = `
            <div class="conflict-clean">
                ✓ ${report.pairs_checked} cross-document pair(s) checked. No factual conflicts detected.
            </div>
        `;
        return;
    }

    card.classList.remove('hidden');
    countEl.textContent = conflicts.length;

    content.innerHTML = conflicts.map((c) => {
        const sev = (c.severity || 'MEDIUM').toUpperCase();
        const s1 = c.source_1 || {};
        const s2 = c.source_2 || {};
        const s1Label = [s1.company, s1.period, s1.source].filter(Boolean).join(' · ');
        const s2Label = [s2.company, s2.period, s2.source].filter(Boolean).join(' · ');
        return `
            <div class="conflict-item severity-${sev}">
                <div class="conflict-header">
                    <span class="conflict-severity">${sev}</span>
                    <span class="conflict-type">${escapeHtml(c.type || '')}</span>
                    <span class="conflict-fact">${escapeHtml(c.shared_fact || '')}</span>
                </div>
                <div class="conflict-pair">
                    <div class="conflict-side">
                        <div class="conflict-src">${escapeHtml(s1Label)}</div>
                        <div class="conflict-claim">${escapeHtml(c.claim_1 || '')}</div>
                    </div>
                    <div class="conflict-vs">vs</div>
                    <div class="conflict-side">
                        <div class="conflict-src">${escapeHtml(s2Label)}</div>
                        <div class="conflict-claim">${escapeHtml(c.claim_2 || '')}</div>
                    </div>
                </div>
                <div class="conflict-explanation">${escapeHtml(c.explanation || '')}</div>
            </div>
        `;
    }).join('');
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Update confidence badge color based on value
 */
function updateConfidenceBadge(confidence) {
    confidenceBadge.classList.remove('high', 'medium', 'low');

    if (confidence >= 0.7) {
        confidenceBadge.classList.add('high');
    } else if (confidence >= 0.4) {
        confidenceBadge.classList.add('medium');
    } else {
        confidenceBadge.classList.add('low');
    }
}

/**
 * Render citations
 */
function renderCitations(citations) {
    citationCount.textContent = citations.length;

    if (citations.length === 0) {
        citationsList.innerHTML = '<p class="empty-state">No citations found.</p>';
        return;
    }

    citationsList.innerHTML = citations
        .map(
            (citation) => `
        <div class="citation-item">
            <div class="citation-source">${citation.source}</div>
            ${citation.page ? `<div class="citation-page">Page ${citation.page}</div>` : ''}
            ${citation.excerpt ? `<div style="margin-top: 8px; font-size: 12px; color: #6b7280;">"${citation.excerpt.substring(0, 100)}..."</div>` : ''}
        </div>
    `
        )
        .join('');
}

/**
 * Render retrieved chunks
 */
function renderChunks(chunks) {
    chunksCount.textContent = chunks.length;

    if (chunks.length === 0) {
        chunksList.innerHTML = '<p class="empty-state">No chunks retrieved.</p>';
        return;
    }

    chunksList.innerHTML = chunks
        .map(
            (chunk, index) => `
        <div class="chunk-item">
            <div class="chunk-header">
                <div class="chunk-source">[${index + 1}] ${chunk.source}${
                chunk.page ? ` • Page ${chunk.page}` : ''
            }</div>
                ${
                    chunk.relevance_score
                        ? `<div class="chunk-score">${(chunk.relevance_score * 100).toFixed(0)}%</div>`
                        : ''
                }
            </div>
            <div class="chunk-text">${chunk.text}</div>
        </div>
    `
        )
        .join('');
}

/**
 * Show error message
 */
function showError(message) {
    errorMessage.textContent = message;
    errorState.classList.remove('hidden');
}

/**
 * Hide error message
 */
function hideError() {
    errorState.classList.add('hidden');
}

/**
 * Clear conversation history
 */
function clearHistory() {
    questionInput.value = '';
    responseSection.classList.add('hidden');
    emptyState.classList.remove('hidden');
    hideError();
}

/* ====================================================================== *
 *  FEATURE 1 — Research Brief export
 *  Turns the current analysis into a printable, standalone one-pager.
 * ====================================================================== */

function generateBrief() {
    const r = state.lastResponse;
    if (!r) {
        showError('Run a query first, then generate a brief.');
        return;
    }
    const html = buildBriefHtml(r, state.lastQuestion);
    const win = window.open('', '_blank');
    if (!win) {
        showError('Brief popup was blocked — please allow popups for this site.');
        return;
    }
    win.document.write(html);
    win.document.close();
}

function buildBriefHtml(r, question) {
    const esc = escapeHtml;
    const ts = new Date().toLocaleString();
    const trust = r.trust_score || null;

    const answerHtml = (typeof marked !== 'undefined')
        ? marked.parse(r.answer || '', { breaks: true, gfm: true })
        : '<p>' + esc(r.answer || '') + '</p>';

    // Trust score block
    let trustBlock = '';
    if (trust) {
        const rows = (trust.components || []).map((c) =>
            `<tr><td>${esc(c.name)}</td><td>${Math.round((c.value || 0) * 100)}%</td>` +
            `<td>${Math.round((c.weight || 0) * 100)}%</td>` +
            `<td>+${Math.round((c.weighted || 0) * 100)} pts</td></tr>`).join('');
        trustBlock = `
            <h2>FinSight Trust Score</h2>
            <div class="b-trust">
                <div class="b-score">${trust.composite}<span>/100</span></div>
                <div>
                    <div class="b-band b-band-${esc(trust.band || '')}">${esc((trust.band || '').replace(/_/g, ' '))}</div>
                    <div class="b-muted">${esc(trust.band_description || '')}</div>
                </div>
            </div>
            <table class="b-table">
                <thead><tr><th>Reliability signal</th><th>Score</th><th>Weight</th><th>Contribution</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>`;
    }

    // Conflicts
    let conflictBlock = '';
    const conflicts = (r.conflict_report && r.conflict_report.conflicts) || [];
    if (conflicts.length) {
        const items = conflicts.map((c) => {
            const s1 = c.source_1 || {}, s2 = c.source_2 || {};
            return `<div class="b-conflict">
                <strong>${esc(c.severity || '')} · ${esc(c.shared_fact || '')}</strong>
                <div>${esc(s1.company || s1.source || 'Doc 1')}: ${esc(c.claim_1 || '')}</div>
                <div>${esc(s2.company || s2.source || 'Doc 2')}: ${esc(c.claim_2 || '')}</div>
                <div class="b-muted">${esc(c.explanation || '')}</div>
            </div>`;
        }).join('');
        conflictBlock = `<h2>Cross-Document Conflicts (${conflicts.length})</h2>${items}`;
    }

    // Temporal scope
    let temporalBlock = '';
    const tc = r.temporal_context || [];
    if (tc.length) {
        const badges = tc.map((t) => `<span class="b-badge">${esc(t.badge || '')}</span>`).join(' ');
        temporalBlock = `<h2>Temporal Scope</h2><p>${badges}</p>`;
    }

    // Citations
    let citeBlock = '';
    const cites = r.citations || [];
    if (cites.length) {
        const rows = cites.map((c) =>
            `<tr><td>${esc(c.source || '')}</td><td>${c.page != null ? c.page : '—'}</td>` +
            `<td>${esc((c.excerpt || '').substring(0, 160))}</td></tr>`).join('');
        citeBlock = `<h2>Citations (${cites.length})</h2>
            <table class="b-table"><thead><tr><th>Source</th><th>Page</th><th>Excerpt</th></tr></thead>
            <tbody>${rows}</tbody></table>`;
    }

    // Agent desk trace
    let traceBlock = '';
    const trace = r.multi_agent_trace;
    if (trace && trace.planner_decision) {
        const timings = trace.execution_time_per_agent || {};
        const tRows = Object.keys(timings).map((k) =>
            `<tr><td>${esc(k)}</td><td>${timings[k]}s</td></tr>`).join('');
        traceBlock = `<h2>Agent Desk Trace</h2>
            <p>Routing: <strong>${esc(trace.planner_decision)}</strong> &middot;
            Complexity ${trace.complexity_score || '—'}/5 &middot;
            ${(trace.sub_queries || []).length} sub-queries &middot;
            Total ${trace.total_time_seconds || '—'}s</p>
            ${tRows ? `<table class="b-table"><thead><tr><th>Agent</th><th>Time</th></tr></thead><tbody>${tRows}</tbody></table>` : ''}`;
    }

    const rec = r.recommendation || r.decision || '';
    const recDesc = r.recommendation_description || '';

    return `<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>FinSight Research Brief</title>
<style>
  body { font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif; color: #1f2937;
         max-width: 820px; margin: 32px auto; padding: 0 28px; line-height: 1.55; }
  .b-head { border-bottom: 3px solid #2563eb; padding-bottom: 14px; margin-bottom: 20px; }
  .b-head h1 { color: #2563eb; font-size: 24px; margin: 0 0 4px; }
  .b-meta { font-size: 12px; color: #6b7280; }
  .b-question { background: #f1f5ff; border-left: 4px solid #2563eb; padding: 10px 14px;
                margin: 14px 0; font-weight: 600; }
  h2 { font-size: 15px; color: #1e40af; border-bottom: 1px solid #e5e7eb;
       padding-bottom: 4px; margin-top: 26px; }
  .b-rec { display: inline-block; padding: 5px 14px; border-radius: 6px; color: #fff;
           font-weight: 700; font-size: 13px; background: #2563eb; }
  .b-muted { color: #6b7280; font-size: 12px; }
  .b-trust { display: flex; align-items: center; gap: 18px; margin: 10px 0; }
  .b-score { font-size: 44px; font-weight: 800; color: #2563eb; }
  .b-score span { font-size: 18px; color: #9ca3af; }
  .b-band { display: inline-block; padding: 3px 10px; border-radius: 999px; color: #fff;
            font-size: 11px; font-weight: 700; background: #6b7280; }
  .b-band-HIGH_TRUST { background: #10b981; } .b-band-ANALYST_REVIEW { background: #3b82f6; }
  .b-band-NEEDS_REVIEW { background: #f59e0b; } .b-band-LOW_TRUST { background: #fb923c; }
  .b-band-REJECT { background: #ef4444; }
  .b-table { width: 100%; border-collapse: collapse; font-size: 12px; margin: 8px 0; }
  .b-table th, .b-table td { border: 1px solid #e5e7eb; padding: 5px 8px; text-align: left; }
  .b-table th { background: #f9fafb; }
  .b-conflict { background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px;
                padding: 9px 12px; margin: 8px 0; font-size: 13px; }
  .b-badge { display: inline-block; background: #eef2ff; border: 1px solid #c7d2fe;
             color: #1e40af; border-radius: 999px; padding: 3px 10px; font-size: 12px;
             font-weight: 600; }
  .b-footer { margin-top: 30px; border-top: 1px solid #e5e7eb; padding-top: 12px;
              font-size: 11px; color: #6b7280; }
  .b-print { margin: 16px 0; }
  .b-print button { background: #2563eb; color: #fff; border: 0; border-radius: 6px;
                    padding: 8px 16px; font-size: 13px; cursor: pointer; }
  @media print { .b-print { display: none; } body { margin: 0; } }
</style></head><body>
  <div class="b-head">
    <h1>FinSight Research Brief</h1>
    <div class="b-meta">Generated ${esc(ts)} &middot; Mode: ${esc(state.currentMode)} &middot; Analyst: ${esc(state.currentRole)}</div>
  </div>
  <div class="b-print"><button onclick="window.print()">Print / Save as PDF</button></div>
  <div class="b-question">${esc(question || '(question not recorded)')}</div>

  <h2>Recommendation</h2>
  <p><span class="b-rec">${esc(rec)}</span> &nbsp; <span class="b-muted">${esc(recDesc)}</span></p>
  <p class="b-muted">Legacy decision state: ${esc(r.decision || '')}</p>

  <h2>Answer</h2>
  <div>${answerHtml}</div>

  ${trustBlock}
  ${conflictBlock}
  ${temporalBlock}
  ${citeBlock}
  ${traceBlock}

  <div class="b-footer">
    <strong>Advisory output — analyst review required before financial decisions.</strong><br>
    FinSight Agent is a decision-support system, not an autonomous advisor. Recommendation
    states: ANSWER / HEDGED_ANSWER / CONFLICT_REVIEW / REQUEST_MORE_DOCS / ESCALATE /
    CLARIFY / REFUSE. Every figure should be confirmed against the cited source page.
  </div>
</body></html>`;
}

/* ====================================================================== *
 *  FEATURE 2 — Role-Based Desk (Analyst / Reviewer / Auditor)
 *  A client-side review workflow + audit log backed by localStorage.
 * ====================================================================== */

const AUDIT_KEY = 'finsight_audit_log';
const REVIEW_RECS = ['ESCALATE', 'CONFLICT_REVIEW', 'HEDGED_ANSWER', 'REQUEST_MORE_DOCS'];
const REVIEW_BANDS = ['ANALYST_REVIEW', 'NEEDS_REVIEW', 'LOW_TRUST', 'REJECT'];

function loadAuditLog() {
    try {
        return JSON.parse(localStorage.getItem(AUDIT_KEY)) || [];
    } catch (e) {
        return [];
    }
}

function saveAuditLog(log) {
    try {
        localStorage.setItem(AUDIT_KEY, JSON.stringify(log));
    } catch (e) {
        console.warn('Could not persist audit log:', e);
    }
}

function appendAuditRecord(response) {
    const log = loadAuditLog();
    const trust = response.trust_score || {};
    const conflicts = (response.conflict_report && response.conflict_report.conflicts) || [];
    log.unshift({
        id: 'q' + Date.now(),
        ts: new Date().toISOString(),
        question: state.lastQuestion || '',
        mode: state.currentMode,
        decision: response.decision || '',
        recommendation: response.recommendation || response.decision || '',
        trust_composite: (trust.composite != null) ? trust.composite : null,
        trust_band: trust.band || '',
        conflict_count: conflicts.length,
        answer_excerpt: (response.answer || '').substring(0, 220),
        review_status: 'pending',
        reviewer_note: '',
    });
    saveAuditLog(log);
}

function updateAuditRecord(id, changes) {
    const log = loadAuditLog();
    const rec = log.find((r) => r.id === id);
    if (rec) {
        Object.assign(rec, changes);
        saveAuditLog(log);
    }
}

function clearAuditLog() {
    if (!confirm('Clear the entire audit log? This cannot be undone.')) return;
    saveAuditLog([]);
    renderAuditLog();
    renderReviewQueue();
}

function recordNeedsReview(rec) {
    return REVIEW_RECS.includes(rec.recommendation) || REVIEW_BANDS.includes(rec.trust_band);
}

function switchRole(role) {
    state.currentRole = role;
    analystView.classList.toggle('hidden', role !== 'analyst');
    reviewerView.classList.toggle('hidden', role !== 'reviewer');
    auditorView.classList.toggle('hidden', role !== 'auditor');
    if (role === 'reviewer') renderReviewQueue();
    if (role === 'auditor') renderAuditLog();
}

function renderReviewQueue() {
    if (!reviewQueueEl) return;
    const log = loadAuditLog();
    const pending = log.filter((r) => r.review_status === 'pending' && recordNeedsReview(r));

    if (!pending.length) {
        reviewQueueEl.innerHTML =
            '<p class="empty-state">No answers awaiting review. Flagged answers (escalations, conflicts, low trust) will appear here.</p>';
        return;
    }

    reviewQueueEl.innerHTML = pending.map((r) => `
        <div class="review-item" data-id="${r.id}">
            <div class="review-item-head">
                <span class="recommendation-badge ${escapeHtml(r.recommendation)}">${escapeHtml(r.recommendation)}</span>
                <span class="review-trust">Trust ${r.trust_composite != null ? r.trust_composite : '—'} &middot; ${escapeHtml((r.trust_band || '').replace(/_/g, ' '))}</span>
                <span class="review-ts">${new Date(r.ts).toLocaleString()}</span>
            </div>
            <div class="review-q">${escapeHtml(r.question)}</div>
            <div class="review-excerpt">${escapeHtml(r.answer_excerpt)}&hellip;</div>
            <textarea class="review-note" placeholder="Reviewer note (optional)">${escapeHtml(r.reviewer_note || '')}</textarea>
            <div class="review-actions">
                <button class="review-approve" data-id="${r.id}">✓ Approve</button>
                <button class="review-dispute" data-id="${r.id}">✗ Dispute</button>
            </div>
        </div>
    `).join('');

    reviewQueueEl.querySelectorAll('.review-approve').forEach((b) =>
        b.addEventListener('click', () => reviewAction(b.dataset.id, 'approved')));
    reviewQueueEl.querySelectorAll('.review-dispute').forEach((b) =>
        b.addEventListener('click', () => reviewAction(b.dataset.id, 'disputed')));
}

function reviewAction(id, status) {
    const item = reviewQueueEl.querySelector(`.review-item[data-id="${id}"]`);
    const note = item ? item.querySelector('.review-note').value : '';
    updateAuditRecord(id, { review_status: status, reviewer_note: note });
    renderReviewQueue();
}

function renderAuditLog() {
    if (!auditLogEl) return;
    const log = loadAuditLog();

    if (!log.length) {
        auditLogEl.innerHTML = '<p class="empty-state">Audit log is empty. Run queries in Analyst mode.</p>';
        return;
    }

    const rows = log.map((r) => `
        <tr>
            <td>${new Date(r.ts).toLocaleString()}</td>
            <td>${escapeHtml(r.question)}</td>
            <td>${escapeHtml(r.mode)}</td>
            <td><span class="recommendation-badge ${escapeHtml(r.recommendation)}">${escapeHtml(r.recommendation)}</span></td>
            <td>${r.trust_composite != null ? r.trust_composite : '—'}</td>
            <td class="audit-status status-${escapeHtml(r.review_status)}">${escapeHtml(r.review_status)}</td>
        </tr>
    `).join('');

    auditLogEl.innerHTML = `
        <table class="audit-table">
            <thead><tr><th>Time</th><th>Question</th><th>Mode</th><th>Recommendation</th><th>Trust</th><th>Review</th></tr></thead>
            <tbody>${rows}</tbody>
        </table>`;
}
