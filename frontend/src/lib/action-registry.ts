/**
 * Action Registry - Semantic UI Action System for ElevenLabs Client Tools
 *
 * This module provides a whitelist-based action system that:
 * 1. Maps semantic action_ids to UI handlers
 * 2. Validates inputs against defined schemas
 * 3. Classifies actions into risk tiers (low/medium/high)
 * 4. Returns structured results {ok, did, hint}
 * 5. Supports idempotency/dedup for repeat commands
 *
 * IMPORTANT: ElevenLabs Client Tools call run_ui_action() directly.
 * The agent is the ONLY speaker - no SPEAK: prefix mechanism.
 */

import { AppRouterInstance } from 'next/dist/shared/lib/app-router-context.shared-runtime';

// =============================================================================
// TYPES
// =============================================================================

export type RiskTier = 'low' | 'medium' | 'high';

export interface ActionResult {
  ok: boolean;
  did: string;        // Past tense description of what was done
  hint?: string;      // Optional hint for the agent to speak
  error?: string;     // Error message if ok=false
  data?: Record<string, unknown>; // Optional data payload
}

export interface ActionDefinition {
  id: string;
  description: string;
  risk: RiskTier;
  requiresConfirmation?: boolean;
  params?: {
    [key: string]: {
      type: 'string' | 'number' | 'boolean' | 'array';
      required?: boolean;
      description?: string;
      enum?: string[];
    };
  };
  handler: (args: Record<string, unknown>, ctx: ActionContext) => Promise<ActionResult>;
}

export interface ActionContext {
  router: AppRouterInstance;
  locale: string;
  userId?: number;
  currentRoute: string;
  sessionId?: string;  // Voice session ID for idempotency
}

// =============================================================================
// IDEMPOTENCY TRACKING
// =============================================================================

interface IdempotencyRecord {
  actionId: string;
  argsHash: string;
  timestamp: number;
  result: ActionResult;
}

const idempotencyCache = new Map<string, IdempotencyRecord>();
const IDEMPOTENCY_TTL_MS = 5000; // 5 seconds dedup window

function hashArgs(args: Record<string, unknown>): string {
  return JSON.stringify(args);
}

function checkIdempotency(actionId: string, args: Record<string, unknown>): ActionResult | null {
  const argsHash = hashArgs(args);
  const key = `${actionId}:${argsHash}`;
  const record = idempotencyCache.get(key);

  if (record && Date.now() - record.timestamp < IDEMPOTENCY_TTL_MS) {
    console.log(`[ActionRegistry] Idempotency hit for ${actionId} - returning cached result`);
    return record.result;
  }

  return null;
}

function recordIdempotency(actionId: string, args: Record<string, unknown>, result: ActionResult): void {
  const argsHash = hashArgs(args);
  const key = `${actionId}:${argsHash}`;
  idempotencyCache.set(key, {
    actionId,
    argsHash,
    timestamp: Date.now(),
    result,
  });

  // Clean up old entries
  const now = Date.now();
  for (const [k, v] of idempotencyCache.entries()) {
    if (now - v.timestamp > IDEMPOTENCY_TTL_MS * 2) {
      idempotencyCache.delete(k);
    }
  }
}

// =============================================================================
// ACTION HANDLERS
// =============================================================================

// Navigation handlers
async function navigateHandler(args: Record<string, unknown>, ctx: ActionContext): Promise<ActionResult> {
  const page = args.page as string;
  const routeMap: Record<string, string> = {
    courses: '/courses',
    sessions: '/sessions',
    forum: '/forum',
    console: '/console',
    reports: '/reports',
    dashboard: '/dashboard',
    integrations: '/integrations',
    introduction: '/platform-guide',
    profile: '/profile',
  };

  const route = routeMap[page.toLowerCase()];
  if (!route) {
    return {
      ok: false,
      did: 'navigation failed',
      error: `Unknown page: ${page}`,
      hint: `I don't recognize that page. Available pages are: ${Object.keys(routeMap).join(', ')}.`,
    };
  }

  ctx.router.push(route);
  const pageName = page.charAt(0).toUpperCase() + page.slice(1);

  return {
    ok: true,
    did: `navigated to ${pageName}`,
    hint: ctx.locale === 'es' ? `Llevándote a ${pageName}.` : `Taking you to ${pageName}.`,
  };
}

