/**
 * Voice Action Executor - Execute → Verify → Repair Loop
 *
 * This module implements the verification loop for voice actions:
 * 1. Capture UI state before action
 * 2. Execute the action
 * 3. Wait for UI stability
 * 4. Capture UI state after action
 * 5. Verify expected change occurred
 * 6. If failed, attempt repair or report error
 */

import {
  VoiceAction,
  ActionResult,
  validateVoiceAction,
} from './voice-action-schema';

import {
  UiState,
  getUiState,
  waitForUiStability,
  computeStateDiff,
  findElementByVoiceId,
  StateDiff,
} from './voice-ui-state';

// ============================================================================
// EXECUTION RESULT TYPES
// ============================================================================

export interface ExecutionContext {
  action: VoiceAction;
  stateBefore: UiState;
  stateAfter: UiState;
  diff: StateDiff;
  executionTimeMs: number;
  retryCount: number;
}

export interface ExecutionSuccess {
  success: true;
  context: ExecutionContext;
  message: string;
}

export interface ExecutionFailure {
  success: false;
  context: ExecutionContext | null;
  error: string;
  recoverable: boolean;
  repairAttempted: boolean;
  suggestion?: string;
}

export type ExecutionResult = ExecutionSuccess | ExecutionFailure;

// ============================================================================
// LOGGING
// ============================================================================

const LOG_PREFIX = '🎤 VoiceExecutor:';

function logAction(action: VoiceAction, phase: string) {
  console.log(`${LOG_PREFIX} [${phase}] ${action.type}`, action.payload);
}

function logVerification(passed: boolean, reason: string) {
  const icon = passed ? '✅' : '❌';
  console.log(`${LOG_PREFIX} ${icon} Verification: ${reason}`);
}

// ============================================================================
// ACTION EXECUTORS
// ============================================================================

/**
 * Execute a navigation action
 */
function executeNavigate(payload: { route: string }): boolean {
  if (typeof window !== 'undefined') {
    window.location.href = payload.route;
    return true;
  }
  return false;
}

/**
 * Execute a tab switch action
 */
function executeSwitchTab(payload: { voiceId: string }): boolean {
  const element = findElementByVoiceId(payload.voiceId);
  if (!element) {
    console.warn(`${LOG_PREFIX} Tab not found: ${payload.voiceId}`);
    return false;
  }

  element.click();
  return true;
}

/**
 * Execute a button click action
 */
function executeClickButton(payload: { voiceId: string }): boolean {
  const element = findElementByVoiceId(payload.voiceId);
  if (!element) {
    console.warn(`${LOG_PREFIX} Button not found: ${payload.voiceId}`);
    return false;
  }

  // Check if button is disabled
  if (element.hasAttribute('disabled') || element.getAttribute('aria-disabled') === 'true') {
    console.warn(`${LOG_PREFIX} Button is disabled: ${payload.voiceId}`);
    return false;
  }

  element.click();
  return true;
}

/**
 * Execute a dropdown expand action
 */
function executeExpandDropdown(payload: { voiceId: string }): boolean {
  const element = findElementByVoiceId(payload.voiceId);
  if (!element) {
    console.warn(`${LOG_PREFIX} Dropdown not found: ${payload.voiceId}`);
    return false;
  }

  // For native selects, focus to show options
  if (element.tagName === 'SELECT') {
    element.focus();
    // Simulate click to open dropdown
    element.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    return true;
  }

  // For custom dropdowns, click to expand
  element.click();
  return true;
}

/**
 * Execute a dropdown select action with React-compatible value setting
 */
