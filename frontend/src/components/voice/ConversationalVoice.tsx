'use client';

import { useEffect, useState, useRef } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { Mic, MicOff, Settings, Minimize2, Maximize2, MessageSquare, Sparkles } from 'lucide-react';
import { useUser } from '@/lib/context';
import { cn } from '@/lib/utils';
import { executeUiAction, type UiAction } from '@/lib/ui-actions';

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

const RECORD_DURATION_MS = 8000;

export function ConversationalVoice({
  onNavigate,
  onActiveChange,
  autoStart = true,
  greeting,
  className,
}: ConversationalVoiceProps) {
  const router = useRouter();
  const pathname = usePathname();
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
  const conversationContextRef = useRef<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isInitializingRef = useRef(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const recordTimeoutRef = useRef<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const sessionActiveRef = useRef(false);

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
        initializeVoiceSession();
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [autoStart, isInstructor, currentUser, state]);

  const cleanup = async () => {
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    if (recordTimeoutRef.current) {
      window.clearTimeout(recordTimeoutRef.current);
      recordTimeoutRef.current = null;
    }
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
  };

  const initializeVoiceSession = async () => {
    setState('connecting');
    setError('');

    try {
      sessionActiveRef.current = true;
      setState('connected');
      onActiveChange?.(true);
      const greetingText = greeting
        || `Hello ${currentUser?.name?.split(' ')[0] || 'there'}! I'm your AristAI assistant. Tell me what you'd like to do.`;
      await speakAndResume(greetingText, false);
      if (continuousMode) {
        await startListening();
      }
    } catch (error: any) {
      console.error('❌ Failed to initialize voice session:', error);
      setError('Failed to initialize voice session.');
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
    conversationContextRef.current.push(`Assistant: ${content}`);
  };

  const executeUIActions = (actions: UiAction[]) => {
    actions.forEach((action) => executeUiAction(action, router));
  };

  const playTTS = async (message: string) => {
    setState('speaking');
    const response = await fetch('/api/voice/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: message }),
    });
    if (!response.ok) {
      throw new Error(`TTS failed: ${response.status}`);
    }
    const audioBlob = await response.blob();
    const audioUrl = URL.createObjectURL(audioBlob);
    if (audioRef.current) {
      audioRef.current.pause();
    }
    audioRef.current = new Audio(audioUrl);
    await new Promise<void>((resolve, reject) => {
      if (!audioRef.current) {
        resolve();
        return;
      }
      audioRef.current.onended = () => resolve();
      audioRef.current.onerror = () => reject(new Error('Audio playback failed'));
      audioRef.current.play().catch(reject);
    });
    URL.revokeObjectURL(audioUrl);
  };

  const speakAndResume = async (message: string, resumeListening = true) => {
    addAssistantMessage(message);
    await playTTS(message);
    if (resumeListening && continuousMode && sessionActiveRef.current) {
      await startListening();
    } else {
      setState('connected');
    }
  };

  const transcribeAudio = async (audioBlob: Blob): Promise<string> => {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'voice.webm');
    const response = await fetch('/api/voice/asr', {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      throw new Error(`ASR failed: ${response.status}`);
    }
    const data = await response.json();
    return data.transcript || '';
  };

  const handleTranscript = async (transcript: string) => {
    if (!transcript) {
      setState('connected');
      if (continuousMode && sessionActiveRef.current) {
        await startListening();
      }
      return;
    }

    addUserMessage(transcript);
    setState('processing');

    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('voice-transcription', {
        detail: `[${new Date().toISOString()}] Transcription: ${transcript}`
      }));
    }

    const response = await fetch('/api/voice-converse/voice/converse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        transcript,
        user_id: currentUser?.id,
        current_page: pathname ?? undefined,
      }),
    });

    if (!response.ok) {
      throw new Error(`MCP request failed: ${response.status}`);
    }

    const { message, action, results } = await response.json();

    if (results?.[0]?.ui_actions) {
      executeUIActions(results[0].ui_actions);
    }

    await speakAndResume(message, true);

    if (action?.type === 'navigate' && action?.target && onNavigate) {
      onNavigate(action.target);
    }
  };

  const startListening = async () => {
    if (!sessionActiveRef.current) {
      return;
    }
    if (mediaRecorderRef.current?.state === 'recording') {
      return;
    }
    setState('listening');
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaStreamRef.current = stream;
    const recorder = new MediaRecorder(stream);
    const chunks: BlobPart[] = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        chunks.push(event.data);
      }
    };
    recorder.onstop = async () => {
      const audioBlob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' });
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
      mediaRecorderRef.current = null;
      if (recordTimeoutRef.current) {
        window.clearTimeout(recordTimeoutRef.current);
        recordTimeoutRef.current = null;
      }
      if (!sessionActiveRef.current) {
        return;
      }
      try {
        const transcript = await transcribeAudio(audioBlob);
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('voice-message', {
            detail: `[${new Date().toISOString()}] user: ${transcript}`
          }));
        }
        await handleTranscript(transcript);
      } catch (error) {
        console.error('❌ Voice processing error:', error);
        setError('Voice processing failed. Please try again.');
        setState('error');
      }
    };
    mediaRecorderRef.current = recorder;
    recorder.start();
    recordTimeoutRef.current = window.setTimeout(() => {
      if (recorder.state === 'recording') {
        recorder.stop();
      }
    }, RECORD_DURATION_MS);
  };

  const stopListening = () => {
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    if (recordTimeoutRef.current) {
      window.clearTimeout(recordTimeoutRef.current);
      recordTimeoutRef.current = null;
    }
  };

  // Start/stop conversation
  const toggleConversation = async () => {
    if (state === 'disconnected' || state === 'error') {
      await initializeVoiceSession();
    } else {
      sessionActiveRef.current = false;
      stopListening();
      await cleanup();
      setState('disconnected');
      onActiveChange?.(false);
    }
  };

  // Restart conversation
  const restartConversation = async () => {
    await cleanup();
    isInitializingRef.current = false;
    await initializeVoiceSession();
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
