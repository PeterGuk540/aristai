// Voice assistant components
// V1: SPEAK: prefix mechanism (legacy)
export { ConversationalVoice } from './ConversationalVoice';
export type { ConversationState } from './ConversationalVoice';

// V2: ElevenLabs Client Tools architecture (new)
export { ConversationalVoiceV2 } from './ConversationalVoiceV2';
export type { ConversationState as ConversationStateV2 } from './ConversationalVoiceV2';

// Supporting components
export { VoiceOnboarding } from './VoiceOnboarding';
export { VoiceCommandGuide } from './VoiceCommandGuide';
export { VoiceWaveformMini } from './VoiceWaveformMini';

// Feature flag for switching between V1 and V2
// Set to true to use the new Client Tools architecture
export const USE_VOICE_V2 = true;