function executeSelectDropdown(payload: {
  voiceId: string;
  selectionIndex?: number;
  selectionValue?: string;
}): boolean {
  const element = findElementByVoiceId(payload.voiceId) as HTMLSelectElement | null;
  if (!element) {
    console.warn(`${LOG_PREFIX} Dropdown not found: ${payload.voiceId}`);
    return false;
  }

  if (element.tagName !== 'SELECT') {
    console.warn(`${LOG_PREFIX} Element is not a SELECT: ${payload.voiceId}`);
    return false;
  }

  let targetValue: string | null = null;
  let targetIndex: number | null = null;

  // Find the target option
  const options = Array.from(element.options).filter(o => o.value); // Skip empty placeholder

  if (payload.selectionIndex !== undefined) {
    // Handle negative index (last = -1)
    const idx = payload.selectionIndex < 0
      ? options.length + payload.selectionIndex
      : payload.selectionIndex;

    if (idx >= 0 && idx < options.length) {
      targetValue = options[idx].value;
      targetIndex = idx;
    }
  } else if (payload.selectionValue !== undefined) {
    const option = options.find(o => o.value === payload.selectionValue);
    if (option) {
      targetValue = option.value;
      targetIndex = options.indexOf(option);
    }
  }

  if (targetValue === null) {
    console.warn(`${LOG_PREFIX} Could not find option for selection:`, payload);
    return false;
  }

  // React-compatible value setting
  element.focus();

  // Use native setter to bypass React's controlled component protection
  const nativeSelectValueSetter = Object.getOwnPropertyDescriptor(
    window.HTMLSelectElement.prototype,
    'value'
  )?.set;

  if (nativeSelectValueSetter) {
    nativeSelectValueSetter.call(element, targetValue);
  } else {
    element.value = targetValue;
  }

  // Update React's internal tracker
  const tracker = (element as any)._valueTracker;
  if (tracker) {
    tracker.setValue('__voice_trigger__');
  }

  // Dispatch change event
  element.dispatchEvent(new Event('change', { bubbles: true }));
  element.dispatchEvent(new Event('input', { bubbles: true }));

  console.log(`${LOG_PREFIX} Selected dropdown option: ${targetValue}`);
  return true;
}

/**
 * Execute a fill input action with React-compatible value setting
 */
function executeFillInput(payload: {
  voiceId: string;
  content: string;
  append?: boolean;
}): boolean {
  const element = findElementByVoiceId(payload.voiceId) as HTMLInputElement | HTMLTextAreaElement | null;
  if (!element) {
    console.warn(`${LOG_PREFIX} Input not found: ${payload.voiceId}`);
    return false;
  }

  if (element.tagName !== 'INPUT' && element.tagName !== 'TEXTAREA') {
    console.warn(`${LOG_PREFIX} Element is not an input: ${payload.voiceId}`);
    return false;
  }

  element.focus();

  const newValue = payload.append
    ? element.value + payload.content
    : payload.content;

  // Use native setter for React compatibility
  const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
    element.tagName === 'TEXTAREA'
      ? window.HTMLTextAreaElement.prototype
      : window.HTMLInputElement.prototype,
    'value'
  )?.set;

  if (nativeInputValueSetter) {
    nativeInputValueSetter.call(element, newValue);
  } else {
    element.value = newValue;
  }

  // Update React's internal tracker
  const tracker = (element as any)._valueTracker;
  if (tracker) {
    tracker.setValue('__voice_trigger__');
  }

  // Dispatch events
  element.dispatchEvent(new Event('input', { bubbles: true }));
  element.dispatchEvent(new Event('change', { bubbles: true }));

  console.log(`${LOG_PREFIX} Filled input: ${payload.voiceId} = "${newValue.substring(0, 50)}..."`);
  return true;
}

/**
 * Execute a clear input action
 */
function executeClearInput(payload: { voiceId: string }): boolean {
  return executeFillInput({
    voiceId: payload.voiceId,
    content: '',
    append: false,
  });
}

/**
 * Execute a list item selection
 */
function executeSelectListItem(payload: {
  listVoiceId?: string;
  itemIndex?: number;
  itemVoiceId?: string;
}): boolean {
  let targetElement: HTMLElement | null = null;

  if (payload.itemVoiceId) {
    targetElement = findElementByVoiceId(payload.itemVoiceId);
  } else if (payload.listVoiceId && payload.itemIndex !== undefined) {
    const container = findElementByVoiceId(payload.listVoiceId);
    if (container) {
      const items = container.querySelectorAll('[data-voice-id], [role="option"], [role="listitem"]');
      const idx = payload.itemIndex < 0
        ? items.length + payload.itemIndex
        : payload.itemIndex;
      targetElement = items[idx] as HTMLElement;
    }
  }

  if (!targetElement) {
    console.warn(`${LOG_PREFIX} List item not found:`, payload);
    return false;
  }

  targetElement.click();
  return true;
}

/**
 * Execute scroll action
 */
function executeScroll(payload: {
  direction: 'up' | 'down' | 'top' | 'bottom';
  targetVoiceId?: string;
  amount?: number;
}): boolean {
  if (payload.targetVoiceId) {
    const element = findElementByVoiceId(payload.targetVoiceId);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return true;
    }
    return false;
  }

  const scrollAmount = payload.amount ?? 300;
  const container = document.scrollingElement || document.documentElement;

  switch (payload.direction) {
    case 'up':
      container.scrollBy({ top: -scrollAmount, behavior: 'smooth' });
      break;
    case 'down':
      container.scrollBy({ top: scrollAmount, behavior: 'smooth' });
      break;
    case 'top':
      container.scrollTo({ top: 0, behavior: 'smooth' });
      break;
    case 'bottom':
      container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
      break;
  }

  return true;
}

