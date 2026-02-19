/**
 * Voice Action Schema - Strict type definitions for all voice-triggered UI actions.
 *
 * This module provides:
 * 1. Zod schemas for runtime validation
 * 2. TypeScript types for compile-time safety
 * 3. Action creators for consistent action construction
 * 4. Discriminated union type for exhaustive handling
 */

import { z } from 'zod';

// ============================================================================
// BASE SCHEMA
// ============================================================================

const BaseActionSchema = z.object({
  correlationId: z.string().optional(),
  timestamp: z.number().optional(),
});

// ============================================================================
// NAVIGATION ACTION
// ============================================================================

export const NavigateActionSchema = BaseActionSchema.extend({
  type: z.literal('ui.navigate'),
  payload: z.object({
    route: z.enum([
      '/courses',
      '/sessions',
      '/console',
      '/forum',
      '/reports',
      '/dashboard',
      '/integrations',
      '/introduction',
      '/profile',
      '/platform-guide',
    ]),
  }),
});

export type NavigateAction = z.infer<typeof NavigateActionSchema>;

// ============================================================================
// TAB SWITCH ACTION
// ============================================================================

export const SwitchTabActionSchema = BaseActionSchema.extend({
  type: z.literal('ui.switchTab'),
  payload: z.object({
    voiceId: z.string().min(1, 'voiceId is required'),
    tabLabel: z.string().optional(), // Human-readable label for feedback
  }),
});

export type SwitchTabAction = z.infer<typeof SwitchTabActionSchema>;

// ============================================================================
// BUTTON CLICK ACTION
// ============================================================================

export const ClickButtonActionSchema = BaseActionSchema.extend({
  type: z.literal('ui.clickButton'),
  payload: z.object({
    voiceId: z.string().min(1, 'voiceId is required'),
    buttonLabel: z.string().optional(),
  }),
});

export type ClickButtonAction = z.infer<typeof ClickButtonActionSchema>;

// ============================================================================
// DROPDOWN EXPAND ACTION
// ============================================================================

export const ExpandDropdownActionSchema = BaseActionSchema.extend({
  type: z.literal('ui.expandDropdown'),
  payload: z.object({
    voiceId: z.string().min(1, 'voiceId is required'),
    dropdownLabel: z.string().optional(),
  }),
});

export type ExpandDropdownAction = z.infer<typeof ExpandDropdownActionSchema>;

// ============================================================================
// DROPDOWN SELECT ACTION
// ============================================================================

export const SelectDropdownActionSchema = BaseActionSchema.extend({
  type: z.literal('ui.selectDropdown'),
  payload: z.object({
    voiceId: z.string().min(1, 'voiceId is required'),
    // Selection can be by index OR by value - exactly one must be provided
    selectionIndex: z.number().int().optional(),
    selectionValue: z.string().optional(),
    optionLabel: z.string().optional(), // For feedback: "Selected Statistics 101"
  }).refine(
    data => data.selectionIndex !== undefined || data.selectionValue !== undefined,
    'Either selectionIndex or selectionValue must be provided'
  ),
});

export type SelectDropdownAction = z.infer<typeof SelectDropdownActionSchema>;

// ============================================================================
// FILL INPUT ACTION
// ============================================================================

export const FillInputActionSchema = BaseActionSchema.extend({
  type: z.literal('ui.fillInput'),
  payload: z.object({
    voiceId: z.string().min(1, 'voiceId is required'),
    content: z.string(),
    append: z.boolean().optional().default(false), // Append to existing content
    fieldLabel: z.string().optional(),
  }),
});

export type FillInputAction = z.infer<typeof FillInputActionSchema>;

// ============================================================================
// CLEAR INPUT ACTION
// ============================================================================

export const ClearInputActionSchema = BaseActionSchema.extend({
  type: z.literal('ui.clearInput'),
  payload: z.object({
    voiceId: z.string().min(1, 'voiceId is required'),
  }),
});

export type ClearInputAction = z.infer<typeof ClearInputActionSchema>;

