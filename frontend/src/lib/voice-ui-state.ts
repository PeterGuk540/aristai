/**
 * Voice UI State Module - Deterministic UI State Grounding
 *
 * This module provides functions to read the current state of the UI
 * for voice command context and verification. All voice-controllable
 * elements must have a data-voice-id attribute.
 *
 * The state is used for:
 * 1. Providing context to the LLM for intelligent command routing
 * 2. Verifying that actions were executed successfully
 * 3. Computing repair actions when verification fails
 */

// ============================================================================
// UI STATE TYPES
// ============================================================================

export interface TabInfo {
  voiceId: string;
  label: string;
  active: boolean;
  disabled: boolean;
}

export interface ButtonInfo {
  voiceId: string;
  label: string;
  disabled: boolean;
  loading: boolean;
  visible: boolean;
}

export interface InputFieldInfo {
  voiceId: string;
  type: 'input' | 'textarea' | 'select';
  value: string;
  placeholder: string;
  label: string;
  disabled: boolean;
  required: boolean;
  error: string | null;
}

export interface DropdownOptionInfo {
  index: number;
  value: string;
  label: string;
  selected: boolean;
  disabled: boolean;
}

export interface DropdownInfo {
  voiceId: string;
  label: string;
  expanded: boolean;
  selectedValue: string | null;
  selectedLabel: string | null;
  options: DropdownOptionInfo[];
  disabled: boolean;
}

export interface ModalInfo {
  id: string;
  voiceId: string | null;
  title: string;
  open: boolean;
}

export interface ListItemInfo {
  index: number;
  voiceId: string | null;
  label: string;
  selected: boolean;
}

export interface UiState {
  // Current location
  route: string;

  // Active tab on current page
  activeTab: string | null;

  // All visible tabs
  tabs: TabInfo[];

  // All visible buttons
  buttons: ButtonInfo[];

  // All form input fields
  inputFields: InputFieldInfo[];

  // All dropdown/select elements
  dropdowns: DropdownInfo[];

  // Any open modals
  modals: ModalInfo[];

  // List items (for course/session lists)
  listItems: ListItemInfo[];

  // Global states
  isLoading: boolean;
  hasValidationErrors: boolean;

  // Timestamp for staleness detection
  capturedAt: number;
}

// ============================================================================
// ELEMENT DISCOVERY
// ============================================================================

/**
 * Get all elements with data-voice-id attribute
 */
function getVoiceElements(): HTMLElement[] {
  return Array.from(document.querySelectorAll('[data-voice-id]')) as HTMLElement[];
}

/**
 * Check if an element is visible (not hidden, not display:none, not visibility:hidden)
 */
function isElementVisible(element: HTMLElement): boolean {
  if (!element) return false;

  const style = window.getComputedStyle(element);
  if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
    return false;
  }

  // Check if element or ancestors have hidden attribute
  if (element.hidden || element.closest('[hidden]')) {
    return false;
  }

  // Check bounding rect
  const rect = element.getBoundingClientRect();
  if (rect.width === 0 && rect.height === 0) {
    return false;
  }

  return true;
}

/**
 * Check if element is disabled
 */
function isElementDisabled(element: HTMLElement): boolean {
  return (
    element.hasAttribute('disabled') ||
    element.getAttribute('aria-disabled') === 'true' ||
    element.classList.contains('disabled')
  );
}

/**
 * Check if element is in loading state
 */
function isElementLoading(element: HTMLElement): boolean {
  return (
    element.getAttribute('data-loading') === 'true' ||
    element.classList.contains('loading') ||
    element.querySelector('.spinner, .loading-indicator') !== null
  );
}

/**
 * Get the label for an element (text content, aria-label, or placeholder)
 */
function getElementLabel(element: HTMLElement): string {
  // Try aria-label first
  const ariaLabel = element.getAttribute('aria-label');
  if (ariaLabel) return ariaLabel.trim();

  // Try associated label element
  const id = element.id;
  if (id) {
    const label = document.querySelector(`label[for="${id}"]`);
    if (label) return label.textContent?.trim() ?? '';
  }

  // Try text content (for buttons, tabs)
  const textContent = element.textContent?.trim();
  if (textContent && textContent.length < 100) return textContent;

  // Try placeholder (for inputs)
  const placeholder = element.getAttribute('placeholder');
  if (placeholder) return placeholder.trim();

  // Try name attribute
  const name = element.getAttribute('name');
  if (name) return name.replace(/[-_]/g, ' ');

  // Fall back to voice-id
  return element.getAttribute('data-voice-id') ?? '';
}

// ============================================================================
// TAB DISCOVERY
// ============================================================================

