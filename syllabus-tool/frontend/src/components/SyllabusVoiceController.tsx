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
    const el = document.querySelector<HTMLElement>(`[data-voice-id="${params.voiceId}"]`);
    if (el) {
      el.click();
      return JSON.stringify({ ok: true, did: `Clicked ${params.voiceId}` });
    }
    console.warn('[SyllabusVoice] Button not found:', params.voiceId);
    return JSON.stringify({ ok: false, error: `Not found: ${params.voiceId}` });
  }, []);

  const handleFillInput = useCallback(async (params: { voiceId: string; value: string }): Promise<string> => {
    console.log('[SyllabusVoice] Tool: fill_input', { voiceId: params.voiceId, value: params.value?.substring(0, 50) });

    // Strategy 1: Direct DOM manipulation (like forum's action-registry)
    const el = document.querySelector<HTMLInputElement | HTMLTextAreaElement>(
      `[data-voice-id="${params.voiceId}"]`
    );
    if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) {
      setReactInputValue(el, params.value);
      el.focus();
      console.log('[SyllabusVoice] fill_input: Set via native setter', params.voiceId);
      return JSON.stringify({ ok: true, did: `Filled ${params.voiceId}` });
    }

    // Strategy 2: Fallback to custom event (for components that listen for voice:fill)
    console.log('[SyllabusVoice] fill_input: Falling back to voice:fill event', params.voiceId);
    window.dispatchEvent(new CustomEvent('voice:fill', {
      detail: { voiceId: params.voiceId, value: params.value },
    }));
    return JSON.stringify({ ok: true, did: `Filled ${params.voiceId}` });
  }, []);

  const handleSwitchTab = useCallback(async (params: { tabName: string }): Promise<string> => {
    console.log('[SyllabusVoice] Tool: switch_tab', params);
    const el = document.querySelector<HTMLElement>(`[data-voice-id="syllabus-form-tab-${params.tabName}"]`)
            || document.querySelector<HTMLElement>(`[data-voice-id="syllabus-step-${params.tabName}"]`);
    if (el) {
      el.click();
      return JSON.stringify({ ok: true, did: `Switched to ${params.tabName}` });
    }
    console.warn('[SyllabusVoice] Tab not found:', params.tabName);
    return JSON.stringify({ ok: false, error: `Tab not found: ${params.tabName}` });
  }, []);

  const handleSelectDropdown = useCallback(async (params: { voiceId: string; value: string }): Promise<string> => {
    console.log('[SyllabusVoice] Tool: select_dropdown', params);

    // Strategy 1: Direct DOM manipulation (like forum's approach)
    const el = document.querySelector<HTMLSelectElement>(
      `select[data-voice-id="${params.voiceId}"]`
    );
    if (el) {
      setReactSelectValue(el, params.value);
      console.log('[SyllabusVoice] select_dropdown: Set via native setter', params.voiceId, '→', params.value);
      return JSON.stringify({ ok: true, did: `Selected ${params.value} on ${params.voiceId}` });
    }

    // Strategy 2: Fallback to custom event
    console.log('[SyllabusVoice] select_dropdown: Falling back to voice:select event', params.voiceId);
    window.dispatchEvent(new CustomEvent('voice:select', {
      detail: { voiceId: params.voiceId, value: params.value },
    }));
    return JSON.stringify({ ok: true, did: `Selected ${params.value} on ${params.voiceId}` });
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

    try {
      // Request microphone permission
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach(track => track.stop());
      } catch {
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
  // RENDER
  // =============================================================================

  // Status indicator color
  const statusDot = () => {
    switch (state) {
      case 'connecting': return 'bg-yellow-500 animate-pulse';
      case 'connected': return 'bg-green-500';
      case 'listening': return 'bg-red-500 animate-pulse';
      case 'processing': return 'bg-blue-500 animate-pulse';
      case 'speaking': return 'bg-purple-500 animate-pulse';
      case 'error': return 'bg-red-600';
      default: return 'bg-gray-300';
    }
  };

  const statusText = () => {
    const labels: Record<ConversationState, [string, string]> = {
      connecting: ['Connecting...', 'Conectando...'],
      connected: ['Ready', 'Listo'],
      listening: ['Listening...', 'Escuchando...'],
      processing: ['Thinking...', 'Pensando...'],
      speaking: ['Speaking...', 'Hablando...'],
      disconnected: ['Disconnected', 'Desconectado'],
      error: ['Error', 'Error'],
    };
    const [en, es] = labels[state] || ['', ''];
    return lang === 'es' ? es : en;
  };

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
              <svg className="w-5 h-5 text-emerald-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="23" />
                <line x1="8" y1="23" x2="16" y2="23" />
              </svg>
              <span className="text-sm font-medium text-gray-900">
                {lang === 'es' ? 'Asistente de Voz' : 'Voice Assistant'}
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
                title={lang === 'en' ? 'English' : 'Spanish'}
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="2" y1="12" x2="22" y2="12" />
                  <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                </svg>
                <span className="text-xs font-medium uppercase">{lang}</span>
              </button>
              {/* Expand/collapse */}
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="p-1 rounded hover:bg-gray-100 transition-colors"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  {isExpanded
                    ? <><polyline points="4 14 10 14 10 20" /><polyline points="20 10 14 10 14 4" /><line x1="14" y1="10" x2="21" y2="3" /><line x1="3" y1="21" x2="10" y2="14" /></>
                    : <><polyline points="15 3 21 3 21 9" /><polyline points="9 21 3 21 3 15" /><line x1="21" y1="3" x2="14" y2="10" /><line x1="3" y1="21" x2="10" y2="14" /></>
                  }
                </svg>
              </button>
              {/* Minimize */}
              <button
                onClick={() => setIsMinimized(true)}
                className="p-1 rounded hover:bg-gray-100 transition-colors"
              >
                <div className="w-4 h-1 bg-gray-500" />
              </button>
            </div>
          </div>

          {/* Status bar */}
          <div className="px-3 py-2 text-xs text-center border-b border-gray-200">
            <div className="flex items-center justify-center gap-2">
              <div className={`w-2 h-2 rounded-full ${statusDot()}`} />
              <span className="text-gray-600 capitalize">{statusText()}</span>
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
                    <div className="w-6 h-6 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0">
                      <svg className="w-4 h-4 text-emerald-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                      </svg>
                    </div>
                  )}
                  <div className={`max-w-[75%] px-3 py-2 rounded-lg text-sm ${
                    msg.role === 'user'
                      ? 'bg-emerald-600 text-white'
                      : 'bg-gray-100 text-gray-900'
                  }`}>
                    {msg.content}
                  </div>
                  {msg.role === 'user' && (
                    <div className="w-6 h-6 rounded-full bg-emerald-600 flex items-center justify-center flex-shrink-0">
                      <svg className="w-3 h-3 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                      </svg>
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
                    ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                    : 'bg-red-600 hover:bg-red-700 text-white'
                } ${isConnecting ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                {state === 'disconnected' || state === 'error' ? (
                  <>
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                    </svg>
                    {lang === 'es' ? 'Iniciar' : 'Start'}
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <line x1="1" y1="1" x2="23" y2="23" />
                      <path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6" />
                      <path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2c0 .76-.12 1.5-.34 2.18" />
                    </svg>
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
        /* Minimized - circular button */
        <div className="flex items-center justify-center h-full">
          <button
            onClick={() => setIsMinimized(false)}
            className="flex items-center justify-center w-full h-full hover:bg-gray-100 transition-colors rounded-lg relative"
          >
            <svg className="w-6 h-6 text-emerald-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="23" />
              <line x1="8" y1="23" x2="16" y2="23" />
            </svg>
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
