/**
 * Action Registry - Smart UI Action System for ElevenLabs Client Tools
 *
 * This module uses FREE-FORM STRING parameters instead of enums.
 * ElevenLabs passes natural language targets, frontend resolves them.
 *
 * Key features:
 * 1. resolveTarget() - Fuzzy matches natural language to DOM elements
 * 2. No enum maintenance - just add data-voice-id to new elements
 * 3. Alias mapping for common terms
 * 4. Risk tiers with confirmation for high-risk actions
 *
 * ElevenLabs only needs 6 tools with string parameters!
 */

import { AppRouterInstance } from 'next/dist/shared/lib/app-router-context.shared-runtime';

// =============================================================================
// TYPES
// =============================================================================

export type RiskTier = 'low' | 'medium' | 'high';

export interface ActionResult {
  ok: boolean;
  did: string;
  hint?: string;
  error?: string;
  data?: Record<string, unknown>;
}

export interface ActionContext {
  router: AppRouterInstance;
  locale: string;
  userId?: number;
  currentRoute: string;
  sessionId?: string;
}

// =============================================================================
// ALIAS MAPPING - Common terms to voice IDs
// =============================================================================

const TAB_ALIASES: Record<string, string> = {
  // Courses page
  'courses': 'tab-courses',
  'overview': 'tab-courses',
  'create': 'tab-create',
  'new': 'tab-create',
  'join': 'tab-join',
  'advanced': 'tab-advanced',
  'enrollment': 'tab-advanced',
  'enroll': 'tab-advanced',
  'students': 'tab-advanced',
  'ai insights': 'tab-ai-insights',
  'insights': 'tab-insights',

  // Sessions page
  'sessions': 'tab-sessions',
  'materials': 'tab-materials',
  'upload': 'tab-materials',
  'manage': 'tab-manage',
  'status': 'tab-manage',
  'ai features': 'tab-ai-features',
  'ai': 'tab-ai-features',
  'enhanced': 'tab-ai-features',

  // Console page
  'copilot': 'tab-copilot',
  'polls': 'tab-polls',
  'poll': 'tab-polls',
  'cases': 'tab-cases',
  'case': 'tab-cases',
  'tools': 'tab-tools',
  'timer': 'tab-tools',
  'breakout': 'tab-tools',
  'requests': 'tab-requests',
  'roster': 'tab-roster',

  // Forum page
  'discussion': 'tab-discussion',
  'posts': 'tab-discussion',

  // Reports page
  'summary': 'tab-summary',
  'participation': 'tab-participation',
  'scoring': 'tab-scoring',
  'scores': 'tab-scoring',
  'analytics': 'tab-analytics',
};

const BUTTON_ALIASES: Record<string, string> = {
  // Session management
  'go live': 'go-live',
  'start live': 'go-live',
  'live': 'go-live',
  'end session': 'end-session',
  'stop session': 'end-session',
  'complete session': 'complete-session',
  'delete session': 'delete-session',
  'edit session': 'edit-session',
  'create session': 'create-session',
  'schedule': 'schedule-session',
  'draft': 'set-to-draft',

  // Course management
  'create course': 'create-course',
  'delete course': 'delete-course',
  'enroll selected': 'enroll-selected',
  'enroll all': 'enroll-all',

  // Console actions
  'start copilot': 'start-copilot',
  'stop copilot': 'stop-copilot',
  'create poll': 'create-poll',
  'post case': 'post-case',
  'approve': 'approve-instructor-request',
  'reject': 'reject-instructor-request',

  // AI features
  'generate summary': 'generate-live-summary',
  'summary': 'generate-live-summary',
  'generate questions': 'generate-questions',
  'questions': 'generate-questions',
  'match reviews': 'match-peer-reviews',
  'peer review': 'match-peer-reviews',

  // Timer
  'start timer': 'start-session-timer',
  'pause timer': 'pause-timer',
  'resume timer': 'resume-timer',
  'stop timer': 'stop-timer',

  // Breakout
  'create groups': 'create-breakout-groups',
  'dissolve groups': 'dissolve-breakout-groups',

  // Integration
  'push to canvas': 'push-to-canvas',
  'import': 'import-external-course',
  'sync materials': 'sync-all-materials',
  'sync roster': 'sync-roster',

  // General
  'save': 'btn-save',
  'cancel': 'btn-cancel',
  'confirm': 'btn-confirm',
  'submit': 'submit-post',
  'refresh': 'refresh',
  'generate report': 'generate-report',
};