async function switchTabHandler(args: Record<string, unknown>, ctx: ActionContext): Promise<ActionResult> {
  const tabVoiceId = args.tab_voice_id as string;
  const tabLabel = (args.tab_label as string) || tabVoiceId;

  // Dispatch custom event for tab switching
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('voice-select-tab', {
      detail: { voiceId: tabVoiceId, tabName: tabVoiceId },
    }));
  }

  return {
    ok: true,
    did: `switched to ${tabLabel} tab`,
    hint: ctx.locale === 'es' ? `Cambiando a la pestaña ${tabLabel}.` : `Switching to ${tabLabel} tab.`,
  };
}

async function clickButtonHandler(args: Record<string, unknown>, ctx: ActionContext): Promise<ActionResult> {
  const buttonVoiceId = args.button_voice_id as string;
  const buttonLabel = (args.button_label as string) || buttonVoiceId;

  // Find and click the button
  if (typeof window !== 'undefined') {
    const button = document.querySelector(`[data-voice-id="${buttonVoiceId}"]`) as HTMLElement;
    if (button) {
      button.click();
      return {
        ok: true,
        did: `clicked ${buttonLabel}`,
        hint: ctx.locale === 'es' ? `Haciendo clic en ${buttonLabel}.` : `Clicking ${buttonLabel}.`,
      };
    }

    return {
      ok: false,
      did: 'button click failed',
      error: `Button not found: ${buttonVoiceId}`,
      hint: ctx.locale === 'es'
        ? `No pude encontrar ese botón.`
        : `I couldn't find that button.`,
    };
  }

  return { ok: false, did: 'failed', error: 'Not in browser' };
}

async function fillInputHandler(args: Record<string, unknown>, ctx: ActionContext): Promise<ActionResult> {
  const fieldVoiceId = args.field_voice_id as string;
  const content = args.content as string;
  const append = args.append as boolean;

  if (typeof window !== 'undefined') {
    const field = document.querySelector(`[data-voice-id="${fieldVoiceId}"]`) as HTMLInputElement | HTMLTextAreaElement;
    if (field) {
      if (append) {
        field.value += content;
      } else {
        field.value = content;
      }
      // Trigger input event for React
      field.dispatchEvent(new Event('input', { bubbles: true }));
      field.dispatchEvent(new Event('change', { bubbles: true }));

      return {
        ok: true,
        did: `filled ${fieldVoiceId}`,
        hint: ctx.locale === 'es' ? `Campo completado.` : `Field filled.`,
      };
    }

    return {
      ok: false,
      did: 'input fill failed',
      error: `Input not found: ${fieldVoiceId}`,
    };
  }

  return { ok: false, did: 'failed', error: 'Not in browser' };
}

async function selectDropdownHandler(args: Record<string, unknown>, ctx: ActionContext): Promise<ActionResult> {
  const dropdownVoiceId = args.dropdown_voice_id as string;
  const selectionIndex = args.selection_index as number | undefined;
  const selectionText = args.selection_text as string | undefined;

  if (typeof window !== 'undefined') {
    // Dispatch custom event for dropdown selection
    window.dispatchEvent(new CustomEvent('voice-select-dropdown', {
      detail: {
        voiceId: dropdownVoiceId,
        selectionIndex,
        selectionText,
      },
    }));

    const selection = selectionText || (selectionIndex !== undefined ? `option ${selectionIndex + 1}` : 'option');
    return {
      ok: true,
      did: `selected ${selection}`,
      hint: ctx.locale === 'es' ? `Seleccionando ${selection}.` : `Selecting ${selection}.`,
    };
  }

  return { ok: false, did: 'failed', error: 'Not in browser' };
}