/**
 * Execute form submission
 */
function executeSubmitForm(payload: {
  formVoiceId?: string;
  submitButtonVoiceId?: string;
}): boolean {
  if (payload.submitButtonVoiceId) {
    return executeClickButton({ voiceId: payload.submitButtonVoiceId });
  }

  if (payload.formVoiceId) {
    const form = findElementByVoiceId(payload.formVoiceId) as HTMLFormElement;
    if (form && form.tagName === 'FORM') {
      form.requestSubmit();
      return true;
    }
  }

  // Try to find any submit button in the active form
  const submitButton = document.querySelector('button[type="submit"]:not([disabled])') as HTMLElement;
  if (submitButton) {
    submitButton.click();
    return true;
  }

  return false;
}

/**
 * Execute toast notification
 */
function executeToast(payload: { message: string; variant?: string; duration?: number }): boolean {
  window.dispatchEvent(new CustomEvent('ui.toast', { detail: payload }));
  return true;
}

/**
 * Execute modal actions
 */
function executeOpenModal(payload: { modalId: string }): boolean {
  window.dispatchEvent(new CustomEvent('ui.openModal', { detail: payload }));
  return true;
}

function executeCloseModal(payload: { modalId?: string }): boolean {
  // Try to find and click close button
  const closeButton = document.querySelector(
    '[role="dialog"] [data-voice-id="close-modal"], ' +
    '[role="dialog"] button[aria-label="Close"]'
  ) as HTMLElement;

  if (closeButton) {
    closeButton.click();
    return true;
  }

  // Dispatch close event
  window.dispatchEvent(new CustomEvent('ui.closeModal', { detail: payload }));
  return true;
}

/**
 * Execute menu action
 */
function executeOpenMenuAndClick(payload: { menuVoiceId: string; itemVoiceId: string }): boolean {
  const menu = findElementByVoiceId(payload.menuVoiceId);
  if (!menu) {
    console.warn(`${LOG_PREFIX} Menu not found: ${payload.menuVoiceId}`);
    return false;
  }

  // Open the menu
  menu.click();

  // Wait briefly for menu to open, then click item
  setTimeout(() => {
    const item = findElementByVoiceId(payload.itemVoiceId);
    if (item) {
      item.click();
    }
  }, 100);

  return true;
}

// ============================================================================
// MAIN EXECUTOR
// ============================================================================

/**
 * Execute a voice action and return the raw result (no verification)
 */
function executeActionRaw(action: VoiceAction): boolean {
  switch (action.type) {
    case 'ui.navigate':
      return executeNavigate(action.payload);
    case 'ui.switchTab':
      return executeSwitchTab(action.payload);
    case 'ui.clickButton':
      return executeClickButton(action.payload);
    case 'ui.expandDropdown':
      return executeExpandDropdown(action.payload);
    case 'ui.selectDropdown':
      return executeSelectDropdown(action.payload);
    case 'ui.fillInput':
      return executeFillInput(action.payload);
    case 'ui.clearInput':
      return executeClearInput(action.payload);
    case 'ui.selectListItem':
      return executeSelectListItem(action.payload);
    case 'ui.scroll':
      return executeScroll(action.payload);
    case 'ui.submitForm':
      return executeSubmitForm(action.payload);
    case 'ui.toast':
      return executeToast(action.payload);
    case 'ui.openModal':
      return executeOpenModal(action.payload);
    case 'ui.closeModal':
      return executeCloseModal(action.payload);
    case 'ui.openMenuAndClick':
      return executeOpenMenuAndClick(action.payload);
    default:
      console.warn(`${LOG_PREFIX} Unknown action type:`, action);
      return false;
  }
}

// ============================================================================
// VERIFICATION
// ============================================================================

interface VerificationResult {
  passed: boolean;
  reason: string;
  suggestion?: string;
}

/**
 * Verify that an action had the expected effect
 */
