from mcp_server.tools import voice


def test_collect_emails():
    result = voice._collect_emails(["A@example.com", "b@example.com "], "c@example.com")
    assert result == ["a@example.com", "b@example.com", "c@example.com"]


def test_parse_csv_emails():
    csv_text = "email,name\nstudent@example.com,Student Name\n"
    result = voice._parse_csv_emails(csv_text)
    assert result == ["student@example.com"]
