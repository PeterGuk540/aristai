'use client';

/**
 * VoiceUIController - Handles voice-triggered UI interactions
 *
 * This controller:
 * 1. Listens for voice UI action events (ui.switchTab, ui.clickButton, etc.)
 * 2. Uses dynamic DOM discovery (no hardcoded element registries)
 * 3. Executes actions with verification loop
 * 4. Reports results for voice feedback
 *
 * All voice-controllable elements must have a data-voice-id attribute.
 */

import { useEffect, useCallback, useRef } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import {
  getUiState,
  getCompactUiState,
  findElementByVoiceId,
  waitForUiStability,
  computeStateDiff,
} from '@/lib/voice-ui-state';
import {
  executeVoiceAction,
  ExecutionResult,
} from '@/lib/voice-action-executor';
import type { VoiceAction } from '@/lib/voice-action-schema';

// ============================================================================
// GLOBAL UI ELEMENTS (Shell-level, always present)
// ============================================================================

const GLOBAL_VOICE_IDS = [
  'theme-toggle',
  'user-menu',
  'sign-out',
  'language-toggle',
  'workspace-search',
];

// ============================================================================
// LOGGING
// ============================================================================

const LOG_PREFIX = '🎤 VoiceUI:';

function log(message: string, ...args: unknown[]) {
  console.log(`${LOG_PREFIX} ${message}`, ...args);
}

function warn(message: string, ...args: unknown[]) {
  console.warn(`${LOG_PREFIX} ${message}`, ...args);
}

// ============================================================================
// ELEMENT FINDING (Dynamic, no hardcoded registry)
// ============================================================================

/**
 * Find an element by voice-id or fallback strategies.
 * NO hardcoded element registry - all discovery is dynamic.
 */
function findElement(target: string | undefined): HTMLElement | null {
  if (!target) return null;

  // 1. Direct voice-id lookup
  let element = document.querySelector(`[data-voice-id="${target}"]`) as HTMLElement | null;
  if (element) return element;

  // 2. Partial voice-id match (for flexibility)
  element = document.querySelector(`[data-voice-id*="${target}"]`) as HTMLElement | null;
  if (element) return element;

  // 3. Try common variations
  const variations = [
    target,
    target.toLowerCase(),
    target.replace(/_/g, '-'),
    target.replace(/-/g, '_'),
    `tab-${target}`,
    `${target}-button`,
  ];

  for (const variation of variations) {
    element = document.querySelector(`[data-voice-id="${variation}"]`) as HTMLElement | null;
    if (element) return element;
  }

  // 4. Search by text content (buttons, tabs)
  const targetLower = target.toLowerCase().replace(/[-_]/g, ' ');
  const clickables = document.querySelectorAll('button, [role="button"], [role="tab"]');
  for (const el of clickables) {
    const text = el.textContent?.toLowerCase().trim() || '';
    const ariaLabel = el.getAttribute('aria-label')?.toLowerCase() || '';
    if (text.includes(targetLower) || targetLower.includes(text) ||
        ariaLabel.includes(targetLower)) {
      return el as HTMLElement;
    }
  }

  return null;
}

/**
 * Find a dropdown element
 */
function findDropdown(target: string | undefined): HTMLSelectElement | null {
  if (target) {
    const element = findElement(target);
    if (element?.tagName === 'SELECT') {
      return element as HTMLSelectElement;
    }
  }

  // Find first visible select on page
  const selects = document.querySelectorAll('select');
  for (const select of selects) {
    const rect = select.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      return select as HTMLSelectElement;
    }
  }

  return null;
}

/**
 * Find an input element
 */
function findInput(target: string | undefined): HTMLInputElement | HTMLTextAreaElement | null {
  // Special case: focused input
  if (target === 'focused-input') {
    const focused = document.activeElement;
    if (focused?.tagName === 'INPUT' || focused?.tagName === 'TEXTAREA') {
      return focused as HTMLInputElement | HTMLTextAreaElement;
    }
  }

  if (target) {
    const element = findElement(target);
    if (element?.tagName === 'INPUT' || element?.tagName === 'TEXTAREA') {
      return element as HTMLInputElement | HTMLTextAreaElement;
    }
  }

  // Find first visible, empty input
  const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]), textarea');
  for (const input of inputs) {
    const el = input as HTMLInputElement | HTMLTextAreaElement;
    const rect = el.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0 && !el.value) {
      return el;
    }
  }

  // Fall back to any visible input
  for (const input of inputs) {
    const el = input as HTMLInputElement | HTMLTextAreaElement;
    const rect = el.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      return el;
    }
  }

  return null;
}