async function confirmActionHandler(args: Record<string, unknown>, ctx: ActionContext): Promise<ActionResult> {
  const confirmed = args.confirmed as boolean;

  if (typeof window !== 'undefined') {
    // Find and click confirm/cancel button based on user response
    const buttonSelector = confirmed
      ? '[data-voice-id="confirm"], [data-voice-id="btn-confirm"], button:has-text("Confirm"), button:has-text("Yes")'
      : '[data-voice-id="cancel"], [data-voice-id="btn-cancel"], button:has-text("Cancel"), button:has-text("No")';

    const button = document.querySelector(buttonSelector) as HTMLElement;
    if (button) {
      button.click();
    }
  }

  return {
    ok: true,
    did: confirmed ? 'confirmed action' : 'cancelled action',
    hint: confirmed
      ? (ctx.locale === 'es' ? 'Confirmado.' : 'Confirmed.')
      : (ctx.locale === 'es' ? 'Cancelado.' : 'Cancelled.'),
  };
}

// Session management handlers
async function goLiveHandler(args: Record<string, unknown>, ctx: ActionContext): Promise<ActionResult> {
  if (typeof window !== 'undefined') {
    const button = document.querySelector('[data-voice-id="go-live"]') as HTMLElement;
    if (button) {
      button.click();
      return {
        ok: true,
        did: 'started live session',
        hint: ctx.locale === 'es' ? 'Iniciando sesión en vivo.' : 'Starting live session.',
      };
    }
  }

  return {
    ok: false,
    did: 'go live failed',
    error: 'Go live button not found',
    hint: ctx.locale === 'es'
      ? 'No pude encontrar el botón para iniciar en vivo. Asegúrate de estar en la pestaña correcta.'
      : "I couldn't find the go live button. Make sure you're on the right tab.",
  };
}

async function endSessionHandler(args: Record<string, unknown>, ctx: ActionContext): Promise<ActionResult> {
  if (typeof window !== 'undefined') {
    const button = document.querySelector('[data-voice-id="end-session"]') as HTMLElement;
    if (button) {
      button.click();
      return {
        ok: true,
        did: 'ended session',
        hint: ctx.locale === 'es' ? 'Sesión terminada.' : 'Session ended.',
      };
    }
  }

  return {
    ok: false,
    did: 'end session failed',
    error: 'End session button not found',
  };
}

// =============================================================================
// ACTION REGISTRY
// =============================================================================

