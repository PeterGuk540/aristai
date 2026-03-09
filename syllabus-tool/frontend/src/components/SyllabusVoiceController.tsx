/**
 * SyllabusVoiceController - Standalone voice controller for the Syllabus Tool
 *
 * Adapted from the forum's ConversationalVoiceV2, but simpler:
 * - No navigation, generate_content, or get_smart_context
 * - Only 5 syllabus-specific client tools
 * - Executes directly in the same DOM (no iframe/bridge)
 */

import { useEffect, useState, useRef, useCallback } from 'react';
import { Conversation } from '@elevenlabs/client';
import { fetchWithAuth } from '../lib/fetchWithAuth';

// =============================================================================
// ALIAS MAPS — Common terms the agent might use → actual data-voice-id
// =============================================================================

const INPUT_ALIASES: Record<string, string> = {
  'title': 'syllabus-draft-title',
  'course title': 'syllabus-draft-title',
  'name': 'syllabus-draft-title',
  'audience': 'syllabus-draft-audience',
  'target audience': 'syllabus-draft-audience',
  'students': 'syllabus-draft-audience',
  'duration': 'syllabus-draft-duration',
  'length': 'syllabus-draft-duration',
  'weeks': 'syllabus-draft-duration',
  'syllabus': 'syllabus-draft-syllabus',
  'content': 'syllabus-draft-syllabus',
  'syllabus content': 'syllabus-draft-syllabus',
};

const DROPDOWN_ALIASES: Record<string, string> = {
  'reference': 'syllabus-draft-reference',
  'reference file': 'syllabus-draft-reference',
  'reference document': 'syllabus-draft-reference',
  'file': 'syllabus-draft-reference',
  'document': 'syllabus-draft-reference',
  'duration': 'syllabus-draft-duration',
};

const BUTTON_ALIASES: Record<string, string> = {
  'generate': 'syllabus-generate-btn',
  'generate syllabus': 'syllabus-generate-btn',
  'create': 'syllabus-generate-btn',
  'download': 'syllabus-download-btn',
  'save': 'syllabus-save-btn',
  'export': 'syllabus-export-btn',
  'reset': 'syllabus-reset-btn',
  'clear': 'syllabus-reset-btn',
};

const TAB_ALIASES: Record<string, string> = {
  'upload': 'syllabus-step-upload',
  'draft': 'syllabus-step-draft',
  'review': 'syllabus-step-review',
  'edit': 'syllabus-form-tab-edit',
  'preview': 'syllabus-form-tab-preview',
  'compare': 'syllabus-form-tab-compare',
  'diff': 'syllabus-form-tab-compare',
};

/**
 * Fuzzy resolve a voice target to a DOM element.
 * Mirrors the forum's resolveTarget() with 5 strategies.
 */
function resolveVoiceTarget(
  target: string,
  aliasMap: Record<string, string>
): HTMLElement | null {
  const normalized = target.toLowerCase().trim();
  const hyphenated = normalized.replace(/\s+/g, '-');

  // Strategy 1: Check alias map
  const aliasId = aliasMap[normalized];
  if (aliasId) {
    const el = document.querySelector<HTMLElement>(`[data-voice-id="${aliasId}"]`);
    if (el) return el;
  }

  // Strategy 2: Direct data-voice-id match
  let el = document.querySelector<HTMLElement>(`[data-voice-id="${target}"]`);
  if (el) return el;

  // Strategy 3: Hyphenated match
  el = document.querySelector<HTMLElement>(`[data-voice-id="${hyphenated}"]`);
  if (el) return el;

  // Strategy 4: Partial match (data-voice-id contains the target)
  el = document.querySelector<HTMLElement>(`[data-voice-id*="${hyphenated}"]`);
  if (el) return el;

  // Strategy 5: Fuzzy word match — all words in target appear in some voice-id
  const targetWords = normalized.split(/\s+/);
  if (targetWords.length > 0) {
    const allVoiceElements = document.querySelectorAll('[data-voice-id]');
    for (const elem of allVoiceElements) {
      const voiceId = elem.getAttribute('data-voice-id')?.toLowerCase() || '';
      if (targetWords.every(word => voiceId.includes(word))) {
        return elem as HTMLElement;
      }
    }
  }

  return null;
}

