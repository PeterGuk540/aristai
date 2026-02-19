# Voice Controller Architecture

## Overview

The AristAI voice controller implements a **pure LLM-based** architecture for understanding and executing user voice commands. The system follows a **State → Plan → Act → Verify** loop with no regex/keyword matching.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ElevenLabs Agent                                   │
│                    (ASR/TTS + Conversational Layer)                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ WebSocket (Signed URL)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Voice API v2 (FastAPI)                               │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐            │
│  │ /voice/v2/      │   │ VoiceProcessor  │   │ Voice Agent     │            │
│  │ process         │──▶│ (LLM-based)     │──▶│ Tools           │            │
│  │ ui-state        │   │                 │   │                 │            │
│  │ execute-tool    │   │                 │   │                 │            │
│  │ tools           │   │                 │   │                 │            │
│  └─────────────────┘   └─────────────────┘   └─────────────────┘            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ JSON UI Actions
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                                    │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐            │
│  │ VoiceUI         │   │ Voice Action    │   │ Voice UI        │            │
│  │ Controller      │◀──│ Executor        │──▶│ State           │            │
│  │ (React)         │   │ (Verify Loop)   │   │ (DOM Reader)    │            │
│  └─────────────────┘   └─────────────────┘   └─────────────────┘            │
│          │                     │                     │                       │
│          ▼                     ▼                     ▼                       │
│  ┌─────────────────────────────────────────────────────────────┐            │
│  │              UI Elements with data-voice-id                  │            │
│  │   [Tabs] [Buttons] [Inputs] [Dropdowns] [Modals]            │            │
│  └─────────────────────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Frontend Components

#### `voice-action-schema.ts`
Defines the strict UI Action Contract using Zod schemas:

```typescript
// Supported action types
type VoiceActionType =
  | 'ui.navigate'      // Navigate to page
  | 'ui.switchTab'     // Switch active tab
  | 'ui.clickButton'   // Click a button
  | 'ui.expandDropdown'// Expand dropdown
  | 'ui.selectDropdown'// Select option
  | 'ui.fillInput'     // Fill form field
  | 'ui.clearInput'    // Clear form field
  | 'ui.selectListItem'// Select list item
  | 'ui.openModal'     // Open modal
  | 'ui.closeModal'    // Close modal
  | 'ui.toast'         // Show toast
  | 'ui.scroll'        // Scroll page
  | 'ui.submitForm'    // Submit form
  | 'ui.openMenuAndClick' // Open menu + click

// All actions require voice-id based targeting
interface ActionPayload {
  voiceId: string;      // Required - stable element identifier
  // ... action-specific parameters
}
```

#### `voice-ui-state.ts`
Provides deterministic UI state grounding:

```typescript
interface UiState {
  route: string;           // Current page path
  activeTab: string | null;// Active tab voice-id
  tabs: TabInfo[];         // All visible tabs
  buttons: ButtonInfo[];   // All visible buttons
  inputFields: InputFieldInfo[]; // Form inputs
  dropdowns: DropdownInfo[];// Dropdowns with options
  modals: ModalInfo[];     // Open modals
  listItems: ListItemInfo[];// List items
  isLoading: boolean;      // Loading state
  hasValidationErrors: boolean;
  capturedAt: number;      // Timestamp
}

// Key functions:
getUiState()         // Full state snapshot
getCompactUiState()  // Minimal state for LLM context
waitForUiStability() // Wait for DOM to settle
computeStateDiff()   // Compare before/after states
```

#### `voice-action-executor.ts`
Implements the Execute → Verify → Repair loop:

```typescript
async function executeVoiceAction(action: VoiceAction): Promise<ExecutionResult> {
  // 1. Validate action against schema
  const validated = validateVoiceAction(action);

  // 2. Capture state BEFORE
  const stateBefore = getUiState();

  // 3. Execute the action
  const executed = executeActionRaw(validated);

  // 4. Wait for UI stability
  await waitForUiStability(200);

  // 5. Capture state AFTER
  const stateAfter = getUiState();
  const diff = computeStateDiff(stateBefore, stateAfter);

  // 6. Verify expected change occurred
  const verification = verifyAction(validated, stateBefore, stateAfter, diff);

  // 7. Attempt repair if failed
  if (!verification.passed && retryCount < MAX_RETRIES) {
    return computeRepairAction(validated, stateAfter, verification);
  }

  return { success: verification.passed, context, message };
}
```

