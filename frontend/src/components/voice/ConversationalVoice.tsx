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
import { VoiceWaveformMini } from './VoiceWaveformMini';

export type ConversationState = 
  | 'initializing'
  | 'listening' 
  | 'processing' 
  | 'speaking' 
  | 'paused'
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
  const [audioLevel, setAudioLevel] = useState(0);
  const [error, setError] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  
  // Settings
  const [sensitivity, setSensitivity] = useState(0.02); // Voice activity detection threshold
  const [silenceTimeout, setSilenceTimeout] = useState(1500); // ms of silence before processing
  const [continuousMode, setContinuousMode] = useState(true);
  
  // Refs
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const animationFrameRef = useRef<number | null>(null);
  const silenceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isRecordingRef = useRef(false);
  const lastSpeechTimeRef = useRef<number>(Date.now());
  const conversationContextRef = useRef<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

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

  // Auto-start listening for instructors
  useEffect(() => {
    if (autoStart && isInstructor && currentUser && state === 'initializing') {
      // Small delay to let the page load
      const timer = setTimeout(() => {
        startListening();
        // Speak greeting
        if (greeting) {
          speakAndListen(greeting);
        } else {
          speakAndListen(`Hello ${currentUser.name.split(' ')[0]}! I'm your voice assistant. How can I help you today?`);
        }
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [autoStart, isInstructor, currentUser, state]);

  const cleanup = () => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
    }
    if (speechSynthesis.speaking) {
      speechSynthesis.cancel();
    }
  };

  // Voice activity detection
  const detectVoiceActivity = useCallback(() => {
    if (!analyserRef.current || !isRecordingRef.current) return;
    
    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
    analyserRef.current.getByteFrequencyData(dataArray);
    
    const average = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
    const normalizedLevel = average / 255;
    setAudioLevel(normalizedLevel);
    
    // Voice activity detection
    if (normalizedLevel > sensitivity) {
      lastSpeechTimeRef.current = Date.now();
      
      // Clear any existing silence timer
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current);
        silenceTimerRef.current = null;
      }
    } else if (isRecordingRef.current && state === 'listening') {
      // Check for silence
      const silenceDuration = Date.now() - lastSpeechTimeRef.current;
      
      if (silenceDuration > silenceTimeout && !silenceTimerRef.current) {
        // User stopped speaking, process the audio
        silenceTimerRef.current = setTimeout(() => {
          if (chunksRef.current.length > 0) {
            stopAndProcess();
          }
        }, 200);
      }
    }
    
    if (isRecordingRef.current) {
      animationFrameRef.current = requestAnimationFrame(detectVoiceActivity);
    }
  }, [sensitivity, silenceTimeout, state]);

  // Start listening
  const startListening = async () => {
    setError('');
    
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        }
      });
      streamRef.current = stream;
      
      // Set up audio analysis
      audioContextRef.current = new AudioContext();
      const source = audioContextRef.current.createMediaStreamSource(stream);
      analyserRef.current = audioContextRef.current.createAnalyser();
      analyserRef.current.fftSize = 256;
      source.connect(analyserRef.current);
      
      // Start MediaRecorder
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      chunksRef.current = [];
      
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };
      
      recorder.start(100); // Collect data every 100ms
      mediaRecorderRef.current = recorder;
      isRecordingRef.current = true;
      lastSpeechTimeRef.current = Date.now();
      
      setState('listening');
      onActiveChange?.(true);
      
      // Start voice activity detection
      detectVoiceActivity();
      
    } catch (err: any) {
      console.error('Failed to start listening:', err);
      setError('Microphone access denied');
      setState('error');
    }
  };

  // Stop recording and process
  const stopAndProcess = async () => {
    if (!mediaRecorderRef.current || mediaRecorderRef.current.state === 'inactive') return;
    
    isRecordingRef.current = false;
    
    // Stop the recorder
    mediaRecorderRef.current.stop();
    
    // Wait for final data
    await new Promise(resolve => setTimeout(resolve, 100));
    
    const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
    chunksRef.current = [];
    
    // Only process if there's enough audio
    if (blob.size > 1000) {
      await processAudio(blob);
    }
    
    // Restart listening if in continuous mode
    if (continuousMode && state !== 'error') {
      // Restart the recorder
      if (mediaRecorderRef.current && streamRef.current) {
        const recorder = new MediaRecorder(streamRef.current, { mimeType: 'audio/webm' });
        recorder.ondataavailable = (e) => {
          if (e.data.size > 0) {
            chunksRef.current.push(e.data);
          }
        };
        recorder.start(100);
        mediaRecorderRef.current = recorder;
        isRecordingRef.current = true;
        lastSpeechTimeRef.current = Date.now();
        
        if (state !== 'speaking') {
          setState('listening');
        }
        
        detectVoiceActivity();
      }
    }
  };

  // Process audio through the conversational API
  const processAudio = async (blob: Blob) => {
    setState('processing');
    
    try {
      // Transcribe
      const transcribeResult = await api.transcribeAudio(blob);
      const userText = transcribeResult.transcript.trim();
      
      if (!userText || userText.length < 2) {
        if (continuousMode) setState('listening');
        return;
      }
      
      // Add user message
      const userMessage: Message = {
        id: Date.now().toString(),
        role: 'user',
        content: userText,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, userMessage]);
      
      // Update conversation context
      conversationContextRef.current.push(`User: ${userText}`);
      if (conversationContextRef.current.length > 10) {
        conversationContextRef.current = conversationContextRef.current.slice(-10);
      }
      
      // Get conversational response
      const response = await api.voiceConverse({
        transcript: userText,
        context: conversationContextRef.current,
        user_id: currentUser?.id,
        current_page: window.location.pathname,
      });
      
      // Add assistant message
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.message,
        timestamp: new Date(),
        action: response.action,
      };
      setMessages(prev => [...prev, assistantMessage]);
      
      // Update context
      conversationContextRef.current.push(`Assistant: ${response.message}`);
      
      // Handle navigation
      if (response.action?.type === 'navigate' && response.action.target) {
        const target = response.action.target;
        // Speak then navigate
        await speakAndListen(response.message);
        
        setTimeout(() => {
          if (onNavigate) {
            onNavigate(target);
          } else {
            router.push(target);
          }
        }, 500);
        return;
      }
      
      // Handle execution results
      if (response.action?.type === 'execute' && response.results) {
        // Results are already included in the message
      }
      
      // Speak response and continue listening
      await speakAndListen(response.message);
      
    } catch (err: any) {
      console.error('Processing failed:', err);
      const errorMsg = "I'm sorry, I had trouble understanding that. Could you try again?";
      
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: errorMsg,
        timestamp: new Date(),
      }]);
      
      await speakAndListen(errorMsg);
    }
  };

  // Speak text and then resume listening
  const speakAndListen = (text: string): Promise<void> => {
    return new Promise((resolve) => {
      if (!('speechSynthesis' in window)) {
        resolve();
        return;
      }
      
      // Pause recording while speaking
      isRecordingRef.current = false;
      setState('speaking');
      
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      
      utterance.onend = () => {
        // Resume listening
        if (continuousMode && streamRef.current) {
          isRecordingRef.current = true;
          lastSpeechTimeRef.current = Date.now();
          setState('listening');
          detectVoiceActivity();
        } else {
          setState('paused');
        }
        resolve();
      };
      
      utterance.onerror = () => {
        if (continuousMode) {
          isRecordingRef.current = true;
          setState('listening');
          detectVoiceActivity();
        }
        resolve();
      };
      
      speechSynthesis.speak(utterance);
    });
  };

  // Pause/resume listening
  const togglePause = () => {
    if (state === 'listening') {
      isRecordingRef.current = false;
      setState('paused');
      onActiveChange?.(false);
    } else if (state === 'paused') {
      isRecordingRef.current = true;
      lastSpeechTimeRef.current = Date.now();
      setState('listening');
      onActiveChange?.(true);
      detectVoiceActivity();
    }
  };

  // Stop completely
  const stopListening = () => {
    cleanup();
    setState('paused');
    onActiveChange?.(false);
  };

  // Restart
  const restartListening = () => {
    cleanup();
    setTimeout(() => startListening(), 100);
  };

  // Get status text
  const getStatusText = () => {
    switch (state) {
      case 'initializing': return 'Starting...';
      case 'listening': return 'Listening...';
      case 'processing': return 'Thinking...';
      case 'speaking': return 'Speaking...';
      case 'paused': return 'Paused';
      case 'error': return 'Error';
      default: return '';
    }
  };

  // Get status color
  const getStatusColor = () => {
    switch (state) {
      case 'listening': return 'bg-green-500';
      case 'processing': return 'bg-yellow-500';
      case 'speaking': return 'bg-blue-500';
      case 'paused': return 'bg-gray-500';
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
                state === 'listening' && 'animate-pulse'
              )} />
              {state === 'listening' && (
                <div className={cn(
                  'absolute inset-0 w-3 h-3 rounded-full animate-ping',
                  getStatusColor(),
                  'opacity-75'
                )} />
              )}
            </div>
            
            {!isMinimized && (
              <>
                <span className="font-medium text-sm">{getStatusText()}</span>
                {state === 'listening' && (
                  <VoiceWaveformMini level={audioLevel} />
                )}
              </>
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
                  onClick={(e) => { e.stopPropagation(); togglePause(); }}
                  className="p-1.5 rounded-lg hover:bg-white/20 transition-colors"
                >
                  {state === 'paused' ? <Mic className="h-4 w-4" /> : <MicOff className="h-4 w-4" />}
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
                    <span className="text-sm text-gray-600 dark:text-gray-400">Continuous listening</span>
                    <input
                      type="checkbox"
                      checked={continuousMode}
                      onChange={(e) => setContinuousMode(e.target.checked)}
                      className="rounded border-gray-300"
                    />
                  </label>
                  
                  <div>
                    <label className="text-sm text-gray-600 dark:text-gray-400">
                      Silence detection ({silenceTimeout}ms)
                    </label>
                    <input
                      type="range"
                      min="500"
                      max="3000"
                      step="100"
                      value={silenceTimeout}
                      onChange={(e) => setSilenceTimeout(Number(e.target.value))}
                      className="w-full"
                    />
                  </div>
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
                  <p className="text-sm">Start speaking to interact</p>
                  <p className="text-xs mt-1">Try: "Show me my courses"</p>
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
                  onClick={restartListening}
                  className="ml-2 underline"
                >
                  Retry
                </button>
              </div>
            )}

            {/* Quick actions */}
            <div className="px-4 py-3 bg-gray-50 dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700">
              <div className="flex flex-wrap gap-2">
                <QuickAction onClick={() => speakAndListen("What would you like to do?")} label="Help" />
                <QuickAction onClick={() => processTextCommand("Show my courses")} label="Courses" />
                <QuickAction onClick={() => processTextCommand("Show live sessions")} label="Sessions" />
                <QuickAction onClick={() => processTextCommand("Open forum")} label="Forum" />
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );

  // Process a text command directly (for quick actions)
  async function processTextCommand(text: string) {
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMessage]);
    
    setState('processing');
    
    try {
      const response = await api.voiceConverse({
        transcript: text,
        context: conversationContextRef.current,
        user_id: currentUser?.id,
        current_page: window.location.pathname,
      });
      
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.message,
        timestamp: new Date(),
        action: response.action,
      };
      setMessages(prev => [...prev, assistantMessage]);
      
      if (response.action?.type === 'navigate' && response.action.target) {
        await speakAndListen(response.message);
        setTimeout(() => router.push(response.action!.target!), 500);
      } else {
        await speakAndListen(response.message);
      }
    } catch (err) {
      console.error(err);
      await speakAndListen("Sorry, I couldn't process that request.");
    }
  }
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