const INPUT_ALIASES: Record<string, string> = {
  'title': 'course-title',
  'course title': 'course-title',
  'name': 'course-title',
  'syllabus': 'syllabus',
  'objectives': 'learning-objectives',
  'learning objectives': 'learning-objectives',
  'poll question': 'poll-question',
  'question': 'poll-question',
  'case': 'case-prompt',
  'case prompt': 'case-prompt',
  'post': 'textarea-post-content',
  'content': 'textarea-post-content',
  'timer': 'timer-duration-minutes',
  'duration': 'timer-duration-minutes',
  'groups': 'num-breakout-groups',
  'number of groups': 'num-breakout-groups',
  'comments': 'peer-review-comments',
  'feedback': 'peer-review-comments',
};

const DROPDOWN_ALIASES: Record<string, string> = {
  'course': 'select-course',
  'session': 'select-session',
  'student': 'select-student',
  'canvas': 'select-canvas-connection',
  'provider': 'select-integration-provider',
  'connection': 'select-provider-connection',
  'external course': 'select-external-course',
  'target course': 'select-target-course',
  'target session': 'select-target-session',
};

// =============================================================================
// SMART RESOLVER - Finds DOM elements from natural language
// =============================================================================

/**
 * Resolve a natural language target to a DOM element.
 * Uses multiple strategies: aliases, direct match, partial match, text content.
 */
export function resolveTarget(
  target: string,
  elementType: 'tab' | 'button' | 'input' | 'dropdown'
): HTMLElement | null {
  if (typeof window === 'undefined') return null;

  const normalized = target.toLowerCase().trim();
  const hyphenated = normalized.replace(/\s+/g, '-');

  // Get the appropriate alias map
  const aliasMap = {
    tab: TAB_ALIASES,
    button: BUTTON_ALIASES,
    input: INPUT_ALIASES,
    dropdown: DROPDOWN_ALIASES,
  }[elementType];

  // Strategy 1: Check alias map first
  const aliasId = aliasMap[normalized];
  if (aliasId) {
    const el = document.querySelector(`[data-voice-id="${aliasId}"]`);
    if (el) return el as HTMLElement;
  }

  // Strategy 2: Direct voice-id match (hyphenated)
  let el = document.querySelector(`[data-voice-id="${hyphenated}"]`);
  if (el) return el as HTMLElement;

  // Strategy 3: Direct voice-id match with prefix
  const prefix = elementType === 'tab' ? 'tab-' :
                 elementType === 'dropdown' ? 'select-' : '';
  if (prefix) {
    el = document.querySelector(`[data-voice-id="${prefix}${hyphenated}"]`);
    if (el) return el as HTMLElement;
  }

  // Strategy 4: Partial match in voice-id
  el = document.querySelector(`[data-voice-id*="${hyphenated}"]`);
  if (el) return el as HTMLElement;

  // Strategy 5: Text content match
  const selector = elementType === 'tab'
    ? '[data-voice-id^="tab-"], [role="tab"]'
    : elementType === 'button'
    ? '[data-voice-id], button:not([disabled])'
    : elementType === 'input'
    ? 'input[data-voice-id], textarea[data-voice-id]'
    : 'select[data-voice-id], [data-voice-id^="select-"]';

  const candidates = document.querySelectorAll(selector);
  for (const candidate of candidates) {
    const text = candidate.textContent?.toLowerCase() || '';
    const label = candidate.getAttribute('aria-label')?.toLowerCase() || '';
    const placeholder = (candidate as HTMLInputElement).placeholder?.toLowerCase() || '';

    if (text.includes(normalized) || label.includes(normalized) || placeholder.includes(normalized)) {
      return candidate as HTMLElement;
    }
  }

  // Strategy 6: Fuzzy match - check if target words appear in voice-id
  const targetWords = normalized.split(/\s+/);
  const allVoiceElements = document.querySelectorAll('[data-voice-id]');
  for (const elem of allVoiceElements) {
    const voiceId = elem.getAttribute('data-voice-id')?.toLowerCase() || '';
    if (targetWords.every(word => voiceId.includes(word))) {
      return elem as HTMLElement;
    }
  }

  return null;
}

/**
 * Parse ordinal strings to index numbers
 */
