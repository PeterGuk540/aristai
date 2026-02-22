/**
 * Voice Tab Handler - Shared utility for voice-controlled tab switching
 *
 * This utility provides a consistent way to handle voice tab switching events
 * across all pages with tabs. It uses DYNAMIC DISCOVERY with fuzzy matching
 * to find the best matching tab, reducing reliance on hardcoded mappings.
 */

/**
 * Calculate similarity between two strings (0-1 score)
 */
function calculateTabSimilarity(input: string, tabId: string): number {
  const s1 = input.toLowerCase().replace(/[-_\s]/g, '');
  const s2 = tabId.toLowerCase().replace(/[-_\s]/g, '');

  // Exact match
  if (s1 === s2) return 1.0;

  // One contains the other
  if (s1.includes(s2) || s2.includes(s1)) return 0.9;

  // Prefix match
  const minLen = Math.min(s1.length, s2.length);
  let prefixMatch = 0;
  for (let i = 0; i < minLen; i++) {
    if (s1[i] === s2[i]) prefixMatch++;
    else break;
  }
  if (prefixMatch >= 3) {
    return 0.5 + (0.4 * prefixMatch / Math.max(s1.length, s2.length));
  }

  return 0;
}

/**
 * Find the best matching tab from available tabs using fuzzy matching
 */
function findBestTabMatch(
  input: string,
  availableTabs: string[]
): string | null {
  const normalizedInput = input.toLowerCase().replace(/[-_\s]/g, '');
  let bestMatch: { tab: string; score: number } | null = null;

  for (const tab of availableTabs) {
    const score = calculateTabSimilarity(normalizedInput, tab);
    if (score > 0.5 && (!bestMatch || score > bestMatch.score)) {
      bestMatch = { tab, score };
    }
  }

  return bestMatch?.tab || null;
}

/**
 * Creates a voice tab handler with dynamic discovery and optional mappings
 * @param pageTabMap - Page-specific tab name mappings (used as hints, not requirements)
 * @param setActiveTab - State setter for the active tab
 * @param pageName - Name of the page (for logging)
 * @returns Event handler function for voice tab events
 */
export function createVoiceTabHandler(
  pageTabMap: Record<string, string>,
  setActiveTab: (tab: string) => void,
  pageName: string
): (event: CustomEvent) => void {
  // Extract available tabs from the mapping for fuzzy matching
  const availableTabIds = [...new Set(Object.values(pageTabMap))];

  return (event: CustomEvent) => {
    const { tab, tabName } = event.detail || {};
    const rawTab = tab || tabName;

    if (!rawTab) return;

    // Normalize: remove hyphens, spaces, lowercase
    const normalizedTab = String(rawTab).toLowerCase().replace(/[-\s]/g, '');
    console.log(`🎤 ${pageName}: Voice tab switch request:`, rawTab, '→', normalizedTab);

    // Strategy 1: Try exact mapping first
    let targetTab = pageTabMap[normalizedTab];

    // Strategy 2: If no exact match, use fuzzy matching against available tabs
    if (!targetTab) {
      targetTab = findBestTabMatch(normalizedTab, availableTabIds) || undefined;
      if (targetTab) {
        console.log(`🎤 ${pageName}: Fuzzy matched to tab:`, targetTab);
      }
    }

    // Strategy 3: Fall back to raw tab name (let React handle it)
    if (!targetTab) {
      targetTab = rawTab;
      console.log(`🎤 ${pageName}: Using raw tab name:`, targetTab);
    }

    console.log(`🎤 ${pageName}: Switching to tab:`, targetTab);
    setActiveTab(targetTab);
  };
}

/**
 * Sets up voice tab event listeners (both ui.switchTab and voice-select-tab)
 * @param handler - The event handler created by createVoiceTabHandler
 * @returns Cleanup function to remove listeners
 */
export function setupVoiceTabListeners(
  handler: (event: CustomEvent) => void
): () => void {
  window.addEventListener('ui.switchTab', handler as EventListener);
  window.addEventListener('voice-select-tab', handler as EventListener);

  return () => {
    window.removeEventListener('ui.switchTab', handler as EventListener);
    window.removeEventListener('voice-select-tab', handler as EventListener);
  };
}

// Common tab name normalizations shared across pages
export const COMMON_TAB_MAPPINGS: Record<string, string> = {
  // AI-related
  'aifeatures': 'ai-features',
  'aifeature': 'ai-features',
  'aitools': 'ai-features',
  'enhancedfeatures': 'ai-features',
  'enhancedai': 'ai-features',
  'aiinsights': 'ai-insights',
  'aiinsight': 'ai-insights',
  'aianalytics': 'ai-insights',
  'aicopilot': 'copilot',
  'aiassistant': 'copilot',

  // Common tabs
  'materials': 'materials',
  'material': 'materials',
  'coursematerials': 'materials',
  'sessionmaterials': 'materials',
  'files': 'materials',
  'documents': 'materials',

  // Insights/Analytics
  'insights': 'insights',
  'insight': 'insights',
  'sessioninsights': 'insights',
  'analytics': 'analytics',
  'sessionanalytics': 'insights',
  'engagement': 'insights',

  // Participation
  'participation': 'participation',
  'participationinsights': 'participation',

  // Polls
  'polls': 'polls',
  'poll': 'polls',
  'polling': 'polls',

  // Cases
  'cases': 'cases',
  'case': 'cases',
  'casestudy': 'cases',
  'casestudies': 'cases',
  'postcase': 'cases',
};

/**
 * Creates a merged tab map by combining common mappings with page-specific ones
 * @param pageSpecific - Page-specific tab mappings (take precedence)
 * @returns Merged tab mapping
 */
export function mergeTabMappings(
  pageSpecific: Record<string, string>
): Record<string, string> {
  return { ...COMMON_TAB_MAPPINGS, ...pageSpecific };
}
