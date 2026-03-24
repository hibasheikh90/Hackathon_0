# Platinum Tier: Always-On Cloud + Local Executive Architecture

## Overview
This document outlines the architecture for the Platinum Tier implementation, featuring a distributed AI employee system with cloud and local components that work together through synchronized vaults and specialized responsibilities.

## Architecture Components

### 1. Cloud Component
- **Location**: Always-on Cloud VM (Oracle/AWS/etc.)
- **Responsibilities**:
  - Email triage and draft replies
  - Social post drafts and scheduling (draft-only)
  - Monitoring and initial processing
  - Draft accounting actions in Odoo (requires local approval)

### 2. Local Component
- **Location**: User's local machine
- **Responsibilities**:
  - Final approvals for cloud-drafted items
  - WhatsApp session management
  - Payments and banking operations
  - Final "send/post" actions
  - Single-writer rule for Dashboard.md

### 3. Vault Synchronization
The vault is synchronized between cloud and local using Git with the following folder structure:

#### Folder Structure:
- `/Needs_Action/<domain>/` - Items needing action by either component
- `/Plans/<domain>/` - Planning documents
- `/Pending_Approval/<domain>/` - Items awaiting approval (cloud → local)
- `/In_Progress/<agent>/` - Claimed items (claim-by-move rule)
- `/Updates/` or `/Signals/` - Updates from cloud to be merged into Dashboard.md by local
- `/Done/` - Completed items

#### Claim-by-Move Rule:
- First agent to move an item from `/Needs_Action` to `/In_Progress/<agent>/` owns it
- Other agents must ignore claimed items
- Prevents double-work and ensures coordination

### 4. Security Rules
- Vault sync includes only markdown/state files
- Secrets never sync (.env, tokens, WhatsApp sessions, banking credentials)
- Cloud never stores or uses sensitive credentials
- Local handles all sensitive operations

## MCP Server Separation

### Cloud MCP Servers:
- `cloud_vault_server.py` - Handles cloud-specific vault operations
- `cloud_email_server.py` - Manages email triage and draft creation
- `cloud_social_server.py` - Creates social media drafts
- `cloud_accounting_server.py` - Creates draft accounting entries

### Local MCP Servers:
- `local_approval_server.py` - Handles approval workflows
- `local_payment_server.py` - Manages payments and banking
- `local_communication_server.py` - Handles WhatsApp and final communications
- `local_dashboard_server.py` - Manages Dashboard.md updates

## Deployment Architecture

### Cloud Deployment:
- Oracle Cloud Free VM or AWS instance
- Docker containers for application components
- Health monitoring and auto-restart
- SSL/TLS termination
- Backup systems for data integrity

### Local Deployment:
- Local Python environment
- Vault synchronization with cloud
- Local MCP servers for sensitive operations
- Secure credential storage

## Data Flow

### Email Processing:
1. Cloud receives email notification via watcher
2. Cloud creates draft reply in `/Needs_Action/email_drafts/`
3. Local syncs and reviews draft
4. Local approves and moves to `/Pending_Approval/`
5. Local MCP server sends final email

### Social Media Posting:
1. Cloud identifies content opportunities
2. Cloud creates draft posts in `/Needs_Action/social_drafts/`
3. Local reviews and approves
4. Local MCP server publishes final posts

### Accounting Operations:
1. Cloud monitors business activities
2. Cloud creates draft accounting entries in Odoo
3. Items placed in `/Pending_Approval/accounting/`
4. Local reviews and approves
5. Local MCP server posts to accounting system

## Health Monitoring

### Cloud Health Checks:
- Application uptime monitoring
- Vault sync status
- External service connectivity
- Resource utilization

### Failover Mechanisms:
- Automatic restart of failed services
- Notification system for critical failures
- Manual takeover procedures