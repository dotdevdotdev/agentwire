/**
 * Ask Modal Component - AskUserQuestion popup handling
 *
 * Shows a modal when Claude Code asks a question with options.
 */

// Element references
let modalElement = null;
let badgeElement = null;
let textElement = null;
let optionsElement = null;
let customElement = null;
let customInputElement = null;

// Current question state
let currentQuestion = null;
let submitCallback = null;

/**
 * Initialize the ask modal with DOM element references
 * @param {Object} elements - Object containing modal elements
 * @param {HTMLElement} elements.modal - The modal container
 * @param {HTMLElement} elements.badge - The header badge
 * @param {HTMLElement} elements.text - The question text container
 * @param {HTMLElement} elements.options - The options container
 * @param {HTMLElement} elements.custom - The custom input container
 * @param {HTMLElement} elements.customInput - The custom text input
 */
export function init(elements) {
    modalElement = elements.modal;
    badgeElement = elements.badge;
    textElement = elements.text;
    optionsElement = elements.options;
    customElement = elements.custom;
    customInputElement = elements.customInput;
}

/**
 * Check if an option label is a "type something" option
 * @param {string} label - Option label
 * @returns {boolean}
 */
function isTypeOption(label) {
    const lower = label.toLowerCase().trim();
    return lower.startsWith('type ') ||
           lower === 'type something' ||
           lower === 'type something.' ||
           lower === 'something else' ||
           lower === 'other' ||
           lower === 'other...';
}

/**
 * Show the question modal
 * @param {string} header - Modal header badge text
 * @param {string} question - The question text
 * @param {Array} options - Array of option objects: { number, label, description? }
 * @param {Function} callback - Called with (answer, isCustom) when user submits
 */
export function show(header, question, options, callback) {
    currentQuestion = { header, question, options };
    submitCallback = callback;

    if (badgeElement) {
        badgeElement.textContent = header;
    }

    if (textElement) {
        textElement.textContent = question;
    }

    if (optionsElement) {
        optionsElement.innerHTML = options.map(opt => {
            if (isTypeOption(opt.label)) {
                return `
                    <div class="question-option type-option">
                        <span class="num">${opt.number}</span>
                        <div class="type-input-wrapper">
                            <input type="text"
                                   class="type-input"
                                   id="typeInput${opt.number}"
                                   placeholder="${opt.label}..."
                                   autocomplete="off">
                            <button class="type-submit" data-option="${opt.number}">
                                Send
                            </button>
                        </div>
                    </div>
                `;
            }
            return `
                <button class="question-option" data-answer="${opt.number}">
                    <span class="num">${opt.number}</span>
                    <div>
                        <div class="label">${opt.label}</div>
                        ${opt.description ? `<div class="desc">${opt.description}</div>` : ''}
                    </div>
                </button>
            `;
        }).join('');

        // Add click handlers for options
        optionsElement.querySelectorAll('.question-option[data-answer]').forEach(btn => {
            btn.addEventListener('click', () => {
                const answer = btn.dataset.answer;
                submitAnswer(answer, false);
            });
        });

        // Add handlers for type inputs
        optionsElement.querySelectorAll('.type-submit').forEach(btn => {
            btn.addEventListener('click', () => {
                const optNum = btn.dataset.option;
                submitTypedAnswer(optNum);
            });
        });

        options.forEach(opt => {
            if (isTypeOption(opt.label)) {
                const input = document.getElementById(`typeInput${opt.number}`);
                if (input) {
                    input.addEventListener('keydown', (e) => {
                        if (e.key === 'Enter' && input.value.trim()) {
                            submitTypedAnswer(opt.number);
                        }
                    });
                }
            }
        });
    }

    if (customElement) {
        customElement.classList.remove('visible');
    }

    if (modalElement) {
        modalElement.classList.add('visible');
    }
}

/**
 * Submit a numbered answer
 * @param {string} answer - The answer (option number or custom text)
 * @param {boolean} isCustom - Whether this is a custom typed answer
 */
function submitAnswer(answer, isCustom) {
    if (submitCallback) {
        submitCallback(answer, isCustom);
    }
    hide();
}

/**
 * Submit a typed answer from a type-input field
 * @param {string} optionNumber - The option number
 */
function submitTypedAnswer(optionNumber) {
    const input = document.getElementById(`typeInput${optionNumber}`);
    const text = input ? input.value.trim() : '';
    if (!text) return;

    if (submitCallback) {
        submitCallback(text, true, optionNumber);
    }
    hide();
}

/**
 * Hide the question modal
 */
export function hide() {
    if (modalElement) {
        modalElement.classList.remove('visible');
    }
    if (customElement) {
        customElement.classList.remove('visible');
    }
    currentQuestion = null;
    submitCallback = null;
}

/**
 * Check if the modal is currently visible
 * @returns {boolean}
 */
export function isVisible() {
    return modalElement && modalElement.classList.contains('visible');
}

/**
 * Get the current question data
 * @returns {Object|null}
 */
export function getCurrentQuestion() {
    return currentQuestion;
}
