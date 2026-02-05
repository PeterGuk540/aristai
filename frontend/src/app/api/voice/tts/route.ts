import { NextResponse } from 'next/server';

export const runtime = 'nodejs';

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

  const response = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${voiceId}`, {
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
  });

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