function verifyAction(
  action: VoiceAction,
  stateBefore: UiState,
  stateAfter: UiState,
  diff: StateDiff
): VerificationResult {
  switch (action.type) {
    case 'ui.navigate':
      // Navigation changes the page, so we can't verify in the same context
      return { passed: true, reason: 'Navigation initiated' };

    case 'ui.switchTab':
      if (diff.tabChanged && stateAfter.activeTab === action.payload.voiceId) {
        return { passed: true, reason: `Tab switched to ${action.payload.voiceId}` };
      }
      if (stateAfter.activeTab === action.payload.voiceId) {
        return { passed: true, reason: 'Tab was already active' };
      }
      return {
        passed: false,
        reason: `Tab did not switch. Expected: ${action.payload.voiceId}, Got: ${stateAfter.activeTab}`,
        suggestion: 'Try clicking the tab directly',
      };

    case 'ui.clickButton':
      // Buttons might trigger various effects - we can't verify specifically
      // but we can check if the button was found and not disabled
      const button = stateAfter.buttons.find(b => b.voiceId === action.payload.voiceId);
      if (!button) {
        return {
          passed: false,
          reason: `Button not found: ${action.payload.voiceId}`,
          suggestion: 'The button may not be visible on this page',
        };
      }
      return { passed: true, reason: 'Button clicked' };

    case 'ui.selectDropdown':
      if (diff.dropdownsChanged.includes(action.payload.voiceId)) {
        return { passed: true, reason: 'Dropdown selection changed' };
      }
      // Check if the value matches what we expect
      const dropdown = stateAfter.dropdowns.find(d => d.voiceId === action.payload.voiceId);
      if (!dropdown) {
        return {
          passed: false,
          reason: `Dropdown not found: ${action.payload.voiceId}`,
        };
      }
      if (action.payload.selectionValue && dropdown.selectedValue === action.payload.selectionValue) {
        return { passed: true, reason: 'Selection confirmed' };
      }
      if (action.payload.selectionIndex !== undefined) {
        const expectedOption = dropdown.options[action.payload.selectionIndex];
        if (expectedOption && dropdown.selectedValue === expectedOption.value) {
          return { passed: true, reason: 'Selection confirmed by index' };
        }
      }
      return {
        passed: false,
        reason: `Dropdown selection did not change as expected`,
        suggestion: 'Try selecting by name instead of index',
      };

    case 'ui.fillInput':
      if (diff.fieldsChanged.includes(action.payload.voiceId)) {
        return { passed: true, reason: 'Input value changed' };
      }
      const field = stateAfter.inputFields.find(f => f.voiceId === action.payload.voiceId);
      if (!field) {
        return {
          passed: false,
          reason: `Input not found: ${action.payload.voiceId}`,
        };
      }
      if (field.value.includes(action.payload.content)) {
        return { passed: true, reason: 'Content filled' };
      }
      return {
        passed: false,
        reason: `Input content did not update`,
        suggestion: 'The field might be read-only or have validation',
      };

    case 'ui.clearInput':
      const clearedField = stateAfter.inputFields.find(f => f.voiceId === action.payload.voiceId);
      if (clearedField && clearedField.value === '') {
        return { passed: true, reason: 'Input cleared' };
      }
      return {
        passed: false,
        reason: `Input was not cleared`,
      };

    case 'ui.openModal':
      if (diff.modalOpened) {
        return { passed: true, reason: `Modal opened: ${diff.modalOpened}` };
      }
      return {
        passed: false,
        reason: 'Modal did not open',
      };

    case 'ui.closeModal':
      if (diff.modalClosed || stateAfter.modals.length < stateBefore.modals.length) {
        return { passed: true, reason: 'Modal closed' };
      }
      if (stateAfter.modals.length === 0) {
        return { passed: true, reason: 'No modal to close' };
      }
      return {
        passed: false,
        reason: 'Modal did not close',
      };

    default:
      // For actions we can't verify, assume success if execution didn't fail
      return { passed: true, reason: 'Action executed (no specific verification)' };
  }
}

// ============================================================================
// REPAIR STRATEGIES
// ============================================================================

/**
 * Attempt to compute a repair action when verification fails
 */
function computeRepairAction(
  action: VoiceAction,
  stateAfter: UiState,
  verificationResult: VerificationResult
): VoiceAction | null {
  // For now, we don't auto-repair. This could be extended to:
  // - Retry with slight variations
  // - Try alternative element selectors
  // - Wait longer and retry

  // Return null to indicate no repair is possible
  return null;
}

// ============================================================================
// MAIN EXECUTION FUNCTION
// ============================================================================

const MAX_RETRIES = 1;
const STABILITY_WAIT_MS = 200;

