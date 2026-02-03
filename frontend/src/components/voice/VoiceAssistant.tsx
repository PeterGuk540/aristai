'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Settings,
  X,
  Loader2,
  CheckCircle,
  AlertCircle,
  Radio,
  Square,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { VoicePlan, VoiceStepResult } from '@/types';
import { api } from '@/lib/api';
import { useUser } from '@/lib/context';
import { VoiceWaveform } from './VoiceWaveform';
import { VoicePlanPreview } from './VoicePlanPreview';
import { VoiceSettings } from './VoiceSettings';

export type VoiceMode = 'push-to-talk' | 'wake-word' | 'continuous';
export type VoiceState = 'idle' | 'listening' | 'processing' | 'speaking' | 'confirming' | 'error';

export interface VoiceAssistantProps {
  className?: string;
  defaultMode?: VoiceMode;
  onTranscript?: (transcript: string) => void;
  onPlan?: (plan: VoicePlan) => void;
  onResult?: (results: VoiceStepResult[], summary: string) => void;
  onError?: (error: string) => void;
  compact?: boolean;
}

export function VoiceAssistant({
  className,
  defaultMode = 'push-to-talk',
  onTranscript,
  onPlan,
  onResult,
  onError,
  compact = false,
}: VoiceAssistantProps) {
  const { currentUser } = useUser();
  
  // Core state
  const [mode, setMode] = useState<VoiceMode>(defaultMode);
  const [state, setState] = useState<VoiceState>('idle');
  const [isEnabled, setIsEnabled] = useState(false);
  
  // Audio state
  const [audioLevel, setAudioLevel] = useState(0);
  const [isMuted, setIsMuted] = useState(false);
  
  // Transcript and plan state
  const [transcript, setTranscript] = useState('');
  const [plan, setPlan] = useState<VoicePlan | null>(null);
  const [results, setResults] = useState<VoiceStepResult[]>([]);
  const [summary, setSummary] = useState('');
  const [error, setError] = useState('');
  
  // Settings
  const [showSettings, setShowSettings] = useState(false);
  const [autoConfirm, setAutoConfirm] = useState(false);
  const [wakeWord, setWakeWord] = useState('hey assistant');
  
  // Refs
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const animationFrameRef = useRef<number | null>(null);
  const speechSynthRef = useRef<SpeechSynthesisUtterance | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopRecording();
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      if (speechSynthesis.speaking) {
        speechSynthesis.cancel();
      }
    };
  }, []);

  // Monitor audio levels
  const updateAudioLevel = useCallback(() => {
    if (!analyserRef.current) return;
    
    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
    analyserRef.current.getByteFrequencyData(dataArray);
    
    const average = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
    setAudioLevel(average / 255);
    
    if (state === 'listening') {
      animationFrameRef.current = requestAnimationFrame(updateAudioLevel);
    }
  }, [state]);

  // Start recording
  const startRecording = async () => {
    setError('');
    setTranscript('');
    setPlan(null);
    setResults([]);
    setSummary('');
    
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        } 
      });
      streamRef.current = stream;
      
      // Set up audio analysis for visual feedback
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
      
      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        await processAudio(blob);
      };
      
      recorder.start();
      mediaRecorderRef.current = recorder;
      setState('listening');
      setIsEnabled(true);
      
      // Start audio level monitoring
      updateAudioLevel();
      
    } catch (err: any) {
      console.error('Failed to start recording:', err);
      setError('Microphone access denied or unavailable');
      setState('error');
      onError?.('Microphone access denied or unavailable');
    }
  };

  // Stop recording
  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    
    setAudioLevel(0);
    
    if (state === 'listening') {
      setState('processing');
    }
  };

  // Process recorded audio
  const processAudio = async (blob: Blob) => {
    setState('processing');
    
    try {
      // Step 1: Transcribe
      const transcribeResult = await api.transcribeAudio(blob);
      const text = transcribeResult.transcript;
      setTranscript(text);
      onTranscript?.(text);
      
      // Step 2: Generate plan
      const planResult = await api.voicePlan(text);
      setPlan(planResult.plan);
      onPlan?.(planResult.plan);
      
      // Step 3: Check if confirmation needed
      if (planResult.plan.required_confirmations.length > 0 && !autoConfirm) {
        setState('confirming');
      } else {
        // Auto-execute if no confirmations needed or autoConfirm is on
        await executeplan(planResult.plan, planResult.plan.required_confirmations.length === 0);
      }
      
    } catch (err: any) {
      console.error('Audio processing failed:', err);
      setError(err.message || 'Failed to process audio');
      setState('error');
      onError?.(err.message || 'Failed to process audio');
    }
  };

  // Execute the plan
  const executeplan = async (planToExecute: VoicePlan, confirmed: boolean) => {
    setState('processing');
    
    try {
      const result = await api.voiceExecute(planToExecute, confirmed, currentUser?.id);
      setResults(result.results);
      setSummary(result.summary);
      onResult?.(result.results, result.summary);
      
      // Speak the summary
      if (result.summary && !isMuted && 'speechSynthesis' in window) {
        setState('speaking');
        const utterance = new SpeechSynthesisUtterance(result.summary);
        speechSynthRef.current = utterance;
        
        utterance.onend = () => {
          setState('idle');
          setIsEnabled(false);
        };
        
        utterance.onerror = () => {
          setState('idle');
          setIsEnabled(false);
        };
        
        speechSynthesis.speak(utterance);
      } else {
        setState('idle');
        setIsEnabled(false);
      }
      
    } catch (err: any) {
      console.error('Execution failed:', err);
      setError(err.message || 'Failed to execute plan');
      setState('error');
      onError?.(err.message || 'Failed to execute plan');
    }
  };

  // Handle confirmation
  const handleConfirm = () => {
    if (plan) {
      executeplan(plan, true);
    }
  };

  // Handle cancel
  const handleCancel = () => {
    setPlan(null);
    setState('idle');
    setIsEnabled(false);
  };

  // Stop speaking
  const stopSpeaking = () => {
    if (speechSynthesis.speaking) {
      speechSynthesis.cancel();
    }
    setState('idle');
    setIsEnabled(false);
  };

  // Push-to-talk handlers
  const handlePushStart = () => {
    if (mode === 'push-to-talk' && state === 'idle') {
      startRecording();
    }
  };

  const handlePushEnd = () => {
    if (mode === 'push-to-talk' && state === 'listening') {
      stopRecording();
    }
  };

  // Toggle for continuous mode
  const toggleContinuous = () => {
    if (state === 'listening') {
      stopRecording();
    } else if (state === 'idle') {
      startRecording();
    }
  };

  // Get state-specific styles
  const getStateStyles = () => {
    switch (state) {
      case 'listening':
        return 'bg-red-500 hover:bg-red-600 animate-pulse';
      case 'processing':
        return 'bg-yellow-500 hover:bg-yellow-600';
      case 'speaking':
        return 'bg-green-500 hover:bg-green-600';
      case 'confirming':
        return 'bg-blue-500 hover:bg-blue-600';
      case 'error':
        return 'bg-red-600 hover:bg-red-700';
      default:
        return 'bg-primary-600 hover:bg-primary-700';
    }
  };

  // Get state icon
  const getStateIcon = () => {
    switch (state) {
      case 'listening':
        return <Radio className="h-6 w-6 animate-pulse" />;
      case 'processing':
        return <Loader2 className="h-6 w-6 animate-spin" />;
      case 'speaking':
        return <Volume2 className="h-6 w-6" />;
      case 'confirming':
        return <CheckCircle className="h-6 w-6" />;
      case 'error':
        return <AlertCircle className="h-6 w-6" />;
      default:
        return <Mic className="h-6 w-6" />;
    }
  };

  // Compact mode - just the button
  if (compact) {
    return (
      <div className={cn('relative', className)}>
        <button
          onMouseDown={mode === 'push-to-talk' ? handlePushStart : undefined}
          onMouseUp={mode === 'push-to-talk' ? handlePushEnd : undefined}
          onMouseLeave={mode === 'push-to-talk' && state === 'listening' ? handlePushEnd : undefined}
          onClick={mode !== 'push-to-talk' ? toggleContinuous : undefined}
          disabled={state === 'processing'}
          className={cn(
            'p-3 rounded-full text-white shadow-lg transition-all',
            getStateStyles(),
            'focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500'
          )}
          title={state === 'idle' ? (mode === 'push-to-talk' ? 'Hold to talk' : 'Click to start') : state}
        >
          {getStateIcon()}
        </button>
        
        {/* Audio level indicator */}
        {state === 'listening' && (
          <div 
            className="absolute inset-0 rounded-full border-4 border-red-400 animate-ping pointer-events-none"
            style={{ opacity: audioLevel }}
          />
        )}
      </div>
    );
  }

  // Full mode with transcript and controls
  return (
    <div className={cn('bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700', className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-2">
          <Mic className="h-5 w-5 text-primary-600" />
          <span className="font-medium text-gray-900 dark:text-white">Voice Assistant</span>
          <span className={cn(
            'px-2 py-0.5 text-xs rounded-full',
            state === 'idle' ? 'bg-gray-100 text-gray-600' :
            state === 'listening' ? 'bg-red-100 text-red-700' :
            state === 'processing' ? 'bg-yellow-100 text-yellow-700' :
            state === 'speaking' ? 'bg-green-100 text-green-700' :
            state === 'confirming' ? 'bg-blue-100 text-blue-700' :
            'bg-red-100 text-red-700'
          )}>
            {state}
          </span>
        </div>
        
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsMuted(!isMuted)}
            className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
            title={isMuted ? 'Unmute' : 'Mute'}
          >
            {isMuted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
          </button>
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
            title="Settings"
          >
            <Settings className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Settings Panel */}
      {showSettings && (
        <VoiceSettings
          mode={mode}
          onModeChange={setMode}
          wakeWord={wakeWord}
          onWakeWordChange={setWakeWord}
          autoConfirm={autoConfirm}
          onAutoConfirmChange={setAutoConfirm}
          onClose={() => setShowSettings(false)}
        />
      )}

      {/* Main Content */}
      <div className="p-4 space-y-4">
        {/* Waveform / Visual Feedback */}
        <VoiceWaveform 
          isActive={state === 'listening'} 
          audioLevel={audioLevel}
          state={state}
        />

        {/* Transcript */}
        {transcript && (
          <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-3">
            <p className="text-xs text-gray-500 mb-1">You said:</p>
            <p className="text-gray-900 dark:text-white">{transcript}</p>
          </div>
        )}

        {/* Plan Preview */}
        {plan && state === 'confirming' && (
          <VoicePlanPreview
            plan={plan}
            onConfirm={handleConfirm}
            onCancel={handleCancel}
          />
        )}

        {/* Results */}
        {results.length > 0 && (
          <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-3">
            <p className="text-xs text-green-600 dark:text-green-400 mb-1">Result:</p>
            <p className="text-gray-900 dark:text-white">{summary}</p>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-3 flex items-start gap-2">
            <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
              <button
                onClick={() => { setError(''); setState('idle'); }}
                className="text-xs text-red-600 hover:underline mt-1"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {/* Main Control Button */}
        <div className="flex justify-center">
          {state === 'speaking' ? (
            <button
              onClick={stopSpeaking}
              className="flex items-center gap-2 px-6 py-3 rounded-full bg-green-500 hover:bg-green-600 text-white font-medium transition-colors"
            >
              <Square className="h-5 w-5" />
              Stop Speaking
            </button>
          ) : mode === 'push-to-talk' ? (
            <button
              onMouseDown={handlePushStart}
              onMouseUp={handlePushEnd}
              onMouseLeave={state === 'listening' ? handlePushEnd : undefined}
              onTouchStart={handlePushStart}
              onTouchEnd={handlePushEnd}
              disabled={state === 'processing' || state === 'confirming'}
              className={cn(
                'flex items-center gap-2 px-6 py-3 rounded-full text-white font-medium transition-all',
                getStateStyles(),
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              {getStateIcon()}
              <span>
                {state === 'idle' ? 'Hold to Talk' :
                 state === 'listening' ? 'Listening...' :
                 state === 'processing' ? 'Processing...' :
                 state === 'confirming' ? 'Confirm Above' :
                 'Error'}
              </span>
            </button>
          ) : (
            <button
              onClick={toggleContinuous}
              disabled={state === 'processing' || state === 'confirming'}
              className={cn(
                'flex items-center gap-2 px-6 py-3 rounded-full text-white font-medium transition-all',
                getStateStyles(),
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              {state === 'listening' ? <MicOff className="h-5 w-5" /> : getStateIcon()}
              <span>
                {state === 'idle' ? 'Start Listening' :
                 state === 'listening' ? 'Stop Listening' :
                 state === 'processing' ? 'Processing...' :
                 state === 'confirming' ? 'Confirm Above' :
                 'Error'}
              </span>
            </button>
          )}
        </div>

        {/* Mode indicator */}
        <p className="text-center text-xs text-gray-500">
          Mode: {mode.replace('-', ' ')}
          {mode === 'push-to-talk' && ' • Hold the button while speaking'}
          {mode === 'wake-word' && ` • Say "${wakeWord}" to activate`}
          {mode === 'continuous' && ' • Always listening'}
        </p>
      </div>
    </div>
  );
}