#### `VoiceUIController.tsx`
React component that listens for CustomEvents and executes DOM actions:

```typescript
// Event handlers registered:
- 'ui.selectDropdown'  → handleSelectDropdown
- 'ui.expandDropdown'  → handleExpandDropdown
- 'ui.clickButton'     → handleClickButton
- 'ui.fillInput'       → handleFillInput
- 'ui.switchTab'       → handleSwitchTab
- 'ui.selectListItem'  → handleSelectListItem
- etc.

// Element finding strategy (no hardcoded registry):
1. Direct data-voice-id match
2. Partial data-voice-id match
3. Common variations (tab-X, X-button)
4. Text content / aria-label search
```

### 2. Backend Components

#### `voice_processor.py`
Core LLM-based voice processing:

```python
class VoiceProcessor:
    def process(
        self,
        user_input: str,
        ui_state: UiState,        # From frontend
        conversation_state: str,   # idle, awaiting_confirmation, etc.
        language: str,             # en, es
        active_course: str,        # Context
        active_session: str,       # Context
    ) -> VoiceProcessorResponse:

        # 1. Build prompt with UI context
        prompt = self._build_prompt(user_input, ui_state, ...)

        # 2. LLM classifies intent + extracts parameters
        llm_response = invoke_llm_with_metrics(self._llm, prompt)

        # 3. Parse structured JSON response
        parsed = parse_json_response(llm_response.content)

        # 4. Execute appropriate tool
        tool_result = execute_voice_tool(parsed['tool_name'], parsed['parameters'])

        return VoiceProcessorResponse(
            success=True,
            spoken_response=parsed['spoken_response'],
            ui_action=tool_result.ui_action,  # Sent to frontend
        )
```

#### `voice_agent_tools.py`
Tool definitions for ElevenLabs Agent:

```python
VOICE_AGENT_TOOLS = [
    {
        "name": "navigate_to_page",
        "parameters": {"page": {"type": "string", "enum": [...]}}
    },
    {
        "name": "switch_tab",
        "parameters": {"tab_voice_id": {"type": "string"}}
    },
    {
        "name": "click_button",
        "parameters": {"button_voice_id": {"type": "string"}}
    },
    {
        "name": "fill_input",
        "parameters": {
            "field_voice_id": {"type": "string"},
            "content": {"type": "string"},
            "append": {"type": "boolean"}
        }
    },
    {
        "name": "select_dropdown_option",
        "parameters": {
            "dropdown_voice_id": {"type": "string"},
            "selection_index": {"type": "integer"},
            "selection_text": {"type": "string"}
        }
    },
    # ... more tools
]
```

#### `voice_v2_router.py`
FastAPI endpoints:

```python
@router.post("/process")
async def process_voice_command(request: ProcessVoiceRequest):
    """Process voice command with LLM understanding."""

@router.post("/ui-state")
async def update_ui_state(request: UiStateRequest):
    """Receive UI state from frontend."""

@router.get("/tools")
async def list_tools():
    """Get tool definitions for ElevenLabs Agent."""
```

## The State → Plan → Act → Verify Loop

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. STATE: Capture UI snapshot                                            │
│    - getUiState() reads DOM elements with data-voice-id                 │
│    - Tabs, buttons, inputs, dropdowns, modals, loading states           │
│    - Sent to backend with voice command                                  │
└────────────────────────────────────────┬────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. PLAN: LLM determines intent and action                                │
│    - VoiceProcessor builds context-rich prompt                          │
│    - LLM returns: {tool_name, parameters, confidence, spoken_response}  │
│    - No regex/keyword matching - pure natural language understanding     │
└────────────────────────────────────────┬────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. ACT: Execute UI action                                                │
│    - voice_agent_tools.py returns ui_action JSON                        │
│    - Frontend receives via processCommand()                             │
│    - VoiceUIController dispatches CustomEvent                           │
│    - React-compatible value setters update DOM                          │
└────────────────────────────────────────┬────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. VERIFY: Confirm action succeeded                                      │
│    - waitForUiStability() waits for DOM to settle                       │
│    - Capture state AFTER action                                          │
│    - computeStateDiff() compares before/after                           │
│    - verifyAction() checks expected change occurred                     │
│    - If failed: attempt repair or report error                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Stable Identifiers (data-voice-id)

