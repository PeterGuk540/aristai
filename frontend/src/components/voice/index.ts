// Voice assistant components
// ========================================
// Architecture: ElevenLabs Client Tools with smart frontend resolution
// - 6 Client Tools with string parameters (no enums)
// - Frontend fuzzy matching via resolveTarget() in action-registry.ts
// - Single response guaranteed (no muting, no SPEAK: prefix)
// ========================================

// Main voice component (Client Tools architecture)
export { ConversationalVoiceV2 } from './ConversationalVoiceV2';
export type { ConversationState } from './ConversationalVoiceV2';

// Legacy V1 component (SPEAK: prefix mechanism - deprecated)
export { ConversationalVoice as ConversationalVoiceLegacy } from './ConversationalVoice';

// Supporting components
export { VoiceOnboarding } from './VoiceOnboarding';
export { VoiceCommandGuide } from './VoiceCommandGuide';
export { VoiceWaveformMini } from './VoiceWaveformMini';
