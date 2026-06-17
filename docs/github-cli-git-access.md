# GitHub CLI Git Access

Install GitHub CLI:

```bash
sudo apt-get update
sudo apt-get install -y gh
```

Authenticate GitHub CLI for HTTPS Git operations:

```bash
gh auth login --hostname github.com --git-protocol https --web
```

Follow the browser/device-code flow. Choose GitHub.com, HTTPS, and authenticate Git with GitHub credentials.

Configure Git to use `gh` as credential helper:

```bash
gh auth setup-git --hostname github.com
```

Verify:

```bash
gh auth status
git config --global --get-regexp '^credential\.'
```

Expected Git config includes:

```text
credential.https://github.com.helper=
credential.https://github.com.helper=!/usr/bin/gh auth git-credential
credential.https://gist.github.com.helper=
credential.https://gist.github.com.helper=!/usr/bin/gh auth git-credential
```

For any repo, set HTTPS remote if missing:

```bash
git remote add origin https://github.com/<owner>/<repo>.git
```

If `origin` already exists:

```bash
git remote set-url origin https://github.com/<owner>/<repo>.git
```