export const ACTION_REGISTRY: Record<string, ActionDefinition> = {
  // Navigation - LOW risk
  NAV_COURSES: {
    id: 'NAV_COURSES',
    description: 'Navigate to courses page',
    risk: 'low',
    handler: async (_, ctx) => navigateHandler({ page: 'courses' }, ctx),
  },
  NAV_SESSIONS: {
    id: 'NAV_SESSIONS',
    description: 'Navigate to sessions page',
    risk: 'low',
    handler: async (_, ctx) => navigateHandler({ page: 'sessions' }, ctx),
  },
  NAV_FORUM: {
    id: 'NAV_FORUM',
    description: 'Navigate to forum page',
    risk: 'low',
    handler: async (_, ctx) => navigateHandler({ page: 'forum' }, ctx),
  },
  NAV_CONSOLE: {
    id: 'NAV_CONSOLE',
    description: 'Navigate to console page',
    risk: 'low',
    handler: async (_, ctx) => navigateHandler({ page: 'console' }, ctx),
  },
  NAV_REPORTS: {
    id: 'NAV_REPORTS',
    description: 'Navigate to reports page',
    risk: 'low',
    handler: async (_, ctx) => navigateHandler({ page: 'reports' }, ctx),
  },
  NAV_DASHBOARD: {
    id: 'NAV_DASHBOARD',
    description: 'Navigate to dashboard',
    risk: 'low',
    handler: async (_, ctx) => navigateHandler({ page: 'dashboard' }, ctx),
  },
  NAV_INTEGRATIONS: {
    id: 'NAV_INTEGRATIONS',
    description: 'Navigate to integrations page',
    risk: 'low',
    handler: async (_, ctx) => navigateHandler({ page: 'integrations' }, ctx),
  },

  // Generic navigate with page param
  NAVIGATE: {
    id: 'NAVIGATE',
    description: 'Navigate to a page',
    risk: 'low',
    params: {
      page: { type: 'string', required: true, description: 'Page name' },
    },
    handler: navigateHandler,
  },

  // Tab switching - LOW risk
  SWITCH_TAB: {
    id: 'SWITCH_TAB',
    description: 'Switch to a tab on current page',
    risk: 'low',
    params: {
      tab_voice_id: { type: 'string', required: true },
      tab_label: { type: 'string', required: false },
    },
    handler: switchTabHandler,
  },
  SWITCH_TAB_COURSES: {
    id: 'SWITCH_TAB_COURSES',
    description: 'Switch to courses tab',
    risk: 'low',
    handler: async (_, ctx) => switchTabHandler({ tab_voice_id: 'tab-courses', tab_label: 'Courses' }, ctx),
  },
  SWITCH_TAB_CREATE: {
    id: 'SWITCH_TAB_CREATE',
    description: 'Switch to create tab',
    risk: 'low',
    handler: async (_, ctx) => switchTabHandler({ tab_voice_id: 'tab-create', tab_label: 'Create' }, ctx),
  },
  SWITCH_TAB_ADVANCED: {
    id: 'SWITCH_TAB_ADVANCED',
    description: 'Switch to advanced/enrollment tab',
    risk: 'low',
    handler: async (_, ctx) => switchTabHandler({ tab_voice_id: 'tab-advanced', tab_label: 'Advanced' }, ctx),
  },
  SWITCH_TAB_AI_FEATURES: {
    id: 'SWITCH_TAB_AI_FEATURES',
    description: 'Switch to AI features tab',
    risk: 'low',
    handler: async (_, ctx) => switchTabHandler({ tab_voice_id: 'tab-ai-features', tab_label: 'AI Features' }, ctx),
  },
  SWITCH_TAB_MATERIALS: {
    id: 'SWITCH_TAB_MATERIALS',
    description: 'Switch to materials tab',
    risk: 'low',
    handler: async (_, ctx) => switchTabHandler({ tab_voice_id: 'tab-materials', tab_label: 'Materials' }, ctx),
  },
  SWITCH_TAB_MANAGE: {
    id: 'SWITCH_TAB_MANAGE',
    description: 'Switch to manage tab',
    risk: 'low',
    handler: async (_, ctx) => switchTabHandler({ tab_voice_id: 'tab-manage', tab_label: 'Manage' }, ctx),
  },
  SWITCH_TAB_POLLS: {
    id: 'SWITCH_TAB_POLLS',
    description: 'Switch to polls tab',
    risk: 'low',
    handler: async (_, ctx) => switchTabHandler({ tab_voice_id: 'tab-polls', tab_label: 'Polls' }, ctx),
  },
  SWITCH_TAB_COPILOT: {
    id: 'SWITCH_TAB_COPILOT',
    description: 'Switch to copilot tab',
    risk: 'low',
    handler: async (_, ctx) => switchTabHandler({ tab_voice_id: 'tab-copilot', tab_label: 'Copilot' }, ctx),
  },
  SWITCH_TAB_TOOLS: {
    id: 'SWITCH_TAB_TOOLS',
    description: 'Switch to tools tab',
    risk: 'low',
    handler: async (_, ctx) => switchTabHandler({ tab_voice_id: 'tab-tools', tab_label: 'Tools' }, ctx),
  },

  // Button clicks - MEDIUM risk
  CLICK_BUTTON: {
    id: 'CLICK_BUTTON',
    description: 'Click a button by voice ID',
    risk: 'medium',
    params: {
      button_voice_id: { type: 'string', required: true },
      button_label: { type: 'string', required: false },
    },
    handler: clickButtonHandler,
  },

  // Form inputs - MEDIUM risk
  FILL_INPUT: {
    id: 'FILL_INPUT',
    description: 'Fill a form input field',
    risk: 'medium',
    params: {
      field_voice_id: { type: 'string', required: true },
      content: { type: 'string', required: true },
      append: { type: 'boolean', required: false },
    },
    handler: fillInputHandler,
  },

  // Dropdown selection - MEDIUM risk
  SELECT_DROPDOWN: {
    id: 'SELECT_DROPDOWN',
    description: 'Select an option from a dropdown',
    risk: 'medium',
    params: {
      dropdown_voice_id: { type: 'string', required: true },
      selection_index: { type: 'number', required: false },
      selection_text: { type: 'string', required: false },
    },
    handler: selectDropdownHandler,
  },

  // Confirmation - LOW risk
  CONFIRM: {
    id: 'CONFIRM',
    description: 'Confirm a pending action',
    risk: 'low',
    handler: async (_, ctx) => confirmActionHandler({ confirmed: true }, ctx),
  },
  CANCEL: {
    id: 'CANCEL',
    description: 'Cancel a pending action',
    risk: 'low',
    handler: async (_, ctx) => confirmActionHandler({ confirmed: false }, ctx),
  },

  // Session management - MEDIUM/HIGH risk
  GO_LIVE: {
    id: 'GO_LIVE',
    description: 'Start a live session',
    risk: 'medium',
    handler: goLiveHandler,
  },
  END_SESSION: {
    id: 'END_SESSION',
    description: 'End the current live session',
    risk: 'high',
    requiresConfirmation: true,
    handler: endSessionHandler,
  },

  // Delete actions - HIGH risk
  DELETE_SESSION: {
    id: 'DELETE_SESSION',
    description: 'Delete the selected session',
    risk: 'high',
    requiresConfirmation: true,
    handler: async (_, ctx) => {
      if (typeof window !== 'undefined') {
        const button = document.querySelector('[data-voice-id="delete-session"]') as HTMLElement;
        if (button) {
          button.click();
          return {
            ok: true,
            did: 'initiated session deletion',
            hint: ctx.locale === 'es'
              ? 'Por favor confirma si deseas eliminar esta sesión.'
              : 'Please confirm if you want to delete this session.',
          };
        }
      }
      return { ok: false, did: 'delete failed', error: 'Delete button not found' };
    },
  },
  DELETE_COURSE: {
    id: 'DELETE_COURSE',
    description: 'Delete the selected course',
    risk: 'high',
    requiresConfirmation: true,
    handler: async (_, ctx) => {
      if (typeof window !== 'undefined') {
        const button = document.querySelector('[data-voice-id="delete-course"]') as HTMLElement;
        if (button) {
          button.click();
          return {
            ok: true,
            did: 'initiated course deletion',
            hint: ctx.locale === 'es'
              ? 'Por favor confirma si deseas eliminar este curso.'
              : 'Please confirm if you want to delete this course.',
          };
        }
      }
      return { ok: false, did: 'delete failed', error: 'Delete button not found' };
    },
  },
};

