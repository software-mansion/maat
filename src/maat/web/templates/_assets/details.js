const STORAGE_KEY = 'maat-details-states';

export function setupDetailsMemory() {
    // First, restore saved states.
    restore();

    // Then set up listeners for future changes.
    for (const detail of document.querySelectorAll("details")) {
        detail.addEventListener('toggle', save, {passive: true});
    }

    // Watch for dynamically added details elements.
    const observer = new MutationObserver(mutations => {
        for (const mutation of mutations) {
            for (const node of mutation.addedNodes) {
                if (node.nodeName === 'DETAILS') {
                    node.addEventListener('toggle', save, {passive: true});
                } else if (node.querySelectorAll) {
                    for (const detail of node.querySelectorAll('details')) {
                        detail.addEventListener('toggle', save, {passive: true});
                    }
                }
            }
        }
    });

    observer.observe(document.body, {childList: true, subtree: true});
}

export function setupAltClickOnSummaries() {
    // macOS conventions differ from Windows/Linux.
    // noinspection JSDeprecatedSymbols
    const isMac = navigator.platform.startsWith("Mac") || navigator.platform === "iPhone";

    for (const summary of document.querySelectorAll("summary")) {
        // Add a tooltip explaining the shortcut.
        summary.title = `${isMac ? "⌥" : "Ctrl"}+Click to expand/collapse all sections`;

        // Add a click handler for the modifier key.
        summary.addEventListener('click', (event) => {
            const isModifierPressed = isMac ? event.altKey : event.ctrlKey;

            if (isModifierPressed) {
                event.preventDefault();
                toggleAll();
            }
        });
    }
}

function toggleAll() {
    const details = document.querySelectorAll("details");
    const shouldOpen = [...details].filter(d => d.open).length / details.length < 0.5;
    for (const d of details) {
        d.open = shouldOpen;
    }
    save();
}

function save() {
    const detailsStates = {};
    for (const detail of document.querySelectorAll("details")) {
        if (detail.id) {
            detailsStates[detail.id] = detail.open;
        }
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(detailsStates));
}

function restore() {
    try {
        const savedStates = localStorage.getItem(STORAGE_KEY);
        if (savedStates) {
            const detailsStates = JSON.parse(savedStates);
            for (const detail of document.querySelectorAll("details")) {
                if (detail.id && detail.id in detailsStates) {
                    detail.open = detailsStates[detail.id];
                }
            }
        }
    } catch (e) {
        console.error('error loading details states:', e);
        localStorage.removeItem(STORAGE_KEY);
    }
}
