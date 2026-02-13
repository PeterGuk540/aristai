import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const maxDuration = 30;

const BACKEND_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://ec2-13-219-204-7.compute-1.amazonaws.com:8000';
const REQUEST_TIMEOUT_MS = 12000;

const fetchWithTimeout = async (url: string, init: RequestInit, timeoutMs: number) => {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
};

export async function GET(request: NextRequest) {
  try {
    const targetUrl = `${BACKEND_BASE}/api/voice/agent/signed-url`;

    const response = await fetchWithTimeout(targetUrl, {
      method: 'GET',
      headers: {
        Authorization: request.headers.get('Authorization') || 'Bearer dummy-token',
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    }, REQUEST_TIMEOUT_MS);

    if (!response.ok) {
      const errorText = await response.text();
      return NextResponse.json(
        { error: `Backend error: ${response.status}`, details: errorText },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      return NextResponse.json(
        { error: 'Signed URL request timed out', timeout_ms: REQUEST_TIMEOUT_MS },
        { status: 504 }
      );
    }

    const errorMessage = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      { error: 'Internal server error', details: errorMessage },
      { status: 500 }
    );
  }
}
