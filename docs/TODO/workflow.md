# Workflow Plan: HiDrive + GitHub Actions for `pe-flac-mixer`

This plan describes how the guitarist uploads raw multitrack recordings to HiDrive, triggers a GitHub Actions pipeline, has `pe-flac-mixer` process the mix locally inside the CI runner, and uploads the final mix back to HiDrive.

---

## 1. Prerequisites & Setup

- **HiDrive Access:**
  - A dedicated HiDrive account or sub-user with access to the rehearsal room folder.
  - Protocol: **SFTP** (recommended for easy file transfers via CLI tools like `sftp` or `rsync`) or **WebDAV**.
- **GitHub Repository:**
  - The repository is shared between team members (e.g., drummer and guitarist).
- **GitHub Secrets:**
  - Configured under `Settings -> Secrets and variables -> Actions`:
    - `HIDRIVE_HOST` (e.g., `sftp.hidrive.ionos.com`)
    - `HIDRIVE_USER` (Username)
    - `HIDRIVE_PASSWORD` (Password or SSH key)

---

## 2. GitHub Action Structure (`.github/workflows/mix.yml`)

The pipeline is triggered manually via the GitHub web interface (`workflow_dispatch`), optionally with input parameters for the rehearsal date or folder name.

### Pipeline Steps:
1. **Checkout:** Load repository code (including `pe-flac-mixer`).
2. **Environment Setup:** Set up Python and install dependencies via `uv`.
3. **Download from HiDrive:**
   - Connect to HiDrive (e.g., via `lftp`, `rsync`, or a small Python script).
   - Download raw FLAC tracks for the specified session.
4. **Run Mix Process:**
   - Execute the mixer CLI: `uv run pe-flac-mixer mix ./raw_tracks --setup probe`.
5. **Upload to HiDrive:**
   - Upload the mixed output (e.g., stereo mix in MP3/FLAC) back to the corresponding HiDrive folder.
6. **Cleanup:** Remove temporary files from the CI environment.

---

## 3. Team Workflow Steps

1. **Guitarist** uploads raw rehearsal recordings to the HiDrive folder as usual (e.g., `/Proben/2026-03-25/`).
2. **Band member** goes to GitHub under the **Actions** tab, selects the workflow, and clicks **Run workflow**.
3. **Pipeline** runs automatically (takes a few minutes depending on file size).
4. **Band** finds the ready-to-use mixes in the HiDrive folder (`/Proben/2026-03-25/Mix/`) and can practice immediately.
