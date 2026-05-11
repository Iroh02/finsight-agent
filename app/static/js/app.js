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

    // Answer
    answerText.textContent = response.answer;

    // Confidence
    const confidence = response.confidence;
    const confidencePercent = (confidence * 100).toFixed(0);
    confidenceValue.textContent = `${confidencePercent}%`;
    updateConfidenceBadge(confidence);

    // Decision
    decisionState.textContent = response.decision;
    decisionState.className = `decision-badge ${response.decision}`;
    decisionReason.textContent = response.reason;

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
