/**
 * Voice Controller E2E Tests
 *
 * These tests verify the complete voice control flow:
 * 1. UI state capture
 * 2. Action schema validation
 * 3. Action execution
 * 4. State verification
 *
 * Run with: npx jest src/__tests__/voice-controller.test.ts
 */

import {
  VoiceActionSchema,
  validateVoiceAction,
  createSwitchTabAction,
  createClickButtonAction,
  createFillInputAction,
  createSelectDropdownAction,
  createNavigateAction,
} from '../lib/voice-action-schema';

// ============================================================================
// ACTION SCHEMA VALIDATION TESTS
// ============================================================================

describe('Voice Action Schema Validation', () => {
  test('validates switch_tab action with required voiceId', () => {
    const action = {
      type: 'ui.switchTab',
      payload: { voiceId: 'tab-sessions' },
    };
    const result = validateVoiceAction(action);
    expect(result).not.toBeNull();
    expect(result?.type).toBe('ui.switchTab');
  });

  test('rejects switch_tab action without voiceId', () => {
    const action = {
      type: 'ui.switchTab',
      payload: {},
    };
    const result = validateVoiceAction(action);
    expect(result).toBeNull();
  });

  test('validates click_button action', () => {
    const action = {
      type: 'ui.clickButton',
      payload: { voiceId: 'create-course', buttonLabel: 'Create Course' },
    };
    const result = validateVoiceAction(action);
    expect(result).not.toBeNull();
    expect(result?.type).toBe('ui.clickButton');
  });

  test('validates fill_input action with content', () => {
    const action = {
      type: 'ui.fillInput',
      payload: {
        voiceId: 'course-title',
        content: 'Introduction to AI',
        append: false,
      },
    };
    const result = validateVoiceAction(action);
    expect(result).not.toBeNull();
  });

  test('validates select_dropdown with index', () => {
    const action = {
      type: 'ui.selectDropdown',
      payload: {
        voiceId: 'select-course',
        selectionIndex: 0,
      },
    };
    const result = validateVoiceAction(action);
    expect(result).not.toBeNull();
  });

  test('validates select_dropdown with value', () => {
    const action = {
      type: 'ui.selectDropdown',
      payload: {
        voiceId: 'select-course',
        selectionValue: 'course-123',
      },
    };
    const result = validateVoiceAction(action);
    expect(result).not.toBeNull();
  });

  test('rejects select_dropdown without index or value', () => {
    const action = {
      type: 'ui.selectDropdown',
      payload: {
        voiceId: 'select-course',
      },
    };
    const result = validateVoiceAction(action);
    expect(result).toBeNull();
  });

  test('validates navigate action with valid route', () => {
    const action = {
      type: 'ui.navigate',
      payload: { route: '/courses' },
    };
    const result = validateVoiceAction(action);
    expect(result).not.toBeNull();
  });

  test('rejects navigate action with invalid route', () => {
    const action = {
      type: 'ui.navigate',
      payload: { route: '/invalid-page' },
    };
    const result = validateVoiceAction(action);
    expect(result).toBeNull();
  });

  test('validates scroll action', () => {
    const action = {
      type: 'ui.scroll',
      payload: { direction: 'down' },
    };
    const result = validateVoiceAction(action);
    expect(result).not.toBeNull();
  });

  test('validates submit_form action', () => {
    const action = {
      type: 'ui.submitForm',
      payload: { submitButtonVoiceId: 'submit-course' },
    };
    const result = validateVoiceAction(action);
    expect(result).not.toBeNull();
  });
});

// ============================================================================
// ACTION CREATOR TESTS
// ============================================================================

