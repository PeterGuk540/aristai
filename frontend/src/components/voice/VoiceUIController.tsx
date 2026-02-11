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
    'generate-report': '[data-voice-id="generate-report"]',
    'refreshButton': '[data-voice-id="refresh-report"]',
    'refresh-report': '[data-voice-id="refresh-report"]',
    'regenerate-report': '[data-voice-id="regenerate-report"]',
    // Report tabs
    'summaryTab': '[data-voice-id="tab-summary"]',
    'tab-summary': '[data-voice-id="tab-summary"]',
    'summary': '[data-voice-id="tab-summary"]',
    'participationTab': '[data-voice-id="tab-participation"]',
    'tab-participation': '[data-voice-id="tab-participation"]',
    'participation': '[data-voice-id="tab-participation"]',
    'scoringTab': '[data-voice-id="tab-scoring"]',
    'tab-scoring': '[data-voice-id="tab-scoring"]',
    'scoring': '[data-voice-id="tab-scoring"]',
    'answer-scores': '[data-voice-id="tab-scoring"]',
    'analyticsTab': '[data-voice-id="tab-analytics"]',
    'tab-analytics': '[data-voice-id="tab-analytics"]',
    'analytics': '[data-voice-id="tab-analytics"]',
  },
  // Courses page elements
  '/courses': {
    'courseDropdown': '[data-voice-id="select-course"]',
    'courseTitleInput': '[data-voice-id="course-title"]',
    'course-title': '[data-voice-id="course-title"]',
    'syllabusInput': '[data-voice-id="syllabus"]',
    'syllabus': '[data-voice-id="syllabus"]',
    'objectivesInput': '[data-voice-id="learning-objectives"]',
    'learning-objectives': '[data-voice-id="learning-objectives"]',
    'createButton': '[data-voice-id="create-course"]',
    'create-course': '[data-voice-id="create-course"]',
    'createWithPlansButton': '[data-voice-id="create-course-with-plans"]',
    'create-course-with-plans': '[data-voice-id="create-course-with-plans"]',
    'generatePlansButton': '[data-voice-id="generate-plans"]',
    'generate-plans': '[data-voice-id="generate-plans"]',
    'enrollButton': '[data-voice-id="enroll-students"]',
    'enroll-students': '[data-voice-id="enroll-students"]',
    'refreshButton': '[data-voice-id="refresh"]',
    'refresh': '[data-voice-id="refresh"]',
    // Courses tabs
    'coursesTab': '[data-voice-id="tab-courses"]',
    'tab-courses': '[data-voice-id="tab-courses"]',
    'courses': '[data-voice-id="tab-courses"]',
    'view-courses': '[data-voice-id="tab-courses"]',
    'createTab': '[data-voice-id="tab-create"]',
    'tab-create': '[data-voice-id="tab-create"]',
    'create': '[data-voice-id="tab-create"]',
    'enrollmentTab': '[data-voice-id="tab-enrollment"]',
    'tab-enrollment': '[data-voice-id="tab-enrollment"]',
    'enrollment': '[data-voice-id="tab-enrollment"]',
    'manage-enrollment': '[data-voice-id="tab-enrollment"]',
    'joinTab': '[data-voice-id="tab-join"]',
    'tab-join': '[data-voice-id="tab-join"]',
    'join': '[data-voice-id="tab-join"]',
    'join-course': '[data-voice-id="tab-join"]',
    'instructorTab': '[data-voice-id="tab-instructor"]',
    'tab-instructor': '[data-voice-id="tab-instructor"]',
    'instructor': '[data-voice-id="tab-instructor"]',
    'become-instructor': '[data-voice-id="tab-instructor"]',
    'joinCodeInput': '[data-voice-id="join-code"]',
    'join-code': '[data-voice-id="join-code"]',
    'joinButton': '[data-voice-id="join-course-button"]',
  },
  // Sessions page elements
  '/sessions': {
    'courseDropdown': '[data-voice-id="select-course"]',
    'sessionTitleInput': '[data-voice-id="session-title"]',
    'createButton': '[data-voice-id="create-session"]',
    'create-session': '[data-voice-id="create-session"]',
    'goLiveButton': '[data-voice-id="go-live"]',
    'go-live': '[data-voice-id="go-live"]',
    'completeButton': '[data-voice-id="complete-session"]',
    'complete-session': '[data-voice-id="complete-session"]',
    'scheduleButton': '[data-voice-id="schedule-session"]',
    'schedule-session': '[data-voice-id="schedule-session"]',
    'set-to-draft': '[data-voice-id="set-to-draft"]',
    'sessionList': '[data-voice-id="session-list"]',
    // Sessions tabs
    'sessionsTab': '[data-voice-id="tab-sessions"]',
    'tab-sessions': '[data-voice-id="tab-sessions"]',
    'sessions': '[data-voice-id="tab-sessions"]',
    'view-sessions': '[data-voice-id="tab-sessions"]',
    'materialsTab': '[data-voice-id="tab-materials"]',
    'tab-materials': '[data-voice-id="tab-materials"]',
    'materials': '[data-voice-id="tab-materials"]',
    'createTab': '[data-voice-id="tab-create"]',
    'tab-create': '[data-voice-id="tab-create"]',
    'create': '[data-voice-id="tab-create"]',
    'manageTab': '[data-voice-id="tab-manage"]',
    'tab-manage': '[data-voice-id="tab-manage"]',
    'manage': '[data-voice-id="tab-manage"]',
    'manage-status': '[data-voice-id="tab-manage"]',
    'insightsTab': '[data-voice-id="tab-insights"]',
    'tab-insights': '[data-voice-id="tab-insights"]',
    'insights': '[data-voice-id="tab-insights"]',
    // Post-class summary buttons
    'send-summary-to-students': '[data-voice-id="send-summary-to-students"]',
    'generate-session-summary': '[data-voice-id="generate-session-summary"]',
  },
  // Forum page elements
  '/forum': {
    'courseDropdown': '[data-voice-id="select-course"]',
    'sessionDropdown': '[data-voice-id="select-session"]',
    'postTextarea': '[data-voice-id="new-post"]',
    'new-post': '[data-voice-id="new-post"]',
    'postButton': '[data-voice-id="submit-post"]',
    'submit-post': '[data-voice-id="submit-post"]',
    'refreshButton': '[data-voice-id="refresh"]',
    'refresh': '[data-voice-id="refresh"]',
    // Forum tabs
    'casesTab': '[data-voice-id="tab-cases"]',
    'tab-cases': '[data-voice-id="tab-cases"]',
    'cases': '[data-voice-id="tab-cases"]',
    'case-studies': '[data-voice-id="tab-cases"]',
    'discussionTab': '[data-voice-id="tab-discussion"]',
    'tab-discussion': '[data-voice-id="tab-discussion"]',
    'discussion': '[data-voice-id="tab-discussion"]',
  },
  // Console page elements
  '/console': {
    'courseDropdown': '[data-voice-id="select-course"]',
    'sessionDropdown': '[data-voice-id="select-session"]',
    'startCopilotButton': '[data-voice-id="start-copilot"]',
    'start-copilot': '[data-voice-id="start-copilot"]',
    'stopCopilotButton': '[data-voice-id="stop-copilot"]',
    'stop-copilot': '[data-voice-id="stop-copilot"]',
    'refreshButton': '[data-voice-id="refresh-interventions"]',
    'refresh-interventions': '[data-voice-id="refresh-interventions"]',
    'pollQuestionInput': '[data-voice-id="poll-question"]',
    'poll-question': '[data-voice-id="poll-question"]',
    'poll-option-1': '[data-voice-id="poll-option-1"]',
    'poll-option-2': '[data-voice-id="poll-option-2"]',
    'poll-option-3': '[data-voice-id="poll-option-3"]',
    'poll-option-4': '[data-voice-id="poll-option-4"]',
    'createPollButton': '[data-voice-id="create-poll"]',
    'create-poll': '[data-voice-id="create-poll"]',
    'caseTextarea': '[data-voice-id="case-prompt"]',
    'case-prompt': '[data-voice-id="case-prompt"]',
    'postCaseButton': '[data-voice-id="post-case"]',
    'post-case': '[data-voice-id="post-case"]',
    // Console tabs
    'copilotTab': '[data-voice-id="tab-copilot"]',
    'tab-copilot': '[data-voice-id="tab-copilot"]',
    'copilot': '[data-voice-id="tab-copilot"]',
    'ai-copilot': '[data-voice-id="tab-copilot"]',
    'pollsTab': '[data-voice-id="tab-polls"]',
    'tab-polls': '[data-voice-id="tab-polls"]',
    'polls': '[data-voice-id="tab-polls"]',
    'casesTab': '[data-voice-id="tab-cases"]',
    'tab-cases': '[data-voice-id="tab-cases"]',
    'cases': '[data-voice-id="tab-cases"]',
    'case-studies': '[data-voice-id="tab-cases"]',
    'toolsTab': '[data-voice-id="tab-tools"]',
    'tab-tools': '[data-voice-id="tab-tools"]',
    'tools': '[data-voice-id="tab-tools"]',
    'instructor-tools': '[data-voice-id="tab-tools"]',
    'requestsTab': '[data-voice-id="tab-requests"]',
    'tab-requests': '[data-voice-id="tab-requests"]',
    'requests': '[data-voice-id="tab-requests"]',
    'instructor-requests': '[data-voice-id="tab-requests"]',
    'rosterTab': '[data-voice-id="tab-roster"]',
    'tab-roster': '[data-voice-id="tab-roster"]',
    'roster': '[data-voice-id="tab-roster"]',
    // Instructor tools - Session Timer
    'open-timer-form': '[data-voice-id="open-timer-form"]',
    'start-session-timer': '[data-voice-id="start-session-timer"]',
    'pause-timer': '[data-voice-id="pause-timer"]',
    'resume-timer': '[data-voice-id="resume-timer"]',
    'stop-timer': '[data-voice-id="stop-timer"]',
    // Instructor tools - Breakout Groups
    'open-breakout-form': '[data-voice-id="open-breakout-form"]',
    'create-breakout-groups': '[data-voice-id="create-breakout-groups"]',
    'dissolve-breakout-groups': '[data-voice-id="dissolve-breakout-groups"]',
    'rosterCourseDropdown': '[data-voice-id="roster-course"]',
    'uploadRosterButton': '[data-voice-id="upload-roster"]',
    // Session status management buttons
    'go-live': '[data-voice-id="go-live"]',
    'goLiveButton': '[data-voice-id="go-live"]',
    'set-to-draft': '[data-voice-id="set-to-draft"]',
    'setToDraftButton': '[data-voice-id="set-to-draft"]',
    'complete-session': '[data-voice-id="complete-session"]',
    'completeSessionButton': '[data-voice-id="complete-session"]',
    'schedule-session': '[data-voice-id="schedule-session"]',
    'scheduleSessionButton': '[data-voice-id="schedule-session"]',
    // Report buttons
    'refresh-report': '[data-voice-id="refresh-report"]',
    'refreshReportButton': '[data-voice-id="refresh-report"]',
    'regenerate-report': '[data-voice-id="regenerate-report"]',
    'regenerateReportButton': '[data-voice-id="regenerate-report"]',
    'generate-report': '[data-voice-id="generate-report"]',
    'generateReportButton': '[data-voice-id="generate-report"]',
    // Theme and user menu
    'toggle-theme': '[data-voice-id="toggle-theme"]',
    'toggleTheme': '[data-voice-id="toggle-theme"]',
    'user-menu': '[data-voice-id="user-menu"]',
    'userMenu': '[data-voice-id="user-menu"]',
    'view-voice-guide': '[data-voice-id="view-voice-guide"]',
    'viewVoiceGuide': '[data-voice-id="view-voice-guide"]',
    'forum-instructions': '[data-voice-id="forum-instructions"]',
    'forumInstructions': '[data-voice-id="forum-instructions"]',
    // Got It buttons for closing floating windows
    'got-it-voice-guide': '[data-voice-id="got-it-voice-guide"]',
    'got-it-platform-guide': '[data-voice-id="got-it-platform-guide"]',
    'open-profile': '[data-voice-id="open-profile"]',
    'openProfile': '[data-voice-id="open-profile"]',
    'sign-out': '[data-voice-id="sign-out"]',
    'signOut': '[data-voice-id="sign-out"]',
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
 * - ui.clearInput: Clears an input field
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
   * Set select value using React-compatible approach
   * React controlled components need special handling to trigger state updates
   */
  const setSelectValueReactCompatible = useCallback((select: HTMLSelectElement, newValue: string) => {
    // Focus first to ensure React is tracking this element
    select.focus();

    // Get the native value setter for HTMLSelectElement
    const nativeSelectValueSetter = Object.getOwnPropertyDescriptor(
      window.HTMLSelectElement.prototype,
      'value'
    )?.set;

    if (nativeSelectValueSetter) {
      nativeSelectValueSetter.call(select, newValue);
    } else {
      select.value = newValue;
    }

    // React 16+ uses a tracker on the DOM node to detect value changes
    // We need to update this tracker for React to pick up our change
    const tracker = (select as any)._valueTracker;
    if (tracker) {
      tracker.setValue('__voice_trigger__'); // Set to something different so React sees a change
    }

    // Dispatch change event - this should now be picked up by React
    const changeEvent = new Event('change', { bubbles: true });
    select.dispatchEvent(changeEvent);

    // Also dispatch input event for good measure
    const inputEvent = new Event('input', { bubbles: true });
    select.dispatchEvent(inputEvent);

    console.log('🎤 VoiceUI: Set select value (React-compatible):', newValue);
  }, []);

  const handleSelectOnElement = useCallback((select: HTMLSelectElement, value?: string, optionName?: string, optionIndex?: number) => {
    const options = getDropdownOptions(select);

    // If a specific value is provided, use it directly
    if (value !== undefined && value !== null) {
      setSelectValueReactCompatible(select, String(value));
      console.log('🎤 VoiceUI: Selected by value:', value);
      return;
    }

    // If an option index is provided (0-based, or -1 for last)
    if (optionIndex !== undefined && optionIndex !== null) {
      const actualIndex = optionIndex === -1 ? options.length - 1 : optionIndex;
      if (actualIndex >= 0 && actualIndex < options.length) {
        setSelectValueReactCompatible(select, options[actualIndex].value);
        console.log('🎤 VoiceUI: Selected by index:', actualIndex, options[actualIndex].text);
        return;
      }
    }

    // If an option name is provided, find best match
    if (optionName) {
      const match = findBestOption(options, optionName);
      if (match) {
        setSelectValueReactCompatible(select, match.value);
        console.log('🎤 VoiceUI: Selected by name:', match.text);
        return;
      }
    }

    // Default to first non-empty option
    if (options.length > 0) {
      setSelectValueReactCompatible(select, options[0].value);
      console.log('🎤 VoiceUI: Selected first option:', options[0].text);
    }
  }, [getDropdownOptions, findBestOption, setSelectValueReactCompatible]);

  /**
   * UNIVERSAL dropdown selection - works for ANY dropdown on any page
   * Finds by: data-voice-id, label text, name, or first visible dropdown
   */
  const handleSelectDropdown = useCallback((event: CustomEvent) => {
    const { target, value, optionName, optionIndex } = event.detail || {};
    console.log('🎤 VoiceUI: selectDropdown', { target, value, optionName, optionIndex });

    let element: HTMLElement | null = null;

    // Try to find by target first
    if (target) {
      element = findElement(target);

      // Try to find by label if not found
      if (!element || element.tagName !== 'SELECT') {
        const targetLower = target.toLowerCase().replace(/-/g, ' ');
        const selects = Array.from(document.querySelectorAll('select'));
        for (const select of selects) {
          const label = select.closest('div')?.querySelector('label')?.textContent?.toLowerCase() || '';
          const ariaLabel = select.getAttribute('aria-label')?.toLowerCase() || '';
          const name = select.getAttribute('name')?.toLowerCase() || '';
          if (label.includes(targetLower) || ariaLabel.includes(targetLower) ||
              name.includes(targetLower) || targetLower.includes(label.split(' ')[0])) {
            element = select as HTMLElement;
            break;
          }
        }
      }
    }

    // UNIVERSAL: If no target or not found, use the first visible select
    if (!element || element.tagName !== 'SELECT') {
      const selects = Array.from(document.querySelectorAll('select')).filter(sel => {
        const rect = sel.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
      });
      if (selects.length > 0) {
        element = selects[0] as HTMLElement;
      }
    }

    if (element && element.tagName === 'SELECT') {
      handleSelectOnElement(element as HTMLSelectElement, value, optionName, optionIndex);
    } else {
      console.warn('🎤 VoiceUI: No dropdown found');
    }
  }, [findElement, handleSelectOnElement]);

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
      const buttons = Array.from(document.querySelectorAll('button'));
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
   * Handle opening a menu and clicking an item inside it with proper timing
   * This handles dropdown menus where items are only rendered when menu is open
   */
  const handleOpenMenuAndClick = useCallback((event: CustomEvent) => {
    const { menuTarget, itemTarget } = event.detail || {};
    console.log('🎤 VoiceUI: openMenuAndClick', { menuTarget, itemTarget });

    // First, find and click the menu button
    const menuButton = findElement(menuTarget);
    if (!menuButton) {
      console.warn('🎤 VoiceUI: Menu button not found:', menuTarget);
      return;
    }

    menuButton.click();
    console.log('🎤 VoiceUI: Clicked menu button:', menuTarget);

    // Wait for menu to render, then click the item
    setTimeout(() => {
      const menuItem = findElement(itemTarget);
      if (menuItem) {
        menuItem.click();
        console.log('🎤 VoiceUI: Clicked menu item:', itemTarget);
      } else {
        console.warn('🎤 VoiceUI: Menu item not found after delay:', itemTarget);
      }
    }, 300); // 300ms delay for menu to render
  }, [findElement]);

  /**
   * UNIVERSAL input fill - works for ANY input field on any page
   * Finds inputs by: data-voice-id, label text, placeholder, aria-label, or active focus
   */
  const handleFillInput = useCallback((event: CustomEvent) => {
    const { target, value } = event.detail || {};
    console.log('🎤 VoiceUI: fillInput', { target, value });

    let element: HTMLElement | null = null;

    // Special case: "focused-input" means fill the currently focused element or first visible input
    if (target === 'focused-input') {
      const focused = document.activeElement;
      if (focused && (focused.tagName === 'INPUT' || focused.tagName === 'TEXTAREA')) {
        element = focused as HTMLElement;
      }
    }

    // Try to find by voice-id first
    if (!element && target && target !== 'focused-input') {
      element = findElement(target);
    }

    // Try to find by label text (universal approach)
    if (!element && target && target !== 'focused-input') {
      const targetLower = target.toLowerCase().replace(/-/g, ' ');

      // Search for input by associated label
      const labels = Array.from(document.querySelectorAll('label'));
      for (const label of labels) {
        const labelText = label.textContent?.toLowerCase() || '';
        // Match if label contains target or target contains any word from label
        if (labelText.includes(targetLower) || targetLower.split(' ').some((word: string) => labelText.includes(word))) {
          const forId = label.getAttribute('for');
          if (forId) {
            element = document.getElementById(forId) as HTMLElement;
          } else {
            // Label might wrap the input
            element = label.querySelector('input, textarea') as HTMLElement;
          }
          if (element) break;
        }
      }

      // Search by placeholder or aria-label
      if (!element) {
        const inputs = Array.from(document.querySelectorAll('input:not([type="hidden"]), textarea'));
        for (const input of inputs) {
          const placeholder = input.getAttribute('placeholder')?.toLowerCase() || '';
          const ariaLabel = input.getAttribute('aria-label')?.toLowerCase() || '';
          const name = input.getAttribute('name')?.toLowerCase() || '';
          const id = input.getAttribute('id')?.toLowerCase() || '';
          if (placeholder.includes(targetLower) || ariaLabel.includes(targetLower) ||
              name.includes(targetLower) || id.includes(targetLower) ||
              targetLower.includes(placeholder) || targetLower.includes(name)) {
            element = input as HTMLElement;
            break;
          }
        }
      }
    }

    // UNIVERSAL FALLBACK: Find the first visible, empty or focusable input
    if (!element) {
      const visibleInputs = Array.from(document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]), textarea')).filter(el => {
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
      }) as HTMLInputElement[];

      // Prefer empty inputs, then inputs in forms
      const emptyInput = visibleInputs.find(inp => !inp.value);
      element = emptyInput || visibleInputs[0] || null;
    }

    // Fill the input - use React-compatible approach to trigger state updates
    if (element && (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA')) {
      const input = element as HTMLInputElement | HTMLTextAreaElement;

      // Focus first to ensure React is tracking this element
      input.focus();

      // Get the native value setter
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        element.tagName === 'INPUT' ? window.HTMLInputElement.prototype : window.HTMLTextAreaElement.prototype,
        'value'
      )?.set;

      if (nativeInputValueSetter) {
        nativeInputValueSetter.call(input, value || '');
      } else {
        input.value = value || '';
      }

      // React 16+ uses a tracker on the DOM node to detect value changes
      // We need to update this tracker for React to pick up our change
      const tracker = (input as any)._valueTracker;
      if (tracker) {
        tracker.setValue(''); // Set to something different so React sees a change
      }

      // Dispatch input event - this should now be picked up by React
      const inputEvent = new Event('input', { bubbles: true });
      input.dispatchEvent(inputEvent);

      // Also dispatch change event
      const changeEvent = new Event('change', { bubbles: true });
      input.dispatchEvent(changeEvent);

      console.log('🎤 VoiceUI: Filled input:', element.getAttribute('data-voice-id') || element.getAttribute('name') || 'unknown', 'with:', value);
    } else {
      console.warn('🎤 VoiceUI: No input found to fill');
    }
  }, [findElement]);

  /**
   * UNIVERSAL input clearing - clears an input/textarea by voice-id
   */
  const handleClearInput = useCallback((event: CustomEvent) => {
    const { target } = event.detail || {};
    console.log('🎤 VoiceUI: clearInput', { target });

    let element: HTMLElement | null = null;

    // Find by voice-id
    if (target) {
      element = findElement(target);
    }

    // Clear the input using React-compatible approach
    if (element && (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA')) {
      const input = element as HTMLInputElement | HTMLTextAreaElement;

      // Focus first
      input.focus();

      // Get the native value setter
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        element.tagName === 'INPUT' ? window.HTMLInputElement.prototype : window.HTMLTextAreaElement.prototype,
        'value'
      )?.set;

      if (nativeInputValueSetter) {
        nativeInputValueSetter.call(input, '');
      } else {
        input.value = '';
      }

      // Update React's tracker
      const tracker = (input as any)._valueTracker;
      if (tracker) {
        tracker.setValue('something'); // Set to something different so React sees a change
      }

      // Dispatch events
      const inputEvent = new Event('input', { bubbles: true });
      input.dispatchEvent(inputEvent);
      const changeEvent = new Event('change', { bubbles: true });
      input.dispatchEvent(changeEvent);

      // Blur to unfocus
      input.blur();

      console.log('🎤 VoiceUI: Cleared input:', target);
    } else {
      console.warn('🎤 VoiceUI: No input found to clear:', target);
    }
  }, [findElement]);

  /**
   * UNIVERSAL dropdown expansion - works for ANY dropdown on any page
   * Finds dropdowns by: data-voice-id, label, or just finds any visible dropdown
   */
  const handleExpandDropdown = useCallback((event: CustomEvent) => {
    const { target, findAny } = event.detail || {};
    console.log('🎤 VoiceUI: expandDropdown', { target, findAny });

    let element: HTMLElement | null = null;

    // Try to find by target first
    if (target) {
      element = findElement(target);

      // Try to find by label if not found
      if (!element || element.tagName !== 'SELECT') {
        const targetLower = target.toLowerCase().replace(/-/g, ' ');
        const selects = Array.from(document.querySelectorAll('select'));
        for (const select of selects) {
          // Check label
          const label = select.closest('div')?.querySelector('label')?.textContent?.toLowerCase() || '';
          const ariaLabel = select.getAttribute('aria-label')?.toLowerCase() || '';
          const name = select.getAttribute('name')?.toLowerCase() || '';
          if (label.includes(targetLower) || ariaLabel.includes(targetLower) ||
              name.includes(targetLower) || targetLower.includes(label.split(' ')[0])) {
            element = select as HTMLElement;
            break;
          }
        }
      }
    }

    // UNIVERSAL: If not found or findAny is true, get the first visible select on the page
    if (!element || element.tagName !== 'SELECT') {
      const selects = Array.from(document.querySelectorAll('select')).filter(sel => {
        const rect = sel.getBoundingClientRect();
        const style = window.getComputedStyle(sel);
        return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden';
      });
      if (selects.length > 0) {
        element = selects[0] as HTMLElement;
      }
    }

    if (element && element.tagName === 'SELECT') {
      const select = element as HTMLSelectElement;
      // Focus and open the dropdown
      select.focus();
      select.click();
      select.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));

      // List available options for voice feedback
      const options = Array.from(select.options).filter(opt => opt.value);
      console.log('🎤 VoiceUI: Expanded dropdown with options:', options.map((o, i) => `${i + 1}. ${o.text}`));

      // Dispatch event with available options (for voice assistant to announce)
      window.dispatchEvent(new CustomEvent('voice-dropdown-options', {
        detail: { options: options.map(o => o.text) }
      }));
    } else {
      console.warn('🎤 VoiceUI: No dropdown found on page');
    }
  }, [findElement]);

  /**
   * UNIVERSAL tab switch - works for ANY tab on any page
   * Finds tabs by: value attribute (Radix), data-voice-id, text content, role="tab"
   *
   * IMPORTANT: The tabName from backend should be the actual tab value (e.g., "cases", "discussion")
   * not the display text (e.g., "Post a Case", "Discussion (5)")
   */
  const handleSwitchTab = useCallback((event: CustomEvent) => {
    const { target, tabName } = event.detail || {};
    console.log('🎤 VoiceUI: switchTab', { target, tabName });

    const searchName = tabName || target || '';
    const searchNameLower = searchName.toLowerCase().replace(/-/g, '').replace(/tab|panel|section/g, '').trim();

    // First try the voice-select-tab custom event (supported by many pages)
    window.dispatchEvent(new CustomEvent('voice-select-tab', {
      detail: { tab: searchNameLower }
    }));

    let element: HTMLElement | null = null;

    // 1. Try to find by data-voice-id first (most specific)
    element = findElement(target);

    // 2. Try to find Radix TabsTrigger by value attribute (exact match)
    if (!element) {
      // Radix UI tabs have a data-state and value attribute
      const radixTabs = Array.from(document.querySelectorAll('[data-radix-collection-item]'));
      for (const tab of radixTabs) {
        const tabValue = tab.getAttribute('value')?.toLowerCase() || '';
        if (tabValue === searchNameLower) {
          element = tab as HTMLElement;
          console.log('🎤 VoiceUI: Found tab by value attribute:', tabValue);
          break;
        }
      }
    }

    // 3. Try to find by role="tab" with aria-controls matching
    if (!element) {
      const roleTabs = Array.from(document.querySelectorAll('[role="tab"]'));
      for (const tab of roleTabs) {
        const ariaControls = tab.getAttribute('aria-controls')?.toLowerCase() || '';
        const tabId = tab.getAttribute('id')?.toLowerCase() || '';
        if (ariaControls.includes(searchNameLower) || tabId.includes(searchNameLower)) {
          element = tab as HTMLElement;
          console.log('🎤 VoiceUI: Found tab by aria-controls:', ariaControls);
          break;
        }
      }
    }

    // 4. Try to find by partial text content match (fallback)
    if (!element) {
      const tabSelectors = [
        '[role="tab"]',
        '[data-radix-collection-item]',
        'button[class*="tab"]',
      ];

      for (const selector of tabSelectors) {
        const tabs = Array.from(document.querySelectorAll(selector));
        for (const tab of tabs) {
          const tabText = tab.textContent?.toLowerCase().replace(/\(\d+\)/g, '').trim() || '';
          const voiceId = tab.getAttribute('data-voice-id')?.toLowerCase() || '';
          // Match if tab text starts with or equals search term
          if (tabText === searchNameLower ||
              tabText.startsWith(searchNameLower) ||
              voiceId.includes(searchNameLower)) {
            element = tab as HTMLElement;
            console.log('🎤 VoiceUI: Found tab by text content:', tabText);
            break;
          }
        }
        if (element) break;
      }
    }

    if (element) {
      // Check if the tab is disabled
      const isDisabled = element.hasAttribute('disabled') ||
                         element.getAttribute('aria-disabled') === 'true' ||
                         element.classList.contains('disabled') ||
                         element.hasAttribute('data-disabled') ||
                         (element as HTMLButtonElement).disabled;

      if (isDisabled) {
        console.warn('🎤 VoiceUI: Tab is disabled:', searchName);
        // Dispatch an event to notify that the tab is disabled
        window.dispatchEvent(new CustomEvent('voice-tab-disabled', {
          detail: { tabName: searchName, message: 'This tab is disabled. Please select a session first.' }
        }));
        return;
      }

      element.click();
      console.log('🎤 VoiceUI: Switched to tab:', searchName, element);
    } else {
      console.warn('🎤 VoiceUI: Tab not found:', searchName);
      // List available tabs for debugging
      const availableTabs = Array.from(document.querySelectorAll('[data-radix-collection-item], [role="tab"]'));
      console.log('🎤 VoiceUI: Available tabs:', availableTabs.map(t => ({
        value: t.getAttribute('value'),
        text: t.textContent?.trim().substring(0, 30),
        voiceId: t.getAttribute('data-voice-id'),
      })));
    }
  }, [findElement]);

  /**
   * Handle list item selection
   */
  const handleSelectListItem = useCallback((event: CustomEvent) => {
    const { target, itemName, itemIndex } = event.detail || {};
    console.log('🎤 VoiceUI: selectListItem', { target, itemName, itemIndex });

    const container = findElement(target) || document;
    const items = Array.from(container.querySelectorAll('[data-voice-item], [role="listitem"], li, button[data-state]'));

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
      // If the item contains a checkbox, click the checkbox directly
      // This avoids double-triggering from li onClick + checkbox onChange
      const checkbox = selectedItem.querySelector('input[type="checkbox"]') as HTMLInputElement;
      if (checkbox) {
        checkbox.click();
        console.log('🎤 VoiceUI: Clicked checkbox in list item:', itemName || itemIndex);
      } else {
        selectedItem.click();
        console.log('🎤 VoiceUI: Selected list item:', itemName || itemIndex);
      }
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
      'ui.expandDropdown': handleExpandDropdown,
      'ui.clickButton': handleClickButton,
      'ui.openMenuAndClick': handleOpenMenuAndClick,
      'ui.fillInput': handleFillInput,
      'ui.clearInput': handleClearInput,
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
    handleExpandDropdown,
    handleClickButton,
    handleOpenMenuAndClick,
    handleFillInput,
    handleClearInput,
    handleSwitchTab,
    handleSelectListItem,
    handleGetAvailableElements,
  ]);

  return null;
};

export default VoiceUIController;
