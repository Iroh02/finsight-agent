/**
 * FinSight Agent - Frontend JavaScript
 * Handles UI interactions, API calls, and response rendering
 */

// State management
const state = {
    currentMode: 'agentic',
    selectedDocs: [],
    isLoading: false,
    lastResponse: null,
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
