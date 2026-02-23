'use client';

/**
 * ConversationalVoiceV2 - ElevenLabs Client Tools Architecture
 *
 * This component uses ElevenLabs as the "brain" with Client Tools for UI actions.
 * Key differences from V1:
 * - NO SPEAK: prefix mechanism
 * - NO volume muting
 * - NO state machine for response gating
 * - ElevenLabs handles all conversation logic
 * - Client Tools execute UI actions directly
 *
 * Architecture:
 * 1. User speaks → ElevenLabs transcribes and decides action
 * 2. ElevenLabs calls Client Tool (e.g., navigate, switch_tab)
 * 3. Client Tool handler executes via Action Registry
 * 4. Handler returns result → ElevenLabs speaks response
 */

import { useEffect, useState, useRef, useCallback } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { Conversation } from '@elevenlabs/client';
import { Volume2, Mic, MicOff, Settings, Minimize2, Maximize2, Sparkles, Globe } from 'lucide-react';
import { useUser } from '@/lib/context';
import { useLanguage } from '@/lib/i18n-provider';
import { cn } from '@/lib/utils';
import {
  run_ui_action,
  ActionContext,
  ActionResult,
  getAvailableActions,
  requiresConfirmation,
} from '@/lib/action-registry';

// =============================================================================
// TYPES
// =============================================================================

export type ConversationState =
  | 'initializing'
  | 'connecting'
  | 'connected'
  | 'listening'
  | 'processing'
  | 'speaking'
  | 'disconnected'
  | 'error';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  action?: {
    type: string;
    result?: ActionResult;
  };
}

interface ConversationalVoiceProps {
  onNavigate?: (path: string) => void;
  onActiveChange?: (active: boolean) => void;
  autoStart?: boolean;
  greeting?: string;
  className?: string;
}

// =============================================================================
// CLIENT TOOLS DEFINITIONS
// =============================================================================

/**
 * These are the tools that ElevenLabs will call.
 * They map to actions in our Action Registry.
 */
const CLIENT_TOOLS = {
  // Navigation tools
  navigate: {
    description: 'Navigate to a page in the application',
    parameters: {
      page: { type: 'string', description: 'Page name: courses, sessions, forum, console, reports, dashboard, integrations' },
    },
  },
  switch_tab: {
    description: 'Switch to a tab on the current page',
    parameters: {
      tab_voice_id: { type: 'string', description: 'Tab voice ID (e.g., tab-courses, tab-create, tab-advanced)' },
    },
  },
  click_button: {
    description: 'Click a button by its voice ID',
    parameters: {
      button_voice_id: { type: 'string', description: 'Button voice ID' },
    },
  },
  fill_input: {
    description: 'Fill a form input field',
    parameters: {
      field_voice_id: { type: 'string', description: 'Field voice ID' },
      content: { type: 'string', description: 'Content to fill' },
    },
  },
  select_dropdown: {
    description: 'Select an option from a dropdown',
    parameters: {
      dropdown_voice_id: { type: 'string', description: 'Dropdown voice ID' },
      selection_index: { type: 'number', description: 'Option index (0-based)' },
      selection_text: { type: 'string', description: 'Option text to select' },
    },
  },
  confirm_action: {
    description: 'Confirm or cancel a pending action',
    parameters: {
      confirmed: { type: 'boolean', description: 'true to confirm, false to cancel' },
    },
  },
  go_live: {
    description: 'Start a live session',
    parameters: {},
  },
  end_session: {
    description: 'End the current live session',
    parameters: {},
  },
  get_ui_state: {
    description: 'Get current UI state (tabs, buttons, inputs)',
    parameters: {},
  },
};

// =============================================================================
// COMPONENT
// =============================================================================