function discoverTabs(): TabInfo[] {
  const tabs: TabInfo[] = [];

  // Find tabs by voice-id pattern
  const tabElements = document.querySelectorAll('[data-voice-id^="tab-"]');

  tabElements.forEach((element) => {
    const el = element as HTMLElement;
    if (!isElementVisible(el)) return;

    const voiceId = el.getAttribute('data-voice-id') ?? '';
    const isActive =
      el.getAttribute('aria-selected') === 'true' ||
      el.classList.contains('active') ||
      el.getAttribute('data-state') === 'active';

    tabs.push({
      voiceId,
      label: getElementLabel(el),
      active: isActive,
      disabled: isElementDisabled(el),
    });
  });

  return tabs;
}

// ============================================================================
// BUTTON DISCOVERY
// ============================================================================

function discoverButtons(): ButtonInfo[] {
  const buttons: ButtonInfo[] = [];

  // Find all buttons with voice-id (excluding tabs)
  const buttonElements = document.querySelectorAll(
    'button[data-voice-id]:not([data-voice-id^="tab-"]), ' +
    '[role="button"][data-voice-id]:not([data-voice-id^="tab-"])'
  );

  buttonElements.forEach((element) => {
    const el = element as HTMLElement;

    buttons.push({
      voiceId: el.getAttribute('data-voice-id') ?? '',
      label: getElementLabel(el),
      disabled: isElementDisabled(el),
      loading: isElementLoading(el),
      visible: isElementVisible(el),
    });
  });

  return buttons.filter(b => b.visible);
}

// ============================================================================
// INPUT FIELD DISCOVERY
// ============================================================================

function discoverInputFields(): InputFieldInfo[] {
  const fields: InputFieldInfo[] = [];

  const inputElements = document.querySelectorAll(
    'input[data-voice-id], textarea[data-voice-id]'
  );

  inputElements.forEach((element) => {
    const el = element as HTMLInputElement | HTMLTextAreaElement;
    if (!isElementVisible(el)) return;

    // Find associated error message
    const errorId = el.getAttribute('aria-describedby');
    let error: string | null = null;
    if (errorId) {
      const errorEl = document.getElementById(errorId);
      if (errorEl && errorEl.classList.contains('error')) {
        error = errorEl.textContent?.trim() ?? null;
      }
    }

    fields.push({
      voiceId: el.getAttribute('data-voice-id') ?? '',
      type: el.tagName.toLowerCase() === 'textarea' ? 'textarea' : 'input',
      value: el.value,
      placeholder: el.getAttribute('placeholder') ?? '',
      label: getElementLabel(el),
      disabled: isElementDisabled(el),
      required: el.hasAttribute('required') || el.getAttribute('aria-required') === 'true',
      error,
    });
  });

  return fields;
}

// ============================================================================
// DROPDOWN DISCOVERY
// ============================================================================

function discoverDropdowns(): DropdownInfo[] {
  const dropdowns: DropdownInfo[] = [];

  // Native select elements
  const selectElements = document.querySelectorAll('select[data-voice-id]');

  selectElements.forEach((element) => {
    const el = element as HTMLSelectElement;
    if (!isElementVisible(el)) return;

    const options: DropdownOptionInfo[] = [];
    for (let i = 0; i < el.options.length; i++) {
      const opt = el.options[i];
      // Skip placeholder options
      if (!opt.value && i === 0) continue;

      options.push({
        index: options.length, // 0-based index of non-placeholder options
        value: opt.value,
        label: opt.text,
        selected: opt.selected,
        disabled: opt.disabled,
      });
    }

    const selectedOpt = el.options[el.selectedIndex];

    dropdowns.push({
      voiceId: el.getAttribute('data-voice-id') ?? '',
      label: getElementLabel(el),
      expanded: false, // Native selects don't have expanded state
      selectedValue: selectedOpt?.value ?? null,
      selectedLabel: selectedOpt?.text ?? null,
      options,
      disabled: isElementDisabled(el),
    });
  });

  // Custom dropdown components (common patterns)
  const customDropdowns = document.querySelectorAll(
    '[data-voice-id][role="listbox"], ' +
    '[data-voice-id][role="combobox"]'
  );

  customDropdowns.forEach((element) => {
    const el = element as HTMLElement;
    if (!isElementVisible(el)) return;

    const expanded = el.getAttribute('aria-expanded') === 'true';
    const options: DropdownOptionInfo[] = [];

    // Find options within the dropdown
    const optionElements = el.querySelectorAll('[role="option"]');
    optionElements.forEach((optEl, idx) => {
      const opt = optEl as HTMLElement;
      options.push({
        index: idx,
        value: opt.getAttribute('data-value') ?? opt.textContent?.trim() ?? '',
        label: opt.textContent?.trim() ?? '',
        selected: opt.getAttribute('aria-selected') === 'true',
        disabled: isElementDisabled(opt),
      });
    });

    const selectedOption = options.find(o => o.selected);

    dropdowns.push({
      voiceId: el.getAttribute('data-voice-id') ?? '',
      label: getElementLabel(el),
      expanded,
      selectedValue: selectedOption?.value ?? null,
      selectedLabel: selectedOption?.label ?? null,
      options,
      disabled: isElementDisabled(el),
    });
  });

  return dropdowns;
}

