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
 * Calculate similarity score between two strings (0-1)
 * Uses a combination of substring matching and word overlap
 */
function calculateSimilarity(str1: string, str2: string): number {
  const s1 = str1.toLowerCase().replace(/[-_\s]/g, '');
  const s2 = str2.toLowerCase().replace(/[-_\s]/g, '');

  // Exact match
  if (s1 === s2) return 1.0;

  // One contains the other
  if (s1.includes(s2) || s2.includes(s1)) return 0.9;

  // Word-based matching
  const words1 = str1.toLowerCase().split(/[-_\s]+/).filter(w => w.length > 2);
  const words2 = str2.toLowerCase().split(/[-_\s]+/).filter(w => w.length > 2);

  let matchedWords = 0;
  for (const w1 of words1) {
    for (const w2 of words2) {
      if (w1.includes(w2) || w2.includes(w1)) {
        matchedWords++;
        break;
      }
    }
  }

  if (words1.length > 0 && matchedWords > 0) {
    return 0.5 + (0.4 * matchedWords / Math.max(words1.length, words2.length));
  }

  // Prefix matching
  const minLen = Math.min(s1.length, s2.length);
  let prefixMatch = 0;
  for (let i = 0; i < minLen; i++) {
    if (s1[i] === s2[i]) prefixMatch++;
    else break;
  }

  if (prefixMatch >= 3) {
    return 0.3 + (0.3 * prefixMatch / Math.max(s1.length, s2.length));
  }

  return 0;
}

/**
 * Dynamically discover all tabs on the current page
 * Returns array of tab elements with their semantic identities
 */
function discoverAllTabs(): Array<{
  element: HTMLElement;
  identities: string[];  // All possible names for this tab
  isActive: boolean;
}> {
  const tabs: Array<{ element: HTMLElement; identities: string[]; isActive: boolean }> = [];

  // Find all tab-like elements using multiple selectors
  const tabSelectors = [
    '[role="tab"]',
    '[data-radix-collection-item]',
    'button[data-state]',
    '[data-voice-id^="tab-"]',
  ];

  const seenElements = new Set<HTMLElement>();

  for (const selector of tabSelectors) {
    const elements = document.querySelectorAll(selector);
    for (const el of elements) {
      const element = el as HTMLElement;
      if (seenElements.has(element)) continue;
      seenElements.add(element);

      // Extract all possible identities for this tab
      const identities: string[] = [];

      // 1. data-voice-id (highest priority)
      const voiceId = element.getAttribute('data-voice-id');
      if (voiceId) {
        identities.push(voiceId);
        identities.push(voiceId.replace('tab-', ''));
      }

      // 2. value attribute (Radix tabs)
      const value = element.getAttribute('value');
      if (value) identities.push(value);

      // 3. aria-controls
      const ariaControls = element.getAttribute('aria-controls');
      if (ariaControls) {
        identities.push(ariaControls);
        identities.push(ariaControls.replace('-tab', '').replace('-panel', ''));
      }

      // 4. Text content (cleaned)
      const text = element.textContent?.trim().replace(/\(\d+\)/g, '').trim();
      if (text && text.length < 50) identities.push(text);

      // 5. aria-label
      const ariaLabel = element.getAttribute('aria-label');
      if (ariaLabel) identities.push(ariaLabel);

      // 6. id attribute
      const id = element.getAttribute('id');
      if (id) identities.push(id);

      // Determine if tab is active
      const isActive = element.getAttribute('aria-selected') === 'true' ||
                       element.getAttribute('data-state') === 'active' ||
                       element.classList.contains('active');

      if (identities.length > 0) {
        tabs.push({ element, identities, isActive });
      }
    }
  }

  return tabs;
}

/**
 * Find the best matching tab for a given intent using fuzzy matching
 * NO hardcoded mappings - purely dynamic discovery
 */