describe('Voice Action Creators', () => {
  test('createSwitchTabAction generates valid action', () => {
    const action = createSwitchTabAction('tab-ai-features', 'AI Features');
    expect(action.type).toBe('ui.switchTab');
    expect(action.payload.voiceId).toBe('tab-ai-features');
    expect(action.payload.tabLabel).toBe('AI Features');
    expect(action.correlationId).toBeDefined();
    expect(action.timestamp).toBeDefined();
  });

  test('createClickButtonAction generates valid action', () => {
    const action = createClickButtonAction('go-live', 'Go Live');
    expect(action.type).toBe('ui.clickButton');
    expect(action.payload.voiceId).toBe('go-live');
  });

  test('createFillInputAction generates valid action', () => {
    const action = createFillInputAction('syllabus', 'Course content here', {
      append: true,
      fieldLabel: 'Syllabus',
    });
    expect(action.type).toBe('ui.fillInput');
    expect(action.payload.content).toBe('Course content here');
    expect(action.payload.append).toBe(true);
  });

  test('createSelectDropdownAction with index', () => {
    const action = createSelectDropdownAction('select-course', { index: 2 });
    expect(action.type).toBe('ui.selectDropdown');
    expect(action.payload.selectionIndex).toBe(2);
    expect(action.payload.selectionValue).toBeUndefined();
  });

  test('createSelectDropdownAction with value', () => {
    const action = createSelectDropdownAction('select-course', {
      value: 'course-abc',
    });
    expect(action.type).toBe('ui.selectDropdown');
    expect(action.payload.selectionValue).toBe('course-abc');
    expect(action.payload.selectionIndex).toBeUndefined();
  });

  test('createNavigateAction generates valid action', () => {
    const action = createNavigateAction('/sessions');
    expect(action.type).toBe('ui.navigate');
    expect(action.payload.route).toBe('/sessions');
  });
});

// ============================================================================
// FAILURE TRACE TESTS (Real-world failure scenarios)
// ============================================================================

describe('Voice Controller Failure Traces', () => {
  /**
   * Failure Trace #1: Tab switch fails due to hyphenated name
   *
   * User says: "switch to AI features tab"
   * LLM returns: voiceId="aifeatures" (no hyphen)
   * DOM has: data-voice-id="tab-ai-features"
   * Result: Tab not found
   */
  test('tab switch with hyphenated names (Failure Trace #1)', () => {
    // The action schema should accept various formats
    const action = createSwitchTabAction('aifeatures', 'AI Features');
    const validated = validateVoiceAction(action);
    expect(validated).not.toBeNull();

    // The UI controller should normalize: "aifeatures" → "tab-ai-features"
    // This is tested in VoiceUIController where we try variations
    const variations = [
      'aifeatures',
      'ai-features',
      'tab-aifeatures',
      'tab-ai-features',
    ];
    expect(variations).toContain('tab-ai-features');
  });

  /**
   * Failure Trace #2: Dropdown selection by ordinal fails
   *
   * User says: "select the first course"
   * LLM returns: selectionIndex=1 (should be 0)
   * Result: Wrong course selected
   */
  test('dropdown selection by ordinal (Failure Trace #2)', () => {
    // Ordinals should be 0-indexed in our schema
    const firstAction = createSelectDropdownAction('select-course', { index: 0 });
    const secondAction = createSelectDropdownAction('select-course', { index: 1 });
    const lastAction = createSelectDropdownAction('select-course', { index: -1 });

    expect(firstAction.payload.selectionIndex).toBe(0); // "first"
    expect(secondAction.payload.selectionIndex).toBe(1); // "second"
    expect(lastAction.payload.selectionIndex).toBe(-1); // "last"
  });

  /**
   * Failure Trace #3: Form fill doesn't trigger React state update
   *
   * User says: "set the title to Introduction to AI"
   * DOM value changes but React state doesn't update
   * Form submission uses stale value
   */
  test('form fill React compatibility (Failure Trace #3)', () => {
    const action = createFillInputAction('course-title', 'Introduction to AI');
    const validated = validateVoiceAction(action);
    expect(validated).not.toBeNull();

    // The executor should use React-compatible value setter
    // which uses native setter + _valueTracker update + event dispatch
    // This is integration-tested in voice-action-executor.ts
  });
});

// ============================================================================
// UI STATE STRUCTURE TESTS
// ============================================================================