// ============================================================================
// SELECT LIST ITEM ACTION
// ============================================================================

export const SelectListItemActionSchema = BaseActionSchema.extend({
  type: z.literal('ui.selectListItem'),
  payload: z.object({
    listVoiceId: z.string().optional(), // Container voice-id
    itemIndex: z.number().int().optional(),
    itemVoiceId: z.string().optional(),
    itemLabel: z.string().optional(),
  }).refine(
    data => data.itemIndex !== undefined || data.itemVoiceId !== undefined,
    'Either itemIndex or itemVoiceId must be provided'
  ),
});

export type SelectListItemAction = z.infer<typeof SelectListItemActionSchema>;

// ============================================================================
// OPEN MODAL ACTION
// ============================================================================

export const OpenModalActionSchema = BaseActionSchema.extend({
  type: z.literal('ui.openModal'),
  payload: z.object({
    modalId: z.string().min(1),
    title: z.string().optional(),
  }),
});

export type OpenModalAction = z.infer<typeof OpenModalActionSchema>;

// ============================================================================
// CLOSE MODAL ACTION
// ============================================================================

export const CloseModalActionSchema = BaseActionSchema.extend({
  type: z.literal('ui.closeModal'),
  payload: z.object({
    modalId: z.string().optional(), // If not provided, closes topmost modal
  }),
});

export type CloseModalAction = z.infer<typeof CloseModalActionSchema>;

// ============================================================================
// TOAST ACTION
// ============================================================================

export const ToastActionSchema = BaseActionSchema.extend({
  type: z.literal('ui.toast'),
  payload: z.object({
    message: z.string().min(1),
    variant: z.enum(['info', 'success', 'warning', 'error']).optional().default('info'),
    duration: z.number().positive().optional().default(5000),
  }),
});

export type ToastAction = z.infer<typeof ToastActionSchema>;

// ============================================================================
// SCROLL ACTION
// ============================================================================

export const ScrollActionSchema = BaseActionSchema.extend({
  type: z.literal('ui.scroll'),
  payload: z.object({
    direction: z.enum(['up', 'down', 'top', 'bottom']),
    targetVoiceId: z.string().optional(), // Scroll to specific element
    amount: z.number().positive().optional(), // Pixels to scroll
  }),
});

export type ScrollAction = z.infer<typeof ScrollActionSchema>;

// ============================================================================
// SUBMIT FORM ACTION
// ============================================================================

export const SubmitFormActionSchema = BaseActionSchema.extend({
  type: z.literal('ui.submitForm'),
  payload: z.object({
    formVoiceId: z.string().optional(),
    submitButtonVoiceId: z.string().optional(),
  }),
});

export type SubmitFormAction = z.infer<typeof SubmitFormActionSchema>;

// ============================================================================
// OPEN MENU AND CLICK ACTION
// ============================================================================

export const OpenMenuAndClickActionSchema = BaseActionSchema.extend({
  type: z.literal('ui.openMenuAndClick'),
  payload: z.object({
    menuVoiceId: z.string().min(1),
    itemVoiceId: z.string().min(1),
  }),
});

export type OpenMenuAndClickAction = z.infer<typeof OpenMenuAndClickActionSchema>;

// ============================================================================
// DISCRIMINATED UNION OF ALL ACTIONS
// ============================================================================

export const VoiceActionSchema = z.discriminatedUnion('type', [
  NavigateActionSchema,
  SwitchTabActionSchema,
  ClickButtonActionSchema,
  ExpandDropdownActionSchema,
  SelectDropdownActionSchema,
  FillInputActionSchema,
  ClearInputActionSchema,
  SelectListItemActionSchema,
  OpenModalActionSchema,
  CloseModalActionSchema,
  ToastActionSchema,
  ScrollActionSchema,
  SubmitFormActionSchema,
  OpenMenuAndClickActionSchema,
]);

export type VoiceAction = z.infer<typeof VoiceActionSchema>;

// ============================================================================
// ACTION TYPE ENUM
// ============================================================================

