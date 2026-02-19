'use client';

import { useEffect, useState, useRef } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { Conversation } from '@elevenlabs/client';
import { Volume2, Mic, MicOff, Settings, Minimize2, Maximize2, MessageSquare, Sparkles, Globe } from 'lucide-react';
import { useUser } from '@/lib/context';
import { useLanguage } from '@/lib/i18n-provider';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { executeUiAction, UiAction } from '@/lib/ui-actions';

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
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  action?: {
    type: 'navigate' | 'execute' | 'info';
    target?: string;
    executed?: boolean;
  };
}

interface ConversationalVoiceProps {
  /** Called when assistant wants to navigate */
  onNavigate?: (path: string) => void;
  /** Called when voice is activated/deactivated */
  onActiveChange?: (active: boolean) => void;
  /** Whether to start in active listening mode */
  autoStart?: boolean;
  /** Custom greeting message */
  greeting?: string;
  /** Class name */
  className?: string;
}

// MCP_RESPONSE_PREFIX removed - not needed with Option A architecture
// ElevenLabs agent handles all responses, backend only executes UI actions

// Prefix used to send MCP responses through ElevenLabs
const MCP_RESPONSE_PREFIX = 'MCP_RESPONSE:';

// Feature flag: Use V2 LLM-based processing (no regex, pure LLM)
// Set to true to use the new architecture
const USE_VOICE_V2 = true;

/**
 * Phase 2: Collect rich page context for smarter LLM intent detection
 * Scans the DOM for available UI elements that can be voice-controlled
 */
function collectPageContext(): {
  available_tabs: string[];
  available_buttons: string[];
  active_course_name?: string;
  active_session_name?: string;
  is_session_live?: boolean;
  copilot_active?: boolean;
} {
  const context: {
    available_tabs: string[];
    available_buttons: string[];
    active_course_name?: string;
    active_session_name?: string;
    is_session_live?: boolean;
    copilot_active?: boolean;
  } = {
    available_tabs: [],
    available_buttons: [],
  };

  if (typeof window === 'undefined') return context;

  // Collect tabs from elements with data-voice-tab or role="tab"
  const tabs = document.querySelectorAll('[data-voice-tab], [role="tab"], [data-state]');
  tabs.forEach((tab) => {
    const tabName =
      tab.getAttribute('data-voice-tab') ||
      tab.getAttribute('data-value') ||
      tab.textContent?.trim();
    if (tabName && tabName.length < 50) {
      context.available_tabs.push(tabName);
    }
  });

  // Collect clickable buttons with data-voice-id or visible text
  const buttons = document.querySelectorAll('[data-voice-id], button:not([disabled]), [role="button"]');
  buttons.forEach((btn) => {
    const btnId = btn.getAttribute('data-voice-id');
    const btnText = btn.textContent?.trim();
    const ariaLabel = btn.getAttribute('aria-label');
    const name = btnId || ariaLabel || btnText;
    if (name && name.length < 50 && !name.includes('\n')) {
      context.available_buttons.push(name);
    }
  });

  // Deduplicate
  context.available_tabs = Array.from(new Set(context.available_tabs));
  context.available_buttons = Array.from(new Set(context.available_buttons)).slice(0, 20); // Limit to 20 buttons

  // Check for active course/session name in page header or breadcrumb
  const pageTitle = document.querySelector('h1, [data-voice-context="course-name"], [data-voice-context="session-name"]');
  if (pageTitle) {
    const titleText = pageTitle.textContent?.trim();
    const pathname = window.location.pathname;
    if (pathname.includes('/courses/') && titleText) {
      context.active_course_name = titleText;
    }
    if (pathname.includes('/sessions/') && titleText) {
      context.active_session_name = titleText;
    }
  }

  // Check if session is live
  const liveIndicator = document.querySelector('[data-voice-context="session-live"], .live-indicator, [data-state="live"]');
  if (liveIndicator) {
    context.is_session_live = true;
  }

  // Check if copilot is active
  const copilotIndicator = document.querySelector('[data-voice-context="copilot-active"], .copilot-active');
  if (copilotIndicator) {
    context.copilot_active = true;
  }

  return context;
}

/**
 * V2: Collect full UI state for LLM-based processing
 * Returns structured data about all interactive elements on the page
 */