// ============================================================================
// REACT-COMPATIBLE VALUE SETTERS
// ============================================================================

/**
 * Set input value in a React-compatible way
 */
function setInputValueReactCompatible(
  input: HTMLInputElement | HTMLTextAreaElement,
  value: string
): void {
  input.focus();

  const prototype = input.tagName === 'TEXTAREA'
    ? window.HTMLTextAreaElement.prototype
    : window.HTMLInputElement.prototype;

  const nativeSetter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;

  if (nativeSetter) {
    nativeSetter.call(input, value);
  } else {
    input.value = value;
  }

  // Update React's internal tracker
  const tracker = (input as any)._valueTracker;
  if (tracker) {
    tracker.setValue('__voice_trigger__');
  }

  // Dispatch events
  input.dispatchEvent(new Event('input', { bubbles: true }));
  input.dispatchEvent(new Event('change', { bubbles: true }));
}

/**
 * Set select value in a React-compatible way
 */
function setSelectValueReactCompatible(
  select: HTMLSelectElement,
  value: string
): void {
  select.focus();

  const nativeSetter = Object.getOwnPropertyDescriptor(
    window.HTMLSelectElement.prototype,
    'value'
  )?.set;

  if (nativeSetter) {
    nativeSetter.call(select, value);
  } else {
    select.value = value;
  }

  // Update React's internal tracker
  const tracker = (select as any)._valueTracker;
  if (tracker) {
    tracker.setValue('__voice_trigger__');
  }

  // Dispatch events
  select.dispatchEvent(new Event('change', { bubbles: true }));
  select.dispatchEvent(new Event('input', { bubbles: true }));
}

// ============================================================================
// GET DROPDOWN OPTIONS
// ============================================================================

function getDropdownOptions(select: HTMLSelectElement): Array<{
  value: string;
  text: string;
  index: number;
}> {
  const options: Array<{ value: string; text: string; index: number }> = [];
  let validIndex = 0;

  for (let i = 0; i < select.options.length; i++) {
    const opt = select.options[i];
    // Skip empty placeholder options
    if (opt.value) {
      options.push({
        value: opt.value,
        text: opt.text,
        index: validIndex++,
      });
    }
  }

  return options;
}

// ============================================================================
// VOICE UI CONTROLLER COMPONENT
// ============================================================================

