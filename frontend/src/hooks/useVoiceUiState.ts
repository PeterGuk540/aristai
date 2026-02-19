/**
 * useVoiceUiState Hook
 *
 * This hook provides:
 * 1. Periodic UI state synchronization to backend
 * 2. Voice command processing through v2 API
 * 3. Action result handling with verification
 */

import { useEffect, useCallback, useRef } from 'react';
import { usePathname } from 'next/navigation';
import { getCompactUiState, UiState } from '@/lib/voice-ui-state';
import { API_BASE } from '@/lib/api';

// ============================================================================
// CONFIGURATION
// ============================================================================

const UI_STATE_SYNC_INTERVAL = 5000; // Sync every 5 seconds
const UI_STATE_CHANGE_DEBOUNCE = 500; // Debounce rapid changes

// ============================================================================
// API CALLS
// ============================================================================

async function syncUiState(userId: number, uiState: ReturnType<typeof getCompactUiState>): Promise<void> {
  try {
    await fetch(`${API_BASE}/voice/v2/ui-state`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
        ui_state: uiState,
      }),
    });
  } catch (error) {
    console.error('Failed to sync UI state:', error);
  }
}

export interface ProcessVoiceResponse {
  success: boolean;
  spoken_response: string;
  ui_action?: {
    type: string;
    payload: Record<string, unknown>;
  };
  tool_used?: string;
  confidence: number;
  needs_confirmation: boolean;
  confirmation_context?: Record<string, unknown>;
}

async function processVoiceCommand(
  userId: number,
  transcript: string,
  language: string,
  conversationState: string,
  activeCourse?: string,
  activeSession?: string,
): Promise<ProcessVoiceResponse> {
  const uiState = getCompactUiState();

  const response = await fetch(`${API_BASE}/voice/v2/process`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      transcript,
      language,
      ui_state: uiState,
      conversation_state: conversationState,
      active_course_name: activeCourse,
      active_session_name: activeSession,
    }),
  });

  if (!response.ok) {
    throw new Error(`Voice processing failed: ${response.statusText}`);
  }

  return response.json();
}

// ============================================================================
// HOOK
// ============================================================================

interface UseVoiceUiStateOptions {
  userId?: number;
  enabled?: boolean;
  onUiAction?: (action: { type: string; payload: Record<string, unknown> }) => void;
}

export function useVoiceUiState(options: UseVoiceUiStateOptions = {}) {
  const { userId, enabled = true, onUiAction } = options;
  const pathname = usePathname();
  const lastSyncRef = useRef<string>('');
  const syncTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Sync UI state to backend
  const syncState = useCallback(async () => {
    if (!userId || !enabled) return;

    const uiState = getCompactUiState();
    const stateJson = JSON.stringify(uiState);

    // Only sync if state changed
    if (stateJson !== lastSyncRef.current) {
      lastSyncRef.current = stateJson;
      await syncUiState(userId, uiState);
    }
  }, [userId, enabled]);

  // Process voice command
  const processCommand = useCallback(async (
    transcript: string,
    language: string = 'en',
    conversationState: string = 'idle',
    activeCourse?: string,
    activeSession?: string,
  ): Promise<ProcessVoiceResponse> => {
    if (!userId) {
      throw new Error('User ID required');
    }

    const result = await processVoiceCommand(
      userId,
      transcript,
      language,
      conversationState,
      activeCourse,
      activeSession,
    );

    // Execute UI action if present
    if (result.ui_action && onUiAction) {
      onUiAction(result.ui_action);
    }

    // Also dispatch as CustomEvent for VoiceUIController
    if (result.ui_action) {
      window.dispatchEvent(new CustomEvent(result.ui_action.type, {
        detail: result.ui_action.payload,
      }));
    }

    return result;
  }, [userId, onUiAction]);

  // Periodic sync
  useEffect(() => {
    if (!userId || !enabled) return;

    // Initial sync
    syncState();

    // Periodic sync
    const intervalId = setInterval(syncState, UI_STATE_SYNC_INTERVAL);

    return () => {
      clearInterval(intervalId);
    };
  }, [userId, enabled, syncState]);

  // Sync on route change
  useEffect(() => {
    if (!userId || !enabled) return;

    // Debounce sync on route change
    if (syncTimeoutRef.current) {
      clearTimeout(syncTimeoutRef.current);
    }

    syncTimeoutRef.current = setTimeout(() => {
      syncState();
    }, UI_STATE_CHANGE_DEBOUNCE);

    return () => {
      if (syncTimeoutRef.current) {
        clearTimeout(syncTimeoutRef.current);
      }
    };
  }, [pathname, userId, enabled, syncState]);

  // Sync on visibility change (when user returns to tab)
  useEffect(() => {
    if (!userId || !enabled) return;

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        syncState();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [userId, enabled, syncState]);

  return {
    syncState,
    processCommand,
    getUiState: getCompactUiState,
  };
}

export default useVoiceUiState;
