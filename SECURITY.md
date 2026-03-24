# Security Policy

## Overview
This Personal AI Employee system implements several security measures to protect user data and prevent unauthorized actions.

## Security Measures Implemented

### 1. Credential Management
- All sensitive credentials stored in `.env` file (not committed to version control)
- Environment variables used for API keys and tokens
- No hardcoded credentials in source code

### 2. Human-in-the-Loop (HITL)
- Critical actions require explicit human approval
- Approval workflow implemented via vault file movement
- `/Pending_Approval`, `/Approved`, and `/Rejected` directories manage approval states

### 3. Permission Boundaries
- Predefined thresholds for auto-approval vs manual approval
- Payment approval requirements based on amount
- Email and social media approval policies

### 4. Audit Logging
- Comprehensive logging of all actions taken by the AI
- JSON-formatted audit logs with timestamps and action details
- Log rotation to prevent excessive storage consumption

### 5. Sandboxing & Isolation
- Development mode with dry-run capabilities
- Rate limiting for external API calls
- Isolated browser contexts for social media automation

### 6. Data Protection
- Local-first architecture keeps sensitive data on user's machine
- No cloud storage of personal/financial information
- File-based vault system with user-controlled access

## Supported Versions

| Version | Supported |
| ------- | --------- |
| Gold Tier | ✅ |
| Silver Tier | ✅ |
| Bronze Tier | ✅ |

## Reporting a Vulnerability

If you discover a security vulnerability, please contact the project maintainers directly. Do not submit security issues through public GitHub issues.

For security-related concerns about the AI behavior, review the Company_Handbook.md which defines the operational boundaries.