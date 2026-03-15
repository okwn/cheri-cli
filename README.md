<div align="center">

# Cheri

**CLI-first workspace sync and collaboration for small teams**

<p>
  Workspace-based file sync • Team invites • Activity history • Task-based folder automation
</p>

<p>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9%2B-111111?style=for-the-badge&logo=python&logoColor=white">
  <img alt="Cloudflare Workers" src="https://img.shields.io/badge/Cloudflare-Workers-111111?style=for-the-badge&logo=cloudflare&logoColor=white">
  <img alt="R2" src="https://img.shields.io/badge/Storage-R2-111111?style=for-the-badge">
  <img alt="KV" src="https://img.shields.io/badge/Metadata-KV-111111?style=for-the-badge">
  <img alt="CLI" src="https://img.shields.io/badge/Interface-CLI-111111?style=for-the-badge">
</p>

</div>

---

## ✦ What is Cheri?

Cheri is a **CLI-first collaborative workspace sync tool** built for lightweight team workflows.

It gives you a command-line workflow for:

- creating an account and workspace
- joining workspaces with invite codes
- uploading, listing, and downloading shared files
- reviewing recent workspace activity
- creating local sync tasks for files and folders

> [!NOTE]
> Cheri is designed around a **CLI client + Worker API backend**.  
> The old browser/dashboard-first flow is **not** the main product path anymore.

---

## ✦ Current Status

<table>
<tr>
<td valign="top" width="50%">

### ✅ Ready now
- Register / login / logout
- Workspace create / list / use / join
- File upload / download / list
- Team invite / list / invite-reset
- Activity feed
- Task create / list / start / stop / run / logs / watch
- System provider support
- Worker + KV + R2 backend

</td>
<td valign="top" width="50%">

### ⚠ Current limits
- `System (recommended)` is the only public-ready provider
- S3 / Google Drive / Backblaze are scaffolded, not public-ready
- Task automation is upload-only today
- Conflict handling and bidirectional sync are not implemented
- If `cheri` is not found after install, your Python scripts directory may need to be on `PATH`

</td>
</tr>
</table>

---

## ✦ Feature Snapshot

| Area | What you get |
|---|---|
| **Auth** | `cheri register`, `cheri login`, `cheri logout` |
| **Workspace** | Create, list, switch, and join shared workspaces |
| **Files** | Upload, list, and download workspace files |
| **Teams** | Invite teammates with short codes like `CHR-TEAM-8X2K91QZ` |
| **Activity** | Review recent workspace events |
| **Tasks** | Auto-started local sync tasks for files and folders |
| **Storage** | Worker API + KV metadata + R2 blob storage |

---

## ✦ Architecture

```text
Local CLI
   │
   ▼
Cloudflare Worker API
   ├── KV (users, sessions, invites, activity, metadata)
   └── R2 (file/blob storage)

<div align="center">

# Cheri

**CLI-first workspace sync and collaboration for small teams**

<p>
  Workspace-based file sync • Team invites • Activity history • Task-based folder automation
</p>

<p>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9%2B-111111?style=for-the-badge&logo=python&logoColor=white">
  <img alt="Cloudflare Workers" src="https://img.shields.io/badge/Cloudflare-Workers-111111?style=for-the-badge&logo=cloudflare&logoColor=white">
  <img alt="R2" src="https://img.shields.io/badge/Storage-R2-111111?style=for-the-badge">
  <img alt="KV" src="https://img.shields.io/badge/Metadata-KV-111111?style=for-the-badge">
  <img alt="CLI" src="https://img.shields.io/badge/Interface-CLI-111111?style=for-the-badge">
</p>

</div>

---

## ✦ What is Cheri?

Cheri is a **CLI-first collaborative workspace sync tool** built for lightweight team workflows.

It gives you a command-line workflow for:

- creating an account and workspace
- joining workspaces with invite codes
- uploading, listing, and downloading shared files
- reviewing recent workspace activity
- creating local sync tasks for files and folders

> [!NOTE]
> Cheri is designed around a **CLI client + Worker API backend**.  
> The old browser/dashboard-first flow is **not** the main product path anymore.

---

## ✦ Current Status

<table>
<tr>
<td valign="top" width="50%">

### ✅ Ready now
- Register / login / logout
- Workspace create / list / use / join
- File upload / download / list
- Team invite / list / invite-reset
- Activity feed
- Task create / list / start / stop / run / logs / watch
- System provider support
- Worker + KV + R2 backend

</td>
<td valign="top" width="50%">

### ⚠ Current limits
- `System (recommended)` is the only public-ready provider
- S3 / Google Drive / Backblaze are scaffolded, not public-ready
- Task automation is upload-only today
- Conflict handling and bidirectional sync are not implemented
- If `cheri` is not found after install, your Python scripts directory may need to be on `PATH`

</td>
</tr>
</table>

---

## ✦ Feature Snapshot

| Area | What you get |
|---|---|
| **Auth** | `cheri register`, `cheri login`, `cheri logout` |
| **Workspace** | Create, list, switch, and join shared workspaces |
| **Files** | Upload, list, and download workspace files |
| **Teams** | Invite teammates with short codes like `CHR-TEAM-8X2K91QZ` |
| **Activity** | Review recent workspace events |
| **Tasks** | Auto-started local sync tasks for files and folders |
| **Storage** | Worker API + KV metadata + R2 blob storage |

---

## ✦ Architecture

```text
Local CLI
   │
   ▼
Cloudflare Worker API
   ├── KV (users, sessions, invites, activity, metadata)
   └── R2 (file/blob storage)

✦ Installation

[!TIP]
The supported install path today is Python-based.

Requirements
Python 3.9+
pip
Node.js 18+ for Worker-side testing

Wrangler if you want to deploy the backend yourself

macOS / Linux
git clone <your-github-url> cheri-app
cd cheri-app
python3 -m pip install .
cheri --help

Windows
git clone <your-github-url> cheri-app
cd cheri-app
py -3 -m pip install .
cheri --help
