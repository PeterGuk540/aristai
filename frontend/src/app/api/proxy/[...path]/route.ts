import { NextRequest, NextResponse } from 'next/server';

const BACKEND_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://ec2-13-219-204-7.compute-1.amazonaws.com:8000';

const API_PROXY_BASE = '/api/proxy';

const buildTargetUrl = (request: NextRequest, pathSegments: string[], baseUrl: string) => {
  const pathname = pathSegments.join('/');
  const url = new URL(request.url);
  const search = url.search ? url.search : '';
  return `${baseUrl}/api/${pathname}${search}`;
};

const rewriteLocationHeader = (location: string | null, baseUrl: string) => {
  if (!location) return location;

  if (location.startsWith('/api/')) {
    return `${API_PROXY_BASE}${location.slice('/api'.length)}`;
  }

  const normalizedBase = baseUrl.replace(/\/$/, '');
  if (location.startsWith(normalizedBase)) {
    const relative = location.slice(normalizedBase.length);
    if (relative.startsWith('/api/')) {
      return `${API_PROXY_BASE}${relative.slice('/api'.length)}`;
    }
    return `${API_PROXY_BASE}${relative}`;
  }

  return location;
};

const forwardRequest = async (request: NextRequest, pathSegments: string[]) => {
  const targetUrl = buildTargetUrl(request, pathSegments, BACKEND_BASE);
  const headers = new Headers(request.headers);
  headers.delete('host');

  // Handle body for methods that have one (fixes Node.js 18+ duplex requirement)
  let body: BodyInit | undefined;
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    const contentType = request.headers.get('content-type') || '';

    // For multipart/form-data (file uploads), pass raw bytes to preserve binary data
    if (contentType.includes('multipart/form-data')) {
      try {
        body = await request.arrayBuffer();
      } catch {
        body = undefined;
      }
    } else {
      // For JSON and other text content, read as text
      try {
        body = await request.text();
      } catch {
        body = undefined;
      }
    }
  }

  try {
    const response = await fetch(targetUrl, {
      method: request.method,
      headers,
      body,
      redirect: 'follow',  // Follow redirects server-side to avoid redirect loops
    });

    const responseHeaders = new Headers(response.headers);
    responseHeaders.set('x-proxy-target', targetUrl);

    return new NextResponse(response.body, {
      status: response.status,
      headers: responseHeaders,
    });
  } catch (error) {
    const fallbackBase = BACKEND_BASE.startsWith('https://')
      ? BACKEND_BASE.replace('https://', 'http://')
      : null;

    if (fallbackBase && fallbackBase !== BACKEND_BASE) {
      const fallbackUrl = buildTargetUrl(request, pathSegments, fallbackBase);
      try {
        const fallbackResponse = await fetch(fallbackUrl, {
          method: request.method,
          headers,
          body,
          redirect: 'follow',
        });

        const responseHeaders = new Headers(fallbackResponse.headers);
        responseHeaders.set('x-proxy-target', fallbackUrl);
        responseHeaders.set('x-proxy-fallback', 'true');

        return new NextResponse(fallbackResponse.body, {
          status: fallbackResponse.status,
          headers: responseHeaders,
        });
      } catch (fallbackError) {
        const message = fallbackError instanceof Error ? fallbackError.message : String(fallbackError);
        return NextResponse.json(
          {
            detail: 'Proxy request failed',
            error: message,
            target: targetUrl,
            fallback_target: fallbackUrl,
          },
          { status: 502 }
        );
      }
    }

    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      {
        detail: 'Proxy request failed',
        error: message,
        target: targetUrl,
      },
      { status: 502 }
    );
  }
};

export async function GET(request: NextRequest, context: { params: { path: string[] } }) {
  return forwardRequest(request, context.params.path);
}

export async function POST(request: NextRequest, context: { params: { path: string[] } }) {
  return forwardRequest(request, context.params.path);
}

export async function PUT(request: NextRequest, context: { params: { path: string[] } }) {
  return forwardRequest(request, context.params.path);
}

export async function PATCH(request: NextRequest, context: { params: { path: string[] } }) {
  return forwardRequest(request, context.params.path);
}

export async function DELETE(request: NextRequest, context: { params: { path: string[] } }) {
  return forwardRequest(request, context.params.path);
}