function parseOrdinal(selection: string): number | null {
  const ordinals: Record<string, number> = {
    'first': 0, 'primero': 0, 'primera': 0, '1st': 0,
    'second': 1, 'segundo': 1, 'segunda': 1, '2nd': 1,
    'third': 2, 'tercero': 2, 'tercera': 2, '3rd': 2,
    'fourth': 3, 'cuarto': 3, 'cuarta': 3, '4th': 3,
    'fifth': 4, 'quinto': 4, 'quinta': 4, '5th': 4,
    'last': -1, 'último': -1, 'última': -1,
  };

  const normalized = selection.toLowerCase().trim();
  if (normalized in ordinals) {
    return ordinals[normalized];
  }

  // Try parsing as number
  const num = parseInt(normalized, 10);
  if (!isNaN(num)) {
    return num - 1; // Convert to 0-based index
  }

  return null;
}

// =============================================================================
// IDEMPOTENCY
// =============================================================================

const idempotencyCache = new Map<string, { result: ActionResult; timestamp: number }>();
const IDEMPOTENCY_TTL_MS = 5000;

function checkIdempotency(key: string): ActionResult | null {
  const cached = idempotencyCache.get(key);
  if (cached && Date.now() - cached.timestamp < IDEMPOTENCY_TTL_MS) {
    console.log(`[ActionRegistry] Idempotency hit: ${key}`);
    return cached.result;
  }
  return null;
}

function recordIdempotency(key: string, result: ActionResult): void {
  idempotencyCache.set(key, { result, timestamp: Date.now() });

  // Cleanup old entries
  const now = Date.now();
  for (const [k, v] of idempotencyCache.entries()) {
    if (now - v.timestamp > IDEMPOTENCY_TTL_MS * 2) {
      idempotencyCache.delete(k);
    }
  }
}

// =============================================================================
// CLIENT TOOL HANDLERS
// =============================================================================

/**
 * Navigate to a page
 */
export async function navigate(
  page: string,
  ctx: ActionContext
): Promise<ActionResult> {
  const cacheKey = `navigate:${page}`;
  const cached = checkIdempotency(cacheKey);
  if (cached) return cached;

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
      hint: ctx.locale === 'es'
        ? `No conozco esa página. Páginas disponibles: ${Object.keys(routeMap).join(', ')}.`
        : `I don't recognize that page. Available: ${Object.keys(routeMap).join(', ')}.`,
    };
  }

  ctx.router.push(route);
  const pageName = page.charAt(0).toUpperCase() + page.slice(1);

  const result: ActionResult = {
    ok: true,
    did: `navigated to ${pageName}`,
    hint: ctx.locale === 'es' ? `Llevándote a ${pageName}.` : `Taking you to ${pageName}.`,
  };

  recordIdempotency(cacheKey, result);
  return result;
}

/**
 * Switch to a tab using natural language target
 */
export async function switchTab(
  target: string,
  ctx: ActionContext
): Promise<ActionResult> {
  const cacheKey = `switchTab:${target}`;
  const cached = checkIdempotency(cacheKey);
  if (cached) return cached;

  const tab = resolveTarget(target, 'tab');

  if (tab) {
    // Dispatch event for tab switching
    const voiceId = tab.getAttribute('data-voice-id') || target;
    window.dispatchEvent(new CustomEvent('voice-select-tab', {
      detail: { voiceId, tabName: voiceId },
    }));

    // Also try clicking if it's a tab element
    if (tab.getAttribute('role') === 'tab') {
      tab.click();
    }

    const result: ActionResult = {
      ok: true,
      did: `switched to ${target} tab`,
      hint: ctx.locale === 'es'
        ? `Cambiando a la pestaña ${target}.`
        : `Switching to ${target} tab.`,
    };

    recordIdempotency(cacheKey, result);
    return result;
  }

  return {
    ok: false,
    did: 'tab switch failed',
    error: `Tab not found: ${target}`,
    hint: ctx.locale === 'es'
      ? `No pude encontrar esa pestaña. Intenta con otro nombre.`
      : `I couldn't find that tab. Try a different name.`,
  };
}

/**
 * Click a button using natural language target
 */
