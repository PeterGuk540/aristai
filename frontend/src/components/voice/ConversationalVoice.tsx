'use client';

import { useEffect, useRef, useState } from 'react';
import {
  ChevronDown,
  ChevronUp,
  Loader2,
  Mic,
  MicOff,
  MessageSquare,
  Settings,
  Volume2,
} from 'lucide-react';

import { Conversation } from '@elevenlabs/client';
import { api } from '@/lib/api';
import { useUser } from '@/lib/context';
import { cn } from '@/lib/utils';

export type ConversationState =
  | 'idle'
  | 'connecting'
  | 'listening'
  | 'speaking'
  | 'paused'
  | 'error';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
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

type AudioQueueItem = {
  blob: Blob;
};

type ConversationSession = {
  on?: (event: string, handler: (...args: any[]) => void) => void;
  off?: (event: string, handler: (...args: any[]) => void) => void;
  endSession?: () => Promise<void> | void;
  close?: () => Promise<void> | void;
  startMicrophone?: () => Promise<void> | void;
  stopMicrophone?: () => Promise<void> | void;
  startRecording?: () => Promise<void> | void;
  stopRecording?: () => Promise<void> | void;
};

export function ConversationalVoice({
  onNavigate,
  onActiveChange,
  autoStart = true,
  greeting,
  className,
}: ConversationalVoiceProps) {
  const { currentUser, isInstructor, isAdmin } = useUser();

  const [state, setState] = useState<ConversationState>('idle');
  const [isExpanded, setIsExpanded] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [error, setError] = useState('');
  const [showSettings, setShowSettings] = useState(false);

  const sessionRef = useRef<ConversationSession | null>(null);
  const audioQueueRef = useRef<AudioQueueItem[]>([]);
  const isPlayingRef = useRef(false);
  const isStoppingRef = useRef(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    return () => cleanup();
  }, []);

  useEffect(() => {
    const active = state === 'connecting' || state === 'listening' || state === 'speaking';
    onActiveChange?.(active);
  }, [state, onActiveChange]);

  useEffect(() => {
    if (autoStart && (isInstructor || isAdmin) && currentUser && state === 'idle') {
      const timer = setTimeout(() => {
        void startSession();
        if (greeting) {
          appendMessage('assistant', greeting);
        }
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [autoStart, currentUser, greeting, isInstructor, isAdmin, state]);

  const cleanup = () => {
    isStoppingRef.current = true;
    void endSdkSession();
    sessionRef.current = null;
    audioQueueRef.current = [];
    isPlayingRef.current = false;
  };

  const appendMessage = (role: Message['role'], content: string) => {
    setMessages(prev => [
      ...prev,
      { id: `${Date.now()}-${Math.random()}`, role, content, timestamp: new Date() },
    ]);
  };

  const enqueueAudio = (blob: Blob) => {
    audioQueueRef.current.push({ blob });
    if (!isPlayingRef.current) {
      void playNextAudio();
    }
  };

  const playNextAudio = async () => {
    const next = audioQueueRef.current.shift();
    if (!next) {
      isPlayingRef.current = false;
      if (!isStoppingRef.current) {
        setState('listening');
      }
      return;
    }

    isPlayingRef.current = true;
    setState('speaking');

    const url = URL.createObjectURL(next.blob);
    const audio = new Audio(url);
    audio.onended = () => {
      URL.revokeObjectURL(url);
      void playNextAudio();
    };
    audio.onerror = () => {
      URL.revokeObjectURL(url);
      void playNextAudio();
    };
    await audio.play();
  };

  const startSession = async () => {
    setError('');
    isStoppingRef.current = false;
    setState('connecting');

    try {
      const { signed_url } = await api.voiceAgentSignedUrl();
      const session = await Conversation.startSession({
        signedUrl: signed_url,
        connectionType: 'websocket',
      });

      sessionRef.current = session as ConversationSession;
      registerSessionHandlers(sessionRef.current);
      await startSdkMicrophone();
      setState('listening');
    } catch (err) {
      console.error('Failed to start ElevenLabs session:', err);
      setError('Failed to start realtime voice session.');
      setState('error');
    }
  };

  const registerSessionHandlers = (session: ConversationSession | null) => {
    if (!session?.on) return;

    session.on('transcript', (payload: any) => {
      const transcript = payload?.text ?? payload?.transcript;
      if (!transcript) return;
      const role = normalizeRole(payload?.role ?? payload?.speaker);
      appendMessage(role, transcript);
    });

    session.on('message', (payload: any) => {
      const transcript = payload?.text ?? payload?.transcript;
      if (!transcript) return;
      const role = normalizeRole(payload?.role ?? payload?.speaker);
      appendMessage(role, transcript);

      if (payload?.action?.type === 'navigate' && payload?.action?.target && onNavigate) {
        onNavigate(payload.action.target);
      }
    });

    session.on('audio', (payload: any) => {
      const blob = payload instanceof Blob ? payload : new Blob([payload]);
      enqueueAudio(blob);
    });

    session.on('connection_state', (payload: any) => {
      const stateValue = `${payload?.state ?? payload}`.toLowerCase();
      if (stateValue.includes('connecting')) setState('connecting');
      if (stateValue.includes('listening')) setState('listening');
      if (stateValue.includes('speaking')) setState('speaking');
      if (stateValue.includes('closed')) setState('paused');
    });

    session.on('error', (payload: any) => {
      console.error('ElevenLabs session error:', payload);
      setError('Realtime voice session error.');
      setState('error');
    });
  };

  const startSdkMicrophone = async () => {
    const session = sessionRef.current;
    if (!session) return;
    if (session.startMicrophone) {
      await session.startMicrophone();
      return;
    }
    if (session.startRecording) {
      await session.startRecording();
      return;
    }
    console.warn('ElevenLabs SDK microphone start method not found.');
  };

  const endSdkSession = async () => {
    const session = sessionRef.current;
    if (!session) return;
    if (session.stopMicrophone) {
      await session.stopMicrophone();
    } else if (session.stopRecording) {
      await session.stopRecording();
    }

    if (session.endSession) {
      await session.endSession();
    } else if (session.close) {
      await session.close();
    }
  };

  const stopSession = () => {
    cleanup();
    setState('paused');
  };

  const restartSession = () => {
    cleanup();
    setState('idle');
    void startSession();
  };

  const getStatusText = () => {
    switch (state) {
      case 'idle':
        return 'Ready';
      case 'connecting':
        return 'Connecting...';
      case 'listening':
        return 'Listening...';
      case 'speaking':
        return 'Speaking...';
      case 'paused':
        return 'Paused';
      case 'error':
        return 'Error';
      default:
        return '';
    }
  };

  const getStatusColor = () => {
    switch (state) {
      case 'listening':
        return 'bg-green-500';
      case 'speaking':
        return 'bg-blue-500';
      case 'connecting':
        return 'bg-yellow-500';
      case 'paused':
        return 'bg-gray-500';
      case 'error':
        return 'bg-red-500';
      default:
        return 'bg-gray-400';
    }
  };

  if (!isInstructor && !isAdmin) return null;

  return (
    <div className={cn('fixed bottom-4 right-4 z-50', className)}>
      <div
        className={cn(
          'bg-white dark:bg-gray-800 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 overflow-hidden transition-all duration-300',
          isMinimized ? 'w-auto' : isExpanded ? 'w-96' : 'w-80'
        )}
      >
        <div
          className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-primary-600 to-primary-700 text-white cursor-pointer"
          onClick={() => !isMinimized && setIsExpanded(!isExpanded)}
        >
          <div className="flex items-center gap-3">
            <div className="relative">
              <div
                className={cn(
                  'w-3 h-3 rounded-full',
                  getStatusColor(),
                  state === 'listening' && 'animate-pulse'
                )}
              />
              {state === 'listening' && (
                <div
                  className={cn(
                    'absolute inset-0 w-3 h-3 rounded-full animate-ping',
                    getStatusColor(),
                    'opacity-75'
                  )}
                />
              )}
            </div>

            {!isMinimized && (
              <>
                <span className="font-medium text-sm">{getStatusText()}</span>
                {state === 'speaking' && <Volume2 className="h-4 w-4 animate-pulse" />}
                {state === 'connecting' && <Loader2 className="h-4 w-4 animate-spin" />}
              </>
            )}
          </div>

          <div className="flex items-center gap-1">
            {!isMinimized && (
              <>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowSettings(!showSettings);
                  }}
                  className="p-1.5 rounded-lg hover:bg-white/20 transition-colors"
                >
                  <Settings className="h-4 w-4" />
                </button>
                {state === 'listening' || state === 'speaking' ? (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      stopSession();
                    }}
                    className="p-1.5 rounded-lg hover:bg-white/20 transition-colors"
                  >
                    <MicOff className="h-4 w-4" />
                  </button>
                ) : (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      void startSession();
                    }}
                    className="p-1.5 rounded-lg hover:bg-white/20 transition-colors"
                  >
                    <Mic className="h-4 w-4" />
                  </button>
                )}
              </>
            )}
            <button
              onClick={(e) => {
                e.stopPropagation();
                setIsMinimized(!isMinimized);
              }}
              className="p-1.5 rounded-lg hover:bg-white/20 transition-colors"
            >
              {isMinimized ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
          </div>
        </div>

        {!isMinimized && (
          <>
            {showSettings && (
              <div className="p-4 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
                <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                  Realtime Agent Settings
                </h4>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  This voice chat connects to ElevenLabs realtime Agents using a signed URL from the backend.
                </p>
              </div>
            )}

            <div
              className={cn(
                'overflow-y-auto p-4 space-y-3',
                isExpanded ? 'max-h-96' : 'max-h-64'
              )}
            >
              {messages.length === 0 ? (
                <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                  <MessageSquare className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">Press start to talk with your agent</p>
                  <p className="text-xs mt-1">Audio streams to ElevenLabs in realtime</p>
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
                    <div
                      className={cn(
                        'max-w-[85%] rounded-2xl px-4 py-2',
                        msg.role === 'user'
                          ? 'bg-primary-600 text-white rounded-br-md'
                          : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white rounded-bl-md'
                      )}
                    >
                      <p className="text-sm">{msg.content}</p>
                    </div>
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            {error && (
              <div className="px-4 py-2 bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
                {error}
                <button onClick={restartSession} className="ml-2 underline">
                  Retry
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

const normalizeRole = (raw?: string): Message['role'] => {
  if (!raw) return 'assistant';
  const value = raw.toLowerCase();
  if (value.includes('user')) return 'user';
  return 'assistant';
};

export default ConversationalVoice;