function collectUiStateV2(): {
  route: string;
  activeTab?: string;
  tabs: Array<{ id: string; label: string; active: boolean }>;
  buttons: Array<{ id: string; label: string }>;
  inputs: Array<{ id: string; label: string; value: string }>;
  dropdowns: Array<{
    id: string;
    label: string;
    selected?: string;
    options: Array<{ idx: number; label: string }>;
  }>;
  modal?: string;
} {
  const state: ReturnType<typeof collectUiStateV2> = {
    route: typeof window !== 'undefined' ? window.location.pathname : '/',
    tabs: [],
    buttons: [],
    inputs: [],
    dropdowns: [],
  };

  if (typeof window === 'undefined') return state;

  // Collect tabs with voice-id
  const tabElements = document.querySelectorAll('[data-voice-id^="tab-"], [role="tab"]');
  tabElements.forEach((tab) => {
    const id = tab.getAttribute('data-voice-id') || tab.getAttribute('id') || '';
    const label = tab.textContent?.trim() || '';
    const isActive = tab.getAttribute('aria-selected') === 'true' ||
                     tab.getAttribute('data-state') === 'active' ||
                     tab.classList.contains('active');
    if (id || label) {
      state.tabs.push({ id, label, active: isActive });
      if (isActive) state.activeTab = id;
    }
  });

  // Collect buttons with voice-id
  const buttonElements = document.querySelectorAll('[data-voice-id]:not([data-voice-id^="tab-"])');
  buttonElements.forEach((btn) => {
    const id = btn.getAttribute('data-voice-id') || '';
    const label = btn.textContent?.trim() || btn.getAttribute('aria-label') || '';
    if (id && label.length < 50) {
      state.buttons.push({ id, label });
    }
  });

  // Collect inputs with voice-id
  const inputElements = document.querySelectorAll('input[data-voice-id], textarea[data-voice-id]');
  inputElements.forEach((input) => {
    const el = input as HTMLInputElement | HTMLTextAreaElement;
    const id = el.getAttribute('data-voice-id') || '';
    const label = el.getAttribute('placeholder') || el.getAttribute('aria-label') || '';
    state.inputs.push({ id, label, value: el.value || '' });
  });

  // Collect dropdowns/selects with voice-id
  const selectElements = document.querySelectorAll('select[data-voice-id]');
  selectElements.forEach((select) => {
    const el = select as HTMLSelectElement;
    const id = el.getAttribute('data-voice-id') || '';
    const label = el.getAttribute('aria-label') || '';
    const options: Array<{ idx: number; label: string }> = [];
    let selectedLabel: string | undefined;

    Array.from(el.options).forEach((opt, idx) => {
      if (opt.value) {
        options.push({ idx, label: opt.text });
        if (opt.selected) selectedLabel = opt.text;
      }
    });

    state.dropdowns.push({ id, label, selected: selectedLabel, options });
  });

  // Check for open modal
  const modal = document.querySelector('[role="dialog"][aria-modal="true"], .modal.show, [data-state="open"]');
  if (modal) {
    state.modal = modal.getAttribute('aria-label') ||
                  modal.querySelector('h2, h3, [class*="title"]')?.textContent?.trim() ||
                  'Modal';
  }

  return state;
}

