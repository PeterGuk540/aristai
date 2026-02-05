'use client';

import { useUiActionStream } from '@/lib/ui-actions';

type VoiceUiActionBridgeProps = {
  userId?: number;
  onStatusChange?: (connected: boolean) => void;
};

export const VoiceUiActionBridge = ({ userId, onStatusChange }: VoiceUiActionBridgeProps) => {
  useUiActionStream(userId, onStatusChange);
  return null;
};