// =============================================================================
// MAIN ENTRY POINT
// =============================================================================

/**
 * Execute a UI action by its semantic action_id.
 *
 * This is the MAIN ENTRY POINT for ElevenLabs Client Tools.
 * All UI actions flow through this function.
 *
 * @param actionId - The semantic action ID (e.g., 'NAV_COURSES', 'SWITCH_TAB_CREATE')
 * @param args - Arguments for the action (validated against schema)
 * @param ctx - Action context (router, locale, userId, etc.)
 * @returns ActionResult with {ok, did, hint}
 */
export async function run_ui_action(
  actionId: string,
  args: Record<string, unknown>,
  ctx: ActionContext
): Promise<ActionResult> {
  console.log(`[ActionRegistry] run_ui_action: ${actionId}`, args);

  // Check action exists in registry
  const action = ACTION_REGISTRY[actionId];
  if (!action) {
    console.error(`[ActionRegistry] Unknown action: ${actionId}`);
    return {
      ok: false,
      did: 'action not found',
      error: `Unknown action: ${actionId}`,
      hint: ctx.locale === 'es'
        ? 'No reconozco esa acción.'
        : "I don't recognize that action.",
    };
  }

  // Check idempotency
  const cachedResult = checkIdempotency(actionId, args);
  if (cachedResult) {
    return cachedResult;
  }

  // Validate required params
  if (action.params) {
    for (const [paramName, paramDef] of Object.entries(action.params)) {
      if (paramDef.required && !(paramName in args)) {
        return {
          ok: false,
          did: 'validation failed',
          error: `Missing required parameter: ${paramName}`,
        };
      }

      // Type validation
      if (paramName in args) {
        const value = args[paramName];
        const actualType = Array.isArray(value) ? 'array' : typeof value;
        if (actualType !== paramDef.type && value !== null && value !== undefined) {
          return {
            ok: false,
            did: 'validation failed',
            error: `Invalid type for ${paramName}: expected ${paramDef.type}, got ${actualType}`,
          };
        }

        // Enum validation
        if (paramDef.enum && !paramDef.enum.includes(value as string)) {
          return {
            ok: false,
            did: 'validation failed',
            error: `Invalid value for ${paramName}: must be one of ${paramDef.enum.join(', ')}`,
          };
        }
      }
    }
  }

  // Log action attempt
  logActionRun(actionId, args, ctx, 'pending');

  try {
    // Execute the handler
    const result = await action.handler(args, ctx);

    // Record idempotency
    recordIdempotency(actionId, args, result);

    // Log completion
    logActionRun(actionId, args, ctx, result.ok ? 'success' : 'failure', result);

    return result;
  } catch (error) {
    const errorMsg = error instanceof Error ? error.message : String(error);
    console.error(`[ActionRegistry] Error executing ${actionId}:`, error);

    const result: ActionResult = {
      ok: false,
      did: 'action failed',
      error: errorMsg,
      hint: ctx.locale === 'es'
        ? 'Ocurrió un error. Por favor intenta de nuevo.'
        : 'An error occurred. Please try again.',
    };

    logActionRun(actionId, args, ctx, 'failure', result);
    return result;
  }
}