export async function clickButton(
  target: string,
  ctx: ActionContext
): Promise<ActionResult> {
  const cacheKey = `clickButton:${target}`;
  const cached = checkIdempotency(cacheKey);
  if (cached) return cached;

  const button = resolveTarget(target, 'button');

  if (button) {
    button.click();

    const result: ActionResult = {
      ok: true,
      did: `clicked ${target}`,
      hint: ctx.locale === 'es'
        ? `Haciendo clic en ${target}.`
        : `Clicking ${target}.`,
    };

    recordIdempotency(cacheKey, result);
    return result;
  }

  return {
    ok: false,
    did: 'button click failed',
    error: `Button not found: ${target}`,
    hint: ctx.locale === 'es'
      ? `No pude encontrar ese botón.`
      : `I couldn't find that button.`,
  };
}

/**
 * Fill an input field using natural language target
 */
export async function fillInput(
  target: string,
  content: string,
  ctx: ActionContext
): Promise<ActionResult> {
  const field = resolveTarget(target, 'input') as HTMLInputElement | HTMLTextAreaElement | null;

  if (field) {
    field.value = content;
    field.dispatchEvent(new Event('input', { bubbles: true }));
    field.dispatchEvent(new Event('change', { bubbles: true }));

    return {
      ok: true,
      did: `filled ${target}`,
      hint: ctx.locale === 'es' ? `Campo completado.` : `Field filled.`,
    };
  }

  return {
    ok: false,
    did: 'input fill failed',
    error: `Input not found: ${target}`,
    hint: ctx.locale === 'es'
      ? `No pude encontrar ese campo.`
      : `I couldn't find that field.`,
  };
}

/**
 * Select an item from a dropdown using natural language
 */
