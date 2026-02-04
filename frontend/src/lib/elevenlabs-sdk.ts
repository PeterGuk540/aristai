/**
 * ElevenLabs SDK loader module.
 * 
 * Dynamically imports the official ElevenLabs client SDK from a local vendor path
 * to ensure offline compatibility and avoid external dependencies.
 */

// Default SDK URL - vendored copy of @elevenlabs/client@0.6.0
const SDK_URL = '/vendor/elevenlabs-client-0.6.0.mjs';

export interface ElevenLabsConversation {
  startSession: (options: {
    signedUrl: string;
    connectionType: "websocket";
    onConnect?: (data: { conversationId: string }) => void;
    onDisconnect?: (data?: any) => void;
    onStatusChange?: (status: string) => void;
    onModeChange?: (mode: string) => void;
    onMessage?: (message: { source: "user" | "ai"; message: string }) => void;
    onError?: (error: any) => void;
    onAudio?: (audio: any) => void;
    onDebug?: (debug: any) => void;
  }) => Promise<{
    conversationId: string;
    endSession: () => Promise<void>;
    setVolume: (options: { volume: number }) => void;
    // Add other SDK methods as needed
  }>;
}

/**
 * Dynamically loads the ElevenLabs SDK from the local vendor path.
 * 
 * @returns Promise<ElevenLabsConversation> - The Conversation class from the SDK
 * @throws Error if the SDK fails to load or Conversation export is missing
 */
export async function loadElevenLabsSDK(): Promise<typeof ElevenLabsConversation> {
  try {
    // Use dynamic ESM import with webpackIgnore to prevent bundling issues
    // @ts-ignore - webpackIgnore comment
    const mod = await import(/* webpackIgnore: true */ SDK_URL);
    
    // Check if the Conversation export exists
    if (!mod.Conversation) {
      throw new Error('ElevenLabs SDK loaded but Conversation export is missing');
    }
    
    return mod.Conversation;
  } catch (error) {
    console.error('Failed to load ElevenLabs SDK:', error);
    
    if (error instanceof Error) {
      throw new Error(`Failed to load ElevenLabs SDK: ${error.message}`);
    } else {
      throw new Error('Failed to load ElevenLabs SDK: Unknown error');
    }
  }
}

/**
 * Utility function to check if the SDK is available in the current environment.
 * 
 * @returns boolean - True if the SDK can be loaded
 */
export async function isSDKAvailable(): Promise<boolean> {
  try {
    await loadElevenLabsSDK();
    return true;
  } catch {
    return false;
  }
}

/**
 * Preload the SDK to ensure it's available when needed.
 * Call this during app initialization to avoid loading delays.
 * 
 * @returns Promise<void>
 */
export async function preloadSDK(): Promise<void> {
  try {
    await loadElevenLabsSDK();
    console.log('✅ ElevenLabs SDK preloaded successfully');
  } catch (error) {
    console.warn('⚠️ Failed to preload ElevenLabs SDK:', error);
  }
}