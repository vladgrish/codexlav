# GCP Console Assistant prompt

Use this prompt in the GCP Console Gemini / assistant flow to create the VM from scratch:

```text
Create a Debian 12 GCE VM for Codexlav, a Telegram long-polling Codex bot.

Requirements:
- project: YOUR_GCP_PROJECT_ID
- zone: us-central1-a
- machine type: e2-micro
- boot disk: Debian 12 Bookworm
- enable external IP
- attach the default compute service account with cloud-platform scope
- allow SSH access for my user
- keep the VM simple, no container platform, no managed instance group
- name it codexlav-vm

After creation, show me:
- instance name
- zone
- external IP
- service account email
- scopes
```

After the VM exists, SSH into it and install repo prerequisites:

```bash
sudo apt-get update
sudo apt-get install -y git python3 gh
```

Install and authenticate `gcloud` if your image does not include it. Install Codex CLI before running `scripts/check_local_requirements.sh`.

Cloud Shell copy-paste bootstrap:

```bash
export GCP_PROJECT=your-gcp-project-id
export GCP_REGION=us-central1
export GCP_ZONE=us-central1-a
export VM_NAME=codexlav-vm
curl -fsS https://raw.githubusercontent.com/vladgrish/codexlav/main/scripts/cloud_shell_bootstrap.sh | bash
```
