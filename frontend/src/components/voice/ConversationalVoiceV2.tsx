'use client';

/**
 * ConversationalVoiceV2 - ElevenLabs Client Tools with Smart Resolution
 *
 * This component uses ElevenLabs as the "brain" with only 6 Client Tools.
 * No enums needed - natural language targets are resolved by the frontend.
 *
 * Key features:
 * - NO SPEAK: prefix mechanism
 * - NO volume muting
 * - NO state machine
 * - Single response guaranteed (ElevenLabs controls flow)
 * - Smart resolution of natural language targets
 */

import { useEffect, useState, useRef, useCallback } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { Conversation } from '@elevenlabs/client';
import { Mic, MicOff, Minimize2, Maximize2, Sparkles, Globe } from 'lucide-react';
import { useUser } from '@/lib/context';
import { useLanguage } from '@/lib/i18n-provider';
import { cn } from '@/lib/utils';
import {
  navigate,
  switchTab,
  clickButton,
  fillInput,
  selectItem,
  getPageInfo,
  generateContent,
  isHighRiskAction,
  ActionContext,
  ActionResult,
  ContentType,
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
}

interface ConversationalVoiceProps {
  onNavigate?: (path: string) => void;
  onActiveChange?: (active: boolean) => void;
  autoStart?: boolean;
  greeting?: string;
  className?: string;
}

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

  // Refs
  const conversationRef = useRef<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isInitializingRef = useRef(false);
  const sessionIdRef = useRef<string>('');
  const previousLocaleRef = useRef<string>(locale);
  const isReconnectingRef = useRef(false);
  const hasUserActivatedRef = useRef(false); // Track if user has started a session

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

  // Language switch detection - reconnect when language changes
  useEffect(() => {
    const previousLocale = previousLocaleRef.current;

    // Only reconnect if language actually changed and user has activated voice at least once
    if (previousLocale !== locale && hasUserActivatedRef.current && !isReconnectingRef.current) {
      console.log(`[Voice] Language changed: ${previousLocale} → ${locale}, reconnecting...`);
      previousLocaleRef.current = locale;

      // Capture the new locale to avoid closure issues
      const newLocale = locale;

      const reconnect = async () => {
        isReconnectingRef.current = true;
        // Clean up existing conversation if any
        if (conversationRef.current) {
          await cleanup();
        }
        await new Promise(resolve => setTimeout(resolve, 300));
        isInitializingRef.current = false;
        // Pass the new locale explicitly to avoid stale closure
        await initializeConversation(newLocale);
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
        console.error('[Voice] Error ending conversation:', error);
      }
      conversationRef.current = null;
    }
  };

  // =============================================================================
  // ACTION CONTEXT
  // =============================================================================

  const getActionContext = useCallback((): ActionContext => ({
    router,
    locale,
    userId: currentUser?.id,
    currentRoute: pathname,
    sessionId: sessionIdRef.current,
  }), [router, locale, currentUser?.id, pathname]);

  // =============================================================================
  // CLIENT TOOL HANDLERS
  // =============================================================================

  /**
   * Handle navigate tool call
   */
  const handleNavigate = useCallback(async (params: { page: string }): Promise<string> => {
    console.log('[Voice] Tool: navigate', params);
    const result = await navigate(params.page, getActionContext());
    return JSON.stringify(result);
  }, [getActionContext]);

  /**
   * Handle switch_tab tool call
   */
  const handleSwitchTab = useCallback(async (params: { target: string }): Promise<string> => {
    console.log('[Voice] Tool: switch_tab', params);
    const result = await switchTab(params.target, getActionContext());
    return JSON.stringify(result);
  }, [getActionContext]);

  /**
   * Handle click_button tool call
   */
  const handleClickButton = useCallback(async (params: { target: string }): Promise<string> => {
    console.log('[Voice] Tool: click_button', params);

    // Check if high-risk action
    if (isHighRiskAction(params.target)) {
      return JSON.stringify({
        ok: true,
        did: 'awaiting confirmation',
        hint: locale === 'es'
          ? `Esta es una acción importante. ¿Estás seguro de que quieres ${params.target}?`
          : `This is an important action. Are you sure you want to ${params.target}?`,
        requiresConfirmation: true,
      });
    }

    const result = await clickButton(params.target, getActionContext());
    return JSON.stringify(result);
  }, [getActionContext, locale]);

  /**
   * Handle fill_input tool call
   */
  const handleFillInput = useCallback(async (params: { target: string; content: string }): Promise<string> => {
    console.log('[Voice] Tool: fill_input', params);
    const result = await fillInput(params.target, params.content, getActionContext());
    return JSON.stringify(result);
  }, [getActionContext]);

  /**
   * Handle select_item tool call
   */
  const handleSelectItem = useCallback(async (params: { target: string; selection: string }): Promise<string> => {
    console.log('[Voice] Tool: select_item', params);
    const result = await selectItem(params.target, params.selection, getActionContext());
    return JSON.stringify(result);
  }, [getActionContext]);

  /**
   * Handle get_page_info tool call
   */
  const handleGetPageInfo = useCallback(async (): Promise<string> => {
    console.log('[Voice] Tool: get_page_info');
    const info = getPageInfo();
    return JSON.stringify({
      ok: true,
      did: 'retrieved page info',
      data: info,
    });
  }, []);

  /**
   * Handle generate_content tool call
   * Uses backend OpenAI API to generate content and optionally fill a form field
   */
  const handleGenerateContent = useCallback(async (params: {
    content_type: ContentType;
    context: string;
    target_field?: string;
  }): Promise<string> => {
    console.log('[Voice] Tool: generate_content', params);
    const result = await generateContent(
      params.content_type,
      params.context,
      params.target_field,
      getActionContext()
    );
    return JSON.stringify(result);
  }, [getActionContext]);

  // =============================================================================
  // INITIALIZATION
  // =============================================================================

  const initializeConversation = async (targetLocale?: string) => {
    if (isInitializingRef.current) return;
    isInitializingRef.current = true;

    // Use passed locale or current locale (to avoid closure issues)
    const langToUse = targetLocale || locale;

    setState('connecting');
    setError('');

    try {
      // Request microphone permission
      console.log('[Voice] Requesting microphone permission...');
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach(track => track.stop());
        console.log('[Voice] Microphone permission granted');
      } catch (micError) {
        console.error('[Voice] Microphone permission denied:', micError);
        setState('error');
        setError('Microphone access is required. Please allow microphone access and try again.');
        isInitializingRef.current = false;
        return;
      }

      // Get signed URL with language parameter
      console.log(`[Voice] Getting signed URL (language=${langToUse})...`);
      const response = await fetch(`/api/voice/agent/signed-url?language=${langToUse}`, {
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
      console.log('[Voice] Got signed URL');

      // Start conversation with Client Tools
      console.log('[Voice] Starting conversation with Client Tools...');

      conversationRef.current = await Conversation.startSession({
        signedUrl: signed_url,

        // Client Tools - 7 tools with string parameters!
        clientTools: {
          navigate: handleNavigate,
          switch_tab: handleSwitchTab,
          click_button: handleClickButton,
          fill_input: handleFillInput,
          select_item: handleSelectItem,
          get_page_info: handleGetPageInfo,
          generate_content: handleGenerateContent,
        },

        onConnect: ({ conversationId }: { conversationId: string }) => {
          console.log('[Voice] Connected:', conversationId);
          sessionIdRef.current = conversationId;
          setState('connected');
          onActiveChange?.(true);
          isInitializingRef.current = false;

          // Add greeting message (use langToUse to avoid closure issues)
          const userName = currentUser?.name?.split(' ')[0] || (langToUse === 'es' ? 'amigo' : 'there');
          const greetingMsg = greeting || (langToUse === 'es'
            ? `¡Hola ${userName}! Soy tu asistente AristAI. ¿Qué te gustaría hacer?`
            : `Hello ${userName}! I'm your AristAI assistant. What would you like to do?`);
          addMessage('assistant', greetingMsg);
        },

        onDisconnect: () => {
          console.log('[Voice] Disconnected');
          setState('disconnected');
          conversationRef.current = null;
          onActiveChange?.(false);
        },

        onStatusChange: ({ status }: { status: string }) => {
          console.log('[Voice] Status:', status);
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
          // Show exactly what was said in the chatbox
          if (message && message.trim()) {
            console.log(`[Voice] ${source}:`, message);
            addMessage(source === 'user' ? 'user' : 'assistant', message);
          }
        },

        onError: (error: string) => {
          console.error('[Voice] Error:', error);
          setError(error);
          setState('error');
        },
      });

    } catch (error: any) {
      console.error('[Voice] Failed to initialize:', error);
      setError(error.message || 'Failed to initialize voice assistant');
      setState('error');
      onActiveChange?.(false);
      isInitializingRef.current = false;
    }
  };

  // =============================================================================
  // MESSAGE HELPERS
  // =============================================================================

  const addMessage = (role: 'user' | 'assistant' | 'system', content: string) => {
    const message: Message = {
      id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
      role,
      content,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, message]);
  };

  // =============================================================================
  // CONTROLS
  // =============================================================================

  const toggleConversation = async () => {
    if (state === 'disconnected' || state === 'error') {
      hasUserActivatedRef.current = true; // User manually started
      await initializeConversation();
    } else if (conversationRef.current) {
      await conversationRef.current.endSession();
      setState('disconnected');
      onActiveChange?.(false);
    }
  };

  const restartConversation = async () => {
    hasUserActivatedRef.current = true; // User manually restarted
    await cleanup();
    setMessages([]);
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
              {/* Language toggle */}
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
                {state === 'connecting' && (locale === 'es' ? 'Conectando...' : 'Connecting...')}
                {state === 'connected' && (locale === 'es' ? 'Listo' : 'Ready')}
                {state === 'listening' && (locale === 'es' ? 'Escuchando...' : 'Listening...')}
                {state === 'processing' && (locale === 'es' ? 'Pensando...' : 'Thinking...')}
                {state === 'speaking' && (locale === 'es' ? 'Hablando...' : 'Speaking...')}
                {state === 'disconnected' && (locale === 'es' ? 'Desconectado' : 'Disconnected')}
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
                {isReady
                  ? (locale === 'es' ? 'Escuchando... Habla ahora.' : 'Listening... Speak now.')
                  : (locale === 'es' ? 'Haz clic en Iniciar para comenzar' : 'Click Start to begin')}
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
                    {locale === 'es' ? 'Iniciar' : 'Start'}
                  </>
                ) : (
                  <>
                    <MicOff className="w-4 h-4" />
                    {locale === 'es' ? 'Detener' : 'Stop'}
                  </>
                )}
              </button>

              {state === 'error' && (
                <button
                  onClick={restartConversation}
                  className="px-3 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg text-sm font-medium transition-colors"
                >
                  {locale === 'es' ? 'Reiniciar' : 'Restart'}
                </button>
              )}
            </div>
          </div>
        </div>
      ) : (
        /* Minimized */
        <div className="flex items-center justify-center h-full">
          <button
            onClick={() => setIsMinimized(false)}
            className="flex items-center justify-center w-full h-full hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors rounded-lg relative"
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
