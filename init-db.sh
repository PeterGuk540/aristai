#!/bin/bash
psql -U aristai -d aristai -c "CREATE DATABASE syllabus_tool;" 2>/dev/null || true
