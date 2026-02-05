import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  try {
    console.log('📡 Next.js API proxy: Forwarding request to backend');
    
    // Forward to backend voice service on EC2
    const backendUrl = process.env.BACKEND_URL
      || process.env.NEXT_PUBLIC_API_URL
      || 'http://ec2-13-219-204-7.compute-1.amazonaws.com:8000'; // EC2 backend URL
    const targetUrl = `${backendUrl}/api/voice/agent/signed-url`;
    
    const response = await fetch(targetUrl, {
      method: 'GET',
      headers: {
        'Authorization': request.headers.get('Authorization') || 'Bearer dummy-token',
        'Content-Type': 'application/json',
      },
    });
    
    console.log('🔗 Backend response status:', response.status);
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error('❌ Backend error:', errorText);
      return NextResponse.json(
        { error: `Backend error: ${response.status}`, details: errorText },
        { status: response.status }
      );
    }
    
    const data = await response.json();
    console.log('✅ Backend response received');
    return NextResponse.json(data);
    
  } catch (error) {
    console.error('❌ Proxy error:', error);
    const errorMessage = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      { error: 'Internal server error', details: errorMessage },
      { status: 500 }
    );
  }
}
