'use client';

import { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Conversation } from '@elevenlabs/client';
import { Volume2, Mic, MicOff, Settings, Minimize2, Maximize2, MessageSquare, Sparkles } from 'lucide-react';
import { useUser } from '@/lib/context';
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

const MCP_RESPONSE_PREFIX = 'MCP_RESPONSE:';

export function ConversationalVoice(props: ConversationalVoiceProps) {
  const {
    onActiveChange,
    autoStart = true,
    greeting,
    className,
  } = props;
  const { currentUser, isInstructor } = useUser();
  const router = useRouter();
  
  // Core state
  const [state, setState] = useState<ConversationState>('initializing');
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

  // Auto-start connection for instructors
  useEffect(() => {
    if (autoStart && isInstructor && currentUser && state === 'initializing' && !isInitializingRef.current) {
      isInitializingRef.current = true;
      const timer = setTimeout(() => {
        initializeConversation();
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [autoStart, isInstructor, currentUser, state]);

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

  const initializeConversation = async () => {
    setState('connecting');
    setError('');

    try {
      // Get signed URL from our backend
      console.log('🔑 Getting signed URL from backend...');
      // Use relative URL for all environments to leverage Next.js API routes
      const apiUrl = '/api';
      const response = await fetch(`${apiUrl}/voice/agent/signed-url`, {
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
          
          // Speak greeting
          if (greeting) {
            addAssistantMessage(greeting);
          } else {
            addAssistantMessage(`Hello ${currentUser?.name?.split(' ')[0] || 'there'}! I'm your AristAI assistant, an expert in educational platform operations. I can help you navigate instantly to any page, create courses with AI-generated plans, manage live sessions, create polls, generate comprehensive reports, and much more. Just tell me what you'd like to do!`);
          }
        },
        onDisconnect: (data?: any) => {
          console.log('🔌 Disconnected from AristAI voice service:', data);
          setState('disconnected');
          conversationRef.current = null;
          onActiveChange?.(false);
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
            // Add user message (this should be the transcribed speech)
            addUserMessage(message);
            console.log('🎤 User speech transcribed:', message);
            
            // Emit transcription event
            if (typeof window !== 'undefined') {
              window.dispatchEvent(new CustomEvent('voice-transcription', {
                detail: `[${new Date().toISOString()}] Transcription: ${message}`
              }));
            }
            handleTranscript(message);
          } else if (source === 'ai') {
            // ElevenLabs agent responses are not used as final product output.
            console.log('🤖 Ignoring ElevenLabs agent response:', message);
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
          // Optional: Handle audio data if needed for debugging
          console.log('🔊 Audio received:', audio);
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

  const extractUiActions = (results: any[] | undefined, action?: { type?: string; target?: string }): UiAction[] => {
    const uiActionsFromResults = (results ?? []).flatMap((result) => {
      if (!result) return [];
      const direct = result.ui_actions ?? result.result?.ui_actions;
      if (Array.isArray(direct)) {
        return direct;
      }
      return [];
    });

    const actionFromResponse: UiAction[] = [];
    if (action?.type === 'navigate' && action?.target) {
      actionFromResponse.push({ type: 'ui.navigate', payload: { path: action.target } });
    }

    return [...uiActionsFromResults, ...actionFromResponse];
  };

  const speakViaElevenLabs = (text: string) => {
    if (!text || !conversationRef.current) {
      return;
    }
    try {
      conversationRef.current.sendUserMessage(`${MCP_RESPONSE_PREFIX}${text}`);
    } catch (error) {
      console.error('❌ Failed to send MCP message to ElevenLabs:', error);
    }
  };

  const handleTranscript = async (transcript: string) => {
    if (!transcript || isProcessingTranscriptRef.current) {
      return;
    }

    isProcessingTranscriptRef.current = true;
    try {
      const currentPage = typeof window !== 'undefined' ? window.location.pathname : undefined;
      const response = await api.voiceConverse({
        transcript,
        user_id: currentUser?.id,
        current_page: currentPage,
      });

      const uiActions = extractUiActions(response.results, response.action);
      uiActions.forEach((action) => executeUiAction(action, router));

      if (response.message) {
        addAssistantMessage(response.message);
        speakViaElevenLabs(response.message);
      }
    } catch (error) {
      console.error('❌ MCP voice converse failed:', error);
      setError('Unable to reach MCP service. Please try again.');
    } finally {
      isProcessingTranscriptRef.current = false;
    }
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
    
    // Update context
    conversationContextRef.current.push(`User: ${content}`);
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
    
    // Update context
    conversationContextRef.current.push(`Assistant: ${content}`);
  };

  // Start/stop conversation
  const toggleConversation = async () => {
    if (state === 'disconnected' || state === 'error') {
      await initializeConversation();
    } else if (conversationRef.current) {
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

          {/* Messages */}
          {isExpanded && (
            <div className="flex-1 overflow-y-auto p-3 space-y-2">
              {messages.length === 0 ? (
                <div className="text-center text-gray-500 dark:text-gray-400 text-sm py-8">
                  {isReady ? 'Start speaking when you see the listening indicator...' : 'Click start to begin voice conversation'}
                </div>
              ) : (
                messages.map((msg) => (
                  <div key={msg.id} className={cn(
                    "flex gap-2",
                    msg.role === 'user' ? 'justify-end' : 'justify-start'
                  )}>
                    <div className={cn(
                      "max-w-[80%] px-3 py-2 rounded-lg text-sm",
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
                          {msg.action.type === 'execute' && '⚡ Executing...'}
                          {msg.action.type === 'info' && 'ℹ️'}
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>
          )}

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
            <MessageSquare className="w-5 h-5 text-gray-600 dark:text-gray-300" />
            {isActive && (
              <div className="absolute top-2 right-2 w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            )}
          </button>
        </div>
      )}
    </div>
  );
}