// ============================================================================
// MODAL DISCOVERY
// ============================================================================

function discoverModals(): ModalInfo[] {
  const modals: ModalInfo[] = [];

  const modalElements = document.querySelectorAll(
    '[role="dialog"], [role="alertdialog"], [data-modal="true"]'
  );

  modalElements.forEach((element) => {
    const el = element as HTMLElement;
    const isOpen = isElementVisible(el) && el.getAttribute('aria-hidden') !== 'true';

    if (!isOpen) return;

    // Find title
    const titleId = el.getAttribute('aria-labelledby');
    let title = '';
    if (titleId) {
      const titleEl = document.getElementById(titleId);
      title = titleEl?.textContent?.trim() ?? '';
    }

    modals.push({
      id: el.id || `modal-${modals.length}`,
      voiceId: el.getAttribute('data-voice-id'),
      title,
      open: true,
    });
  });

  return modals;
}

// ============================================================================
// LIST ITEM DISCOVERY
// ============================================================================

function discoverListItems(): ListItemInfo[] {
  const items: ListItemInfo[] = [];

  // Look for list containers with voice-controllable items
  const listContainers = document.querySelectorAll(
    '[data-voice-id$="-list"], [data-voice-list="true"]'
  );

  listContainers.forEach((container) => {
    const listItems = container.querySelectorAll(
      '[data-voice-id], [role="option"], [role="listitem"]'
    );

    listItems.forEach((item, idx) => {
      const el = item as HTMLElement;
      if (!isElementVisible(el)) return;

      items.push({
        index: idx,
        voiceId: el.getAttribute('data-voice-id'),
        label: getElementLabel(el),
        selected:
          el.getAttribute('aria-selected') === 'true' ||
          el.classList.contains('selected') ||
          el.classList.contains('active'),
      });
    });
  });

  return items;
}

// ============================================================================
// MAIN STATE FUNCTION
// ============================================================================

/**
 * Get the complete current UI state.
 *
 * This function reads all voice-controllable elements from the DOM
 * and returns a comprehensive state object that can be:
 * 1. Sent to the backend for LLM context
 * 2. Used for verification after action execution
 * 3. Used to compute repair actions
 */
export function getUiState(): UiState {
  const tabs = discoverTabs();
  const activeTab = tabs.find(t => t.active)?.voiceId ?? null;

  const inputFields = discoverInputFields();
  const hasValidationErrors = inputFields.some(f => f.error !== null);

  const buttons = discoverButtons();
  const isLoading = buttons.some(b => b.loading) ||
    document.querySelector('[data-loading="true"]') !== null;

  return {
    route: window.location.pathname,
    activeTab,
    tabs,
    buttons,
    inputFields,
    dropdowns: discoverDropdowns(),
    modals: discoverModals(),
    listItems: discoverListItems(),
    isLoading,
    hasValidationErrors,
    capturedAt: Date.now(),
  };
}

// ============================================================================
// COMPACT STATE FOR LLM CONTEXT
// ============================================================================

export interface CompactUiState {
  route: string;
  activeTab: string | null;
  tabs: Array<{ id: string; label: string; active: boolean }>;
  buttons: Array<{ id: string; label: string }>;
  inputs: Array<{ id: string; label: string; value: string }>;
  dropdowns: Array<{
    id: string;
    label: string;
    selected: string | null;
    options: Array<{ idx: number; label: string }>;
  }>;
  modal: string | null;
}

/**
 * Get a compact version of UI state suitable for LLM prompts.
 * Minimizes token usage while providing necessary context.
 */
export function getCompactUiState(): CompactUiState {
  const state = getUiState();

  return {
    route: state.route,
    activeTab: state.activeTab,
    tabs: state.tabs.map(t => ({
      id: t.voiceId,
      label: t.label,
      active: t.active,
    })),
    buttons: state.buttons
      .filter(b => !b.disabled)
      .map(b => ({
        id: b.voiceId,
        label: b.label,
      })),
    inputs: state.inputFields.map(f => ({
      id: f.voiceId,
      label: f.label || f.placeholder,
      value: f.value,
    })),
    dropdowns: state.dropdowns.map(d => ({
      id: d.voiceId,
      label: d.label,
      selected: d.selectedLabel,
      options: d.options.map(o => ({
        idx: o.index,
        label: o.label,
      })),
    })),
    modal: state.modals.length > 0 ? state.modals[0].title : null,
  };
}

