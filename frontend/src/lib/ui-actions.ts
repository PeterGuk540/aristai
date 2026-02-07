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
