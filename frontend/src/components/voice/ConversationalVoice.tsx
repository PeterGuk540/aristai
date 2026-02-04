'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
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

export function ConversationalVoice({
  onNavigate,
  onActiveChange,
  autoStart = true,
  greeting,
  className,
}: ConversationalVoiceProps) {
  const router = useRouter();
  const { currentUser, isInstructor, isAdmin } = useUser();

  const [state, setState] = useState<ConversationState>('idle');
  const [isExpanded, setIsExpanded] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [error, setError] = useState('');
  const [showSettings, setShowSettings] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
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
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    streamRef.current?.getTracks().forEach(track => track.stop());
    wsRef.current?.close();
    streamRef.current = null;
    mediaRecorderRef.current = null;
    wsRef.current = null;
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
      const ws = new WebSocket(signed_url);
      wsRef.current = ws;

      ws.onopen = async () => {
        setState('listening');
        await startMicrophone();
      };

      ws.onmessage = (event) => {
        handleAgentMessage(event.data);
      };

      ws.onerror = () => {
        setError('Realtime voice connection failed.');
        setState('error');
      };

      ws.onclose = () => {
        if (!isStoppingRef.current) {
          setState('paused');
        }
      };
    } catch (err) {
      console.error('Failed to start ElevenLabs session:', err);
      setError('Failed to start realtime voice session.');
      setState('error');
    }
  };

  const startMicrophone = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      streamRef.current = stream;
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = async (event) => {
        if (!event.data.size || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
          return;
        }
        const base64 = await blobToBase64(event.data);
        const payload = {
          user_audio_chunk: base64,
        };
        wsRef.current.send(JSON.stringify(payload));
      };

      recorder.start(250);
    } catch (err) {
      console.error('Microphone access failed:', err);
      setError('Microphone access denied.');
      setState('error');
    }
  };

  const handleAgentMessage = (raw: Blob | ArrayBuffer | string) => {
    if (typeof raw !== 'string') {
      const blob = raw instanceof Blob ? raw : new Blob([raw]);
      enqueueAudio(blob);
      return;
    }

    try {
      const data = JSON.parse(raw);
      const transcript =
        data.transcript ||
        data.text ||
        data.user_transcript ||
        data.agent_transcript;
      if (transcript) {
        const role = normalizeRole(data.role || data.speaker || data.type);
        appendMessage(role, transcript);
      }

      const audioBase64 = data.audio || data.audio_base64;
      if (audioBase64) {
        const audioBlob = base64ToBlob(audioBase64, data.audio_format || 'audio/mpeg');
        enqueueAudio(audioBlob);
      }

      if (data.action?.type === 'navigate' && data.action.target) {
        if (onNavigate) {
          onNavigate(data.action.target);
        } else {
          router.push(data.action.target);
        }
      }
    } catch (err) {
      console.warn('Failed to parse agent message', err);
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

const blobToBase64 = (blob: Blob): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result?.toString() || '';
      const base64 = result.split(',')[1] || '';
      resolve(base64);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });

const base64ToBlob = (base64: string, mimeType: string): Blob => {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new Blob([bytes], { type: mimeType });
};

const normalizeRole = (raw?: string): Message['role'] => {
  if (!raw) return 'assistant';
  const value = raw.toLowerCase();
  if (value.includes('user')) return 'user';
  return 'assistant';
};

export default ConversationalVoice;
