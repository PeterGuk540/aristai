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
import { Conversation } from "@elevenlabs/client";

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

// MCP Tool Execution for "I speak, you do" functionality
const executeMCPTool = async (
  toolName: string, 
  args: any,
  addAssistantMessage: (content: string, action?: Message['action']) => void
): Promise<boolean> => {
  try {
    console.log('🔧 Executing MCP tool:', { toolName, args });
    
    const response = await fetch('/api/mcp/execute', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ tool: toolName, arguments: args }),
    });

    if (!response.ok) {
      console.error('MCP tool execution failed:', response.status);
      addAssistantMessage(`❌ Failed to execute ${toolName}. Please try again.`);
      return false;
    }

    const result = await response.json();
    console.log('✅ MCP tool executed successfully:', result);
    
    // Provide user-friendly feedback
    addAssistantMessage(`✅ ${toolName} executed successfully.`);
    return true;
    
  } catch (error) {
    console.error('MCP execution error:', error);
    addAssistantMessage(`❌ Error executing ${toolName}: ${error}`);
    return false;
  }
};

const handleActionExecution = async (message: string, onNavigate?: (path: string) => void) => {
  const lowerMessage = message.toLowerCase();
  
  // Navigation actions - still handle directly for better UX
  if (lowerMessage.includes('navigating to') || lowerMessage.includes('take you to')) {
    const pathMatch = message.match(/(?:to|page|section)\s+(.+?)(?:\.|\s|$)/i);
    if (pathMatch && onNavigate) {
      const path = extractPathFromText(pathMatch[1]);
      setTimeout(() => onNavigate(path), 1500);
    }
    return;
  }

  // Course creation via MCP
  if (lowerMessage.includes('create course') || lowerMessage.includes('create a course')) {
    const courseTitle = extractCourseTitle(message);
    if (courseTitle) {
      await executeMCPTool('create_course', { title: courseTitle }, addAssistantMessage);
    }
  }
  
  // Poll creation via MCP  
  if (lowerMessage.includes('create poll') || lowerMessage.includes('create a poll')) {
    const pollData = extractPollData(message);
    if (pollData) {
      await executeMCPTool('create_poll', pollData, addAssistantMessage);
    }
  }
  
  // Report generation via MCP
  if (lowerMessage.includes('generate report') || lowerMessage.includes('create report')) {
    const reportData = extractReportData(message);
    if (reportData) {
      await executeMCPTool('generate_report', reportData, addAssistantMessage);
    }
  }
  
  // Student enrollment via MCP
  if (lowerMessage.includes('enroll students') || lowerMessage.includes('enroll student')) {
    const enrollmentData = extractEnrollmentData(message);
    if (enrollmentData) {
      await executeMCPTool('enroll_students', enrollmentData, addAssistantMessage);
    }
  }
};

const extractCourseTitle = (message: string): string | null => {
  const match = message.match(/(?:course|create).+?(?:called|titled|named)?\s+["'"](.+?)["'"]/i);
  return match ? match[1] : null;
};

const extractPollData = (message: string): any => {
  const questionMatch = message.match(/(?:poll|create).+?(?:question)?\s+["'"](.+?)["'"]/i);
  if (!questionMatch) return null;
  
  const question = questionMatch[1];
  
  // Try to extract options
  const optionsMatch = message.match(/options?[:\s]+(.+?)(?:\.|$)/i);
  if (optionsMatch) {
    const optionsText = optionsMatch[1];
    const options = optionsText.split(/(?:,\s*|\s+and\s+)/).map(opt => opt.trim().replace(/["']/g, ''));
    if (options.length >= 2) {
      return { question, options_json: options };
    }
  }
  
  return { question, options_json: ["Yes", "No", "Maybe"] };
};

const extractReportData = (message: string): any => {
  const sessionMatch = message.match(/(?:report|generate).+?(?:session)?\s+["'"]?(.+?)["'"]?/i);
  if (sessionMatch) {
    return { session_id_or_title: sessionMatch[1] };
  }
  return null;
};

const extractEnrollmentData = (message: string): any => {
  const courseMatch = message.match(/(?:enroll).+?(?:course)?\s+["'"](.+?)["'"]/i);
  const studentMatch = message.match(/(?:enroll).+?(?:students?)\s+(.+?)(?:\.|$)/i);
  
  const data: any = {};
  if (courseMatch) data.course_title = courseMatch[1];
  if (studentMatch) data.student_identifiers = studentMatch[1].split(/(?:,\s*|\s+and\s+)/);
  
  return Object.keys(data).length > 0 ? data : null;
};

const extractPathFromText = (text: string): string => {
  const pathMap: { [key: string]: string } = {
    'courses': '/courses',
    'course': '/courses', 
    'sessions': '/sessions',
    'session': '/sessions',
    'dashboard': '/dashboard',
    'home': '/dashboard',
    'forum': '/forum',
    'reports': '/reports',
    'console': '/console',
    'settings': '/console'
  };
  
  const lowerText = text.toLowerCase().trim();
  
  // Direct path matches
  if (lowerText in pathMap) {
    return pathMap[lowerText];
  }
  
  // Partial matches
  for (const [key, path] of Object.entries(pathMap)) {
    if (lowerText.includes(key)) {
      return path;
    }
  }
  
  return '/dashboard'; // fallback
};

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
      // For production, use proxy route to avoid mixed-content issues
      const apiUrl = process.env.NODE_ENV === 'production' 
        ? '/api/proxy'  // Uses Next.js proxy (same origin)
        : (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000');
      const response = await fetch(`${apiUrl}/voice/agent/signed-url`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer dummy-token`, // TODO: Replace with real auth
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        let errorMessage = 'Failed to get signed URL';
        let errorCode = 'E_UNKNOWN';
        
        switch (response.status) {
          case 401:
            errorMessage = 'Authentication failed. Please check your credentials.';
            errorCode = 'E_AUTH';
            break;
          case 403:
            errorMessage = 'Access denied. You do not have permission to use voice features.';
            errorCode = 'E_AUTH';
            break;
          case 429:
            errorMessage = 'Too many requests. Please try again later.';
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
        
        throw new Error(`${errorMessage} (${errorCode})`);
      }

      const { signed_url } = await response.json();
      console.log('✅ Got signed URL:', signed_url.substring(0, 50) + '...');

      // Start the conversation session using the official SDK
      console.log('🚀 Starting conversation session...');
      conversationRef.current = await Conversation.startSession({
        signedUrl: signed_url,
        connectionType: "websocket",
        onConnect: ({ conversationId }: { conversationId: string }) => {
          console.log('✅ Connected to ElevenLabs:', conversationId);
          setState('connected');
          onActiveChange?.(true);
          
          // Speak greeting
          if (greeting) {
            addAssistantMessage(greeting);
          } else {
            addAssistantMessage(`Hello ${currentUser?.name?.split(' ')[0] || 'there'}! I'm your AristAI assistant. How can I help you today?`);
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
          
          if (source === 'user') {
            addUserMessage(message);
          } else if (source === 'ai') {
            addAssistantMessage(message);
            
            // Auto-execute actions based on AI message content
            handleActionExecution(message, onNavigate);
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
            } else {
              errorMessage = `Voice service error: ${error}`;
              errorCode = 'E_11LABS_ERROR';
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
      
      let errorMessage = 'Failed to initialize voice conversation';
      let errorCode = 'E_INIT_UNKNOWN';
      
      if (error.message) {
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
        } else {
          errorMessage = error.message;
          errorCode = 'E_INIT_CUSTOM';
        }
      }
      
      setError(`${errorMessage} (${errorCode})`);
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