/**
 * Voice Tab Handler - Shared utility for voice-controlled tab switching
 *
 * This utility provides a consistent way to handle voice tab switching events
 * across all pages with tabs. It normalizes tab names from voice commands
 * (which may include spaces, hyphens, or other variations) to the actual
 * tab IDs used in the UI components.
 */

/**
 * Creates a voice tab handler with custom tab mappings for a specific page
 * @param pageTabMap - Page-specific tab name mappings
 * @param setActiveTab - State setter for the active tab
 * @param pageName - Name of the page (for logging)
 * @returns Event handler function for voice tab events
 */
export function createVoiceTabHandler(
  pageTabMap: Record<string, string>,
  setActiveTab: (tab: string) => void,
  pageName: string
): (event: CustomEvent) => void {
  return (event: CustomEvent) => {
    const { tab, tabName } = event.detail || {};
    const rawTab = tab || tabName;

    if (!rawTab) return;

    // Normalize: remove hyphens, spaces, lowercase
    const normalizedTab = String(rawTab).toLowerCase().replace(/[-\s]/g, '');
    console.log(`🎤 ${pageName}: Voice tab switch request:`, rawTab, '→', normalizedTab);

    // Try page-specific mapping first, then fall back to the raw tab name
    const targetTab = pageTabMap[normalizedTab] || rawTab;
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