export const VoiceUIController = () => {
  const router = useRouter();
  const pathname = usePathname();
  const lastActionRef = useRef<number>(0);

  // ========================================================================
  // DROPDOWN SELECTION
  // ========================================================================

  const handleSelectDropdown = useCallback((event: CustomEvent) => {
    const { target, voiceId, value, optionName, optionIndex, selectionIndex, selectionValue } = event.detail || {};
    log('selectDropdown', { target, voiceId, value, optionName, optionIndex, selectionIndex, selectionValue });

    const select = findDropdown(target || voiceId);
    if (!select) {
      warn('No dropdown found');
      return;
    }

    const options = getDropdownOptions(select);
    if (options.length === 0) {
      warn('Dropdown has no options');
      return;
    }

    let targetValue: string | null = null;

    // Priority 1: Direct value
    if (value !== undefined || selectionValue !== undefined) {
      targetValue = String(value ?? selectionValue);
    }
    // Priority 2: Index (0-based, -1 for last)
    else if (optionIndex !== undefined || selectionIndex !== undefined) {
      const idx = optionIndex ?? selectionIndex;
      const actualIdx = idx === -1 ? options.length - 1 : idx;
      if (actualIdx >= 0 && actualIdx < options.length) {
        targetValue = options[actualIdx].value;
      }
    }
    // Priority 3: Name matching
    else if (optionName) {
      const nameLower = optionName.toLowerCase();
      const match = options.find(o =>
        o.text.toLowerCase() === nameLower ||
        o.text.toLowerCase().includes(nameLower)
      );
      if (match) {
        targetValue = match.value;
      }
    }

    if (targetValue) {
      setSelectValueReactCompatible(select, targetValue);
      log('Selected:', targetValue);
    } else {
      warn('Could not determine selection');
    }
  }, []);

  // ========================================================================
  // EXPAND DROPDOWN
  // ========================================================================

  const handleExpandDropdown = useCallback((event: CustomEvent) => {
    const { target, voiceId } = event.detail || {};
    log('expandDropdown', { target, voiceId });

    const select = findDropdown(target || voiceId);
    if (!select) {
      warn('No dropdown found');
      return;
    }

    select.focus();
    select.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));

    // Report available options
    const options = getDropdownOptions(select);
    log('Options:', options.map((o, i) => `${i + 1}. ${o.text}`));

    window.dispatchEvent(new CustomEvent('voice-dropdown-options', {
      detail: { options: options.map(o => o.text) }
    }));
  }, []);

  // ========================================================================
  // BUTTON CLICK
  // ========================================================================

  const handleClickButton = useCallback((event: CustomEvent) => {
    const { target, voiceId, buttonLabel } = event.detail || {};
    log('clickButton', { target, voiceId, buttonLabel });

    // Debounce rapid clicks
    const now = Date.now();
    if (now - lastActionRef.current < 500) {
      log('Debounced rapid click');
      return;
    }
    lastActionRef.current = now;

    const element = findElement(target || voiceId) || (buttonLabel ? findElement(buttonLabel) : null);

    if (!element) {
      warn('Button not found:', target || voiceId);
      return;
    }

    if (element.hasAttribute('disabled') || element.getAttribute('aria-disabled') === 'true') {
      warn('Button is disabled');
      return;
    }

    element.click();
    log('Clicked button');
  }, []);

  // ========================================================================
  // MENU AND CLICK
  // ========================================================================

  const handleOpenMenuAndClick = useCallback((event: CustomEvent) => {
    const { menuTarget, menuVoiceId, itemTarget, itemVoiceId } = event.detail || {};
    log('openMenuAndClick', { menuTarget, menuVoiceId, itemTarget, itemVoiceId });

    const menuButton = findElement(menuTarget || menuVoiceId);
    if (!menuButton) {
      warn('Menu button not found');
      return;
    }

    menuButton.click();

    // Wait for menu to render, then click item
    setTimeout(() => {
      const menuItem = findElement(itemTarget || itemVoiceId);
      if (menuItem) {
        menuItem.click();
        log('Clicked menu item');
      } else {
        warn('Menu item not found');
      }
    }, 300);
  }, []);

  // ========================================================================
  // FILL INPUT
  // ========================================================================

  const handleFillInput = useCallback((event: CustomEvent) => {
    const { target, voiceId, value, content, append } = event.detail || {};
    const inputValue = value ?? content ?? '';
    log('fillInput', { target, voiceId, value: inputValue.substring(0, 50) });

    const input = findInput(target || voiceId);
    if (!input) {
      warn('No input found');
      return;
    }

    const newValue = append ? input.value + inputValue : inputValue;
    setInputValueReactCompatible(input, newValue);
    log('Filled input');
  }, []);

  // ========================================================================
  // CLEAR INPUT
  // ========================================================================

  const handleClearInput = useCallback((event: CustomEvent) => {
    const { target, voiceId } = event.detail || {};
    log('clearInput', { target, voiceId });

    const input = findInput(target || voiceId);
    if (!input) {
      warn('No input found');
      return;
    }

    setInputValueReactCompatible(input, '');
    input.blur();
    log('Cleared input');
  }, []);

  // ========================================================================
  // SWITCH TAB
  // ========================================================================

  const handleSwitchTab = useCallback((event: CustomEvent) => {
    const { target, voiceId, tabName } = event.detail || {};
    const searchName = tabName || target || voiceId || '';
    log('switchTab', { searchName });

    if (!searchName) {
      warn('No tab name provided');
      return;
    }

    const searchLower = searchName.toLowerCase().replace(/tab|panel|section/g, '').trim();
    const searchNormalized = searchLower.replace(/-/g, '');

    // Dispatch voice-select-tab for pages that handle it
    window.dispatchEvent(new CustomEvent('voice-select-tab', {
      detail: { tab: searchNormalized }
    }));

    let element: HTMLElement | null = null;

    // 1. Try direct voice-id lookup
    element = findElement(searchName) || findElement(`tab-${searchLower}`);

    // 2. Try Radix TabsTrigger by value
    if (!element) {
      const radixTabs = document.querySelectorAll('[data-radix-collection-item]');
      for (const tab of radixTabs) {
        const tabValue = tab.getAttribute('value')?.toLowerCase() || '';
        if (tabValue === searchLower || tabValue.replace(/-/g, '') === searchNormalized) {
          element = tab as HTMLElement;
          break;
        }
      }
    }

    // 3. Try role="tab" with aria-controls
    if (!element) {
      const roleTabs = document.querySelectorAll('[role="tab"]');
      for (const tab of roleTabs) {
        const ariaControls = tab.getAttribute('aria-controls')?.toLowerCase() || '';
        const tabId = tab.getAttribute('id')?.toLowerCase() || '';
        if (ariaControls.includes(searchLower) || tabId.includes(searchLower)) {
          element = tab as HTMLElement;
          break;
        }
      }
    }

    // 4. Try text content match
    if (!element) {
      const tabSelectors = ['[role="tab"]', '[data-radix-collection-item]', 'button[class*="tab"]'];
      for (const selector of tabSelectors) {
        const tabs = document.querySelectorAll(selector);
        for (const tab of tabs) {
          const tabText = tab.textContent?.toLowerCase().replace(/\(\d+\)/g, '').trim() || '';
          const voiceIdAttr = tab.getAttribute('data-voice-id')?.toLowerCase() || '';
          if (tabText === searchLower || tabText.startsWith(searchLower) ||
              tabText.replace(/-/g, '') === searchNormalized ||
              voiceIdAttr.includes(searchLower)) {
            element = tab as HTMLElement;
            break;
          }
        }
        if (element) break;
      }
    }

    if (element) {
      if (element.hasAttribute('disabled') || element.getAttribute('aria-disabled') === 'true') {
        warn('Tab is disabled');
        window.dispatchEvent(new CustomEvent('voice-tab-disabled', {
          detail: { tabName: searchName }
        }));
        return;
      }

      element.click();
      log('Switched to tab:', searchName);
    } else {
      warn('Tab not found:', searchName);
    }
  }, []);

  // ========================================================================
  // SELECT LIST ITEM
  // ========================================================================

  const handleSelectListItem = useCallback((event: CustomEvent) => {
    const { target, listVoiceId, itemName, itemIndex, itemVoiceId } = event.detail || {};
    log('selectListItem', { target, listVoiceId, itemName, itemIndex, itemVoiceId });

    // Find list container
    const container = findElement(target || listVoiceId) || document;
    const items = container.querySelectorAll('[data-voice-item], [role="listitem"], li, button[data-state]');

    if (items.length === 0) {
      warn('No list items found');
      return;
    }

    let selectedItem: HTMLElement | null = null;

    // Select by voice-id
    if (itemVoiceId) {
      selectedItem = findElement(itemVoiceId);
    }
    // Select by index (0-based, -1 for last)
    else if (itemIndex !== undefined) {
      const idx = itemIndex === -1 ? items.length - 1 : itemIndex;
      if (idx >= 0 && idx < items.length) {
        selectedItem = items[idx] as HTMLElement;
      }
    }
    // Select by name
    else if (itemName) {
      const nameLower = itemName.toLowerCase();
      for (const item of items) {
        const itemText = item.textContent?.toLowerCase() || '';
        if (itemText.includes(nameLower)) {
          selectedItem = item as HTMLElement;
          break;
        }
      }
    }

    if (selectedItem) {
      // If item contains a checkbox, click that directly
      const checkbox = selectedItem.querySelector('input[type="checkbox"]') as HTMLInputElement;
      if (checkbox) {
        checkbox.click();
      } else {
        selectedItem.click();
      }
      log('Selected list item');
    } else {
      warn('List item not found');
    }
  }, []);

  // ========================================================================
  // SEARCH AND NAVIGATE
  // ========================================================================

  const handleSearchAndNavigate = useCallback((event: CustomEvent) => {
    const query = String(event.detail?.query || event.detail?.target || '').trim();
    if (!query) {
      warn('searchAndNavigate missing query');
      return;
    }

    log('searchAndNavigate', { query });

    const input = findInput('workspace-search');
    if (input) {
      setInputValueReactCompatible(input, query);

      // Wait for search results and click best match
      setTimeout(() => {
        const links = document.querySelectorAll('a[href^="/"]') as NodeListOf<HTMLAnchorElement>;
        const queryLower = query.toLowerCase();
        for (const link of links) {
          if (link.textContent?.toLowerCase().includes(queryLower)) {
            link.click();
            log('Clicked search result');
            return;
          }
        }

        // Fallback: direct navigation
        const routes = [
          { keys: ['introduction', 'intro', 'guide', 'platform'], path: '/platform-guide' },
          { keys: ['integration', 'canvas', 'lms'], path: '/integrations' },
          { keys: ['course', 'courses'], path: '/courses' },
          { keys: ['session', 'sessions'], path: '/sessions' },
          { keys: ['forum', 'discussion'], path: '/forum' },
          { keys: ['console', 'copilot'], path: '/console' },
          { keys: ['report', 'reports'], path: '/reports' },
        ];

        const match = routes.find(r => r.keys.some(k => queryLower.includes(k)));
        if (match) {
          router.push(match.path);
        }
      }, 250);
    }
  }, [router]);

  // ========================================================================
  // GET UI STATE (for debugging and LLM context)
  // ========================================================================

  const handleGetUiState = useCallback(() => {
    const state = getCompactUiState();
    log('UI State:', state);

    window.dispatchEvent(new CustomEvent('voice-ui-state', {
      detail: state
    }));

    return state;
  }, []);

  // ========================================================================
  // GET AVAILABLE ELEMENTS
  // ========================================================================

  const handleGetAvailableElements = useCallback(() => {
    const voiceElements = document.querySelectorAll('[data-voice-id]');
    const elements: string[] = [];

    voiceElements.forEach(el => {
      const id = el.getAttribute('data-voice-id');
      if (id) elements.push(id);
    });

    log('Available elements on', pathname, ':', elements);

    window.dispatchEvent(new CustomEvent('voice-ui-elements', {
      detail: { page: pathname, elements }
    }));

    return elements;
  }, [pathname]);

  // ========================================================================
  // EVENT LISTENER SETUP
  // ========================================================================

  useEffect(() => {
    const handlers: Record<string, (event: CustomEvent) => void> = {
      'ui.selectDropdown': handleSelectDropdown,
      'ui.expandDropdown': handleExpandDropdown,
      'ui.clickButton': handleClickButton,
      'ui.openMenuAndClick': handleOpenMenuAndClick,
      'ui.fillInput': handleFillInput,
      'ui.clearInput': handleClearInput,
      'ui.switchTab': handleSwitchTab,
      'ui.selectListItem': handleSelectListItem,
      'ui.searchAndNavigate': handleSearchAndNavigate,
      'ui.getUiState': handleGetUiState as any,
      'ui.getAvailableElements': handleGetAvailableElements as any,
    };

    // Add all event listeners
    Object.entries(handlers).forEach(([event, handler]) => {
      window.addEventListener(event, handler as EventListener);
    });

    log('Initialized on', pathname);

    // Cleanup
    return () => {
      Object.entries(handlers).forEach(([event, handler]) => {
        window.removeEventListener(event, handler as EventListener);
      });
    };
  }, [
    pathname,
    handleSelectDropdown,
    handleExpandDropdown,
    handleClickButton,
    handleOpenMenuAndClick,
    handleFillInput,
    handleClearInput,
    handleSwitchTab,
    handleSelectListItem,
    handleSearchAndNavigate,
    handleGetUiState,
    handleGetAvailableElements,
  ]);

  return null;
};

export default VoiceUIController;
