'use client';

import { useEffect, useCallback, useRef } from 'react';
import { useRouter, usePathname } from 'next/navigation';

/**
 * Page element registry - maps voice targets to DOM selectors
 * This allows the voice assistant to target specific UI elements
 */
const UI_ELEMENT_REGISTRY: Record<string, Record<string, string>> = {
  // Reports page elements
  '/reports': {
    'courseDropdown': '[data-voice-id="select-course"]',
    'sessionDropdown': '[data-voice-id="select-session"]',
    'generateButton': '[data-voice-id="generate-report"]',
    'refreshButton': '[data-voice-id="refresh-report"]',
    'summaryTab': '[data-voice-id="tab-summary"]',
    'participationTab': '[data-voice-id="tab-participation"]',
    'scoringTab': '[data-voice-id="tab-scoring"]',
  },
  // Courses page elements
  '/courses': {
    'courseDropdown': '[data-voice-id="select-course"]',
    'courseTitleInput': '[data-voice-id="course-title"]',
    'syllabusInput': '[data-voice-id="syllabus"]',
    'objectivesInput': '[data-voice-id="objectives"]',
    'createButton': '[data-voice-id="create-course"]',
    'generatePlansButton': '[data-voice-id="generate-plans"]',
    'enrollButton': '[data-voice-id="enroll-students"]',
    'refreshButton': '[data-voice-id="refresh"]',
    'coursesTab': '[data-voice-id="tab-courses"]',
    'createTab': '[data-voice-id="tab-create"]',
    'enrollmentTab': '[data-voice-id="tab-enrollment"]',
    'joinTab': '[data-voice-id="tab-join"]',
    'joinCodeInput': '[data-voice-id="join-code"]',
    'joinButton': '[data-voice-id="join-course"]',
  },
  // Sessions page elements
  '/sessions': {
    'courseDropdown': '[data-voice-id="select-course"]',
    'sessionTitleInput': '[data-voice-id="session-title"]',
    'createButton': '[data-voice-id="create-session"]',
    'goLiveButton': '[data-voice-id="go-live"]',
    'completeButton': '[data-voice-id="complete-session"]',
    'scheduleButton': '[data-voice-id="schedule-session"]',
    'sessionsTab': '[data-voice-id="tab-sessions"]',
    'createTab': '[data-voice-id="tab-create"]',
    'manageTab': '[data-voice-id="tab-manage"]',
    'sessionList': '[data-voice-id="session-list"]',
  },
  // Forum page elements
  '/forum': {
    'courseDropdown': '[data-voice-id="select-course"]',
    'sessionDropdown': '[data-voice-id="select-session"]',
    'postTextarea': '[data-voice-id="new-post"]',
    'postButton': '[data-voice-id="submit-post"]',
    'refreshButton': '[data-voice-id="refresh"]',
    'casesTab': '[data-voice-id="tab-cases"]',
    'discussionTab': '[data-voice-id="tab-discussion"]',
  },
  // Console page elements
  '/console': {
    'courseDropdown': '[data-voice-id="select-course"]',
    'sessionDropdown': '[data-voice-id="select-session"]',
    'startCopilotButton': '[data-voice-id="start-copilot"]',
    'stopCopilotButton': '[data-voice-id="stop-copilot"]',
    'refreshButton': '[data-voice-id="refresh-interventions"]',
    'pollQuestionInput': '[data-voice-id="poll-question"]',
    'createPollButton': '[data-voice-id="create-poll"]',
    'caseTextarea': '[data-voice-id="case-prompt"]',
    'postCaseButton': '[data-voice-id="post-case"]',
    'copilotTab': '[data-voice-id="tab-copilot"]',
    'pollsTab': '[data-voice-id="tab-polls"]',
    'casesTab': '[data-voice-id="tab-cases"]',
    'requestsTab': '[data-voice-id="tab-requests"]',
    'rosterTab': '[data-voice-id="tab-roster"]',
    'rosterCourseDropdown': '[data-voice-id="roster-course"]',
    'uploadRosterButton': '[data-voice-id="upload-roster"]',
  },
};

/**
 * Voice-friendly names mapping to actual option values
 * Helps match spoken words like "first", "second" to actual options
 */