// =============================================================================
// ACTION RUN LOGGING
// =============================================================================

interface ActionRunLog {
  action_id: string;
  args: Record<string, unknown>;
  user_id?: number;
  route: string;
  status: 'pending' | 'success' | 'failure';
  result?: ActionResult;
  timestamp: number;
}

const actionRunLogs: ActionRunLog[] = [];

function logActionRun(
  actionId: string,
  args: Record<string, unknown>,
  ctx: ActionContext,
  status: 'pending' | 'success' | 'failure',
  result?: ActionResult
): void {
  const log: ActionRunLog = {
    action_id: actionId,
    args,
    user_id: ctx.userId,
    route: ctx.currentRoute,
    status,
    result,
    timestamp: Date.now(),
  };

  actionRunLogs.push(log);

  // Keep only last 100 logs in memory
  while (actionRunLogs.length > 100) {
    actionRunLogs.shift();
  }

  // Optionally send to backend for persistent logging
  // This can be enabled when the backend endpoint is ready
  // sendActionRunToBackend(log);
}

/**
 * Get recent action runs for debugging/observability
 */
export function getRecentActionRuns(): ActionRunLog[] {
  return [...actionRunLogs].reverse().slice(0, 20);
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Get list of all available action IDs
 */
export function getAvailableActions(): string[] {
  return Object.keys(ACTION_REGISTRY);
}

/**
 * Get action definition by ID
 */
export function getActionDefinition(actionId: string): ActionDefinition | undefined {
  return ACTION_REGISTRY[actionId];
}

/**
 * Check if an action requires confirmation
 */
export function requiresConfirmation(actionId: string): boolean {
  const action = ACTION_REGISTRY[actionId];
  return action?.requiresConfirmation ?? action?.risk === 'high';
}

/**
 * Get the risk tier for an action
 */
export function getActionRisk(actionId: string): RiskTier | undefined {
  return ACTION_REGISTRY[actionId]?.risk;
}