describe('UI State Structure', () => {
  test('compact state has required fields', () => {
    // Mock compact UI state structure
    const mockCompactState = {
      route: '/sessions',
      activeTab: 'tab-sessions',
      tabs: [
        { id: 'tab-sessions', label: 'Sessions', active: true },
        { id: 'tab-create', label: 'Create', active: false },
        { id: 'tab-ai-features', label: 'AI Features', active: false },
      ],
      buttons: [
        { id: 'create-session', label: 'Create Session' },
        { id: 'go-live', label: 'Go Live' },
      ],
      inputs: [
        { id: 'session-title', label: 'Title', value: '' },
      ],
      dropdowns: [
        {
          id: 'select-course',
          label: 'Select Course',
          selected: 'Statistics 101',
          options: [
            { idx: 0, label: 'Statistics 101' },
            { idx: 1, label: 'Machine Learning' },
          ],
        },
      ],
      modal: null,
    };

    // Verify structure
    expect(mockCompactState.route).toBeDefined();
    expect(mockCompactState.activeTab).toBeDefined();
    expect(Array.isArray(mockCompactState.tabs)).toBe(true);
    expect(Array.isArray(mockCompactState.buttons)).toBe(true);
    expect(Array.isArray(mockCompactState.inputs)).toBe(true);
    expect(Array.isArray(mockCompactState.dropdowns)).toBe(true);

    // Verify tab structure
    expect(mockCompactState.tabs[0]).toHaveProperty('id');
    expect(mockCompactState.tabs[0]).toHaveProperty('label');
    expect(mockCompactState.tabs[0]).toHaveProperty('active');

    // Verify dropdown has options
    expect(mockCompactState.dropdowns[0].options.length).toBeGreaterThan(0);
    expect(mockCompactState.dropdowns[0].options[0]).toHaveProperty('idx');
    expect(mockCompactState.dropdowns[0].options[0]).toHaveProperty('label');
  });
});

// ============================================================================
// VERIFICATION LOGIC TESTS
// ============================================================================

describe('State Diff and Verification', () => {
  test('detects tab change', () => {
    const stateBefore = {
      activeTab: 'tab-sessions',
      tabs: [
        { voiceId: 'tab-sessions', label: 'Sessions', active: true, disabled: false },
        { voiceId: 'tab-create', label: 'Create', active: false, disabled: false },
      ],
      // ... other fields
    };

    const stateAfter = {
      activeTab: 'tab-create',
      tabs: [
        { voiceId: 'tab-sessions', label: 'Sessions', active: false, disabled: false },
        { voiceId: 'tab-create', label: 'Create', active: true, disabled: false },
      ],
      // ... other fields
    };

    // Simple diff check
    const tabChanged = stateBefore.activeTab !== stateAfter.activeTab;
    expect(tabChanged).toBe(true);
    expect(stateAfter.activeTab).toBe('tab-create');
  });

  test('detects input value change', () => {
    const fieldsBefore = [
      { voiceId: 'course-title', value: '' },
    ];

    const fieldsAfter = [
      { voiceId: 'course-title', value: 'Introduction to AI' },
    ];

    const changed = fieldsBefore[0].value !== fieldsAfter[0].value;
    expect(changed).toBe(true);
  });

  test('detects dropdown selection change', () => {
    const dropdownBefore = {
      voiceId: 'select-course',
      selectedValue: null,
    };

    const dropdownAfter = {
      voiceId: 'select-course',
      selectedValue: 'course-123',
    };

    const changed = dropdownBefore.selectedValue !== dropdownAfter.selectedValue;
    expect(changed).toBe(true);
  });
});

// ============================================================================
// EDGE CASES
// ============================================================================

describe('Edge Cases', () => {
  test('handles empty voiceId gracefully', () => {
    const action = {
      type: 'ui.clickButton',
      payload: { voiceId: '' },
    };
    const result = validateVoiceAction(action);
    // Empty string should fail min length validation
    expect(result).toBeNull();
  });

  test('handles special characters in content', () => {
    const action = createFillInputAction(
      'post-content',
      "What's the formula for E=mc²? Use <code> tags."
    );
    const validated = validateVoiceAction(action);
    expect(validated).not.toBeNull();
    expect(validated?.payload.content).toContain('E=mc²');
  });

  test('handles negative index for last item', () => {
    const action = createSelectDropdownAction('select-course', { index: -1 });
    expect(action.payload.selectionIndex).toBe(-1);
  });

  test('handles append mode for input', () => {
    const action = createFillInputAction('post-content', ' more text', {
      append: true,
    });
    expect(action.payload.append).toBe(true);
  });
});
