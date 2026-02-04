import { API_BASE } from '../lib/api';

/**
 * Voice synthesis utilities for AristAI voice assistant
 * Replaces browser Speech Synthesis with backend ElevenLabs Agent API calls
 */

export const playBackendAudio = async (text: string): Promise<void> => {
  try {
    const response = await fetch(`${API_BASE}/voice/synthesize`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ text }),
    });

    if (!response.ok) {
      console.error('Failed to synthesize audio:', response.status);
      return;
    }

    const audioBlob = await response.blob();
    const audioUrl = URL.createObjectURL(audioBlob);
    
    // Create and play audio
    const audio = new Audio(audioUrl);
    audio.play();
    
    return new Promise((resolve) => {
      audio.onended = () => resolve();
      audio.onerror = () => {
        console.error('Audio playback failed');
        resolve();
      };
    });
  } catch (error) {
    console.error('Error synthesizing audio:', error);
    // Fall back to browser synthesis
    return;
  }
};

export const isBackendSynthesisAvailable = (): boolean => {
  return true; // Always available since we have the backend endpoint
};

// Fallback to browser synthesis if backend fails
export const speakWithFallback = async (text: string): Promise<void> => {
  try {
    await playBackendAudio(text);
  } catch (error) {
    console.warn('Backend synthesis failed, using browser fallback:', error);
    await new Promise<void>((resolve) => {
      // Fallback to browser Speech Synthesis
      if ('speechSynthesis' in window) {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.0;
        utterance.pitch = 1.0;

        utterance.onend = () => resolve();
        utterance.onerror = (event) => {
          console.error('Browser synthesis failed:', event);
          resolve();
        };

        window.speechSynthesis.speak(utterance);
      } else {
        resolve();
      }
    });
  }
};
