'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Button } from '@/components/ui/Button';
import { cn } from '@/lib/utils';
import { Mic, Volume2 } from 'lucide-react';

interface VoiceOnboardingProps {
  role: 'admin' | 'instructor' | 'student';
  userName: string;
  onComplete: () => void;
}

// Phrases that will dismiss the onboarding
const DISMISS_PHRASES = [
  'got it',
  'i got it',
  'okay',
  'ok',
  'understood',
  'i understand',
  'thanks',
  'thank you',
  'yes',
  'sure',
  'alright',
  'all right',
  'let\'s go',
  "let's go",
  'start',
  'begin',
  'continue',
  'skip',
  'dismiss',
  'close',
  'done',
];

export function VoiceOnboarding({ role, userName, onComplete }: VoiceOnboardingProps) {
  const [isVisible, setIsVisible] = useState(true);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [hasSpoken, setHasSpoken] = useState(false);
  const [transcript, setTranscript] = useState('');
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const animationFrameRef = useRef<number | null>(null);
  const silenceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const lastSpeechTimeRef = useRef<number>(Date.now());

  // Welcome message based on role
  const getWelcomeMessage = () => {
    const firstName = userName.split(' ')[0];
    switch (role) {
      case 'admin':
        return `Welcome ${firstName}! As an administrator, you have full access to manage courses, approve instructor requests, and configure the system. Say "Got it" or "Let's go" when you're ready to begin.`;
      case 'instructor':
        return `Welcome ${firstName}! I'm your AI teaching assistant. You can use voice commands to manage courses, start sessions, create polls, and more. Just speak naturally and I'll help you out. Say "Got it" when you're ready!`;
      case 'student':
        return `Welcome ${firstName}! You can use your voice to navigate courses, join discussions, and get help. Say "Got it" to get started.`;
      default:
        return `Welcome ${firstName}! Say "Got it" when you're ready to begin.`;
    }
  };

  // Speak the welcome message on mount
  useEffect(() => {
    if (!hasSpoken && 'speechSynthesis' in window) {
      const timer = setTimeout(() => {
        speakWelcome();
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [hasSpoken]);

  // Cleanup
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, []);

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

  const speakWelcome = () => {
    setIsSpeaking(true);
    setHasSpoken(true);
    
    const utterance = new SpeechSynthesisUtterance(getWelcomeMessage());
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    
    utterance.onend = () => {
      setIsSpeaking(false);
      // Start listening after speaking
      startListening();
    };
    
    utterance.onerror = () => {
      setIsSpeaking(false);
      startListening();
    };
    
    speechSynthesis.speak(utterance);
  };

  const startListening = async () => {
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
      
      recorder.start(100);
      mediaRecorderRef.current = recorder;
      lastSpeechTimeRef.current = Date.now();
      setIsListening(true);
      
      // Start voice activity detection
      detectVoiceActivity();
      
    } catch (err) {
      console.error('Failed to start listening:', err);
      // Fall back to click-to-dismiss
    }
  };

  const detectVoiceActivity = useCallback(() => {
    if (!analyserRef.current || !isListening) return;
    
    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
    analyserRef.current.getByteFrequencyData(dataArray);
    
    const average = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
    const normalizedLevel = average / 255;
    
    // Voice activity detection
    if (normalizedLevel > 0.02) {
      lastSpeechTimeRef.current = Date.now();
      
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current);
        silenceTimerRef.current = null;
      }
    } else {
      const silenceDuration = Date.now() - lastSpeechTimeRef.current;
      
      if (silenceDuration > 1000 && !silenceTimerRef.current && chunksRef.current.length > 0) {
        silenceTimerRef.current = setTimeout(() => {
          processAudio();
        }, 200);
      }
    }
    
    animationFrameRef.current = requestAnimationFrame(detectVoiceActivity);
  }, [isListening]);

  const processAudio = async () => {
    if (!mediaRecorderRef.current) return;
    
    mediaRecorderRef.current.stop();
    
    await new Promise(resolve => setTimeout(resolve, 100));
    
    const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
    chunksRef.current = [];
    
    if (blob.size < 1000) {
      // Restart recording
      restartRecording();
      return;
    }
    
    try {
      // Simple client-side speech recognition using Web Speech API if available
      // Otherwise fall back to API
      const text = await transcribeLocally(blob);
      
      if (text) {
        setTranscript(text);
        
        // Check if it's a dismiss phrase
        const normalizedText = text.toLowerCase().trim();
        const shouldDismiss = DISMISS_PHRASES.some(phrase => 
          normalizedText.includes(phrase)
        );
        
        if (shouldDismiss) {
          handleDismiss();
          return;
        }
      }
      
      // Not a dismiss phrase, keep listening
      restartRecording();
      
    } catch (err) {
      console.error('Transcription failed:', err);
      restartRecording();
    }
  };

  // Try to use Web Speech API for quick local transcription
  const transcribeLocally = (blob: Blob): Promise<string> => {
    return new Promise((resolve) => {
      // Use the backend API for now since Web Speech API requires user gesture
      // In a real implementation, you might use a lighter-weight local model
      
      // For simplicity, we'll use the backend
      const formData = new FormData();
      formData.append('file', blob, 'audio.webm');
      
      fetch('/api/proxy/voice/transcribe', {
        method: 'POST',
        body: formData,
      })
        .then(res => res.json())
        .then(data => resolve(data.transcript || ''))
        .catch(() => resolve(''));
    });
  };

  const restartRecording = () => {
    if (streamRef.current) {
      const recorder = new MediaRecorder(streamRef.current, { mimeType: 'audio/webm' });
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };
      recorder.start(100);
      mediaRecorderRef.current = recorder;
      lastSpeechTimeRef.current = Date.now();
      
      detectVoiceActivity();
    }
  };

  const handleDismiss = () => {
    cleanup();
    setIsVisible(false);
    
    // Speak confirmation
    if ('speechSynthesis' in window) {
      const utterance = new SpeechSynthesisUtterance("Great! Let's get started.");
      utterance.rate = 1.1;
      speechSynthesis.speak(utterance);
    }
    
    setTimeout(onComplete, 300);
  };

  if (!isVisible) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 dark:bg-black/70">
      <div className="max-w-2xl w-full mx-4 bg-white dark:bg-gray-800 rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-primary-600 to-primary-700 px-8 py-6 text-white">
          <h1 className="text-2xl font-bold mb-1">
            Welcome to AristAI{role === 'admin' ? ' Admin' : role === 'instructor' ? ', Instructor' : ''}!
          </h1>
          <p className="text-primary-100">Hello, {userName}</p>
        </div>

        {/* Content */}
        <div className="p-8">
          {/* Voice status */}
          <div className="flex items-center justify-center gap-4 mb-6">
            {isSpeaking ? (
              <div className="flex items-center gap-2 text-primary-600">
                <Volume2 className="h-6 w-6 animate-pulse" />
                <span className="text-sm font-medium">Speaking...</span>
              </div>
            ) : isListening ? (
              <div className="flex items-center gap-2 text-green-600">
                <Mic className="h-6 w-6 animate-pulse" />
                <span className="text-sm font-medium">Listening... Say "Got it" to continue</span>
              </div>
            ) : null}
          </div>

          {/* Welcome message text */}
          <div className="bg-gray-50 dark:bg-gray-900 rounded-xl p-6 mb-6">
            <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
              {getWelcomeMessage()}
            </p>
          </div>

          {/* Transcript display */}
          {transcript && (
            <div className="mb-6 text-center">
              <p className="text-sm text-gray-500">I heard: "{transcript}"</p>
            </div>
          )}

          {/* Quick tips */}
          <div className="mb-6">
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
              Voice Commands You Can Use:
            </h3>
            <div className="grid grid-cols-2 gap-2 text-sm text-gray-600 dark:text-gray-400">
              <div className="flex items-center gap-2">
                <span className="text-primary-500">→</span>
                "Show my courses"
              </div>
              <div className="flex items-center gap-2">
                <span className="text-primary-500">→</span>
                "Start a session"
              </div>
              <div className="flex items-center gap-2">
                <span className="text-primary-500">→</span>
                "Create a poll"
              </div>
              <div className="flex items-center gap-2">
                <span className="text-primary-500">→</span>
                "Go to forum"
              </div>
            </div>
          </div>

          {/* Manual dismiss button */}
          <div className="flex justify-center">
            <Button
              onClick={handleDismiss}
              className="px-8 py-3"
            >
              Got It - Let's Go!
            </Button>
          </div>

          <p className="text-center text-xs text-gray-400 mt-4">
            Or just say "Got it", "Okay", or "Let's go" to continue
          </p>
        </div>
      </div>
    </div>
  );
}

export default VoiceOnboarding;
