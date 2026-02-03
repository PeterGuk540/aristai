# AristAI Voice Interface Integration Guide

This package contains the frontend voice interface components for AristAI. These components integrate with the backend MCP server and voice loop controller.

## Files Included

```
frontend-voice-components/
├── INTEGRATION.md          # This file
├── AppShellWithVoice.tsx   # Enhanced app shell with voice FAB
└── components/voice/
    ├── index.ts            # Component exports
    ├── VoiceAssistant.tsx  # Main voice assistant component
    ├── VoiceFab.tsx        # Floating action button wrapper
    ├── VoiceHistory.tsx    # Voice command history display
    ├── VoicePlanPreview.tsx # Plan confirmation UI
    ├── VoiceSettings.tsx   # Voice settings panel
    ├── VoiceTabContent.tsx # Console tab replacement
    └── VoiceWaveform.tsx   # Audio visualization
```

## Installation Steps

### Step 1: Copy Component Files

Copy the `components/voice/` directory to your frontend:

```bash
cp -r components/voice/ frontend/src/components/voice/
```

### Step 2: Update Dashboard Layout (Option A - Full Integration)

Replace your `frontend/src/app/(dashboard)/layout.tsx` to use the voice-enabled shell:

```tsx
'use client';

import { AppShellWithVoice } from '@/components/AppShellWithVoice';
import { AuthProvider } from '@/lib/auth-context';
import { UserProvider } from '@/lib/context';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthProvider>
      <UserProvider>
        <AppShellWithVoice>{children}</AppShellWithVoice>
      </UserProvider>
    </AuthProvider>
  );
}
```

This adds a floating voice button (FAB) in the bottom-right corner for instructors.

### Step 3: Update Console Page Voice Tab (Option B - Console Only)

If you prefer to keep voice functionality only in the Console page, replace the existing voice tab in `frontend/src/app/(dashboard)/console/page.tsx`:

```tsx
// Add import at the top
import { VoiceTabContent } from '@/components/voice';

// Replace the <TabsContent value="voice"> section with:
<TabsContent value="voice">
  <VoiceTabContent />
</TabsContent>
```

This replaces the basic push-to-talk with the full-featured voice interface.

## Component Usage

### VoiceAssistant

The main voice assistant component with full UI:

```tsx
import { VoiceAssistant } from '@/components/voice';

// Basic usage
<VoiceAssistant />

// With options
<VoiceAssistant
  defaultMode="push-to-talk"  // 'push-to-talk' | 'wake-word' | 'continuous'
  compact={false}              // Show full UI or just button
  onTranscript={(text) => console.log('Heard:', text)}
  onPlan={(plan) => console.log('Plan:', plan)}
  onResult={(results, summary) => console.log('Done:', summary)}
  onError={(error) => console.error(error)}
/>
```

### VoiceFab

Floating action button that opens the voice assistant:

```tsx
import { VoiceFab } from '@/components/voice';

// Position options: 'bottom-right' | 'bottom-left' | 'top-right' | 'top-left'
<VoiceFab position="bottom-right" />
```

### VoiceTabContent

Complete voice tab content with instructions:

```tsx
import { VoiceTabContent } from '@/components/voice';

<VoiceTabContent />
```

### VoiceHistory

Display command history:

```tsx
import { VoiceHistory } from '@/components/voice';

<VoiceHistory limit={20} />
```

## Voice Modes

1. **Push-to-Talk** (default): Hold button while speaking
2. **Wake Word**: Say wake word (e.g., "hey assistant") to activate
3. **Continuous**: Always listening (best for hands-free)

## Supported Commands

The voice interface supports natural language commands for:

### Courses
- "List all my courses"
- "Show course [name]"
- "Create a new course called [name]"
- "Generate session plans for [course]"

### Sessions
- "List sessions for [course]"
- "Start session [name]"
- "End the current session"
- "What's the session status?"

### Forum & Polls
- "Show recent posts"
- "Create a poll: [question]"
- "Pin the last post"
- "Get poll results"

### AI Copilot
- "Start the copilot"
- "Stop the copilot"
- "Show copilot suggestions"
- "What are the confusion points?"

### Reports
- "Generate a report"
- "Show the session report"
- "Who participated today?"

### Enrollment
- "List enrolled students"
- "Enroll [email] in [course]"
- "How many students are enrolled?"

## Backend Requirements

The voice interface requires the following backend endpoints (already in your API):

- `POST /api/voice/transcribe` - Audio transcription
- `POST /api/voice/plan` - Generate action plan
- `POST /api/voice/execute` - Execute plan
- `GET /api/voice/audit` - Get command history

These should already exist from the MCP server implementation.

## Confirmation Flow

Write operations (create, update, delete) require confirmation:

1. User speaks command
2. Audio is transcribed
3. Plan is generated showing intended actions
4. User sees preview with "Confirm" or "Cancel" buttons
5. On confirm, actions are executed
6. Results are displayed and spoken

Auto-confirm can be enabled in settings to skip the confirmation step.

## Styling

The components use Tailwind CSS and integrate with your existing dark mode support. Colors follow your primary color scheme.

## Browser Compatibility

- **Audio Recording**: Chrome, Firefox, Safari, Edge (modern versions)
- **Speech Synthesis**: All modern browsers (used for voice responses)
- **MediaRecorder API**: Chrome 49+, Firefox 29+, Safari 14.1+, Edge 79+

## Troubleshooting

### Microphone Access Denied
- Check browser permissions for microphone access
- Ensure HTTPS in production (required for getUserMedia)

### No Audio Level
- Verify microphone is working in system settings
- Check that no other app is using the microphone

### Transcription Fails
- Ensure backend transcription endpoint is running
- Check network connectivity to API

### Commands Not Recognized
- Speak clearly and at normal pace
- Use command phrases from the reference list
- Check that the correct session/course is selected
