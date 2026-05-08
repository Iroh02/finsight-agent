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
