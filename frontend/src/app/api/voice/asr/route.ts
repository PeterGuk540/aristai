import { NextResponse } from 'next/server';

export const runtime = 'nodejs';

const ELEVENLABS_ASR_URL = 'https://api.elevenlabs.io/v1/speech-to-text';

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

  const response = await fetch(ELEVENLABS_ASR_URL, {
    method: 'POST',
    headers: {
      'xi-api-key': apiKey,
    },
    body: upstreamForm,
  });

  if (!response.ok) {
    const errorText = await response.text();
    return NextResponse.json({ error: errorText }, { status: response.status });
  }

  const data = await response.json();
  const transcript = data.text || data.transcript || '';
  return NextResponse.json({ transcript });
}
