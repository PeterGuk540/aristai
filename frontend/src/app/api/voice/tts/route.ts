import { NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const maxDuration = 30;
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
  const voiceId = process.env.ELEVENLABS_VOICE_ID;
  if (!apiKey || !voiceId) {
    return NextResponse.json({ error: 'Missing ElevenLabs configuration.' }, { status: 500 });
  }

  const body = await request.json().catch(() => null);
  const text = body?.text;
  if (!text) {
    return NextResponse.json({ error: 'Missing text payload.' }, { status: 400 });
  }

  let response: Response;
  try {
    response = await fetchWithTimeout(`https://api.elevenlabs.io/v1/text-to-speech/${voiceId}`, {
      method: 'POST',
      headers: {
        'xi-api-key': apiKey,
        'Content-Type': 'application/json',
        Accept: 'audio/mpeg',
      },
      body: JSON.stringify({
        text,
        model_id: process.env.ELEVENLABS_TTS_MODEL_ID || 'eleven_multilingual_v2',
        voice_settings: {
          stability: 0.45,
          similarity_boost: 0.85,
          style: 0,
          use_speaker_boost: true,
        },
      }),
    }, REQUEST_TIMEOUT_MS);
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      return NextResponse.json(
        { error: 'TTS request timed out.', timeout_ms: REQUEST_TIMEOUT_MS },
        { status: 504 }
      );
    }
    throw error;
  }

  if (!response.ok) {
    const errorText = await response.text();
    return NextResponse.json({ error: errorText }, { status: response.status });
  }

  const audioBuffer = await response.arrayBuffer();
  return new NextResponse(audioBuffer, {
    headers: {
      'Content-Type': 'audio/mpeg',
    },
  });
}
