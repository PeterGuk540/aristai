import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    console.log('🔧 Next.js MCP proxy: Forwarding request to backend');
    
    const body = await request.json();
    console.log('📨 MCP tool request:', body);
    
    // Forward through the local proxy to avoid exposing backend ports to the browser.
    const targetUrl = new URL('/api/proxy/mcp/execute', request.url).toString();
    
    const response = await fetch(targetUrl, {
      method: 'POST',
      headers: {
        'Authorization': request.headers.get('Authorization') || 'Bearer dummy-token',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    
    console.log('🔗 MCP backend response status:', response.status);
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('❌ MCP backend error:', errorText);
      return NextResponse.json(
        { error: `MCP backend error: ${response.status}`, details: errorText },
        { status: response.status }
      );
    }
    
    const data = await response.json();
    console.log('✅ MCP backend response received');
    return NextResponse.json(data);
    
  } catch (error) {
    console.error('❌ MCP proxy error:', error);
    const errorMessage = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      { error: 'Internal server error', details: errorMessage },
      { status: 500 }
    );
  }
}
