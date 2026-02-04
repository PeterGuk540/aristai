'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  Mic,
  MicOff,
  Volume2,
  X,
  Loader2,
  MessageSquare,
  ChevronUp,
  ChevronDown,
  Settings,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { useUser } from '@/lib/context';
import { loadElevenLabsSDK, type ElevenLabsConversation } from '@/lib/elevenlabs-sdk';
import { installInterceptors } from '@/lib/worklet-interceptor';
import { VoiceWaveformMini } from './VoiceWaveformMini';

export type ConversationState = 
  | 'initializing'
  | 'connecting' 
  | 'connected'
  | 'listening' 
  | 'processing' 
  | 'speaking' 
  | 'paused'
  | 'error'
  | 'disconnected';

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

export function ConversationalVoice({
  onNavigate,
  onActiveChange,
  autoStart = true,
  greeting,
  className,
}: ConversationalVoiceProps) {
  const router = useRouter();
  const { currentUser, isInstructor } = useUser();
  
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

  // Install interceptors once on component mount
  useEffect(() => {
    installInterceptors();
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
      const response = await fetch('/api/voice/agent/signed-url', {
        method: 'GET',
        headers: {
          'Authorization': `Bearer dummy-token`, // TODO: Replace with real auth
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to get signed URL: ${response.status} ${response.statusText}`);
      }

      const { signed_url } = await response.json();
      console.log('✅ Got signed URL:', signed_url.substring(0, 50) + '...');

      // Load the ElevenLabs SDK
      console.log('📦 Loading ElevenLabs SDK...');
      const Conversation = await loadElevenLabsSDK();

      // Start the conversation session
      console.log('🚀 Starting conversation session...');
      conversationRef.current = await Conversation.startSession({
        signedUrl: signed_url,
        connectionType: "websocket",
        onConnect: (data: { conversationId: string }) => {
          console.log('✅ Connected to ElevenLabs:', data.conversationId);
          setState('connected');
          onActiveChange?.(true);
          
          // Speak greeting
          if (greeting) {
            addAssistantMessage(greeting);
          } else {
            addAssistantMessage(`Hello ${currentUser?.name?.split(' ')[0] || 'there'}! I'm your voice assistant. How can I help you today?`);
          }
        },
        onDisconnect: (data?: any) => {
          console.log('🔌 Disconnected from ElevenLabs:', data);
          setState('disconnected');
          conversationRef.current = null;
          onActiveChange?.(false);
        },
        onStatusChange: (status: string) => {
          console.log('📊 Status changed:', status);
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
        onModeChange: (mode: string) => {
          console.log('🔄 Mode changed:', mode);
        },
        onMessage: (message: { source: "user" | "ai"; message: string }) => {
          console.log('💬 Message received:', message);
          
          if (message.source === 'user') {
            addUserMessage(message.message);
          } else if (message.source === 'ai') {
            addAssistantMessage(message.message);
          }
        },
        onError: (error: any) => {
          console.error('❌ ElevenLabs SDK error:', error);
          setError(`Connection error: ${error.message || 'Unknown error'}`);
          setState('error');
        },
        onDebug: (debug: any) => {
          console.log('🐛 Debug:', debug);
        },
      });

    } catch (error: any) {
      console.error('❌ Failed to initialize conversation:', error);
      setError(`Failed to connect: ${error.message}`);
      setState('error');
      isInitializingRef.current = false;
    }
  };

  const addUserMessage = (content: string) => {
    const message: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, message]);
    
    // Update conversation context
    conversationContextRef.current.push(`User: ${content}`);
    if (conversationContextRef.current.length > 10) {
      conversationContextRef.current = conversationContextRef.current.slice(-10);
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
    }
  };

  // Restart conversation
  const restartConversation = async () => {
    await cleanup();
    isInitializingRef.current = false;
    await initializeConversation();
  };

  // Get status text
  const getStatusText = () => {
    switch (state) {
      case 'initializing': return 'Starting...';
      case 'connecting': return 'Connecting...';
      case 'connected': return 'Connected';
      case 'listening': return 'Listening...';
      case 'processing': return 'Thinking...';
      case 'speaking': return 'Speaking...';
      case 'paused': return 'Paused';
      case 'disconnected': return 'Disconnected';
      case 'error': return 'Error';
      default: return '';
    }
  };

  // Get status color
  const getStatusColor = () => {
    switch (state) {
      case 'connecting': return 'bg-yellow-500';
      case 'connected': return 'bg-green-500';
      case 'listening': return 'bg-green-500';
      case 'processing': return 'bg-yellow-500';
      case 'speaking': return 'bg-blue-500';
      case 'paused': return 'bg-gray-500';
      case 'disconnected': return 'bg-gray-500';
      case 'error': return 'bg-red-500';
      default: return 'bg-gray-400';
    }
  };

  // Don't render for non-instructors
  if (!isInstructor) return null;

  return (
    <div className={cn(
      'fixed bottom-4 right-4 z-50',
      className
    )}>
      {/* Main panel */}
      <div className={cn(
        'bg-white dark:bg-gray-800 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 overflow-hidden transition-all duration-300',
        isMinimized ? 'w-auto' : isExpanded ? 'w-96' : 'w-80'
      )}>
        {/* Header - always visible */}
        <div 
          className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-primary-600 to-primary-700 text-white cursor-pointer"
          onClick={() => !isMinimized && setIsExpanded(!isExpanded)}
        >
          <div className="flex items-center gap-3">
            {/* Status indicator */}
            <div className="relative">
              <div className={cn(
                'w-3 h-3 rounded-full',
                getStatusColor(),
                (state === 'listening' || state === 'connected') && 'animate-pulse'
              )} />
              {(state === 'listening' || state === 'connected') && (
                <div className={cn(
                  'absolute inset-0 w-3 h-3 rounded-full animate-ping',
                  getStatusColor(),
                  'opacity-75'
                )} />
              )}
            </div>
            
            {!isMinimized && (
              <span className="font-medium text-sm">{getStatusText()}</span>
            )}
          </div>
          
          <div className="flex items-center gap-1">
            {!isMinimized && (
              <>
                <button
                  onClick={(e) => { e.stopPropagation(); setShowSettings(!showSettings); }}
                  className="p-1.5 rounded-lg hover:bg-white/20 transition-colors"
                >
                  <Settings className="h-4 w-4" />
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); toggleConversation(); }}
                  className="p-1.5 rounded-lg hover:bg-white/20 transition-colors"
                >
                  {(state === 'disconnected' || state === 'error') ? <Mic className="h-4 w-4" /> : <MicOff className="h-4 w-4" />}
                </button>
              </>
            )}
            <button
              onClick={(e) => { e.stopPropagation(); setIsMinimized(!isMinimized); }}
              className="p-1.5 rounded-lg hover:bg-white/20 transition-colors"
            >
              {isMinimized ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
          </div>
        </div>

        {/* Content - hidden when minimized */}
        {!isMinimized && (
          <>
            {/* Settings panel */}
            {showSettings && (
              <div className="p-4 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
                <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Voice Settings</h4>
                
                <div className="space-y-3">
                  <label className="flex items-center justify-between">
                    <span className="text-sm text-gray-600 dark:text-gray-400">Continuous conversation</span>
                    <input
                      type="checkbox"
                      checked={continuousMode}
                      onChange={(e) => setContinuousMode(e.target.checked)}
                      className="rounded border-gray-300"
                    />
                  </label>
                </div>
              </div>
            )}

            {/* Messages */}
            <div className={cn(
              'overflow-y-auto p-4 space-y-3',
              isExpanded ? 'max-h-96' : 'max-h-64'
            )}>
              {messages.length === 0 ? (
                <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                  <MessageSquare className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">
                    {state === 'connecting' ? 'Connecting to voice assistant...' : 'Tap the microphone to start'}
                  </p>
                </div>
              ) : (
                messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={cn(
                      'flex',
                      msg.role === 'user' ? 'justify-end' : 'justify-start'
                    )}
                  >
                    <div className={cn(
                      'max-w-[85%] rounded-2xl px-4 py-2',
                      msg.role === 'user'
                        ? 'bg-primary-600 text-white rounded-br-md'
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white rounded-bl-md'
                    )}>
                      <p className="text-sm">{msg.content}</p>
                      {msg.action?.type === 'navigate' && (
                        <p className="text-xs mt-1 opacity-75">
                          → Navigating to {msg.action.target}
                        </p>
                      )}
                    </div>
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Error display */}
            {error && (
              <div className="px-4 py-2 bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
                {error}
                <button
                  onClick={restartConversation}
                  className="ml-2 underline"
                >
                  Retry
                </button>
              </div>
            )}

            {/* Quick actions */}
            {(state === 'connected' || state === 'disconnected') && (
              <div className="px-4 py-3 bg-gray-50 dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700">
                <div className="flex flex-wrap gap-2">
                  <QuickAction onClick={() => addUserMessage("What would you like to do?")} label="Help" />
                  <QuickAction onClick={() => addUserMessage("Show my courses")} label="Courses" />
                  <QuickAction onClick={() => addUserMessage("Show live sessions")} label="Sessions" />
                  <QuickAction onClick={() => addUserMessage("Open forum")} label="Forum" />
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// Quick action button component
function QuickAction({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button
      onClick={onClick}
      className="px-3 py-1 text-xs rounded-full bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
    >
      {label}
    </button>
  );
}

export default ConversationalVoice;