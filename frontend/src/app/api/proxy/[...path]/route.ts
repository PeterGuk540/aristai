import { NextRequest, NextResponse } from 'next/server';

// Backend API URL - API Gateway with Cognito JWT authentication
// API Gateway in us-east-1 (same region as EC2), using aristai-user-pool for JWT validation
const BACKEND_URL = 'https://koxlvlxb74.execute-api.us-east-1.amazonaws.com';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return handleProxy(request, params, 'GET');
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return handleProxy(request, params, 'POST');
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return handleProxy(request, params, 'PUT');
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return handleProxy(request, params, 'PATCH');
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return handleProxy(request, params, 'DELETE');
}

async function handleProxy(
  request: NextRequest,
  paramsPromise: Promise<{ path: string[] }>,
  method: string
) {
  const params = await paramsPromise;
  const path = params.path.join('/');
  const url = new URL(request.url);
  const queryString = url.search;

  let targetUrl = `${BACKEND_URL}/api/${path}${queryString}`;

  // Legacy voice synthesis endpoint removed - use ElevenLabs Agents signed URL flow instead
  // if (path.includes('voice/synthesize') && process.env.NODE_ENV !== 'production') {
  //   targetUrl = `http://localhost:8000/api/voice/synthesize${queryString}`;
  //   console.log('🎯 Voice synthesis request -> forwarding to local backend:', targetUrl);
  // }
  
  // Note: /api/voice/synthesize is deprecated for production
  // Use /api/voice/agent/signed-url + official ElevenLabs SDK instead

  try {
    const headers = new Headers(request.headers);
    headers.delete('host');
    headers.delete('content-length');

    const fetchOptions: RequestInit = {
      method,
      headers,
    };

    // Include body for POST, PUT, PATCH requests
    if (['POST', 'PUT', 'PATCH'].includes(method)) {
      try {
        const body = await request.arrayBuffer();
        if (body.byteLength > 0) {
          fetchOptions.body = body;
        }
      } catch {
        // No body
      }
    }

    const response = await fetch(targetUrl, fetchOptions);

    // Handle 204 No Content
    if (response.status === 204) {
      return new NextResponse(null, { status: 204 });
    }

    const contentType = response.headers.get('content-type') || '';

    if (contentType.includes('application/json')) {
      const data = await response.json();
      return NextResponse.json(data, { status: response.status });
    }

    const buffer = await response.arrayBuffer();
    const proxiedHeaders = new Headers(response.headers);
    return new NextResponse(buffer, {
      status: response.status,
      headers: proxiedHeaders,
    });
  } catch (error) {
    console.error('Proxy error:', error);
    return NextResponse.json(
      { detail: 'Backend API unavailable' },
      { status: 502 }
    );
  }
}
