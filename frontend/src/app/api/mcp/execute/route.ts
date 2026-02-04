import { NextRequest, NextResponse } from 'next/server';

// MCP Server URL - use local for development, EC2 for production
const MCP_SERVER_URL = process.env.NODE_ENV === 'production'
  ? 'http://ec2-13-219-204-7.compute-1.amazonaws.com:8080'
  : 'http://localhost:8080';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { tool, arguments: args } = body;

    if (!tool) {
      return NextResponse.json(
        { error: 'Tool name is required' },
        { status: 400 }
      );
    }

    console.log(`🔧 Forwarding MCP tool execution: ${tool}`, args);

    // Forward request to MCP server
    const mcpResponse = await fetch(`${MCP_SERVER_URL}/mcp/call`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        method: 'tools/call',
        params: {
          name: tool,
          arguments: args || {},
        },
      }),
    });

    if (!mcpResponse.ok) {
      console.error('MCP server error:', mcpResponse.status);
      return NextResponse.json(
        { error: 'MCP server error' },
        { status: 502 }
      );
    }

    const result = await mcpResponse.json();
    console.log('✅ MCP tool result:', result);

    return NextResponse.json(result);

  } catch (error) {
    console.error('MCP route error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}