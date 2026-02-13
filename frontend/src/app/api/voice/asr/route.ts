import { NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const maxDuration = 30;

const ELEVENLABS_ASR_URL = 'https://api.elevenlabs.io/v1/speech-to-text';
const REQUEST_TIMEOUT_MS = 15000;

const fetchWithTimeout = async (url: string, init: RequestInit, timeoutMs: number) => {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
};

export async function POST(request: Request) {
  const apiKey = process.env.ELEVENLABS_API_KEY;
  if (!apiKey) {
    return NextResponse.json({ error: 'Missing ElevenLabs API key.' }, { status: 500 });
  }

  const formData = await request.formData();
  const audio = formData.get('audio');

  if (!(audio instanceof File)) {
    return NextResponse.json({ error: 'Missing audio payload.' }, { status: 400 });
  }

  const upstreamForm = new FormData();
  upstreamForm.append('audio', audio, audio.name || 'voice.webm');
  upstreamForm.append('model_id', process.env.ELEVENLABS_ASR_MODEL_ID || 'scribe_v1');

  let response: Response;
  try {
    response = await fetchWithTimeout(ELEVENLABS_ASR_URL, {
      method: 'POST',
      headers: {
        'xi-api-key': apiKey,
      },
      body: upstreamForm,
    }, REQUEST_TIMEOUT_MS);
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      return NextResponse.json(
        { error: 'ASR request timed out.', timeout_ms: REQUEST_TIMEOUT_MS },
        { status: 504 }
      );
    }
    throw error;
  }

  if (!response.ok) {
    const errorText = await response.text();
    return NextResponse.json({ error: errorText }, { status: response.status });
  }

  const data = await response.json();
  const transcript = data.text || data.transcript || '';
  return NextResponse.json({ transcript });
}
