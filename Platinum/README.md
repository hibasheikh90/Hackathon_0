# Platinum Tier: Always-On Cloud + Local Executive

This is the highest tier of the Personal AI Employee system, featuring distributed operation between cloud and local components with synchronized vaults and specialized responsibilities.

## Architecture Overview

The Platinum Tier implements a distributed AI employee system with:

- **Cloud Component**: Runs 24/7 on cloud VM, handles email triage, social media draft creation, and accounting draft operations
- **Local Component**: Runs on user's local machine, handles approvals, payments, WhatsApp, and final actions
- **Vault Synchronization**: Git-based synchronization between cloud and local vaults
- **Claim-by-Move System**: Coordination mechanism preventing double-work between components

## Key Features

### Work-Zone Specialization
- **Cloud owns**: Email triage + draft replies, social post drafts/scheduling (draft-only)
- **Local owns**: Approvals, WhatsApp session, payments/banking, final "send/post" actions

### Delegation via Synced Vault
- Agents communicate by writing files into standardized directories:
  - `/Needs_Action/<domain>/`
  - `/Plans/<domain>/`
  - `/Pending_Approval/<domain>/`
- Claim-by-move rule: first agent to move an item from `/Needs_Action` to `/In_Progress/<agent>/` owns it
- Single-writer rule: Local maintains exclusive write access to Dashboard.md

### Security Rules
- Vault sync includes only markdown/state files
- Secrets never sync (.env, tokens, WhatsApp sessions, banking credentials)
- Cloud never stores or uses sensitive credentials

## Directory Structure

```
vault/
├── Needs_Action/
│   ├── email/
│   ├── social/
│   └── accounting/
├── Plans/
│   ├── email/
│   ├── social/
│   └── accounting/
├── Pending_Approval/
│   ├── email_drafts/
│   ├── social_posts/
│   ├── accounting/
│   └── payments/
├── In_Progress/
│   ├── cloud/
│   └── local/
├── Updates/
├── Signals/
├── Done/
└── Logs/
```

## Setup Instructions

### Cloud Component Setup

1. Deploy to cloud VM (Oracle Cloud Free, AWS, etc.)
2. Clone the repository
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure vault synchronization:
   ```bash
   # Add remote repository for vault sync
   git remote add origin <your-vault-repo-url>
   ```
5. Run the cloud component:
   ```bash
   python run_platinum.py --mode cloud --vault ./vault --daemon
   ```

### Local Component Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the local component:
   ```bash
   python run_platinum.py --mode local --vault ./vault --daemon
   ```

## Operation

### Cloud Component Responsibilities
- Monitor email for new messages
- Create draft replies in `/Needs_Action/email_drafts/`
- Identify social media opportunities and create draft posts
- Monitor business activities and create draft accounting entries
- Sync vault changes every 5 minutes

### Local Component Responsibilities
- Review and approve cloud-created drafts
- Execute approved emails, social posts, and payments
- Handle WhatsApp communications
- Update Dashboard.md with cloud-generated updates
- Sync vault changes every 2 minutes

## MCP Servers

### Cloud MCP Servers
- `cloud_vault_server.py`: Handles cloud-specific vault operations
- `cloud_email_server.py`: Manages email triage and draft creation
- `cloud_social_server.py`: Creates social media drafts
- `cloud_accounting_server.py`: Creates draft accounting entries

### Local MCP Servers
- `local_approval_server.py`: Handles approval workflows
- `local_payment_server.py`: Manages payments and banking
- `local_communication_server.py`: Handles WhatsApp and final communications
- `local_dashboard_server.py`: Manages Dashboard.md updates

## Health Monitoring

The system includes comprehensive health monitoring:
- System resource usage (CPU, memory, disk)
- Vault integrity checks
- Git synchronization status
- Component process monitoring
- Failure notifications

Run health checks:
```bash
python run_platinum.py --status --vault ./vault
```

## Demo Scenario

The minimum passing gate for Platinum Tier:

1. Email arrives while Local is offline → Cloud drafts reply + writes approval file
2. When Local returns, user approves → Local executes send via MCP
3. Action is logged → task is moved to `/Done`
4. Both systems remain in sync throughout the process

## Security Considerations

- Never store sensitive credentials in synced vault
- Use environment variables for API keys and tokens
- Implement rate limiting for external services
- Encrypt sensitive local storage
- Regular security audits of code and dependencies

## Troubleshooting

Common issues and solutions:

- **Sync conflicts**: Resolve using git merge tools
- **Permission denied**: Check file permissions in vault directories
- **MCP servers not connecting**: Verify server configurations
- **High resource usage**: Adjust check intervals and batch sizes