/**
 * Execute a voice action with verification loop.
 *
 * This function:
 * 1. Captures UI state before the action
 * 2. Executes the action
 * 3. Waits for UI stability
 * 4. Captures UI state after
 * 5. Verifies the expected change occurred
 * 6. Attempts repair if verification fails
 */
export async function executeVoiceAction(action: VoiceAction): Promise<ExecutionResult> {
  // Validate action
  const validatedAction = validateVoiceAction(action);
  if (!validatedAction) {
    return {
      success: false,
      context: null,
      error: 'Invalid action schema',
      recoverable: false,
      repairAttempted: false,
    };
  }

  logAction(validatedAction, 'START');
  const startTime = Date.now();

  let retryCount = 0;
  let lastContext: ExecutionContext | null = null;

  while (retryCount <= MAX_RETRIES) {
    // Step 1: Capture state before
    const stateBefore = getUiState();

    // Step 2: Execute action
    logAction(validatedAction, retryCount === 0 ? 'EXECUTE' : `RETRY-${retryCount}`);
    const executed = executeActionRaw(validatedAction);

    if (!executed) {
      return {
        success: false,
        context: null,
        error: `Failed to execute ${validatedAction.type}`,
        recoverable: true,
        repairAttempted: retryCount > 0,
        suggestion: 'Element may not be visible or accessible',
      };
    }

    // Step 3: Wait for UI stability
    await waitForUiStability(STABILITY_WAIT_MS);

    // Step 4: Capture state after
    const stateAfter = getUiState();
    const diff = computeStateDiff(stateBefore, stateAfter);
    const executionTimeMs = Date.now() - startTime;

    lastContext = {
      action: validatedAction,
      stateBefore,
      stateAfter,
      diff,
      executionTimeMs,
      retryCount,
    };

    // Step 5: Verify
    const verification = verifyAction(validatedAction, stateBefore, stateAfter, diff);
    logVerification(verification.passed, verification.reason);

    if (verification.passed) {
      return {
        success: true,
        context: lastContext,
        message: verification.reason,
      };
    }

    // Step 6: Attempt repair
    const repairAction = computeRepairAction(validatedAction, stateAfter, verification);
    if (repairAction && retryCount < MAX_RETRIES) {
      console.log(`${LOG_PREFIX} Attempting repair...`);
      retryCount++;
      continue;
    }

    // Verification failed, no repair possible
    return {
      success: false,
      context: lastContext,
      error: verification.reason,
      recoverable: false,
      repairAttempted: retryCount > 0,
      suggestion: verification.suggestion,
    };
  }

  // Should not reach here, but safety return
  return {
    success: false,
    context: lastContext,
    error: 'Max retries exceeded',
    recoverable: false,
    repairAttempted: true,
  };
}

// ============================================================================
// BATCH EXECUTION
// ============================================================================

/**
 * Execute multiple actions in sequence, stopping on first failure
 */
export async function executeVoiceActions(actions: VoiceAction[]): Promise<ExecutionResult[]> {
  const results: ExecutionResult[] = [];

  for (const action of actions) {
    const result = await executeVoiceAction(action);
    results.push(result);

    if (!result.success) {
      break;
    }
  }

  return results;
}

// ============================================================================
// EVENT HANDLER FOR LEGACY COMPATIBILITY
// ============================================================================

/**
 * Handle legacy CustomEvent-based actions.
 * This bridges the old event-based system with the new verified executor.
 */
export function setupLegacyEventHandlers() {
  const actionTypes = [
    'ui.switchTab',
    'ui.clickButton',
    'ui.selectDropdown',
    'ui.expandDropdown',
    'ui.fillInput',
    'ui.selectListItem',
    'ui.openMenuAndClick',
  ];

  actionTypes.forEach(eventType => {
    window.addEventListener(eventType, async (event: Event) => {
      const customEvent = event as CustomEvent;
      const payload = customEvent.detail;

      // Convert legacy event to typed action
      const action: VoiceAction = {
        type: eventType as VoiceAction['type'],
        payload,
        correlationId: payload.correlationId || `legacy-${Date.now()}`,
        timestamp: Date.now(),
      } as VoiceAction;

      // Execute with verification
      const result = await executeVoiceAction(action);

      // Dispatch result event for any listeners
      window.dispatchEvent(new CustomEvent('voice.actionResult', {
        detail: result,
      }));
    });
  });

  console.log(`${LOG_PREFIX} Legacy event handlers set up for ${actionTypes.length} action types`);
}
