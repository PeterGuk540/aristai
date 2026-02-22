import { useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { API_BASE } from './api';
import { getIdToken } from './cognito-auth';
import { getGoogleIdToken } from './google-auth';
import { getMicrosoftIdToken } from './ms-auth';

export type UiAction = {
  type: 'ui.navigate' | 'ui.openTab' | 'ui.openModal' | 'ui.toast' | string;
  payload: Record<string, any>;
  correlation_id?: string;
  created_at?: number;
};

const getAuthToken = async (): Promise<string | null> => {
  const googleToken = getGoogleIdToken();
  const msToken = getMicrosoftIdToken();
  const idToken = googleToken || msToken || await getIdToken();
  return idToken || null;
};

export const executeUiAction = (action: UiAction, router: ReturnType<typeof useRouter>) => {
  const { type, payload } = action;
  console.log('🔧 executeUiAction called:', { type, payload });

  switch (type) {
    case 'ui.navigate':
      if (payload?.path) {
        console.log('🧭 Navigating to:', payload.path);
        try {
          router.push(payload.path);
          console.log('✅ router.push called successfully');
        } catch (navError) {
          console.error('❌ router.push failed, using window.location:', navError);
          // Fallback to window.location if router fails
          window.location.href = payload.path;
        }
      } else {
        console.warn('⚠️ ui.navigate called without path');
      }
      break;
    case 'ui.openTab':
      if (payload?.url) {
        window.open(payload.url, payload.target || '_blank', 'noopener,noreferrer');
      }
      break;
    case 'ui.openModal':
      window.dispatchEvent(new CustomEvent('ui.openModal', { detail: payload }));
      break;
    case 'ui.toast':
      window.dispatchEvent(new CustomEvent('ui.toast', { detail: payload }));
      if (payload?.message) {
        console.info('UI Toast:', payload.message);
      }
      break;
    // New UI element interaction actions - handled by VoiceUIController
    case 'ui.selectDropdown':
      console.log('🎤 Dispatching selectDropdown:', payload);
      window.dispatchEvent(new CustomEvent('ui.selectDropdown', { detail: payload }));
      break;
    case 'ui.expandDropdown':
      console.log('🎤 Dispatching expandDropdown:', payload);
      window.dispatchEvent(new CustomEvent('ui.expandDropdown', { detail: payload }));
      break;
    case 'ui.clickButton':
      console.log('🎤 Dispatching clickButton:', payload);
      window.dispatchEvent(new CustomEvent('ui.clickButton', { detail: payload }));
      break;
    case 'ui.switchTab':
      console.log('🎤 Dispatching switchTab:', payload);
      window.dispatchEvent(new CustomEvent('ui.switchTab', { detail: payload }));
      break;
    case 'ui.fillInput':
      console.log('🎤 Dispatching fillInput:', payload);
      window.dispatchEvent(new CustomEvent('ui.fillInput', { detail: payload }));
      break;
    case 'ui.selectListItem':
      console.log('🎤 Dispatching selectListItem:', payload);
      window.dispatchEvent(new CustomEvent('ui.selectListItem', { detail: payload }));
      break;
    case 'ui.openMenuAndClick':
      console.log('🎤 Dispatching openMenuAndClick:', payload);
      window.dispatchEvent(new CustomEvent('ui.openMenuAndClick', { detail: payload }));
      break;
    case 'voice-menu-action':
      console.log('🎤 Dispatching voice-menu-action:', payload);
      window.dispatchEvent(new CustomEvent('voice-menu-action', { detail: payload }));
      break;
    case 'voice.alert':
      // Proactive voice alert from backend (e.g., copilot alerts)
      console.log('🔔 Voice alert received:', payload);
      window.dispatchEvent(new CustomEvent('voice.alert', { detail: payload }));
      // Also show a toast notification for visibility
      if (payload?.message) {
        window.dispatchEvent(new CustomEvent('ui.toast', {
          detail: {
            message: payload.message,
            type: payload.alert_type || 'info',
            duration: 8000, // Longer duration for alerts
          }
        }));
      }
      break;
    case 'ui.workflow':
      // Handle workflow directly to avoid component remount issues
      // When we navigate, VoiceUIController remounts and loses event listeners
      console.log('🔄 Executing workflow:', payload);
      executeWorkflow(payload, router);
      break;
    default:
      // For any unknown action types, try dispatching as a custom event
      if (type.startsWith('ui.')) {
        console.log('🎤 Dispatching custom UI action:', type, payload);
        window.dispatchEvent(new CustomEvent(type, { detail: payload }));
      } else {
        console.info('Unhandled UI action', action);
      }
  }
};

/**
 * Execute a multi-step workflow directly.
 *
 * KEY INSIGHT: When navigating to a new page AND switching tabs,
 * we combine them into a single navigation with ?tab= parameter.
 * This is more reliable than event dispatching after navigation,
 * and doesn't require hardcoded tab mappings in each page.
 *
 * Pages already handle tab switching via URL params:
 *   const tabFromUrl = searchParams?.get('tab');
 *   if (tabFromUrl) setActiveTab(tabFromUrl);
 */
const executeWorkflow = (
  payload: { workflow?: string; steps?: Array<{ type: string; payload: Record<string, any>; waitForLoad?: boolean }> },
  router: ReturnType<typeof useRouter>
) => {
  const { workflow, steps } = payload;
  console.log('🔄 executeWorkflow:', { workflow, stepCount: steps?.length });

  if (!steps || !Array.isArray(steps) || steps.length === 0) {
    console.warn('⚠️ No workflow steps provided');
    return;
  }

  // OPTIMIZATION: If workflow has navigate + switchTab, combine into single URL with ?tab=
  // This is more reliable than dispatching events after navigation
  if (steps.length >= 2) {
    const navigateStep = steps.find(s => s.type === 'ui.navigate');
    const switchTabStep = steps.find(s => s.type === 'ui.switchTab');

    if (navigateStep && switchTabStep) {
      const path = navigateStep.payload?.path;
      const tabName = switchTabStep.payload?.tabName || switchTabStep.payload?.voiceId || '';
      // Extract actual tab value (e.g., "tab-ai-features" -> "ai-features")
      const tabValue = tabName.toLowerCase().replace(/^tab-/, '');

      if (path && tabValue) {
        // Combine into single navigation with tab parameter
        const urlWithTab = `${path}?tab=${tabValue}`;
        console.log('🧭 Workflow: Combined navigation with tab:', urlWithTab);
        router.push(urlWithTab);
        console.log('✅ Workflow completed:', workflow);
        return;
      }
    }
  }

  // Fallback: Process steps sequentially (for other workflow types)
  let currentStepIndex = 0;

  const executeNextStep = () => {
    if (currentStepIndex >= steps.length) {
      console.log('✅ Workflow completed:', workflow);
      return;
    }

    const step = steps[currentStepIndex];
    console.log(`📍 Executing step ${currentStepIndex + 1}/${steps.length}:`, step.type, step.payload);

    if (step.type === 'ui.navigate') {
      const path = step.payload?.path;
      if (path) {
        console.log('🧭 Workflow: Navigating to:', path);
        router.push(path);
        currentStepIndex++;
        setTimeout(executeNextStep, 800);
      } else {
        console.warn('⚠️ ui.navigate step missing path');
        currentStepIndex++;
        executeNextStep();
      }
    } else if (step.type === 'ui.switchTab') {
      const tabName = step.payload?.tabName || step.payload?.voiceId || '';
      const tabValue = tabName.toLowerCase().replace(/^tab-/, '');
      console.log('📑 Workflow: Switching to tab:', tabValue);

      // Dispatch ui.switchTab for VoiceUIController
      window.dispatchEvent(new CustomEvent('ui.switchTab', {
        detail: { ...step.payload, tabName: tabValue, voiceId: `tab-${tabValue}` }
      }));

      currentStepIndex++;
      setTimeout(executeNextStep, 300);
    } else {
      console.log('🎤 Workflow: Dispatching', step.type);
      window.dispatchEvent(new CustomEvent(step.type, { detail: step.payload }));
      currentStepIndex++;
      setTimeout(executeNextStep, 100);
    }
  };

  executeNextStep();
}

export const useUiActionStream = (
  userId: number | undefined,
  onStatusChange?: (connected: boolean) => void
) => {
  const router = useRouter();
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    let isMounted = true;

    const connect = async () => {
      if (!userId) {
        return;
      }
      const token = await getAuthToken();
      if (!token || !isMounted) {
        return;
      }
      const url = `${API_BASE}/ui-actions/stream?user_id=${userId}&token=${encodeURIComponent(token)}`;
      const source = new EventSource(url);
      eventSourceRef.current = source;

      source.onopen = () => {
        onStatusChange?.(true);
      };

      source.onmessage = (event) => {
        if (!event.data) return;
        try {
          const action = JSON.parse(event.data) as UiAction;
          if (action.type === 'heartbeat') {
            return;
          }
          executeUiAction(action, router);
        } catch (error) {
          console.warn('Failed to parse UI action', error);
        }
      };

      source.onerror = () => {
        onStatusChange?.(false);
      };
    };

    connect();

    return () => {
      isMounted = false;
      onStatusChange?.(false);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [onStatusChange, router, userId]);
};