// =============================================================================
// TYPES
// =============================================================================

type ConversationState =
  | 'connecting'
  | 'connected'
  | 'listening'
  | 'processing'
  | 'speaking'
  | 'disconnected'
  | 'error';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
}

interface Props {
  language?: 'en' | 'es';
}

// =============================================================================
// COMPONENT
// =============================================================================

export function SyllabusVoiceController({ language = 'en' }: Props) {
  const [state, setState] = useState<ConversationState>('disconnected');
  const [isExpanded, setIsExpanded] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [error, setError] = useState('');
  const [lang, setLang] = useState(language);

  const conversationRef = useRef<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isInitializingRef = useRef(false);
  const hasUserActivatedRef = useRef(false);
  const previousLangRef = useRef(lang);

  const apiUrl = import.meta.env.VITE_API_URL || '/api/v1';

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Cleanup on unmount
  useEffect(() => {
    return () => { cleanup(); };
  }, []);

  // Reconnect when language changes (only if user already activated)
  useEffect(() => {
    if (previousLangRef.current !== lang && hasUserActivatedRef.current) {
      const newLang = lang;
      previousLangRef.current = lang;
      (async () => {
        await cleanup();
        await new Promise(r => setTimeout(r, 300));
        isInitializingRef.current = false;
        await initializeConversation(newLang);
      })();
    } else {
      previousLangRef.current = lang;
    }
  }, [lang]);

  const cleanup = async () => {
    if (conversationRef.current) {
      try { await conversationRef.current.endSession(); } catch {}
      conversationRef.current = null;
    }
  };

  // =============================================================================
  // CLIENT TOOLS — Direct DOM manipulation (same approach as the forum)
  // =============================================================================

  /**
   * Set a value on a React controlled input/textarea using native setter
   * + _valueTracker reset to ensure React detects the change.
   */
  const setReactInputValue = (el: HTMLInputElement | HTMLTextAreaElement, value: string) => {
    const isTextArea = el.tagName === 'TEXTAREA';
    const nativeSetter = Object.getOwnPropertyDescriptor(
      isTextArea ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype,
      'value'
    )?.set;

    if (nativeSetter) {
      nativeSetter.call(el, value);
    } else {
      el.value = value;
    }

    // Reset React's internal _valueTracker so React detects the change
    const tracker = (el as any)._valueTracker;
    if (tracker) tracker.setValue('');

    el.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
    el.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
  };

  /**
   * Set a value on a React controlled <select> using native setter
   * + _valueTracker reset.
   */
  const setReactSelectValue = (el: HTMLSelectElement, value: string) => {
    const nativeSetter = Object.getOwnPropertyDescriptor(
      window.HTMLSelectElement.prototype, 'value'
    )?.set;

    if (nativeSetter) {
      nativeSetter.call(el, value);
    } else {
      el.value = value;
    }

    const tracker = (el as any)._valueTracker;
    if (tracker) tracker.setValue('');

    el.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
  };

  const handleClickButton = useCallback(async (params: { voiceId: string }): Promise<string> => {
    console.log('[SyllabusVoice] Tool: click_button', params);
    const el = resolveVoiceTarget(params.voiceId, BUTTON_ALIASES);
    if (el) {
      el.click();
      console.log('[SyllabusVoice] click_button: Clicked', el.getAttribute('data-voice-id'));
      return JSON.stringify({ ok: true, did: `Clicked ${params.voiceId}` });
    }
    console.warn('[SyllabusVoice] Button not found:', params.voiceId);
    return JSON.stringify({ ok: false, error: `Not found: ${params.voiceId}` });
  }, []);

  const handleFillInput = useCallback(async (params: { voiceId: string; value: string }): Promise<string> => {
    console.log('[SyllabusVoice] Tool: fill_input', { voiceId: params.voiceId, value: params.value?.substring(0, 50) });

    // Use fuzzy resolver to find the element (like forum's resolveTarget)
    const el = resolveVoiceTarget(params.voiceId, INPUT_ALIASES);
    const resolvedId = el?.getAttribute('data-voice-id') || params.voiceId;

    // Strategy 1: Direct DOM manipulation (like forum's action-registry)
    if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) {
      setReactInputValue(el as HTMLInputElement | HTMLTextAreaElement, params.value);
      el.focus();
      console.log('[SyllabusVoice] fill_input: Set via native setter', resolvedId);
    }

    // Strategy 2: ALWAYS also dispatch custom event (for components that listen for voice:fill)
    // Use the resolved voice-id so CommandCenter.tsx event listener matches correctly
    console.log('[SyllabusVoice] fill_input: Dispatching voice:fill event', resolvedId);
    window.dispatchEvent(new CustomEvent('voice:fill', {
      detail: { voiceId: resolvedId, value: params.value },
    }));
    return JSON.stringify({ ok: true, did: `Filled ${resolvedId}` });
  }, []);

  const handleSwitchTab = useCallback(async (params: { tabName: string }): Promise<string> => {
    console.log('[SyllabusVoice] Tool: switch_tab', params);
    // Try fuzzy resolution first, then fall back to prefixed lookups
    const el = resolveVoiceTarget(params.tabName, TAB_ALIASES)
            || document.querySelector<HTMLElement>(`[data-voice-id="syllabus-form-tab-${params.tabName}"]`)
            || document.querySelector<HTMLElement>(`[data-voice-id="syllabus-step-${params.tabName}"]`);
    if (el) {
      el.click();
      console.log('[SyllabusVoice] switch_tab: Clicked', el.getAttribute('data-voice-id'));
      return JSON.stringify({ ok: true, did: `Switched to ${params.tabName}` });
    }
    console.warn('[SyllabusVoice] Tab not found:', params.tabName);
    return JSON.stringify({ ok: false, error: `Tab not found: ${params.tabName}` });
  }, []);

  const handleSelectDropdown = useCallback(async (params: { voiceId: string; value: string }): Promise<string> => {
    console.log('[SyllabusVoice] Tool: select_dropdown', params);

    // Use fuzzy resolver to find the element
    const el = resolveVoiceTarget(params.voiceId, DROPDOWN_ALIASES);
    const resolvedId = el?.getAttribute('data-voice-id') || params.voiceId;

    // Strategy 1: Direct DOM manipulation (like forum's approach)
    if (el && el.tagName === 'SELECT') {
      setReactSelectValue(el as HTMLSelectElement, params.value);
      console.log('[SyllabusVoice] select_dropdown: Set via native setter', resolvedId, '→', params.value);
    }

    // Strategy 2: ALWAYS also dispatch custom event
    // Use resolved voice-id so CommandCenter.tsx event listener matches
    console.log('[SyllabusVoice] select_dropdown: Dispatching voice:select event', resolvedId);
    window.dispatchEvent(new CustomEvent('voice:select', {
      detail: { voiceId: resolvedId, value: params.value },
    }));
    return JSON.stringify({ ok: true, did: `Selected ${params.value} on ${resolvedId}` });
  }, []);

  const handleGetUiState = useCallback(async (): Promise<string> => {
    console.log('[SyllabusVoice] Tool: get_ui_state');
    const voiceEls = document.querySelectorAll('[data-voice-id]');
    const visible = Array.from(voiceEls).filter(el => (el as HTMLElement).offsetParent !== null);
    const visibleIds = visible.map(el => el.getAttribute('data-voice-id'));

    const dropdowns: Record<string, { value: string; options: { value: string; label: string }[] }> = {};
    const fields: Record<string, string> = {};
    for (const el of visible) {
      const vid = el.getAttribute('data-voice-id')!;
      if (el.tagName === 'SELECT') {
        const sel = el as HTMLSelectElement;
        dropdowns[vid] = {
          value: sel.value,
          options: Array.from(sel.options).map(o => ({ value: o.value, label: o.text })),
        };
      } else if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        const val = (el as HTMLInputElement).value;
        if (val) fields[vid] = val;
      }
    }

    const step = document.querySelector('[data-voice-id^="syllabus-step-"].font-bold')
      ?.getAttribute('data-voice-id')?.replace('syllabus-step-', '') || 'unknown';
    const activeTab = document.querySelector('[data-voice-id^="syllabus-form-tab-"].border-b-2')
      ?.getAttribute('data-voice-id')?.replace('syllabus-form-tab-', '') || null;

    const state = { step, activeTab, visibleIds, dropdowns, fields };
    console.log('[SyllabusVoice] get_ui_state result:', state);
    return JSON.stringify({ ok: true, did: JSON.stringify(state) });
  }, []);

  // =============================================================================
  // INITIALIZATION
  // =============================================================================

  const initializeConversation = async (targetLang?: string) => {
    if (isInitializingRef.current) return;
    isInitializingRef.current = true;

    const langToUse = targetLang || lang;
    setState('connecting');
    setError('');

    // Warm up AudioContext immediately (synchronous, within user gesture context)
    // This prevents the browser from suspending AudioContext created later by the SDK
    let warmupCtx: AudioContext | null = null;
    try {
      warmupCtx = new AudioContext();
      console.log('[SyllabusVoice] AudioContext warmed up, state:', warmupCtx.state);
    } catch (e) {
      console.warn('[SyllabusVoice] AudioContext warmup failed:', e);
    }

    try {
      // Request microphone permission
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach(track => track.stop());
      } catch {
        warmupCtx?.close();
        setState('error');
        setError(langToUse === 'es'
          ? 'Se necesita acceso al micrófono. Por favor permite el acceso e intenta de nuevo.'
          : 'Microphone access is required. Please allow microphone access and try again.');
        isInitializingRef.current = false;
        return;
      }

      // Get signed URL from our own backend
      const resp = await fetchWithAuth(`${apiUrl}/voice/signed-url?language=${langToUse}`);
      if (!resp.ok) throw new Error(`Failed to get signed URL: ${resp.status}`);
      const { signed_url } = await resp.json();

      // Resume warmup AudioContext to ensure browser allows audio
      if (warmupCtx && warmupCtx.state === 'suspended') {
        await warmupCtx.resume();
        console.log('[SyllabusVoice] AudioContext resumed before startSession');
      }

      // Start ElevenLabs conversation
      conversationRef.current = await Conversation.startSession({
        signedUrl: signed_url,
        overrides: {
          agent: { language: langToUse as 'en' | 'es' },
        },
        dynamicVariables: { language: langToUse },
        clientTools: {
          click_button: handleClickButton,
          fill_input: handleFillInput,
          switch_tab: handleSwitchTab,
          select_dropdown: handleSelectDropdown,
          get_ui_state: handleGetUiState,
        },

        onConnect: ({ conversationId }: { conversationId: string }) => {
          console.log('[SyllabusVoice] Connected:', conversationId);
          setState('connected');
          isInitializingRef.current = false;
          // Close the warmup AudioContext now that the SDK has its own
          warmupCtx?.close();
          warmupCtx = null;

          const greetingMsg = langToUse === 'es'
            ? '¡Hola! Soy tu asistente de sílabo. ¿Qué te gustaría hacer?'
            : 'Hello! I\'m your syllabus assistant. What would you like to do?';
          addMessage('assistant', greetingMsg);
        },

        onDisconnect: () => {
          setState('disconnected');
          conversationRef.current = null;
        },

        onStatusChange: ({ status }: { status: string }) => {
          switch (status) {
            case 'connecting': setState('connecting'); break;
            case 'connected': setState('connected'); break;
            case 'listening': setState('listening'); break;
            case 'thinking': setState('processing'); break;
            case 'speaking': setState('speaking'); break;
            case 'disconnected': setState('disconnected'); break;
          }
        },

        onMessage: ({ source, message }: { source: 'user' | 'ai'; message: string }) => {
          if (message?.trim()) {
            addMessage(source === 'user' ? 'user' : 'assistant', message);
          }
        },

        onError: (err: string) => {
          console.error('[SyllabusVoice] Error:', err);
          setError(err);
          setState('error');
        },
      });
    } catch (err: any) {
      console.error('[SyllabusVoice] Failed to initialize:', err);
      warmupCtx?.close();
      warmupCtx = null;
      setError(err.message || 'Failed to initialize voice assistant');
      setState('error');
      isInitializingRef.current = false;
    }
  };

  // =============================================================================
  // HELPERS
  // =============================================================================

  const addMessage = (role: 'user' | 'assistant' | 'system', content: string) => {
    setMessages(prev => [...prev, {
      id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
      role,
      content,
      timestamp: new Date(),
    }]);
  };

  const toggleConversation = async () => {
    if (state === 'disconnected' || state === 'error') {
      hasUserActivatedRef.current = true;
      await initializeConversation();
    } else if (conversationRef.current) {
      await conversationRef.current.endSession();
      setState('disconnected');
    }
  };

  const restartConversation = async () => {
    hasUserActivatedRef.current = true;
    await cleanup();
    setMessages([]);
    isInitializingRef.current = false;
    await initializeConversation();
  };

  const isConnecting = state === 'connecting';
  const isReady = ['connected', 'listening', 'processing', 'speaking'].includes(state);
  const isActive = state !== 'disconnected' && state !== 'error';

  // =============================================================================
  // RENDER — Identical to forum's ConversationalVoiceV2
  // =============================================================================

  // Mic SVG icons (inline since syllabus tool doesn't have lucide-react)
  const MicIcon = ({ className = 'w-4 h-4' }: { className?: string }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );

  const MicOffIcon = ({ className = 'w-4 h-4' }: { className?: string }) => (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="1" y1="1" x2="23" y2="23" />
      <path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6" />
      <path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2c0 .76-.12 1.5-.34 2.18" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );

  const GlobeIcon = () => (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  );

  const MinimizeIcon = () => (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="4 14 10 14 10 20" /><polyline points="20 10 14 10 14 4" />
      <line x1="14" y1="10" x2="21" y2="3" /><line x1="3" y1="21" x2="10" y2="14" />
    </svg>
  );

  const MaximizeIcon = () => (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="15 3 21 3 21 9" /><polyline points="9 21 3 21 3 15" />
      <line x1="21" y1="3" x2="14" y2="10" /><line x1="3" y1="21" x2="10" y2="14" />
    </svg>
  );

  return (
    <div
      className={`fixed z-50 bg-white rounded-lg shadow-xl border border-gray-200 transition-all duration-300 right-4 bottom-4 ${
        isMinimized ? 'w-12 h-12' : isExpanded ? 'w-96 h-[600px]' : 'w-80 h-[500px]'
      }`}
    >
      {!isMinimized ? (
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between p-3 border-b border-gray-200">
            <div className="flex items-center gap-2">
              <img
                src="/AristAI_icon.png"
                alt="Carol"
                className="w-4 h-4 object-contain"
              />
              <span className="text-sm font-medium text-gray-900">
                Carol
              </span>
              {isActive && (
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              )}
            </div>

            <div className="flex items-center gap-1">
              {/* Language toggle */}
              <button
                onClick={() => setLang(lang === 'en' ? 'es' : 'en')}
                className="p-1 rounded hover:bg-gray-100 transition-colors flex items-center gap-1"
                title={`Language: ${lang === 'en' ? 'English' : 'Spanish'}`}
              >
                <GlobeIcon />
                <span className="text-xs font-medium uppercase">{lang}</span>
              </button>
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="p-1 rounded hover:bg-gray-100 transition-colors"
              >
                {isExpanded ? <MinimizeIcon /> : <MaximizeIcon />}
              </button>
              <button
                onClick={() => setIsMinimized(true)}
                className="p-1 rounded hover:bg-gray-100 transition-colors"
              >
                <div className="w-4 h-1 bg-gray-500" />
              </button>
            </div>
          </div>

          {/* Status */}
          <div className="px-3 py-2 text-xs text-center border-b border-gray-200">
            <div className="flex items-center justify-center gap-2">
              {state === 'connecting' && <div className="w-2 h-2 bg-yellow-500 rounded-full animate-pulse" />}
              {state === 'connected' && <div className="w-2 h-2 bg-green-500 rounded-full" />}
              {state === 'listening' && <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />}
              {state === 'processing' && <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />}
              {state === 'speaking' && <div className="w-2 h-2 bg-purple-500 rounded-full animate-pulse" />}
              {state === 'disconnected' && <div className="w-2 h-2 bg-gray-300 rounded-full" />}
              {state === 'error' && <div className="w-2 h-2 bg-red-600 rounded-full" />}

              <span className="text-gray-600 capitalize">
                {state === 'connecting' && (lang === 'es' ? 'Conectando...' : 'Connecting...')}
                {state === 'connected' && (lang === 'es' ? 'Listo' : 'Ready')}
                {state === 'listening' && (lang === 'es' ? 'Escuchando...' : 'Listening...')}
                {state === 'processing' && (lang === 'es' ? 'Pensando...' : 'Thinking...')}
                {state === 'speaking' && (lang === 'es' ? 'Hablando...' : 'Speaking...')}
                {state === 'disconnected' && (lang === 'es' ? 'Desconectado' : 'Disconnected')}
                {state === 'error' && 'Error'}
              </span>
            </div>
          </div>

          {/* Messages */}
          <div className={`flex-1 overflow-y-auto p-3 space-y-2 ${isExpanded ? 'max-h-[400px]' : 'max-h-[280px]'}`}>
            {messages.length === 0 ? (
              <div className="text-center text-gray-500 text-sm py-4">
                {isReady
                  ? (lang === 'es' ? 'Escuchando... Habla ahora.' : 'Listening... Speak now.')
                  : (lang === 'es' ? 'Haz clic en Iniciar para comenzar' : 'Click Start to begin')}
              </div>
            ) : (
              messages.filter(m => m.role !== 'system').map((msg) => (
                <div key={msg.id} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  {msg.role === 'assistant' && (
                    <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0 overflow-hidden">
                      <img
                        src="/AristAI_icon.png"
                        alt="Carol"
                        className="w-5 h-5 object-contain"
                      />
                    </div>
                  )}
                  <div className={`max-w-[75%] px-3 py-2 rounded-lg text-sm ${
                    msg.role === 'user'
                      ? 'text-white'
                      : 'bg-gray-100 text-gray-900'
                  }`}
                    style={msg.role === 'user' ? { backgroundColor: '#2d5a94' } : undefined}
                  >
                    {msg.content}
                  </div>
                  {msg.role === 'user' && (
                    <div className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0" style={{ backgroundColor: '#2d5a94' }}>
                      <MicIcon className="w-3 h-3 text-white" />
                    </div>
                  )}
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Error */}
          {error && (
            <div className="px-3 py-2 bg-red-50 border-t border-red-200">
              <p className="text-xs text-red-600">{error}</p>
            </div>
          )}

          {/* Controls */}
          <div className="p-3 border-t border-gray-200">
            <div className="flex items-center gap-2">
              <button
                onClick={toggleConversation}
                disabled={isConnecting}
                className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  state === 'disconnected' || state === 'error'
                    ? 'text-white hover:opacity-90'
                    : 'bg-red-600 hover:bg-red-700 text-white'
                } ${isConnecting ? 'opacity-50 cursor-not-allowed' : ''}`}
                style={state === 'disconnected' || state === 'error' ? { backgroundColor: '#2d5a94' } : undefined}
              >
                {state === 'disconnected' || state === 'error' ? (
                  <>
                    <MicIcon />
                    {lang === 'es' ? 'Iniciar' : 'Start'}
                  </>
                ) : (
                  <>
                    <MicOffIcon />
                    {lang === 'es' ? 'Detener' : 'Stop'}
                  </>
                )}
              </button>

              {state === 'error' && (
                <button
                  onClick={restartConversation}
                  className="px-3 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg text-sm font-medium transition-colors"
                >
                  {lang === 'es' ? 'Reiniciar' : 'Restart'}
                </button>
              )}
            </div>
          </div>
        </div>
      ) : (
        /* Minimized */
        <div className="flex items-center justify-center h-full">
          <button
            onClick={() => setIsMinimized(false)}
            className="flex items-center justify-center w-full h-full hover:bg-gray-100 transition-colors rounded-lg relative"
          >
            <img
              src="/AristAI_icon.png"
              alt="AristAI"
              className="w-10 h-10 object-contain"
              onError={(e) => {
                e.currentTarget.style.display = 'none';
              }}
            />
            {isActive && (
              <div className="absolute top-2 right-2 w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            )}
          </button>
        </div>
      )}
    </div>
  );
}

export default SyllabusVoiceController;