export function ConversationalVoice(props: ConversationalVoiceProps) {
  const {
    onActiveChange,
    autoStart = false,  // Changed to false - user must click Start button
    greeting,
    className,
  } = props;
  const { currentUser, isInstructor } = useUser();
  const { locale, setLocale } = useLanguage();
  const router = useRouter();
  const pathname = usePathname();
  
  // Core state - start as 'disconnected' so user can click Start button
  const [state, setState] = useState<ConversationState>('disconnected');
  const [isExpanded, setIsExpanded] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [error, setError] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  // Settings
  const [continuousMode, setContinuousMode] = useState(true);
  
  // Refs
  const conversationRef = useRef<any>(null); // ElevenLabs conversation instance
  const conversationContextRef = useRef<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isInitializingRef = useRef(false);
  const isProcessingTranscriptRef = useRef(false);
  const userInitiatedDisconnectRef = useRef(false); // Track user-initiated Stop clicks
  const previousUserIdRef = useRef<number | null>(null); // Track user ID for logout detection
  const messageCountRef = useRef(0); // Track message count for session refresh
  const previousLocaleRef = useRef<string>(locale); // Track locale for language switch detection
  const isRefreshingRef = useRef(false); // Track if this is a silent refresh (skip greeting)
  const lastUserMessageIdRef = useRef<string | null>(null); // Track last user message for transcript updates
  const pendingTranscriptRef = useRef<string | null>(null); // Track pending transcript to avoid duplicate processing
  const lastAgentResponseRef = useRef<string>(''); // Track last agent response to detect brief acknowledgments
  const lastMcpResponseTimeRef = useRef<number>(0); // Track when MCP_RESPONSE was sent to filter duplicate AI responses
  const lastMcpResponseContentRef = useRef<string>(''); // Track MCP_RESPONSE content to detect duplicates
  const mcpResponseDisplayedRef = useRef<boolean>(false); // Track if MCP_RESPONSE has been displayed already
  const previousPathnameRef = useRef<string | null>(null); // Phase 2.5: Track pathname for pending action detection

  // Session refresh threshold - restart to prevent context buildup slowdown
  const MAX_MESSAGES_BEFORE_REFRESH = Number.MAX_SAFE_INTEGER;

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

  // Phase 2.5: Check for pending actions after page navigation
  // When user issues a cross-page command, we navigate first and store the action.
  // After navigation completes, this effect executes the pending action.
  useEffect(() => {
    const checkPendingAction = async () => {
      // Only check if pathname actually changed and we have a user
      if (previousPathnameRef.current === pathname || !currentUser?.id) {
        previousPathnameRef.current = pathname;
        return;
      }

      const prevPath = previousPathnameRef.current;
      previousPathnameRef.current = pathname;

      // If this is the initial load (prevPath was null), skip
      if (!prevPath) {
        return;
      }

      console.log('🔄 Page changed from', prevPath, 'to', pathname, '- checking for pending actions');

      try {
        const pendingResult = await api.voiceCheckPendingAction({
          user_id: currentUser.id,
          current_page: pathname,
          language: locale,
        });

        if (pendingResult.has_pending && pendingResult.message) {
          console.log('✅ Executing pending action:', pendingResult.action);

          // Speak the response through ElevenLabs
          // NOTE: Do NOT call addAssistantMessage here - ElevenLabs will echo
          // the message back via onMessage(source="ai"), which handles adding
          // the message to the chat. Calling both causes duplicate messages.
          if (conversationRef.current) {
            conversationRef.current.sendUserMessage(`${MCP_RESPONSE_PREFIX}${pendingResult.message}`);
          }
        }
      } catch (error) {
        console.error('❌ Failed to check/execute pending action:', error);
      }
    };

    // Small delay to allow page to fully render
    const timeoutId = setTimeout(checkPendingAction, 500);
    return () => clearTimeout(timeoutId);
  }, [pathname, currentUser?.id, locale]);

  // Auto-start removed - user must click Start button manually
  // This prevents unwanted auto-starting and flipping behavior

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

  // Clear voice context when user logs out
  useEffect(() => {
    const previousUserId = previousUserIdRef.current;
    const currentUserId = currentUser?.id ?? null;

    // Detect logout (user was logged in, now isn't)
    if (previousUserId !== null && currentUserId === null) {
      // User logged out - clear voice context
      const clearVoiceContext = async () => {
        try {
          await fetch('/api/voice/logout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: previousUserId }),
          });
          console.log('🔒 Voice context cleared on logout');
        } catch (error) {
          console.error('Failed to clear voice context:', error);
        }
      };
      clearVoiceContext();
    }

    // Update the previous user ID ref
    previousUserIdRef.current = currentUserId;
  }, [currentUser?.id]);

  // Language switch detection - reconnect ElevenLabs when locale changes
  // This ensures the voice assistant responds in the newly selected language
  useEffect(() => {
    const previousLocale = previousLocaleRef.current;

    // Only act if locale actually changed and conversation is active
    if (previousLocale !== locale && conversationRef.current) {
      console.log(`🌐 Language changed from ${previousLocale} to ${locale} - reconnecting voice assistant`);

      // Update ref first
      previousLocaleRef.current = locale;

      // Trigger a silent refresh to reconnect with new language
      // The signed URL will be fetched with the new locale
      const reconnectWithNewLanguage = async () => {
        isRefreshingRef.current = true; // Skip greeting on reconnect

        // End current session
        if (conversationRef.current) {
          try {
            await conversationRef.current.endSession();
          } catch (error) {
            console.error('Error ending session for language switch:', error);
          }
          conversationRef.current = null;
        }

        // Small delay to ensure clean disconnect
        await new Promise(resolve => setTimeout(resolve, 300));

        // Reinitialize with new language (will use updated locale from hook)
        isInitializingRef.current = false;
        await initializeConversation();

        console.log(`✅ Voice assistant reconnected with language: ${locale}`);
      };

      reconnectWithNewLanguage();
    } else {
      // Just update the ref without reconnecting
      previousLocaleRef.current = locale;
    }
  }, [locale]);

  const initializeConversation = async () => {
    setState('connecting');
    setError('');

    try {
      // Request microphone permission FIRST before connecting
      // This ensures the browser shows the permission dialog
      console.log('🎤 Requesting microphone permission...');
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        // Stop the stream immediately - ElevenLabs SDK will create its own
        stream.getTracks().forEach(track => track.stop());
        console.log('✅ Microphone permission granted');
      } catch (micError: any) {
        console.error('❌ Microphone permission denied:', micError);
        setState('error');
        setError('Microphone access is required for voice assistant. Please allow microphone access and try again.');
        return;
      }

      // Get signed URL from our backend with language parameter
      console.log(`🔑 Getting signed URL from backend (language=${locale})...`);
      // Use relative URL for all environments to leverage Next.js API routes
      const apiUrl = '/api';
      const response = await fetch(`${apiUrl}/voice/agent/signed-url?language=${locale}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer dummy-token`, // TODO: Replace with real auth
          'Content-Type': 'application/json',
        },
      });
      
      console.log('🔗 Voice API response status:', response.status);

      if (!response.ok) {
        let errorMessage = 'Failed to get signed URL';
        let errorCode = 'E_UNKNOWN';
        
        switch (response.status) {
          case 401:
            errorMessage = 'Authentication failed. Please check your credentials.';
            errorCode = 'E_AUTH';
            break;
          case 403:
            errorMessage = 'Access denied. Voice features may not be available for your account.';
            errorCode = 'E_FORBIDDEN';
            break;
          case 404:
            errorMessage = 'Voice service not found. Please contact support.';
            errorCode = 'E_NOT_FOUND';
            break;
          case 429:
            errorMessage = 'Too many requests. Please wait and try again.';
            errorCode = 'E_RATE_LIMIT';
            break;
          case 500:
            errorMessage = 'Server error. Please try again later.';
            errorCode = 'E_SERVER';
            break;
          case 502:
            errorMessage = 'Voice service unavailable. Please try again later.';
            errorCode = 'E_SERVICE';
            break;
          default:
            errorMessage = `Failed to get signed URL: ${response.status} ${response.statusText}`;
            errorCode = `E_HTTP_${response.status}`;
        }
        
        console.error(`❌ Signed URL unavailable: ${errorMessage} (${errorCode})`);
        setState('error');
        onActiveChange?.(false);
        setError(`${errorMessage} (${errorCode})`);
        isInitializingRef.current = false;
        return;
      }

      const { signed_url } = await response.json();
      console.log('✅ Got signed URL:', signed_url.substring(0, 50) + '...');

      // Start the conversation session using the official SDK
      console.log('🚀 Starting conversation session...');
      console.log('🔗 Using signed URL:', signed_url.substring(0, 80) + '...');
      
      conversationRef.current = await Conversation.startSession({
        signedUrl: signed_url,
        connectionType: "websocket",
        onConnect: ({ conversationId }: { conversationId: string }) => {
          console.log('✅ Connected to ElevenLabs:', conversationId);
          setState('connected');
          onActiveChange?.(true);
          isInitializingRef.current = false;

          // Only speak greeting on initial connection, not on refresh
          if (!isRefreshingRef.current) {
            if (greeting) {
              addAssistantMessage(greeting);
            } else {
              // Language-aware greeting
              const userName = currentUser?.name?.split(' ')[0] || (locale === 'es' ? 'amigo' : 'there');
              const greetingMessage = locale === 'es'
                ? `¡Hola ${userName}! Soy tu asistente AristAI. Puedo ayudarte a navegar, crear cursos, gestionar sesiones, crear encuestas, generar reportes y mucho más. ¿Qué te gustaría hacer?`
                : `Hello ${userName}! I'm your AristAI assistant. I can help you navigate, create courses, manage sessions, create polls, generate reports, and much more. What would you like to do?`;
              addAssistantMessage(greetingMessage);
            }
          } else {
            // Silent refresh complete - reset the flag
            console.log('🔄 Session refreshed silently (no greeting)');
            isRefreshingRef.current = false;
          }
        },
        onDisconnect: (data?: any) => {
          console.log('🔌 Disconnected from AristAI voice service:', data);
          setState('disconnected');
          conversationRef.current = null;
          onActiveChange?.(false);

          // REMOVED auto-reconnect - user must manually click Start button
          // This prevents the flipping back and forth issue
        },
        onStatusChange: ({ status }: { status: string }) => {
          console.log('📊 Status changed:', status);
          
          // Emit status event for debugging
          if (typeof window !== 'undefined') {
            window.dispatchEvent(new CustomEvent('voice-status', {
              detail: `[${new Date().toISOString()}] Status: ${status}`
            }));
          }
          
          // Map SDK statuses to our state
          switch (status) {
            case 'connecting':
              setState('connecting');
              break;
            case 'connected':
              setState('connected');
              break;
            case 'listening':
              setState('listening');
              break;
            case 'thinking':
              setState('processing');
              break;
            case 'speaking':
              setState('speaking');
              break;
            case 'disconnected':
              setState('disconnected');
              break;
            default:
              console.log('Unknown status:', status);
          }
        },
        onModeChange: ({ mode }: { mode: string }) => {
          console.log('🔄 Mode changed:', mode);
        },
        onMessage: ({ source, message }: { source: "user" | "ai"; message: string }) => {
          console.log('💬 Message received:', { source, message });

          // Emit events for debugging
          if (typeof window !== 'undefined') {
            window.dispatchEvent(new CustomEvent('voice-message', {
              detail: `[${new Date().toISOString()}] ${source}: ${message}`
            }));
          }

          if (source === 'user') {
            // ElevenLabs sends interim transcripts as user speaks, then final transcript
            // We UPDATE the last user message instead of adding new ones for each interim
            console.log('🎤 User message received:', message);

            // Reset MCP response tracking - new user turn starts
            lastMcpResponseTimeRef.current = 0;
            lastMcpResponseContentRef.current = '';
            mcpResponseDisplayedRef.current = false;

            // Note: MCP_RESPONSE injection removed with Option A architecture
            // All responses come from ElevenLabs agent directly

            // Emit transcription event
            if (typeof window !== 'undefined') {
              window.dispatchEvent(new CustomEvent('voice-transcription', {
                detail: `[${new Date().toISOString()}] Transcription: ${message}`
              }));
            }

            // Update or add user message (handles interim transcripts)
            updateOrAddUserMessage(message);

            // Store pending transcript - will be processed after a brief delay
            // This prevents processing interim transcripts
            pendingTranscriptRef.current = message;

            // Debounce: Wait 500ms after last transcript update before processing
            // This ensures we process the final transcript, not interim ones
            // Clear any existing timeout to prevent race conditions
            if ((window as any).__pendingTranscriptTimeout) {
              clearTimeout((window as any).__pendingTranscriptTimeout);
            }
            (window as any).__pendingTranscriptTimeout = setTimeout(() => {
              // Double-check: only process if this is still the pending transcript
              // AND we're not already processing another request
              if (pendingTranscriptRef.current === message && !isProcessingTranscriptRef.current) {
                handleTranscript(message);
              }
              (window as any).__pendingTranscriptTimeout = null;
            }, 500);
          } else if (source === 'ai') {
            // ElevenLabs agent responses - display what the agent speaks
            console.log('🤖 ElevenLabs agent response:', message);

            // Track the agent's response
            lastAgentResponseRef.current = message || '';

            // CRITICAL: Filter out duplicate responses after MCP_RESPONSE
            // If we just sent MCP_RESPONSE (within last 10 seconds), check if this AI response
            // is a duplicate/follow-up that should be suppressed
            const timeSinceMcpResponse = Date.now() - lastMcpResponseTimeRef.current;
            const recentMcpResponse = timeSinceMcpResponse < 10000; // Within 10 seconds

            if (recentMcpResponse && lastMcpResponseContentRef.current) {
              const mcpContent = lastMcpResponseContentRef.current.toLowerCase();
              const aiContent = message?.toLowerCase() || '';

              // Check if this AI response is related to the MCP content
              const isMcpRelated = mcpContent.includes(aiContent.substring(0, 30)) ||
                                   aiContent.includes(mcpContent.substring(0, 30)) ||
                                   // Check for significant overlap
                                   mcpContent.split(' ').slice(0, 5).some(word =>
                                     word.length > 3 && aiContent.includes(word)
                                   );

              if (isMcpRelated) {
                // This is ElevenLabs speaking the MCP content
                if (mcpResponseDisplayedRef.current) {
                  // We already displayed this MCP content - filter duplicate
                  console.log('🔇 Filtering duplicate MCP echo:', message?.substring(0, 50));
                  return;
                }
                // First time - mark as displayed and let it through
                mcpResponseDisplayedRef.current = true;
                console.log('✅ Displaying MCP response (first time):', message?.substring(0, 50));
              } else if (timeSinceMcpResponse > 1500) {
                // This is a follow-up response after MCP was spoken - filter it
                console.log('🔇 Filtering follow-up AI response after MCP:', message?.substring(0, 50));
                return;
              }
            }

            // Display agent responses in chatbox
            // Skip brief acknowledgments and generic denials - backend is authoritative.
            const briefAcks = [
              "i'm retrieving", "retrieving your", "let me get", "let me check",
              "checking", "one moment", "just a moment", "getting that",
              "fetching", "loading", "looking up", "i'll get",
              "un momento", "buscando", "obteniendo"
            ];
            // Only filter out clear denial phrases that indicate ElevenLabs is rejecting
            // the request before MCP has a chance to respond.
            const genericDenials = [
              "couldn't process that request",
              "couldn't process your request",
              "cannot process your request",
              "unable to assist with that",
              "that feature is not available",
              "i don't have access to that",
              "i'm not able to do that",
              "that's outside my capabilities",
            ];
            const isAck = message && briefAcks.some(ack => message.toLowerCase().includes(ack));
            const isGenericDenial = message && genericDenials.some(p => message.toLowerCase().includes(p));

            if (message && message.length > 5 && !isAck && !isGenericDenial) {
              // Strip MCP_RESPONSE: prefix if ElevenLabs echoed it back
              let cleanMessage = message;
              if (cleanMessage.startsWith('MCP_RESPONSE:')) {
                cleanMessage = cleanMessage.substring('MCP_RESPONSE:'.length).trim();
              }
              // Also handle case where it might be lowercase or have spaces
              const mcpPrefixMatch = cleanMessage.match(/^mcp[_\s]?response[:\s]*/i);
              if (mcpPrefixMatch) {
                cleanMessage = cleanMessage.substring(mcpPrefixMatch[0].length).trim();
              }
              if (cleanMessage.length > 0) {
                addAssistantMessage(cleanMessage);
              }
            }
          }
        },
        


        onError: (error: string, meta?: any) => {
          console.error('❌ ElevenLabs SDK error:', error, meta);
          let errorMessage = 'Voice connection error';
          let errorCode = 'E_11LABS_UNKNOWN';
          
          if (typeof error === 'string') {
            if (error.includes('401') || error.includes('403')) {
              errorMessage = 'Voice service authentication failed. Please try again.';
              errorCode = 'E_11LABS_AUTH';
            } else if (error.includes('429')) {
              errorMessage = 'Voice service rate limit exceeded. Please wait and try again.';
              errorCode = 'E_11LABS_429';
            } else if (error.includes('connection') || error.includes('connect')) {
              errorMessage = 'Cannot connect to voice service. Please check your internet connection.';
              errorCode = 'E_11LABS_CONNECTION';
            }
          }
          
          setError(`${errorMessage} (${errorCode})`);
          setState('error');
        },
        onAudio: (audio: any) => {
          // Monitor audio for stability - only log occasionally to reduce noise
          if (audio && audio.byteLength && Math.random() < 0.05) {
            console.log('🔊 Audio flowing, bytes:', audio.byteLength);
          }
        },
      });
    } catch (error: any) {
      console.error('❌ Failed to initialize conversation:', error);
      console.error('❌ Error type:', typeof error);
      console.error('❌ Error details:', JSON.stringify(error, null, 2));
      
      let errorMessage = 'Failed to initialize voice conversation';
      let errorCode = 'E_INIT_UNKNOWN';
      
      if (error && error.message) {
        if (error.message.includes('E_AUTH')) {
          errorMessage = 'Authentication required. Please log in and try again.';
          errorCode = 'E_INIT_AUTH';
        } else if (error.message.includes('E_CORS') || error.message.includes('CORS')) {
          errorMessage = 'Network error. Please check your browser settings.';
          errorCode = 'E_INIT_CORS';
        } else if (error.message.includes('E_RATE_LIMIT')) {
          errorMessage = 'Service rate limit. Please wait and try again.';
          errorCode = 'E_INIT_RATE_LIMIT';
        } else if (error.message.includes('Failed to fetch')) {
          errorMessage = 'Network connection failed. Please check your internet connection.';
          errorCode = 'E_INIT_NETWORK';
        } else if (error.message.includes('WebSocket')) {
          errorMessage = 'WebSocket connection failed. Please check your network and try again.';
          errorCode = 'E_INIT_WEBSOCKET';
        } else {
          errorMessage = error.message;
          errorCode = 'E_INIT_CUSTOM';
        }
      } else if (error.error || error.code) {
        errorMessage = error.error || error.code || 'Unknown initialization error';
        errorCode = 'E_INIT_CUSTOM';
      }
      
      console.error(`❌ Initialization failed: ${errorMessage} (${errorCode})`);
      setError(`${errorMessage} (${errorCode})`);
      setState('error');
      onActiveChange?.(false);
      isInitializingRef.current = false;
    }
  };

  const extractUiActions = (response: any): UiAction[] => {
    const allActions: UiAction[] = [];

    // 1. Extract from top-level ui_actions (from instructor handlers)
    if (Array.isArray(response?.ui_actions)) {
      allActions.push(...response.ui_actions);
    }

    // 2. Extract from results array
    const results = response?.results ?? [];
    const uiActionsFromResults = results.flatMap((result: any) => {
      if (!result) return [];
      const direct = result.ui_actions ?? result.result?.ui_actions;
      if (Array.isArray(direct)) {
        return direct;
      }
      return [];
    });
    allActions.push(...uiActionsFromResults);

    // 3. Extract from action field (navigate actions)
    const action = response?.action;
    if (action?.type === 'navigate' && action?.target) {
      allActions.push({ type: 'ui.navigate', payload: { path: action.target } });
    }

    // 4. Deduplicate actions by type + payload to prevent multiple executions
    const seen = new Set<string>();
    const uniqueActions = allActions.filter((action) => {
      const key = `${action.type}:${JSON.stringify(action.payload)}`;
      if (seen.has(key)) {
        console.log('🔄 Skipping duplicate action:', key);
        return false;
      }
      seen.add(key);
      return true;
    });

    return uniqueActions;
  };

  // MCP Response prefix for data-driven responses
  const MCP_RESPONSE_PREFIX = 'MCP_RESPONSE:';

  // Speak data-driven content via ElevenLabs agent
  // Used when backend provides dynamic content (dropdown options, student data, etc.)
  const speakViaElevenLabs = (text: string) => {
    if (!text || !conversationRef.current) {
      return;
    }
    try {
      console.log('🔊 Speaking via ElevenLabs:', text.substring(0, 100) + '...');
      // Track when and what we sent so we can filter duplicate AI responses
      lastMcpResponseTimeRef.current = Date.now();
      lastMcpResponseContentRef.current = text;
      conversationRef.current.sendUserMessage(`${MCP_RESPONSE_PREFIX}${text}`);
    } catch (error) {
      console.error('❌ Failed to send MCP message to ElevenLabs:', error);
    }
  };

  const handleTranscript = async (transcript: string) => {
    console.log('🔥 [handleTranscript] CALLED with:', transcript);
    if (!transcript || isProcessingTranscriptRef.current) {
      console.log('🔥 [handleTranscript] SKIPPED - empty or already processing');
      return;
    }

    isProcessingTranscriptRef.current = true;
    console.log('🎯 Processing transcript for UI actions:', transcript);

    try {
      const currentPage = typeof window !== 'undefined' ? window.location.pathname : undefined;
      console.log('📍 Current page:', currentPage);

      // V2 Architecture: Pure LLM-based processing with tools
      if (USE_VOICE_V2 && currentUser?.id) {
        console.log('🚀 Using Voice V2 (LLM-based processing)');

        // Collect full UI state for LLM context
        const uiState = collectUiStateV2();
        const pageContext = collectPageContext();
        console.log('📋 UI State:', uiState);

        const response = await api.voiceProcessV2({
          user_id: currentUser.id,
          transcript,
          language: locale,
          ui_state: uiState,
          conversation_state: 'idle',
          active_course_name: pageContext.active_course_name,
          active_session_name: pageContext.active_session_name,
        });

        console.log('📦 V2 Response:', JSON.stringify(response, null, 2));

        // Execute UI action if present
        if (response.ui_action) {
          console.log('🚀 Executing V2 UI action:', response.ui_action);
          try {
            executeUiAction(response.ui_action as UiAction, router);
            console.log('✅ V2 UI action executed successfully');
          } catch (actionError) {
            console.error('❌ V2 UI action failed:', actionError);
          }
        }

        // Speak the response via ElevenLabs if it contains meaningful content
        if (response.spoken_response && response.spoken_response.length > 5) {
          const msg = response.spoken_response.toLowerCase();
          // Only speak if it's not a simple confirmation that ElevenLabs will handle
          const isSimpleConfirmation =
            msg === 'done' || msg === 'ok' || msg === 'got it' ||
            msg.startsWith('navigating') || msg.startsWith('switching');

          if (!isSimpleConfirmation) {
            console.log('📢 Speaking V2 response via ElevenLabs');
            speakViaElevenLabs(response.spoken_response);
          }
        }

        // Reset and finalize
        lastAgentResponseRef.current = '';
        finalizeUserMessage(transcript);
        return;
      }

      // V1 Architecture (fallback): Regex-based processing
      console.log('📋 Using Voice V1 (legacy processing)');

      // Phase 2: Collect rich page context for smarter LLM intent detection
      const pageContext = collectPageContext();
      console.log('📋 Page context:', pageContext);

      const response = await api.voiceConverse({
        transcript,
        user_id: currentUser?.id,
        current_page: currentPage,
        language: locale,
        // Phase 2: Rich page context
        available_tabs: pageContext.available_tabs,
        available_buttons: pageContext.available_buttons,
        active_course_name: pageContext.active_course_name,
        active_session_name: pageContext.active_session_name,
        is_session_live: pageContext.is_session_live,
        copilot_active: pageContext.copilot_active,
      });

      console.log('📦 Backend response:', JSON.stringify(response, null, 2));

      // Extract and execute UI actions ONLY - no spoken response
      // Pass the full response to extract from top-level ui_actions, results, and action
      const uiActions = extractUiActions(response);
      console.log('🎬 UI Actions to execute:', uiActions);

      if (uiActions.length > 0) {
        uiActions.forEach((action, index) => {
          console.log(`🚀 Executing UI action ${index + 1}:`, action);
          try {
            executeUiAction(action, router);
            console.log(`✅ UI action ${index + 1} executed successfully`);
          } catch (actionError) {
            console.error(`❌ UI action ${index + 1} failed:`, actionError);
          }
        });
      } else {
        console.log('ℹ️ No UI actions needed');
      }

      // OPTION B: Only speak MCP responses when they contain DATA that ElevenLabs
      // doesn't have access to (dropdown options, course lists, student names, etc.)
      // For simple confirmations (navigation, tab switching), ElevenLabs' response is sufficient.
      //
      // This prevents double responses - ElevenLabs speaks the conversational part,
      // MCP only speaks when it has unique data to share.
      //
      // IMPORTANT: Do NOT call addAssistantMessage here!
      // The message will be added to chatbox when ElevenLabs speaks it and fires onMessage.
      if (response?.message) {
        const mcpMessage = response.message.toLowerCase();

        // Detect if MCP response contains DATA that ElevenLabs doesn't have
        // These are dynamic values from the database that only MCP can provide
        const mcpHasData =
          // Numbered lists (dropdown options, course lists, etc.)
          /\b\d+\.\s/.test(mcpMessage) ||
          // Explicit data indicators
          mcpMessage.includes('options are') ||
          mcpMessage.includes('available options') ||
          mcpMessage.includes('your courses') ||
          mcpMessage.includes('your sessions') ||
          mcpMessage.includes('which would you like') ||
          mcpMessage.includes('please choose') ||
          mcpMessage.includes('please select') ||
          mcpMessage.includes('here are') ||
          mcpMessage.includes('i found') ||
          mcpMessage.includes('there are') ||
          // Form field prompts (conversational flow data)
          mcpMessage.includes('what is the') ||
          mcpMessage.includes('please provide') ||
          mcpMessage.includes('please enter') ||
          mcpMessage.includes('what would you like to') ||
          // Error messages with specific details
          mcpMessage.includes('error:') ||
          mcpMessage.includes('failed to') ||
          // Summary/report data
          mcpMessage.includes('summary:') ||
          mcpMessage.includes('report:') ||
          mcpMessage.includes('students') ||
          mcpMessage.includes('participants') ||
          // Question/confirmation requiring user response
          mcpMessage.includes('would you like me to') ||
          mcpMessage.includes('should i') ||
          mcpMessage.includes('do you want');

        if (mcpHasData) {
          console.log('📢 Speaking MCP data response via ElevenLabs');
          speakViaElevenLabs(response.message);
        } else {
          // Skip simple confirmations - ElevenLabs already handled them
          console.log('ℹ️ Skipping MCP simple confirmation (no unique data):', mcpMessage.substring(0, 60));
        }
      } else {
        console.log('ℹ️ No backend message to speak');
      }

      // Reset agent response tracking
      lastAgentResponseRef.current = '';

      // Finalize the user message (update context, check refresh threshold)
      finalizeUserMessage(transcript);
    } catch (error) {
      console.error('❌ Backend call failed:', error);
      // Don't show error to user - agent already responded
      // UI actions just won't execute
    } finally {
      isProcessingTranscriptRef.current = false;
      pendingTranscriptRef.current = null;
    }
  };

  // Update the last user message or add a new one
  // This handles ElevenLabs' interim transcripts - updating the message as user speaks
  const updateOrAddUserMessage = (content: string) => {
    setMessages(prev => {
      // Check if the last message is from the user and was added recently (within 3 seconds)
      const lastMessage = prev[prev.length - 1];
      const isRecentUserMessage = lastMessage?.role === 'user' &&
        (Date.now() - lastMessage.timestamp.getTime()) < 3000;

      if (isRecentUserMessage && lastUserMessageIdRef.current === lastMessage.id) {
        // Update the existing user message with new transcript
        console.log('📝 Updating existing user message with transcript:', content);
        return prev.map(msg =>
          msg.id === lastMessage.id ? { ...msg, content } : msg
        );
      } else {
        // Add a new user message
        const newMessage: Message = {
          id: Date.now().toString(),
          role: 'user',
          content,
          timestamp: new Date(),
        };
        lastUserMessageIdRef.current = newMessage.id;
        console.log('📝 Adding new user message:', content);
        return [...prev, newMessage];
      }
    });
  };

  // Finalize user message - called after transcript is processed
  const finalizeUserMessage = (content: string) => {
    // Update context (keep last 20 entries to prevent memory buildup)
    conversationContextRef.current.push(`User: ${content}`);
    if (conversationContextRef.current.length > 20) {
      conversationContextRef.current = conversationContextRef.current.slice(-20);
    }

    // Increment message count and check for refresh threshold
    messageCountRef.current += 1;
    console.log(`📊 Message count: ${messageCountRef.current}/${MAX_MESSAGES_BEFORE_REFRESH}`);

    if (messageCountRef.current >= MAX_MESSAGES_BEFORE_REFRESH) {
      // Trigger silent refresh after current processing completes
      setTimeout(() => {
        if (!isProcessingTranscriptRef.current && !isRefreshingRef.current) {
          silentRefresh();
        }
      }, 1000);
    }

    // Reset the last user message tracking so next speech creates a new message
    lastUserMessageIdRef.current = null;
  };

  const addUserMessage = (content: string) => {
    const message: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date(),
    };
    setMessages(prev => {
      // Remove any transcript messages - just add new message
      return [...prev, message];
    });

    // Update context (keep last 20 entries to prevent memory buildup)
    conversationContextRef.current.push(`User: ${content}`);
    if (conversationContextRef.current.length > 20) {
      conversationContextRef.current = conversationContextRef.current.slice(-20);
    }

    // Increment message count and check for refresh threshold
    messageCountRef.current += 1;
    console.log(`📊 Message count: ${messageCountRef.current}/${MAX_MESSAGES_BEFORE_REFRESH}`);

    if (messageCountRef.current >= MAX_MESSAGES_BEFORE_REFRESH) {
      // Trigger silent refresh after current processing completes
      setTimeout(() => {
        if (!isProcessingTranscriptRef.current && !isRefreshingRef.current) {
          silentRefresh();
        }
      }, 1000);
    }
  };

  const addAssistantMessage = (content: string, action?: Message['action']) => {
    const message: Message = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content,
      timestamp: new Date(),
      action,
    };
    setMessages(prev => [...prev, message]);

    // Update context (keep last 20 entries to prevent memory buildup)
    conversationContextRef.current.push(`Assistant: ${content}`);
    if (conversationContextRef.current.length > 20) {
      conversationContextRef.current = conversationContextRef.current.slice(-20);
    }
  };

  // Start/stop conversation
  const toggleConversation = async () => {
    if (state === 'disconnected' || state === 'error') {
      userInitiatedDisconnectRef.current = false; // Reset flag when starting
      await initializeConversation();
    } else if (conversationRef.current) {
      userInitiatedDisconnectRef.current = true; // Mark as user-initiated disconnect
      await conversationRef.current.endSession();
      setState('disconnected');
      onActiveChange?.(false);
    }
  };

  // Restart conversation
  const restartConversation = async () => {
    await cleanup();
    isInitializingRef.current = false;
    await initializeConversation();
  };

  // Silent refresh - restart session without greeting to prevent context buildup slowdown
  const silentRefresh = async () => {
    console.log('🔄 Silently refreshing session to prevent slowdown...');
    isRefreshingRef.current = true;
    messageCountRef.current = 0; // Reset counter

    // End current session
    if (conversationRef.current) {
      try {
        await conversationRef.current.endSession();
      } catch (error) {
        console.error('Error ending session for refresh:', error);
      }
      conversationRef.current = null;
    }

    // Small delay to ensure clean disconnect
    await new Promise(resolve => setTimeout(resolve, 500));

    // Reinitialize without greeting
    isInitializingRef.current = false;
    await initializeConversation();
  };

  // Minimize/Expand controls
  const toggleMinimize = () => {
    setIsMinimized(!isMinimized);
  };

  const toggleExpand = () => {
    setIsExpanded(!isExpanded);
  };

  // State-based UI helpers
  const isConnecting = ['initializing', 'connecting'].includes(state);
  const isReady = ['connected', 'listening', 'processing', 'speaking'].includes(state);
  const isDisconnected = ['disconnected', 'error'].includes(state);
  const isActive = state !== 'disconnected' && state !== 'error';

  return (
    <div className={cn(
      "fixed z-50 bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 transition-all duration-300",
      isMinimized ? "w-12 h-12" : isExpanded ? "w-96 h-[600px]" : "w-80 h-[500px]",
      "right-4 bottom-4",
      className
    )}>
      {/* Main Interface */}
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
              {/* Language Toggle */}
              <button
                onClick={() => setLocale(locale === 'en' ? 'es' : 'en')}
                className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors flex items-center gap-1"
                title={`Language: ${locale === 'en' ? 'English' : 'Spanish'} (click to switch)`}
              >
                <Globe className="w-4 h-4" />
                <span className="text-xs font-medium uppercase">{locale}</span>
              </button>
              <button
                onClick={toggleExpand}
                className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                title={isExpanded ? "Collapse" : "Expand"}
              >
                {isExpanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
              </button>
              <button
                onClick={toggleMinimize}
                className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                title="Minimize"
              >
                <div className="w-4 h-1 bg-gray-500 dark:bg-gray-400" />
              </button>
            </div>
          </div>

          {/* Status Indicator */}
          <div className="px-3 py-2 text-xs text-center border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center justify-center gap-2">
              {state === 'initializing' && <div className="w-2 h-2 bg-gray-400 rounded-full animate-pulse" />}
              {state === 'connecting' && <div className="w-2 h-2 bg-yellow-500 rounded-full animate-pulse" />}
              {state === 'connected' && <div className="w-2 h-2 bg-green-500 rounded-full" />}
              {state === 'listening' && <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />}
              {state === 'processing' && <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />}
              {state === 'speaking' && <div className="w-2 h-2 bg-purple-500 rounded-full animate-pulse" />}
              {state === 'disconnected' && <div className="w-2 h-2 bg-gray-300 rounded-full" />}
              {state === 'error' && <div className="w-2 h-2 bg-red-600 rounded-full" />}
              
              <span className="text-gray-600 dark:text-gray-400 capitalize">
                {state === 'initializing' && 'Initializing...'}
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

          {/* Messages - Always visible, scrollable */}
          <div className={cn(
            "flex-1 overflow-y-auto p-3 space-y-2",
            isExpanded ? "max-h-[400px]" : "max-h-[280px]"
          )}>
            {messages.length === 0 ? (
              <div className="text-center text-gray-500 dark:text-gray-400 text-sm py-4">
                {isReady ? 'Listening... Speak now.' : 'Click Start to begin'}
              </div>
            ) : (
              messages.map((msg) => (
                <div key={msg.id} className={cn(
                  "flex gap-2",
                  msg.role === 'user' ? 'justify-end' : 'justify-start'
                )}>
                  {/* Role indicator */}
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
                    <div className="flex items-start gap-2">
                      <span>{msg.content}</span>
                    </div>
                    {msg.action && (
                      <div className="mt-1 text-xs opacity-75">
                        {msg.action.type === 'navigate' && `🔗 ${msg.action.target}`}
                        {msg.action.type === 'execute' && '⚡ Executed'}
                        {msg.action.type === 'info' && 'ℹ️'}
                      </div>
                    )}
                  </div>
                  {/* User indicator */}
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

          {/* Error Display */}
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
                  title="Settings"
                >
                  <Settings className="w-4 h-4 text-gray-600 dark:text-gray-300" />
                </button>
              )}
            </div>

            {/* Settings Panel (Compact View) */}
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
        /* Minimized State */
        <div className="flex items-center justify-center h-full">
          <button
            onClick={toggleMinimize}
            className="flex items-center justify-center w-full h-full hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors rounded-lg"
          >
            <img
              src="/AristAI_logo.png"
              alt="AristAI"
              className="w-8 h-8 object-contain"
              onError={(e) => {
                // Fallback to MessageSquare icon if image fails to load
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