All voice-controllable elements MUST have a `data-voice-id` attribute:

```html
<!-- Tabs -->
<TabsTrigger value="sessions" data-voice-id="tab-sessions">Sessions</TabsTrigger>
<TabsTrigger value="ai-features" data-voice-id="tab-ai-features">AI Features</TabsTrigger>

<!-- Buttons -->
<Button data-voice-id="create-session">Create Session</Button>
<Button data-voice-id="go-live">Go Live</Button>

<!-- Inputs -->
<Input data-voice-id="course-title" placeholder="Course Title" />
<Textarea data-voice-id="syllabus" placeholder="Paste syllabus..." />

<!-- Dropdowns -->
<Select data-voice-id="select-course">
  <option value="1">Statistics 101</option>
  <option value="2">Machine Learning</option>
</Select>
```

### Naming Conventions

- **Tabs**: `tab-{name}` (e.g., `tab-sessions`, `tab-ai-features`)
- **Buttons**: `{action}` or `{action}-{target}` (e.g., `create-session`, `go-live`)
- **Inputs**: `{field-name}` (e.g., `course-title`, `syllabus`)
- **Dropdowns**: `select-{entity}` (e.g., `select-course`, `select-session`)
- **List containers**: `{entity}-list` (e.g., `student-list`, `course-list`)

## ElevenLabs Integration

```
┌──────────────────────────────────────────────────────────────────┐
│                    ElevenLabs Agent                              │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐     │
│  │   ASR          │  │  Conversation  │  │   TTS          │     │
│  │   (Speech →    │  │  AI            │  │   (Text →      │     │
│  │    Text)       │  │  (Dialogue)    │  │    Speech)     │     │
│  └────────────────┘  └────────────────┘  └────────────────┘     │
│           │                  │                    ▲              │
│           ▼                  ▼                    │              │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                   Tool Calling                             │  │
│  │  switch_tab, click_button, fill_input, select_dropdown    │  │
│  └───────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                               │
                               │ HTTP POST /voice/v2/process
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                      Backend API                                  │
│  - Receives transcript + UI state                                │
│  - LLM processes intent                                          │
│  - Returns ui_action JSON                                        │
└──────────────────────────────────────────────────────────────────┘
                               │
                               │ ui_action: {type, payload}
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                      Frontend                                     │
│  - VoiceUIController dispatches CustomEvent                      │
│  - DOM action executed                                           │
│  - State verified                                                │
└──────────────────────────────────────────────────────────────────┘
```

## Key Design Principles

1. **Pure LLM-Based**: No regex, no keyword matching, no hardcoded patterns
2. **Contract-Driven**: All actions follow strict JSON schema
3. **State-Grounded**: Actions always consume fresh UI state
4. **Verification Loop**: Every action is verified post-execution
5. **Stable Selectors**: Elements identified by `data-voice-id`, not CSS
6. **React-Compatible**: Value setters work with React controlled components
7. **Auditable**: Every action + state delta is logged

## Files Reference

| Component | File Path |
|-----------|-----------|
| Action Schema | `frontend/src/lib/voice-action-schema.ts` |
| UI State | `frontend/src/lib/voice-ui-state.ts` |
| Action Executor | `frontend/src/lib/voice-action-executor.ts` |
| UI Controller | `frontend/src/components/voice/VoiceUIController.tsx` |
| UI State Hook | `frontend/src/hooks/useVoiceUiState.ts` |
| Voice Processor | `api/services/voice_processor.py` |
| Agent Tools | `api/services/voice_agent_tools.py` |
| V2 Router | `api/api/voice_v2_router.py` |
| Intent Classifier | `api/api/voice_intent_classifier.py` |
| ElevenLabs Service | `api/services/elevenlabs_agent.py` |