export async function selectItem(
  target: string,
  selection: string,
  ctx: ActionContext
): Promise<ActionResult> {
  // First try to find the dropdown
  const dropdown = resolveTarget(target, 'dropdown');

  // Parse selection - could be ordinal ("first") or text ("Statistics 101")
  const ordinalIndex = parseOrdinal(selection);

  // Dispatch event for custom dropdown handlers
  window.dispatchEvent(new CustomEvent('voice-select-dropdown', {
    detail: {
      voiceId: dropdown?.getAttribute('data-voice-id') || target.toLowerCase().replace(/\s+/g, '-'),
      selectionIndex: ordinalIndex,
      selectionText: ordinalIndex === null ? selection : undefined,
    },
  }));

  // If it's a native select element, handle directly
  if (dropdown && dropdown.tagName === 'SELECT') {
    const selectEl = dropdown as HTMLSelectElement;
    const options = Array.from(selectEl.options);

    let optionIndex = ordinalIndex;
    if (optionIndex === null) {
      // Find by text match
      optionIndex = options.findIndex(opt =>
        opt.text.toLowerCase().includes(selection.toLowerCase())
      );
    } else if (optionIndex === -1) {
      // "last" → get last index
      optionIndex = options.length - 1;
    }

    if (optionIndex >= 0 && optionIndex < options.length) {
      selectEl.selectedIndex = optionIndex;
      selectEl.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }

  return {
    ok: true,
    did: `selected ${selection}`,
    hint: ctx.locale === 'es'
      ? `Seleccionando ${selection}.`
      : `Selecting ${selection}.`,
  };
}

/**
 * Get current page info for ElevenLabs to understand what's available
 */
export function getPageInfo(): {
  route: string;
  activeTab?: string;
  tabs: string[];
  buttons: string[];
  inputs: string[];
  dropdowns: string[];
} {
  if (typeof window === 'undefined') {
    return { route: '/', tabs: [], buttons: [], inputs: [], dropdowns: [] };
  }

  const info = {
    route: window.location.pathname,
    activeTab: undefined as string | undefined,
    tabs: [] as string[],
    buttons: [] as string[],
    inputs: [] as string[],
    dropdowns: [] as string[],
  };

  // Collect tabs
  document.querySelectorAll('[data-voice-id^="tab-"], [role="tab"]').forEach(tab => {
    const id = tab.getAttribute('data-voice-id');
    const text = tab.textContent?.trim();
    const isActive = tab.getAttribute('aria-selected') === 'true' ||
                     tab.getAttribute('data-state') === 'active';

    const label = id?.replace('tab-', '') || text || '';
    if (label && label.length < 30) {
      info.tabs.push(label);
      if (isActive) info.activeTab = label;
    }
  });

  // Collect buttons (limit to 15)
  document.querySelectorAll('[data-voice-id]:not([data-voice-id^="tab-"]):not([data-voice-id^="select-"])').forEach(btn => {
    if (info.buttons.length >= 15) return;
    const id = btn.getAttribute('data-voice-id');
    const text = btn.textContent?.trim();
    const label = id || text || '';
    if (label && label.length < 30 && !label.includes('\n')) {
      info.buttons.push(label);
    }
  });

  // Collect inputs
  document.querySelectorAll('input[data-voice-id], textarea[data-voice-id]').forEach(input => {
    const id = input.getAttribute('data-voice-id');
    const placeholder = (input as HTMLInputElement).placeholder;
    info.inputs.push(id || placeholder || 'input');
  });

  // Collect dropdowns
  document.querySelectorAll('[data-voice-id^="select-"], select[data-voice-id]').forEach(dd => {
    const id = dd.getAttribute('data-voice-id');
    info.dropdowns.push(id?.replace('select-', '') || 'dropdown');
  });

  // Deduplicate
  info.tabs = [...new Set(info.tabs)];
  info.buttons = [...new Set(info.buttons)];
  info.inputs = [...new Set(info.inputs)];
  info.dropdowns = [...new Set(info.dropdowns)];

  return info;
}

// =============================================================================
// HIGH-RISK ACTION CHECKS
// =============================================================================

const HIGH_RISK_KEYWORDS = [
  'delete', 'remove', 'end', 'stop', 'publish', 'send', 'submit',
  'eliminar', 'borrar', 'terminar', 'publicar', 'enviar',
];

/**
 * Check if a target indicates a high-risk action
 */
export function isHighRiskAction(target: string): boolean {
  const normalized = target.toLowerCase();
  return HIGH_RISK_KEYWORDS.some(keyword => normalized.includes(keyword));
}

// =============================================================================
// LEGACY SUPPORT - run_ui_action for backward compatibility
// =============================================================================

export async function run_ui_action(
  actionId: string,
  args: Record<string, unknown>,
  ctx: ActionContext
): Promise<ActionResult> {
  console.log(`[ActionRegistry] run_ui_action: ${actionId}`, args);

  // Map legacy action IDs to new handlers
  if (actionId === 'NAVIGATE' || actionId.startsWith('NAV_')) {
    const page = args.page as string || actionId.replace('NAV_', '').toLowerCase();
    return navigate(page, ctx);
  }

  if (actionId === 'SWITCH_TAB' || actionId.startsWith('SWITCH_TAB_')) {
    const target = args.tab_voice_id as string || args.target as string ||
                   actionId.replace('SWITCH_TAB_', '').toLowerCase().replace(/_/g, ' ');
    return switchTab(target, ctx);
  }

  if (actionId === 'CLICK_BUTTON') {
    const target = args.button_voice_id as string || args.target as string;
    return clickButton(target, ctx);
  }

  if (actionId === 'FILL_INPUT') {
    const target = args.field_voice_id as string || args.target as string;
    const content = args.content as string;
    return fillInput(target, content, ctx);
  }

  if (actionId === 'SELECT_DROPDOWN' || actionId === 'SELECT_ITEM') {
    const target = args.dropdown_voice_id as string || args.target as string;
    const selection = args.selection_text as string || args.selection as string ||
                      (args.selection_index !== undefined ? String(args.selection_index) : 'first');
    return selectItem(target, selection, ctx);
  }

  if (actionId === 'CONFIRM') {
    // Find and click confirm button
    const btn = document.querySelector('[data-voice-id*="confirm"], button:contains("Confirm"), button:contains("Yes")') as HTMLElement;
    if (btn) btn.click();
    return { ok: true, did: 'confirmed', hint: ctx.locale === 'es' ? 'Confirmado.' : 'Confirmed.' };
  }

  if (actionId === 'CANCEL') {
    const btn = document.querySelector('[data-voice-id*="cancel"], button:contains("Cancel"), button:contains("No")') as HTMLElement;
    if (btn) btn.click();
    return { ok: true, did: 'cancelled', hint: ctx.locale === 'es' ? 'Cancelado.' : 'Cancelled.' };
  }

  return {
    ok: false,
    did: 'unknown action',
    error: `Unknown action: ${actionId}`,
  };
}

// =============================================================================
// EXPORTS
// =============================================================================

export type { ActionResult, ActionContext };