export const VoiceActionType = {
  NAVIGATE: 'ui.navigate',
  SWITCH_TAB: 'ui.switchTab',
  CLICK_BUTTON: 'ui.clickButton',
  EXPAND_DROPDOWN: 'ui.expandDropdown',
  SELECT_DROPDOWN: 'ui.selectDropdown',
  FILL_INPUT: 'ui.fillInput',
  CLEAR_INPUT: 'ui.clearInput',
  SELECT_LIST_ITEM: 'ui.selectListItem',
  OPEN_MODAL: 'ui.openModal',
  CLOSE_MODAL: 'ui.closeModal',
  TOAST: 'ui.toast',
  SCROLL: 'ui.scroll',
  SUBMIT_FORM: 'ui.submitForm',
  OPEN_MENU_AND_CLICK: 'ui.openMenuAndClick',
} as const;

// ============================================================================
// ACTION CREATORS
// ============================================================================

export const createNavigateAction = (route: NavigateAction['payload']['route']): NavigateAction => ({
  type: 'ui.navigate',
  payload: { route },
  correlationId: generateCorrelationId(),
  timestamp: Date.now(),
});

export const createSwitchTabAction = (voiceId: string, tabLabel?: string): SwitchTabAction => ({
  type: 'ui.switchTab',
  payload: { voiceId, tabLabel },
  correlationId: generateCorrelationId(),
  timestamp: Date.now(),
});

export const createClickButtonAction = (voiceId: string, buttonLabel?: string): ClickButtonAction => ({
  type: 'ui.clickButton',
  payload: { voiceId, buttonLabel },
  correlationId: generateCorrelationId(),
  timestamp: Date.now(),
});

export const createExpandDropdownAction = (voiceId: string): ExpandDropdownAction => ({
  type: 'ui.expandDropdown',
  payload: { voiceId },
  correlationId: generateCorrelationId(),
  timestamp: Date.now(),
});

export const createSelectDropdownAction = (
  voiceId: string,
  selection: { index: number } | { value: string },
  optionLabel?: string
): SelectDropdownAction => ({
  type: 'ui.selectDropdown',
  payload: {
    voiceId,
    selectionIndex: 'index' in selection ? selection.index : undefined,
    selectionValue: 'value' in selection ? selection.value : undefined,
    optionLabel,
  },
  correlationId: generateCorrelationId(),
  timestamp: Date.now(),
});

export const createFillInputAction = (
  voiceId: string,
  content: string,
  options?: { append?: boolean; fieldLabel?: string }
): FillInputAction => ({
  type: 'ui.fillInput',
  payload: {
    voiceId,
    content,
    append: options?.append ?? false,
    fieldLabel: options?.fieldLabel,
  },
  correlationId: generateCorrelationId(),
  timestamp: Date.now(),
});

export const createToastAction = (
  message: string,
  variant?: 'info' | 'success' | 'warning' | 'error'
): ToastAction => ({
  type: 'ui.toast',
  payload: { message, variant: variant ?? 'info' },
  correlationId: generateCorrelationId(),
  timestamp: Date.now(),
});

// ============================================================================
// VALIDATION HELPERS
// ============================================================================

export const validateVoiceAction = (action: unknown): VoiceAction | null => {
  const result = VoiceActionSchema.safeParse(action);
  if (result.success) {
    return result.data;
  }
  console.error('Voice action validation failed:', result.error.format());
  return null;
};

export const isValidVoiceAction = (action: unknown): action is VoiceAction => {
  return VoiceActionSchema.safeParse(action).success;
};

// ============================================================================
// UTILITIES
// ============================================================================

function generateCorrelationId(): string {
  return `voice-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

// ============================================================================
// ACTION RESULT TYPES
// ============================================================================

export interface ActionSuccess {
  success: true;
  action: VoiceAction;
  elementFound: boolean;
  verificationPassed: boolean;
}

export interface ActionFailure {
  success: false;
  action: VoiceAction;
  error: string;
  recoverable: boolean;
  suggestion?: string;
}

export type ActionResult = ActionSuccess | ActionFailure;
