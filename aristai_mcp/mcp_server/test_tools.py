#!/usr/bin/env python
"""
Test script for AristAI MCP Server.

This script tests the MCP tools without requiring the full MCP protocol.
Useful for development and debugging.

Usage:
    python -m mcp_server.test_tools
"""

import asyncio
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_tool(tool_name: str, **kwargs):
    """Test a single tool and print results."""
    from mcp_server.server import TOOL_REGISTRY
    from api.core.database import SessionLocal
    
    if tool_name not in TOOL_REGISTRY:
        print(f"❌ Unknown tool: {tool_name}")
        return None
    
    tool_info = TOOL_REGISTRY[tool_name]
    handler = tool_info["handler"]
    mode = tool_info["mode"]
    
    print(f"\n{'='*60}")
    print(f"Testing: {tool_name} [{mode.upper()}]")
    print(f"Args: {kwargs}")
    print(f"{'='*60}")
    
    db = SessionLocal()
    try:
        result = handler(db, **kwargs)
        
        # Check for errors
        if isinstance(result, dict) and "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print(f"✅ Success!")
            
            # Print message if available
            if isinstance(result, dict) and "message" in result:
                print(f"\n📢 Message: {result['message']}")
            
            # Print full result
            print(f"\n📄 Full Result:")
            print(json.dumps(result, indent=2, default=str))
        
        return result
        
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        db.close()


def list_all_tools():
    """List all registered tools."""
    from mcp_server.server import TOOL_REGISTRY
    
    print("\n" + "="*60)
    print("AristAI MCP Server - Registered Tools")
    print("="*60)
    
    # Group by category
    categories = {}
    for name, info in TOOL_REGISTRY.items():
        cat = info.get("category", "other")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append((name, info))
    
    for cat, tools in sorted(categories.items()):
        print(f"\n📁 {cat.upper()} ({len(tools)} tools)")
        print("-" * 40)
        for name, info in sorted(tools):
            mode_icon = "📖" if info["mode"] == "read" else "✏️"
            print(f"  {mode_icon} {name}")
            # Print first line of description
            desc = info["description"].split(".")[0]
            print(f"     {desc}")
    
    total = len(TOOL_REGISTRY)
    reads = sum(1 for t in TOOL_REGISTRY.values() if t["mode"] == "read")
    writes = total - reads
    print(f"\n📊 Total: {total} tools ({reads} read, {writes} write)")


def run_interactive():
    """Run interactive testing session."""
    from mcp_server.server import TOOL_REGISTRY
    
    print("\n" + "="*60)
    print("AristAI MCP Server - Interactive Test Mode")
    print("="*60)
    print("Commands:")
    print("  list                    - List all tools")
    print("  test <tool> [args]      - Test a tool")
    print("  help <tool>             - Show tool details")
    print("  quit                    - Exit")
    print("="*60)
    
    while True:
        try:
            cmd = input("\n> ").strip()
            
            if not cmd:
                continue
            
            parts = cmd.split(maxsplit=2)
            action = parts[0].lower()
            
            if action in ["quit", "exit", "q"]:
                print("Goodbye!")
                break
            
            elif action == "list":
                list_all_tools()
            
            elif action == "help" and len(parts) > 1:
                tool_name = parts[1]
                if tool_name in TOOL_REGISTRY:
                    info = TOOL_REGISTRY[tool_name]
                    print(f"\n📖 {tool_name}")
                    print(f"   Mode: {info['mode']}")
                    print(f"   Category: {info['category']}")
                    print(f"   Description: {info['description']}")
                    print(f"   Parameters: {json.dumps(info['parameters'], indent=4)}")
                else:
                    print(f"Unknown tool: {tool_name}")
            
            elif action == "test" and len(parts) > 1:
                tool_name = parts[1]
                args = {}
                
                if len(parts) > 2:
                    try:
                        args = json.loads(parts[2])
                    except json.JSONDecodeError:
                        # Try parsing as key=value pairs
                        for pair in parts[2].split():
                            if "=" in pair:
                                k, v = pair.split("=", 1)
                                # Try to parse value as int
                                try:
                                    v = int(v)
                                except ValueError:
                                    pass
                                args[k] = v
                
                test_tool(tool_name, **args)
            
            else:
                print("Unknown command. Type 'list' for tools or 'quit' to exit.")
                
        except KeyboardInterrupt:
            print("\nInterrupted. Goodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


def run_smoke_tests():
    """Run basic smoke tests on read tools."""
    print("\n" + "="*60)
    print("Running Smoke Tests (Read Tools)")
    print("="*60)
    
    # Test basic read operations
    tests = [
        ("list_courses", {}),
        ("get_users", {}),
        ("get_users", {"role": "student"}),
    ]
    
    passed = 0
    failed = 0
    
    for tool_name, args in tests:
        result = test_tool(tool_name, **args)
        if result and "error" not in result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"Smoke Test Results: {passed} passed, {failed} failed")
    print("="*60)
    
    return failed == 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test AristAI MCP Server tools")
    parser.add_argument("--list", action="store_true", help="List all tools")
    parser.add_argument("--smoke", action="store_true", help="Run smoke tests")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    parser.add_argument("--tool", "-t", help="Test a specific tool")
    parser.add_argument("--args", "-a", help="JSON arguments for the tool")
    
    args = parser.parse_args()
    
    if args.list:
        list_all_tools()
    elif args.smoke:
        success = run_smoke_tests()
        sys.exit(0 if success else 1)
    elif args.tool:
        tool_args = json.loads(args.args) if args.args else {}
        test_tool(args.tool, **tool_args)
    elif args.interactive:
        run_interactive()
    else:
        # Default: list tools and run interactive
        list_all_tools()
        run_interactive()