const ORDINAL_MAP: Record<string, number> = {
  'first': 0,
  'second': 1,
  'third': 2,
  'fourth': 3,
  'fifth': 4,
  'last': -1,
  '1st': 0,
  '2nd': 1,
  '3rd': 2,
  '4th': 3,
  '5th': 4,
  'one': 0,
  'two': 1,
  'three': 2,
  'four': 3,
  'five': 4,
};

/**
 * VoiceUIController - Handles voice-triggered UI interactions within pages
 *
 * Listens for custom events and interacts with UI elements:
 * - ui.selectDropdown: Selects an option from a dropdown
 * - ui.clickButton: Clicks a button
 * - ui.fillInput: Fills an input field
 * - ui.switchTab: Switches to a tab
 * - ui.selectListItem: Selects an item from a list
 */
export const VoiceUIController = () => {
  const router = useRouter();
  const pathname = usePathname();
  const lastActionRef = useRef<number>(0);

  /**
   * Find an element using the registry or direct selector
   */
  const findElement = useCallback((target: string): HTMLElement | null => {
    // First, check if it's a direct voice-id
    let element = document.querySelector(`[data-voice-id="${target}"]`) as HTMLElement;
    if (element) return element;

    // Check the page registry
    const pageRegistry = UI_ELEMENT_REGISTRY[pathname] || {};
    const selector = pageRegistry[target];
    if (selector) {
      element = document.querySelector(selector) as HTMLElement;
      if (element) return element;
    }

    // Try common patterns
    const patterns = [
      `[data-voice-id*="${target}"]`,
      `[id*="${target}"]`,
      `[name*="${target}"]`,
      `select[aria-label*="${target}" i]`,
      `input[placeholder*="${target}" i]`,
      `button:contains("${target}")`,
    ];

    for (const pattern of patterns) {
      try {
        element = document.querySelector(pattern) as HTMLElement;
        if (element) return element;
      } catch {
        // Selector might be invalid, continue
      }
    }

    return null;
  }, [pathname]);

  /**
   * Get all options from a select dropdown
   */
  const getDropdownOptions = useCallback((select: HTMLSelectElement): Array<{value: string, text: string, index: number}> => {
    const options: Array<{value: string, text: string, index: number}> = [];
    for (let i = 0; i < select.options.length; i++) {
      const opt = select.options[i];
      if (opt.value) { // Skip empty placeholder options
        options.push({
          value: opt.value,
          text: opt.text,
          index: i,
        });
      }
    }
    return options;
  }, []);

  /**
   * Find best matching option in dropdown by name or ordinal
   */
  const findBestOption = useCallback((options: Array<{value: string, text: string, index: number}>, searchTerm: string): {value: string, text: string, index: number} | null => {
    if (!options.length) return null;

    const termLower = searchTerm.toLowerCase().trim();

    // Check for ordinal (first, second, etc.)
    if (ORDINAL_MAP[termLower] !== undefined) {
      const idx = ORDINAL_MAP[termLower];
      if (idx === -1) {
        // "last"
        return options[options.length - 1];
      }
      if (idx < options.length) {
        return options[idx];
      }
    }

    // Check for numeric index (e.g., "1", "2")
    const numericMatch = termLower.match(/^(\d+)$/);
    if (numericMatch) {
      const idx = parseInt(numericMatch[1], 10) - 1; // 1-indexed
      if (idx >= 0 && idx < options.length) {
        return options[idx];
      }
    }

    // Exact match (case insensitive)
    const exactMatch = options.find(o => o.text.toLowerCase() === termLower);
    if (exactMatch) return exactMatch;

    // Partial match (contains)
    const partialMatch = options.find(o => o.text.toLowerCase().includes(termLower));
    if (partialMatch) return partialMatch;

    // Fuzzy match - find the option with most words matching
    const searchWords = termLower.split(/\s+/);
    let bestMatch: {value: string, text: string, index: number} | null = null;
    let bestScore = 0;

    for (const opt of options) {
      const optWords = opt.text.toLowerCase().split(/\s+/);
      let score = 0;
      for (const searchWord of searchWords) {
        for (const optWord of optWords) {
          if (optWord.includes(searchWord) || searchWord.includes(optWord)) {
            score++;
          }
        }
      }
      if (score > bestScore) {
        bestScore = score;
        bestMatch = opt;
      }
    }

    return bestMatch;
  }, []);

  /**
   * Handle dropdown selection
   */
  const handleSelectDropdown = useCallback((event: CustomEvent) => {
    const { target, value, optionName } = event.detail || {};
    console.log('🎤 VoiceUI: selectDropdown', { target, value, optionName });

    const element = findElement(target);
    if (!element || element.tagName !== 'SELECT') {
      console.warn('🎤 VoiceUI: Dropdown not found:', target);
      // Try to find any select on the page with the label
      const selects = document.querySelectorAll('select');
      for (const select of selects) {
        const label = select.closest('div')?.querySelector('label')?.textContent?.toLowerCase();
        if (label && target && label.includes(target.toLowerCase())) {
          handleSelectOnElement(select as HTMLSelectElement, value, optionName);
          return;
        }
      }
      return;
    }

    handleSelectOnElement(element as HTMLSelectElement, value, optionName);
  }, [findElement]);

  const handleSelectOnElement = useCallback((select: HTMLSelectElement, value?: string, optionName?: string) => {
    const options = getDropdownOptions(select);

    // If a specific value is provided, use it directly
    if (value !== undefined) {
      select.value = String(value);
      select.dispatchEvent(new Event('change', { bubbles: true }));
      console.log('🎤 VoiceUI: Selected by value:', value);
      return;
    }

    // If an option name is provided, find best match
    if (optionName) {
      const match = findBestOption(options, optionName);
      if (match) {
        select.value = match.value;
        select.dispatchEvent(new Event('change', { bubbles: true }));
        console.log('🎤 VoiceUI: Selected by name:', match.text);
        return;
      }
    }

    // Default to first non-empty option
    if (options.length > 0) {
      select.value = options[0].value;
      select.dispatchEvent(new Event('change', { bubbles: true }));
      console.log('🎤 VoiceUI: Selected first option:', options[0].text);
    }
  }, [getDropdownOptions, findBestOption]);

  /**
   * Handle button click
   */
  const handleClickButton = useCallback((event: CustomEvent) => {
    const { target, buttonLabel } = event.detail || {};
    console.log('🎤 VoiceUI: clickButton', { target, buttonLabel });

    // Debounce rapid clicks
    const now = Date.now();
    if (now - lastActionRef.current < 500) {
      console.log('🎤 VoiceUI: Debounced rapid click');
      return;
    }
    lastActionRef.current = now;

    let element = findElement(target);

    // If not found by target, search by button label
    if (!element && buttonLabel) {
      const buttons = document.querySelectorAll('button');
      const labelLower = buttonLabel.toLowerCase();
      for (const btn of buttons) {
        const btnText = btn.textContent?.toLowerCase() || '';
        if (btnText.includes(labelLower)) {
          element = btn as HTMLElement;
          break;
        }
      }
    }

    if (element) {
      // Check if button is disabled
      if (element.hasAttribute('disabled') || element.classList.contains('disabled')) {
        console.warn('🎤 VoiceUI: Button is disabled:', target);
        return;
      }
      element.click();
      console.log('🎤 VoiceUI: Clicked button:', target || buttonLabel);
    } else {
      console.warn('🎤 VoiceUI: Button not found:', target, buttonLabel);
    }
  }, [findElement]);

  /**
   * Handle input fill
   */
  const handleFillInput = useCallback((event: CustomEvent) => {
    const { target, value } = event.detail || {};
    console.log('🎤 VoiceUI: fillInput', { target, value });

    const element = findElement(target);
    if (element && (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA')) {
      const input = element as HTMLInputElement | HTMLTextAreaElement;
      input.value = value || '';
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
      input.focus();
      console.log('🎤 VoiceUI: Filled input:', target);
    } else {
      console.warn('🎤 VoiceUI: Input not found:', target);
    }
  }, [findElement]);

  /**
   * Handle tab switch
   */
  const handleSwitchTab = useCallback((event: CustomEvent) => {
    const { target, tabName } = event.detail || {};
    console.log('🎤 VoiceUI: switchTab', { target, tabName });

    // First try the existing voice-select-tab event (already supported by pages)
    if (tabName) {
      window.dispatchEvent(new CustomEvent('voice-select-tab', {
        detail: { tab: tabName.toLowerCase().replace(/\s+/g, '') }
      }));
    }

    // Also try to find and click the tab directly
    let element = findElement(target);

    if (!element && tabName) {
      // Search for tab by text content
      const tabButtons = document.querySelectorAll('[role="tab"], [data-radix-collection-item], button');
      const tabNameLower = tabName.toLowerCase();
      for (const tab of tabButtons) {
        const tabText = tab.textContent?.toLowerCase() || '';
        if (tabText.includes(tabNameLower) || tabNameLower.includes(tabText)) {
          element = tab as HTMLElement;
          break;
        }
      }
    }

    if (element) {
      element.click();
      console.log('🎤 VoiceUI: Switched tab:', target || tabName);
    }
  }, [findElement]);

  /**
   * Handle list item selection
   */
  const handleSelectListItem = useCallback((event: CustomEvent) => {
    const { target, itemName, itemIndex } = event.detail || {};
    console.log('🎤 VoiceUI: selectListItem', { target, itemName, itemIndex });

    const container = findElement(target) || document;
    const items = container.querySelectorAll('[data-voice-item], [role="listitem"], li, button[data-state]');

    if (items.length === 0) {
      console.warn('🎤 VoiceUI: No list items found in:', target);
      return;
    }

    let selectedItem: HTMLElement | null = null;

    // Select by index (ordinal or numeric)
    if (itemIndex !== undefined) {
      const idx = typeof itemIndex === 'string' ? (ORDINAL_MAP[itemIndex.toLowerCase()] ?? parseInt(itemIndex, 10) - 1) : itemIndex;
      const actualIdx = idx === -1 ? items.length - 1 : idx;
      if (actualIdx >= 0 && actualIdx < items.length) {
        selectedItem = items[actualIdx] as HTMLElement;
      }
    }

    // Select by name
    if (!selectedItem && itemName) {
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
      selectedItem.click();
      console.log('🎤 VoiceUI: Selected list item:', itemName || itemIndex);
    } else {
      console.warn('🎤 VoiceUI: List item not found:', itemName, itemIndex);
    }
  }, [findElement]);

  /**
   * Get available UI elements on current page (for debugging/help)
   */
  const handleGetAvailableElements = useCallback((event: CustomEvent) => {
    const pageRegistry = UI_ELEMENT_REGISTRY[pathname] || {};
    const available: string[] = [];

    for (const [name, selector] of Object.entries(pageRegistry)) {
      const element = document.querySelector(selector);
      if (element) {
        available.push(name);
      }
    }

    // Also find elements with data-voice-id
    const voiceElements = document.querySelectorAll('[data-voice-id]');
    voiceElements.forEach(el => {
      const id = el.getAttribute('data-voice-id');
      if (id && !available.includes(id)) {
        available.push(id);
      }
    });

    console.log('🎤 VoiceUI: Available elements on', pathname, ':', available);

    // Dispatch result back
    window.dispatchEvent(new CustomEvent('voice-ui-elements', {
      detail: { page: pathname, elements: available }
    }));
  }, [pathname]);

  /**
   * Setup event listeners
   */
  useEffect(() => {
    const handlers = {
      'ui.selectDropdown': handleSelectDropdown,
      'ui.clickButton': handleClickButton,
      'ui.fillInput': handleFillInput,
      'ui.switchTab': handleSwitchTab,
      'ui.selectListItem': handleSelectListItem,
      'ui.getAvailableElements': handleGetAvailableElements,
    };

    // Add all event listeners
    Object.entries(handlers).forEach(([event, handler]) => {
      window.addEventListener(event, handler as EventListener);
    });

    console.log('🎤 VoiceUIController: Initialized on', pathname);

    // Cleanup
    return () => {
      Object.entries(handlers).forEach(([event, handler]) => {
        window.removeEventListener(event, handler as EventListener);
      });
    };
  }, [
    pathname,
    handleSelectDropdown,
    handleClickButton,
    handleFillInput,
    handleSwitchTab,
    handleSelectListItem,
    handleGetAvailableElements,
  ]);

  return null;
};

export default VoiceUIController;