function findTabByIntent(tabIntent: string): HTMLElement | null {
  const tabs = discoverAllTabs();

  if (tabs.length === 0) {
    log('No tabs found on current page');
    return null;
  }

  log(`Discovered ${tabs.length} tabs on page:`, tabs.map(t => t.identities[0]));

  let bestMatch: { element: HTMLElement; score: number } | null = null;

  for (const tab of tabs) {
    for (const identity of tab.identities) {
      const score = calculateSimilarity(tabIntent, identity);
      if (score > 0.5 && (!bestMatch || score > bestMatch.score)) {
        bestMatch = { element: tab.element, score };
      }
    }
  }

  if (bestMatch) {
    log(`Best tab match for "${tabIntent}": score=${bestMatch.score.toFixed(2)}`);
    return bestMatch.element;
  }

  return null;
}

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
  // NAVIGATE (Page navigation)
  // ========================================================================

  const handleNavigate = useCallback((event: CustomEvent) => {
    const { path, route } = event.detail || {};
    const targetPath = path || route;
    log('navigate', { targetPath });

    if (!targetPath) {
      warn('No navigation path provided');
      return;
    }

    router.push(targetPath);
    log('Navigated to:', targetPath);
  }, [router]);

  // ========================================================================
  // WORKFLOW (Multi-step action sequences)
  // ========================================================================

  const handleWorkflow = useCallback(async (event: CustomEvent) => {
    const { workflow, steps, description } = event.detail || {};
    log('workflow', { workflow, stepCount: steps?.length, description });

    if (!steps || !Array.isArray(steps) || steps.length === 0) {
      warn('No workflow steps provided');
      return;
    }

    // Execute steps sequentially
    for (let i = 0; i < steps.length; i++) {
      const step = steps[i];
      log(`Executing step ${i + 1}/${steps.length}:`, step.type);

      // Dispatch the action as a CustomEvent
      window.dispatchEvent(new CustomEvent(step.type, {
        detail: step.payload
      }));

      // Wait for UI to stabilize if this is a navigation step
      if (step.waitForLoad || step.type === 'ui.navigate') {
        // Wait for navigation to complete
        await new Promise(resolve => setTimeout(resolve, 500));
        // Wait for DOM to stabilize
        await waitForUiStability(300);
      } else {
        // Short delay between steps
        await new Promise(resolve => setTimeout(resolve, 100));
      }
    }

    log('Workflow completed:', workflow);
  }, []);

  // ========================================================================
  // SWITCH TAB - Universal dynamic discovery (NO hardcoded mappings)
  // ========================================================================

  const handleSwitchTab = useCallback((event: CustomEvent) => {
    const { target, voiceId, tabName, targetPage } = event.detail || {};
    const searchName = tabName || target || voiceId || '';
    log('switchTab (universal)', { searchName, targetPage });

    if (!searchName) {
      warn('No tab name provided');
      return;
    }

    // Normalize the search term
    const searchNormalized = searchName.toLowerCase()
      .replace(/tab|panel|section/g, '')
      .replace(/[-_\s]/g, '')
      .trim();

    // Dispatch voice-select-tab for pages that handle it via their own handlers
    window.dispatchEvent(new CustomEvent('voice-select-tab', {
      detail: { tab: searchNormalized, tabName: searchName }
    }));

    // UNIVERSAL APPROACH: Use dynamic tab discovery with fuzzy matching
    let element = findTabByIntent(searchName);

    // If not found, try additional variations
    if (!element) {
      const variations = [
        searchName,
        searchName.replace(/[-_]/g, ' '),
        searchName.replace(/\s+/g, '-'),
        `tab-${searchNormalized}`,
      ];
      for (const variant of variations) {
        element = findTabByIntent(variant);
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
      log('Switched to tab via dynamic discovery:', searchName);

      // Notify success
      window.dispatchEvent(new CustomEvent('voice-tab-switched', {
        detail: { tabName: searchName, success: true }
      }));
    } else {
      // Tab not found on current page
      // Check if backend provided a target page for cross-page navigation
      if (targetPage && pathname !== targetPage) {
        log(`Tab '${searchName}' requires navigation to ${targetPage}`);

        // Navigate to the target page first
        router.push(targetPage);

        // After navigation, re-dispatch the tab switch event
        // The page's voice handler will pick it up
        setTimeout(() => {
          log(`Re-dispatching voice-select-tab after navigation for: ${searchName}`);
          window.dispatchEvent(new CustomEvent('voice-select-tab', {
            detail: { tab: searchNormalized, tabName: searchName }
          }));
          // Also try direct tab discovery after page loads
          setTimeout(() => {
            const tabAfterNav = findTabByIntent(searchName);
            if (tabAfterNav) {
              tabAfterNav.click();
              log('Clicked tab after navigation:', searchName);
            }
          }, 300);
        }, 800); // Wait for navigation to complete
      } else {
        // Log available tabs to help debug
        const availableTabs = discoverAllTabs();
        warn(`Tab "${searchName}" not found. Available tabs:`, availableTabs.map(t => t.identities[0]));

        window.dispatchEvent(new CustomEvent('voice-tab-not-found', {
          detail: {
            tabName: searchName,
            availableTabs: availableTabs.map(t => t.identities[0])
          }
        }));
      }
    }
  }, [router, pathname]);

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

  // Store handlers in refs to avoid event listener duplication
  // This prevents the useEffect from re-running when callbacks change
  const handlersRef = useRef<Record<string, (event: CustomEvent) => void>>({});

  // Update refs when handlers change (no effect re-run needed)
  handlersRef.current = {
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
    'ui.navigate': handleNavigate,
    'ui.workflow': handleWorkflow as any,
  };

  useEffect(() => {
    // Create stable wrapper functions that delegate to refs
    // This ensures we add listeners only ONCE
    const eventTypes = [
      'ui.selectDropdown',
      'ui.expandDropdown',
      'ui.clickButton',
      'ui.openMenuAndClick',
      'ui.fillInput',
      'ui.clearInput',
      'ui.switchTab',
      'ui.selectListItem',
      'ui.searchAndNavigate',
      'ui.getUiState',
      'ui.getAvailableElements',
      'ui.navigate',
      'ui.workflow',
    ];

    // Stable handler that delegates to the ref
    const createStableHandler = (eventType: string) => (event: Event) => {
      const handler = handlersRef.current[eventType];
      if (handler) {
        handler(event as CustomEvent);
      }
    };

    // Create and store stable handlers
    const stableHandlers: Record<string, EventListener> = {};
    eventTypes.forEach(eventType => {
      stableHandlers[eventType] = createStableHandler(eventType);
      window.addEventListener(eventType, stableHandlers[eventType]);
    });

    log('Initialized voice UI controller');

    // Cleanup - remove the stable handlers (only runs on unmount)
    return () => {
      eventTypes.forEach(eventType => {
        window.removeEventListener(eventType, stableHandlers[eventType]);
      });
      log('Cleaned up voice UI controller');
    };
  }, []); // Empty dependency array - listeners added only once

  return null;
};

export default VoiceUIController;