// ============================================================================
// ELEMENT FINDERS
// ============================================================================

/**
 * Find an element by its voice-id
 */
export function findElementByVoiceId(voiceId: string): HTMLElement | null {
  return document.querySelector(`[data-voice-id="${voiceId}"]`) as HTMLElement | null;
}

/**
 * Find a dropdown and its options by voice-id
 */
export function findDropdownByVoiceId(voiceId: string): DropdownInfo | null {
  const dropdowns = discoverDropdowns();
  return dropdowns.find(d => d.voiceId === voiceId) ?? null;
}

/**
 * Find a tab by voice-id
 */
export function findTabByVoiceId(voiceId: string): TabInfo | null {
  const tabs = discoverTabs();
  return tabs.find(t => t.voiceId === voiceId) ?? null;
}

// ============================================================================
// WAIT FOR UI STABILITY
// ============================================================================

/**
 * Wait for the UI to stabilize (no pending state changes).
 * Useful before capturing state for verification.
 */
export function waitForUiStability(maxWaitMs: number = 500): Promise<void> {
  return new Promise((resolve) => {
    let timeoutId: NodeJS.Timeout;
    let lastState = JSON.stringify(getCompactUiState());
    let stableCount = 0;
    const requiredStableChecks = 3;
    const checkInterval = 50;

    const check = () => {
      const currentState = JSON.stringify(getCompactUiState());

      if (currentState === lastState) {
        stableCount++;
        if (stableCount >= requiredStableChecks) {
          clearTimeout(timeoutId);
          resolve();
          return;
        }
      } else {
        stableCount = 0;
        lastState = currentState;
      }

      setTimeout(check, checkInterval);
    };

    // Timeout fallback
    timeoutId = setTimeout(() => {
      resolve();
    }, maxWaitMs);

    // Start checking
    setTimeout(check, checkInterval);
  });
}

// ============================================================================
// STATE DIFF
// ============================================================================

export interface StateDiff {
  tabChanged: boolean;
  previousTab: string | null;
  currentTab: string | null;
  fieldsChanged: string[];
  dropdownsChanged: string[];
  buttonsAppeared: string[];
  buttonsDisappeared: string[];
  modalOpened: string | null;
  modalClosed: string | null;
}

/**
 * Compute the difference between two UI states.
 * Useful for verifying that an action had the expected effect.
 */
export function computeStateDiff(before: UiState, after: UiState): StateDiff {
  const fieldsChanged: string[] = [];
  const dropdownsChanged: string[] = [];

  // Check field changes
  for (const afterField of after.inputFields) {
    const beforeField = before.inputFields.find(f => f.voiceId === afterField.voiceId);
    if (!beforeField || beforeField.value !== afterField.value) {
      fieldsChanged.push(afterField.voiceId);
    }
  }

  // Check dropdown changes
  for (const afterDropdown of after.dropdowns) {
    const beforeDropdown = before.dropdowns.find(d => d.voiceId === afterDropdown.voiceId);
    if (!beforeDropdown || beforeDropdown.selectedValue !== afterDropdown.selectedValue) {
      dropdownsChanged.push(afterDropdown.voiceId);
    }
  }

  // Check button changes
  const beforeButtonIds = new Set(before.buttons.map(b => b.voiceId));
  const afterButtonIds = new Set(after.buttons.map(b => b.voiceId));

  const buttonsAppeared = after.buttons
    .filter(b => !beforeButtonIds.has(b.voiceId))
    .map(b => b.voiceId);

  const buttonsDisappeared = before.buttons
    .filter(b => !afterButtonIds.has(b.voiceId))
    .map(b => b.voiceId);

  // Check modal changes
  const beforeModalTitles = new Set(before.modals.map(m => m.title));
  const afterModalTitles = new Set(after.modals.map(m => m.title));

  const modalOpened = after.modals.find(m => !beforeModalTitles.has(m.title))?.title ?? null;
  const modalClosed = before.modals.find(m => !afterModalTitles.has(m.title))?.title ?? null;

  return {
    tabChanged: before.activeTab !== after.activeTab,
    previousTab: before.activeTab,
    currentTab: after.activeTab,
    fieldsChanged,
    dropdownsChanged,
    buttonsAppeared,
    buttonsDisappeared,
    modalOpened,
    modalClosed,
  };
}
