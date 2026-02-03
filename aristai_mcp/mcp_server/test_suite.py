#!/usr/bin/env python
"""
Standalone Test Suite for AristAI MCP Server.

This test validates:
1. MCP server structure and imports
2. Tool registry completeness
3. Tool parameter schemas
4. Voice loop controller structure
5. Integration points

Run without database dependency.
"""

import sys
import os
import json
import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum

# Test results tracking
class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def ok(self, name: str):
        self.passed += 1
        print(f"  ✅ {name}")
    
    def fail(self, name: str, reason: str):
        self.failed += 1
        self.errors.append((name, reason))
        print(f"  ❌ {name}: {reason}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"Test Results: {self.passed}/{total} passed")
        if self.errors:
            print(f"\nFailed tests:")
            for name, reason in self.errors:
                print(f"  - {name}: {reason}")
        print(f"{'='*60}")
        return self.failed == 0


results = TestResult()


def test_section(name: str):
    """Print a test section header."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")


# ============ Test 1: Module Structure ============

def test_module_structure():
    """Test that all MCP server modules exist and have correct structure."""
    test_section("Module Structure")
    
    # Test main package
    try:
        # We'll test the structure by checking file existence
        base_path = os.path.dirname(os.path.abspath(__file__))
        
        required_files = [
            "__init__.py",
            "server.py",
            "voice_loop.py",
            "SKILL.md",
            "tools/__init__.py",
            "tools/courses.py",
            "tools/sessions.py",
            "tools/forum.py",
            "tools/polls.py",
            "tools/reports.py",
            "tools/copilot.py",
            "tools/enrollment.py",
        ]
        
        for file in required_files:
            filepath = os.path.join(base_path, file)
            if os.path.exists(filepath):
                results.ok(f"File exists: {file}")
            else:
                results.fail(f"File exists: {file}", "File not found")
        
    except Exception as e:
        results.fail("Module structure", str(e))


# ============ Test 2: Server.py Structure ============

def test_server_structure():
    """Test server.py has required components."""
    test_section("Server Structure")
    
    try:
        base_path = os.path.dirname(os.path.abspath(__file__))
        server_path = os.path.join(base_path, "server.py")
        
        with open(server_path, 'r') as f:
            content = f.read()
        
        # Check for required imports
        required_imports = [
            "from mcp.server import Server",
            "TOOL_REGISTRY",
            "register_tool",
            "build_tool_registry",
            "list_tools",
            "call_tool",
        ]
        
        for item in required_imports:
            if item in content:
                results.ok(f"Server has: {item}")
            else:
                results.fail(f"Server has: {item}", "Not found in server.py")
        
        # Check for tool categories
        categories = ["courses", "sessions", "forum", "polls", "copilot", "reports", "enrollment"]
        for cat in categories:
            if f'category="{cat}"' in content:
                results.ok(f"Tool category: {cat}")
            else:
                results.fail(f"Tool category: {cat}", "Not registered")
        
    except Exception as e:
        results.fail("Server structure", str(e))


# ============ Test 3: Tool Definitions ============

def test_tool_definitions():
    """Test that tools are properly defined with correct schemas."""
    test_section("Tool Definitions")
    
    # Expected tools with their required parameters
    expected_tools = {
        # Courses
        "list_courses": [],
        "get_course": ["course_id"],
        "create_course": ["title"],
        "generate_session_plans": ["course_id"],
        
        # Sessions
        "list_sessions": ["course_id"],
        "get_session": ["session_id"],
        "get_session_plan": ["session_id"],
        "create_session": ["course_id", "title"],
        "update_session_status": ["session_id", "status"],
        "go_live": ["session_id"],
        "end_session": ["session_id"],
        
        # Forum
        "get_session_cases": ["session_id"],
        "post_case": ["session_id", "prompt"],
        "get_session_posts": ["session_id"],
        "get_latest_posts": ["session_id"],
        "get_pinned_posts": ["session_id"],
        "get_post": ["post_id"],
        "search_posts": ["session_id", "query"],
        "create_post": ["session_id", "user_id", "content"],
        "reply_to_post": ["session_id", "parent_post_id", "user_id", "content"],
        "pin_post": ["post_id", "pinned"],
        "label_post": ["post_id", "labels"],
        "mark_high_quality": ["post_id"],
        "mark_needs_clarification": ["post_id"],
        
        # Polls
        "get_session_polls": ["session_id"],
        "get_poll_results": ["poll_id"],
        "create_poll": ["session_id", "question", "options"],
        "vote_on_poll": ["poll_id", "user_id", "option_index"],
        
        # Copilot
        "get_copilot_status": ["session_id"],
        "get_copilot_suggestions": ["session_id"],
        "start_copilot": ["session_id"],
        "stop_copilot": ["session_id"],
        
        # Reports
        "get_report": ["session_id"],
        "get_report_summary": ["session_id"],
        "get_participation_stats": ["session_id"],
        "get_student_scores": ["session_id"],
        "generate_report": ["session_id"],
        
        # Enrollment
        "get_enrolled_students": ["course_id"],
        "enroll_student": ["user_id", "course_id"],
        "get_users": [],
    }
    
    try:
        base_path = os.path.dirname(os.path.abspath(__file__))
        server_path = os.path.join(base_path, "server.py")
        
        with open(server_path, 'r') as f:
            content = f.read()
        
        for tool_name, required_params in expected_tools.items():
            # Check if tool is registered
            if f'name="{tool_name}"' in content:
                results.ok(f"Tool registered: {tool_name}")
            else:
                results.fail(f"Tool registered: {tool_name}", "Not found")
                continue
            
            # Check if required parameters are documented
            for param in required_params:
                if f'"{param}"' in content:
                    pass  # Parameter exists somewhere
                else:
                    results.fail(f"Tool {tool_name} param: {param}", "Not found")
        
        print(f"\n  Total expected tools: {len(expected_tools)}")
        
    except Exception as e:
        results.fail("Tool definitions", str(e))


# ============ Test 4: Voice Loop Structure ============

def test_voice_loop_structure():
    """Test voice_loop.py has required components."""
    test_section("Voice Loop Structure")
    
    try:
        base_path = os.path.dirname(os.path.abspath(__file__))
        voice_path = os.path.join(base_path, "voice_loop.py")
        
        with open(voice_path, 'r') as f:
            content = f.read()
        
        # Check for required classes
        required_classes = [
            "class VoiceMode",
            "class VoiceState",
            "class VoiceConfig",
            "class VoiceContext",
            "class VoiceLoopController",
            "class VoiceModeIntegration",
        ]
        
        for cls in required_classes:
            if cls in content:
                results.ok(f"Voice loop has: {cls}")
            else:
                results.fail(f"Voice loop has: {cls}", "Not found")
        
        # Check for required methods
        required_methods = [
            "async def start(",
            "async def stop(",
            "async def _listen(",
            "async def _process_command(",
            "async def _speak(",
            "async def _execute_plan(",
            "def get_status(",
        ]
        
        for method in required_methods:
            if method in content:
                results.ok(f"Voice loop method: {method.strip()}")
            else:
                results.fail(f"Voice loop method: {method.strip()}", "Not found")
        
        # Check for VoiceState enum values
        states = ["IDLE", "LISTENING", "PROCESSING", "SPEAKING", "ERROR"]
        for state in states:
            if f'= "{state.lower()}"' in content or f"= '{state.lower()}'" in content:
                results.ok(f"Voice state: {state}")
            else:
                results.fail(f"Voice state: {state}", "Not found")
        
    except Exception as e:
        results.fail("Voice loop structure", str(e))


# ============ Test 5: Tool Module Structure ============

def test_tool_modules():
    """Test that each tool module has proper structure."""
    test_section("Tool Modules")
    
    tool_modules = {
        "courses": ["list_courses", "get_course", "create_course", "generate_session_plans"],
        "sessions": ["list_sessions", "get_session", "create_session", "update_session_status", "go_live", "end_session"],
        "forum": ["get_session_posts", "get_latest_posts", "create_post", "reply_to_post", "pin_post", "label_post"],
        "polls": ["get_session_polls", "get_poll_results", "create_poll", "vote_on_poll"],
        "copilot": ["get_copilot_status", "get_copilot_suggestions", "start_copilot", "stop_copilot"],
        "reports": ["get_report", "get_report_summary", "get_participation_stats", "generate_report"],
        "enrollment": ["get_enrolled_students", "enroll_student", "get_users"],
    }
    
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    for module, functions in tool_modules.items():
        module_path = os.path.join(base_path, "tools", f"{module}.py")
        
        try:
            with open(module_path, 'r') as f:
                content = f.read()
            
            results.ok(f"Module readable: {module}")
            
            for func in functions:
                if f"def {func}(" in content:
                    results.ok(f"  Function: {func}")
                else:
                    results.fail(f"  Function: {func}", f"Not found in {module}.py")
            
            # Check for voice-friendly message in returns
            if '"message"' in content:
                results.ok(f"  Has voice-friendly messages")
            else:
                results.fail(f"  Has voice-friendly messages", "No 'message' field in returns")
                
        except FileNotFoundError:
            results.fail(f"Module readable: {module}", "File not found")
        except Exception as e:
            results.fail(f"Module readable: {module}", str(e))


# ============ Test 6: SKILL.md Documentation ============

def test_skill_documentation():
    """Test SKILL.md has required sections."""
    test_section("SKILL.md Documentation")
    
    try:
        base_path = os.path.dirname(os.path.abspath(__file__))
        skill_path = os.path.join(base_path, "SKILL.md")
        
        with open(skill_path, 'r') as f:
            content = f.read()
        
        required_sections = [
            "# AristAI MCP Server",
            "## Overview",
            "## Installation",
            "## Available Tools",
            "## Voice Command Examples",
            "## Error Handling",
        ]
        
        for section in required_sections:
            if section in content:
                results.ok(f"SKILL.md has: {section}")
            else:
                results.fail(f"SKILL.md has: {section}", "Section not found")
        
        # Check for tool documentation
        tool_categories = ["Course Management", "Session Management", "Forum", "Poll", "Copilot", "Report", "Enrollment"]
        for cat in tool_categories:
            if cat in content:
                results.ok(f"Documented category: {cat}")
            else:
                results.fail(f"Documented category: {cat}", "Not documented")
        
    except Exception as e:
        results.fail("SKILL.md documentation", str(e))


# ============ Test 7: MCP Config ============

def test_mcp_config():
    """Test mcp_config.json is valid."""
    test_section("MCP Configuration")
    
    try:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_path, "mcp_config.json")
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        results.ok("mcp_config.json is valid JSON")
        
        if "mcpServers" in config:
            results.ok("Has 'mcpServers' key")
            
            if "aristai" in config["mcpServers"]:
                results.ok("Has 'aristai' server config")
                
                aristai_config = config["mcpServers"]["aristai"]
                required_keys = ["command", "args"]
                for key in required_keys:
                    if key in aristai_config:
                        results.ok(f"aristai config has: {key}")
                    else:
                        results.fail(f"aristai config has: {key}", "Missing")
            else:
                results.fail("Has 'aristai' server config", "Not found")
        else:
            results.fail("Has 'mcpServers' key", "Not found")
        
    except FileNotFoundError:
        results.fail("mcp_config.json exists", "File not found")
    except json.JSONDecodeError as e:
        results.fail("mcp_config.json is valid JSON", str(e))
    except Exception as e:
        results.fail("MCP configuration", str(e))


# ============ Test 8: Import Simulation ============

def test_import_structure():
    """Test that the import structure would work (without actual imports)."""
    test_section("Import Structure Validation")
    
    try:
        base_path = os.path.dirname(os.path.abspath(__file__))
        server_path = os.path.join(base_path, "server.py")
        
        with open(server_path, 'r') as f:
            content = f.read()
        
        # Check for correct import patterns
        expected_imports = [
            "from mcp_server.tools import",
            "courses",
            "sessions",
            "forum",
            "polls",
            "reports",
            "copilot",
            "enrollment",
        ]
        
        for imp in expected_imports:
            if imp in content:
                results.ok(f"Import pattern: {imp}")
            else:
                results.fail(f"Import pattern: {imp}", "Not found")
        
        # Check tools __init__.py
        tools_init_path = os.path.join(base_path, "tools", "__init__.py")
        with open(tools_init_path, 'r') as f:
            tools_init = f.read()
        
        modules = ["courses", "sessions", "forum", "polls", "copilot", "reports", "enrollment"]
        for mod in modules:
            if mod in tools_init:
                results.ok(f"tools/__init__.py exports: {mod}")
            else:
                results.fail(f"tools/__init__.py exports: {mod}", "Not exported")
        
    except Exception as e:
        results.fail("Import structure", str(e))


# ============ Test 9: Voice Loop Modes ============

def test_voice_modes():
    """Test voice loop supports required modes."""
    test_section("Voice Loop Modes")
    
    try:
        base_path = os.path.dirname(os.path.abspath(__file__))
        voice_path = os.path.join(base_path, "voice_loop.py")
        
        with open(voice_path, 'r') as f:
            content = f.read()
        
        modes = ["PUSH_TO_TALK", "WAKE_WORD", "CONTINUOUS"]
        for mode in modes:
            if mode in content:
                results.ok(f"Voice mode: {mode}")
            else:
                results.fail(f"Voice mode: {mode}", "Not implemented")
        
        # Check for configuration options
        config_options = [
            "wake_word",
            "silence_threshold",
            "auto_listen_after_response",
            "confirmation_required_for_writes",
        ]
        
        for opt in config_options:
            if opt in content:
                results.ok(f"Config option: {opt}")
            else:
                results.fail(f"Config option: {opt}", "Not found")
        
    except Exception as e:
        results.fail("Voice modes", str(e))


# ============ Test 10: API Integration Points ============

def test_api_integration():
    """Test that API integration points are defined."""
    test_section("API Integration Points")
    
    try:
        base_path = os.path.dirname(os.path.abspath(__file__))
        
        # Check router_integration.py
        router_path = os.path.join(base_path, "router_integration.py")
        with open(router_path, 'r') as f:
            router_content = f.read()
        
        endpoints = [
            '"/start"',
            '"/stop"',
            '"/status"',
            '"/command"',
            '"/ws"',
        ]
        
        for endpoint in endpoints:
            if endpoint in router_content:
                results.ok(f"API endpoint: {endpoint}")
            else:
                results.fail(f"API endpoint: {endpoint}", "Not defined")
        
        # Check WebSocket support
        if "WebSocket" in router_content:
            results.ok("WebSocket support")
        else:
            results.fail("WebSocket support", "Not implemented")
        
        # Check for voice loop controller usage
        if "VoiceLoopController" in router_content:
            results.ok("Uses VoiceLoopController")
        else:
            results.fail("Uses VoiceLoopController", "Not imported")
        
    except Exception as e:
        results.fail("API integration", str(e))


# ============ Main ============

def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("AristAI MCP Server - Comprehensive Test Suite")
    print("="*60)
    
    test_module_structure()
    test_server_structure()
    test_tool_definitions()
    test_voice_loop_structure()
    test_tool_modules()
    test_skill_documentation()
    test_mcp_config()
    test_import_structure()
    test_voice_modes()
    test_api_integration()
    
    return results.summary()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
