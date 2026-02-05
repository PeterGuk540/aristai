import { NextRequest, NextResponse } from 'next/server';

const BACKEND_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://ec2-13-219-204-7.compute-1.amazonaws.com:8000';

const buildTargetUrl = (request: NextRequest, pathSegments: string[]) => {
  const pathname = pathSegments.join('/');
  const url = new URL(request.url);
  const search = url.search ? url.search : '';
  return `${BACKEND_BASE}/api/${pathname}${search}`;
};

const forwardRequest = async (request: NextRequest, pathSegments: string[]) => {
  const targetUrl = buildTargetUrl(request, pathSegments);
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
