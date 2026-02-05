import { NextRequest, NextResponse } from 'next/server';

const BACKEND_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://ec2-13-219-204-7.compute-1.amazonaws.com:8000';

const buildTargetUrl = (request: NextRequest, pathSegments: string[], baseUrl: string) => {
  const pathname = pathSegments.join('/');
  const url = new URL(request.url);
  const search = url.search ? url.search : '';
  return `${baseUrl}/api/${pathname}${search}`;
};

const forwardRequest = async (request: NextRequest, pathSegments: string[]) => {
  const targetUrl = buildTargetUrl(request, pathSegments, BACKEND_BASE);
  const headers = new Headers(request.headers);
  headers.delete('host');

  try {
    const response = await fetch(targetUrl, {
      method: request.method,
      headers,
      body: request.method === 'GET' || request.method === 'HEAD' ? undefined : request.body,
      redirect: 'manual',
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
          body: request.method === 'GET' || request.method === 'HEAD' ? undefined : request.body,
          redirect: 'manual',
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
