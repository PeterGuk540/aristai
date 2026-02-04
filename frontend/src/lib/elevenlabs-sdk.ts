const DEFAULT_SDK_URL =
  'https://cdn.jsdelivr.net/npm/@elevenlabs/client@0.6.0/dist/index.js';

export const ELEVENLABS_SDK_URL =
  process.env.NEXT_PUBLIC_ELEVENLABS_SDK_URL || DEFAULT_SDK_URL;

export type ElevenLabsConversation = {
  startSession: (options: { signedUrl: string; connectionType?: string }) => Promise<any>;
};

export async function loadElevenLabsConversation(): Promise<ElevenLabsConversation> {
  const mod = await import(/* webpackIgnore: true */ ELEVENLABS_SDK_URL);
  const conversation = mod.Conversation || mod.default?.Conversation;

  if (!conversation) {
    throw new Error('ElevenLabs SDK Conversation export not found.');
  }

  return conversation as ElevenLabsConversation;
}