export function ConversationalVoiceV2(props: ConversationalVoiceProps) {
  const {
    onActiveChange,
    autoStart = false,
    greeting,
    className,
  } = props;

  const { currentUser } = useUser();
  const { locale, setLocale } = useLanguage();
  const router = useRouter();
  const pathname = usePathname();

  // Core state
  const [state, setState] = useState<ConversationState>('disconnected');
  const [isExpanded, setIsExpanded] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [error, setError] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  const [continuousMode, setContinuousMode] = useState(true);

  // Refs
  const conversationRef = useRef<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isInitializingRef = useRef(false);
  const sessionIdRef = useRef<string>('');
  const previousLocaleRef = useRef<string>(locale);
  const isReconnectingRef = useRef(false);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, []);

  // Language switch detection
  useEffect(() => {
    const previousLocale = previousLocaleRef.current;

    if (previousLocale !== locale && conversationRef.current && !isReconnectingRef.current) {
      console.log(`🌐 Language changed from ${previousLocale} to ${locale} - reconnecting`);
      previousLocaleRef.current = locale;

      const reconnect = async () => {
        isReconnectingRef.current = true;
        await cleanup();
        await new Promise(resolve => setTimeout(resolve, 300));
        isInitializingRef.current = false;
        await initializeConversation();
        isReconnectingRef.current = false;
      };

      reconnect();
    } else {
      previousLocaleRef.current = locale;
    }
  }, [locale]);

  const cleanup = async () => {
    if (conversationRef.current) {
      try {
        await conversationRef.current.endSession();
      } catch (error) {
        console.error('Error ending conversation:', error);
      }
      conversationRef.current = null;
    }
  };

  // =============================================================================
  // CLIENT TOOL HANDLERS
  // =============================================================================

  /**
   * Handle Client Tool calls from ElevenLabs.
   * Maps tool calls to Action Registry and returns results.
   */
  const handleClientToolCall = useCallback(async (
    toolName: string,
    parameters: Record<string, unknown>
  ): Promise<string> => {
    console.log(`🔧 Client Tool called: ${toolName}`, parameters);

    // Build action context
    const ctx: ActionContext = {
      router,
      locale,
      userId: currentUser?.id,
      currentRoute: pathname,
      sessionId: sessionIdRef.current,
    };

    // Map tool calls to Action Registry
    let actionId: string;
    let args: Record<string, unknown> = parameters;

    switch (toolName) {
      case 'navigate':
        actionId = 'NAVIGATE';
        break;
      case 'switch_tab':
        actionId = 'SWITCH_TAB';
        break;
      case 'click_button':
        actionId = 'CLICK_BUTTON';
        break;
      case 'fill_input':
        actionId = 'FILL_INPUT';
        break;
      case 'select_dropdown':
        actionId = 'SELECT_DROPDOWN';
        break;
      case 'confirm_action':
        actionId = parameters.confirmed ? 'CONFIRM' : 'CANCEL';
        args = {};
        break;
      case 'go_live':
        actionId = 'GO_LIVE';
        break;
      case 'end_session':
        actionId = 'END_SESSION';
        break;
      case 'get_ui_state':
        return JSON.stringify(collectUiState());
      default:
        // Try direct action ID mapping (e.g., NAV_COURSES)
        actionId = toolName.toUpperCase();
    }

    // Check if action requires confirmation
    if (requiresConfirmation(actionId)) {
      // For high-risk actions, return a prompt for confirmation
      const confirmHint = locale === 'es'
        ? 'Esta es una acción de alto riesgo. ¿Estás seguro?'
        : 'This is a high-risk action. Are you sure?';
      return JSON.stringify({ ok: true, did: 'awaiting confirmation', hint: confirmHint, requiresConfirmation: true });
    }

    // Execute the action
    const result = await run_ui_action(actionId, args, ctx);

    // Add action to messages
    addMessage('system', `Action: ${actionId}`, { type: actionId, result });

    // Return result for ElevenLabs to speak
    return JSON.stringify(result);
  }, [router, locale, currentUser?.id, pathname]);

  // =============================================================================
  // UI STATE COLLECTION
  // =============================================================================

  const collectUiState = useCallback(() => {
    if (typeof window === 'undefined') {
      return { route: pathname, tabs: [], buttons: [], inputs: [] };
    }

    const state: {
      route: string;
      activeTab?: string;
      tabs: { id: string; label: string; active: boolean }[];
      buttons: { id: string; label: string }[];
      inputs: { id: string; label: string; value: string }[];
      dropdowns: { id: string; label: string; options: string[] }[];
    } = {
      route: pathname,
      tabs: [],
      buttons: [],
      inputs: [],
      dropdowns: [],
    };

    // Collect tabs
    document.querySelectorAll('[data-voice-id^="tab-"], [role="tab"]').forEach((tab) => {
      const id = tab.getAttribute('data-voice-id') || '';
      const label = tab.textContent?.trim() || '';
      const isActive = tab.getAttribute('aria-selected') === 'true' ||
                       tab.getAttribute('data-state') === 'active';
      if (id || label) {
        state.tabs.push({ id, label, active: isActive });
        if (isActive) state.activeTab = id;
      }
    });

    // Collect buttons
    document.querySelectorAll('[data-voice-id]:not([data-voice-id^="tab-"])').forEach((btn) => {
      const id = btn.getAttribute('data-voice-id') || '';
      const label = btn.textContent?.trim() || btn.getAttribute('aria-label') || '';
      if (id && label.length < 50) {
        state.buttons.push({ id, label });
      }
    });

    // Collect inputs
    document.querySelectorAll('input[data-voice-id], textarea[data-voice-id]').forEach((input) => {
      const el = input as HTMLInputElement;
      const id = el.getAttribute('data-voice-id') || '';
      const label = el.getAttribute('placeholder') || el.getAttribute('aria-label') || '';
      state.inputs.push({ id, label, value: el.value || '' });
    });

    return state;
  }, [pathname]);

  // =============================================================================
  // INITIALIZATION
  // =============================================================================

  const initializeConversation = async () => {
    if (isInitializingRef.current) return;
    isInitializingRef.current = true;

    setState('connecting');
    setError('');

    try {
      // Request microphone permission
      console.log('🎤 Requesting microphone permission...');
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach(track => track.stop());
        console.log('✅ Microphone permission granted');
      } catch (micError) {
        console.error('❌ Microphone permission denied:', micError);
        setState('error');
        setError('Microphone access is required. Please allow microphone access and try again.');
        isInitializingRef.current = false;
        return;
      }

      // Get signed URL
      console.log(`🔑 Getting signed URL (language=${locale})...`);
      const response = await fetch(`/api/voice/agent/signed-url?language=${locale}`, {
        method: 'GET',
        headers: {
          'Authorization': 'Bearer dummy-token',
          'Content-Type': 'application/json',
        },
        cache: 'no-store',
      });

      if (!response.ok) {
        throw new Error(`Failed to get signed URL: ${response.status}`);
      }

      const { signed_url } = await response.json();
      console.log('✅ Got signed URL');

      // Start conversation with Client Tools
      console.log('🚀 Starting conversation with Client Tools...');

      conversationRef.current = await Conversation.startSession({
        signedUrl: signed_url,
        connectionType: 'websocket',

        // Client Tools configuration
        clientTools: {
          navigate: async (params: { page: string }) => {
            return handleClientToolCall('navigate', params);
          },
          switch_tab: async (params: { tab_voice_id: string }) => {
            return handleClientToolCall('switch_tab', params);
          },
          click_button: async (params: { button_voice_id: string }) => {
            return handleClientToolCall('click_button', params);
          },
          fill_input: async (params: { field_voice_id: string; content: string }) => {
            return handleClientToolCall('fill_input', params);
          },
          select_dropdown: async (params: { dropdown_voice_id: string; selection_index?: number; selection_text?: string }) => {
            return handleClientToolCall('select_dropdown', params);
          },
          confirm_action: async (params: { confirmed: boolean }) => {
            return handleClientToolCall('confirm_action', params);
          },
          go_live: async () => {
            return handleClientToolCall('go_live', {});
          },
          end_session: async () => {
            return handleClientToolCall('end_session', {});
          },
          get_ui_state: async () => {
            return handleClientToolCall('get_ui_state', {});
          },
        },

        onConnect: ({ conversationId }: { conversationId: string }) => {
          console.log('✅ Connected:', conversationId);
          sessionIdRef.current = conversationId;
          setState('connected');
          onActiveChange?.(true);
          isInitializingRef.current = false;

          // Add greeting
          const userName = currentUser?.name?.split(' ')[0] || (locale === 'es' ? 'amigo' : 'there');
          const greetingMessage = greeting || (locale === 'es'
            ? `¡Hola ${userName}! Soy tu asistente AristAI. ¿Qué te gustaría hacer?`
            : `Hello ${userName}! I'm your AristAI assistant. What would you like to do?`);
          addMessage('assistant', greetingMessage);
        },

        onDisconnect: () => {
          console.log('🔌 Disconnected');
          setState('disconnected');
          conversationRef.current = null;
          onActiveChange?.(false);
        },

        onStatusChange: ({ status }: { status: string }) => {
          console.log('📊 Status:', status);
          switch (status) {
            case 'connecting': setState('connecting'); break;
            case 'connected': setState('connected'); break;
            case 'listening': setState('listening'); break;
            case 'thinking': setState('processing'); break;
            case 'speaking': setState('speaking'); break;
            case 'disconnected': setState('disconnected'); break;
          }
        },

        onMessage: ({ source, message }: { source: 'user' | 'ai'; message: string }) => {
          console.log(`💬 ${source}:`, message);
          if (message && message.trim()) {
            addMessage(source === 'user' ? 'user' : 'assistant', message);
          }
        },

        onError: (error: string) => {
          console.error('❌ Error:', error);
          setError(error);
          setState('error');
        },
      });

    } catch (error: any) {
      console.error('❌ Failed to initialize:', error);
      setError(error.message || 'Failed to initialize voice assistant');
      setState('error');
      onActiveChange?.(false);
      isInitializingRef.current = false;
    }
  };

  // =============================================================================
  // MESSAGE HELPERS
  // =============================================================================

  const addMessage = (role: 'user' | 'assistant' | 'system', content: string, action?: Message['action']) => {
    const message: Message = {
      id: Date.now().toString(),
      role,
      content,
      timestamp: new Date(),
      action,
    };
    setMessages(prev => [...prev, message]);
  };

  // =============================================================================
  // CONTROLS
  // =============================================================================

  const toggleConversation = async () => {
    if (state === 'disconnected' || state === 'error') {
      await initializeConversation();
    } else if (conversationRef.current) {
      await conversationRef.current.endSession();
      setState('disconnected');
      onActiveChange?.(false);
    }
  };

  const restartConversation = async () => {
    await cleanup();
    isInitializingRef.current = false;
    await initializeConversation();
  };

  // State helpers
  const isConnecting = ['initializing', 'connecting'].includes(state);
  const isReady = ['connected', 'listening', 'processing', 'speaking'].includes(state);
  const isActive = state !== 'disconnected' && state !== 'error';

  // =============================================================================
  // RENDER
  // =============================================================================

  return (
    <div className={cn(
      "fixed z-50 bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 transition-all duration-300",
      isMinimized ? "w-12 h-12" : isExpanded ? "w-96 h-[600px]" : "w-80 h-[500px]",
      "right-4 bottom-4",
      className
    )}>
      {!isMinimized ? (
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between p-3 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-primary-600 dark:text-primary-400" />
              <span className="text-sm font-medium text-gray-900 dark:text-white">
                Voice Assistant
              </span>
              {isActive && (
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              )}
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={() => setLocale(locale === 'en' ? 'es' : 'en')}
                className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors flex items-center gap-1"
                title={`Language: ${locale === 'en' ? 'English' : 'Spanish'}`}
              >
                <Globe className="w-4 h-4" />
                <span className="text-xs font-medium uppercase">{locale}</span>
              </button>
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              >
                {isExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
              </button>
              <button
                onClick={() => setIsMinimized(true)}
                className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              >
                <div className="w-4 h-1 bg-gray-500 dark:bg-gray-400" />
              </button>
            </div>
          </div>

          {/* Status */}
          <div className="px-3 py-2 text-xs text-center border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center justify-center gap-2">
              {state === 'connecting' && <div className="w-2 h-2 bg-yellow-500 rounded-full animate-pulse" />}
              {state === 'connected' && <div className="w-2 h-2 bg-green-500 rounded-full" />}
              {state === 'listening' && <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />}
              {state === 'processing' && <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />}
              {state === 'speaking' && <div className="w-2 h-2 bg-purple-500 rounded-full animate-pulse" />}
              {state === 'disconnected' && <div className="w-2 h-2 bg-gray-300 rounded-full" />}
              {state === 'error' && <div className="w-2 h-2 bg-red-600 rounded-full" />}

              <span className="text-gray-600 dark:text-gray-400 capitalize">
                {state === 'connecting' && 'Connecting...'}
                {state === 'connected' && 'Ready'}
                {state === 'listening' && 'Listening...'}
                {state === 'processing' && 'Thinking...'}
                {state === 'speaking' && 'Speaking...'}
                {state === 'disconnected' && 'Disconnected'}
                {state === 'error' && 'Error'}
              </span>
            </div>
          </div>

          {/* Messages */}
          <div className={cn(
            "flex-1 overflow-y-auto p-3 space-y-2",
            isExpanded ? "max-h-[400px]" : "max-h-[280px]"
          )}>
            {messages.length === 0 ? (
              <div className="text-center text-gray-500 dark:text-gray-400 text-sm py-4">
                {isReady ? 'Listening... Speak now.' : 'Click Start to begin'}
              </div>
            ) : (
              messages.filter(m => m.role !== 'system').map((msg) => (
                <div key={msg.id} className={cn(
                  "flex gap-2",
                  msg.role === 'user' ? 'justify-end' : 'justify-start'
                )}>
                  {msg.role === 'assistant' && (
                    <div className="w-6 h-6 rounded-full bg-primary-100 dark:bg-primary-900 flex items-center justify-center flex-shrink-0">
                      <Sparkles className="w-3 h-3 text-primary-600 dark:text-primary-400" />
                    </div>
                  )}
                  <div className={cn(
                    "max-w-[75%] px-3 py-2 rounded-lg text-sm",
                    msg.role === 'user'
                      ? 'bg-primary-600 text-white'
                      : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white'
                  )}>
                    {msg.content}
                  </div>
                  {msg.role === 'user' && (
                    <div className="w-6 h-6 rounded-full bg-primary-600 flex items-center justify-center flex-shrink-0">
                      <Mic className="w-3 h-3 text-white" />
                    </div>
                  )}
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Error */}
          {error && (
            <div className="px-3 py-2 bg-red-50 dark:bg-red-900/20 border-t border-red-200 dark:border-red-800">
              <p className="text-xs text-red-600 dark:text-red-400">{error}</p>
            </div>
          )}

          {/* Controls */}
          <div className="p-3 border-t border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-2">
              <button
                onClick={toggleConversation}
                disabled={isConnecting}
                className={cn(
                  "flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                  state === 'disconnected' || state === 'error'
                    ? "bg-primary-600 hover:bg-primary-700 text-white"
                    : "bg-red-600 hover:bg-red-700 text-white",
                  isConnecting && "opacity-50 cursor-not-allowed"
                )}
              >
                {state === 'disconnected' || state === 'error' ? (
                  <>
                    <Mic className="w-4 h-4" />
                    Start
                  </>
                ) : (
                  <>
                    <MicOff className="w-4 h-4" />
                    Stop
                  </>
                )}
              </button>

              {state === 'error' && (
                <button
                  onClick={restartConversation}
                  className="px-3 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg text-sm font-medium transition-colors"
                >
                  Restart
                </button>
              )}

              {!isExpanded && (
                <button
                  onClick={() => setShowSettings(!showSettings)}
                  className="p-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded-lg transition-colors"
                >
                  <Settings className="w-4 h-4 text-gray-600 dark:text-gray-300" />
                </button>
              )}
            </div>

            {showSettings && !isExpanded && (
              <div className="mt-3 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg space-y-2">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={continuousMode}
                    onChange={(e) => setContinuousMode(e.target.checked)}
                    className="rounded border-gray-300"
                  />
                  <span className="text-gray-700 dark:text-gray-300">Continuous listening</span>
                </label>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* Minimized */
        <div className="flex items-center justify-center h-full">
          <button
            onClick={() => setIsMinimized(false)}
            className="flex items-center justify-center w-full h-full hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors rounded-lg"
          >
            <img
              src="/AristAI_icon.png"
              alt="AristAI"
              className="w-10 h-10 object-contain"
              onError={(e) => {
                e.currentTarget.style.display = 'none';
              }}
            />
            {isActive && (
              <div className="absolute top-2 right-2 w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            )}
          </button>
        </div>
      )}
    </div>
  );
}

export default ConversationalVoiceV2;
