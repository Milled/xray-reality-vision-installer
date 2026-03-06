# VLESS Reality Installer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python3 script that automates VLESS + Reality + Vision server deployment on Ubuntu VPS and outputs client connection parameters.

**Architecture:** A single executable Python file orchestrates system checks, package install, xray install, key generation, config rendering, firewall setup, service startup, and verification. Unit tests validate pure logic (config generation and key parsing) without touching real system state.

**Tech Stack:** Python 3 standard library (`argparse`, `json`, `subprocess`, `secrets`, `pathlib`, `dataclasses`), `unittest`.

---

### Task 1: Add failing tests for key parsing and config rendering

**Files:**
- Create: `install-reality/tests/test_installer.py`
- Test: `install-reality/tests/test_installer.py`

1. Write tests for parsing `xray x25519` output (legacy `PublicKey` and newer `Password`).
2. Write tests for generated Reality config shape and required fields.
3. Run `python3 -m unittest discover -s install-reality/tests -v` and confirm failures.

### Task 2: Implement installer module to satisfy tests

**Files:**
- Create: `install-reality/reality_installer.py`
- Modify: `install-reality/tests/test_installer.py`

1. Implement parsing helpers and JSON config builder.
2. Re-run tests until green.

### Task 3: Implement deployment CLI flow

**Files:**
- Modify: `install-reality/reality_installer.py`

1. Add CLI args, command runner, and deployment steps:
   - preflight checks
   - apt update/upgrade (optional)
   - enable BBR
   - install xray
   - generate UUID/x25519
   - write `/usr/local/etc/xray/config.json`
   - ufw allow 443
   - `xray -test`
   - `systemctl enable/restart xray`
2. Print final client profile parameters.

### Task 4: Add README and one-line bootstrap usage

**Files:**
- Create: `install-reality/README.md`

1. Document prerequisites and safe usage.
2. Provide local run command and GitHub raw one-liner (`curl ... | python3 -`).
3. Include expected outputs and troubleshooting notes.

### Task 5: Final verification

**Files:**
- Verify only files under `install-reality/`.

1. Run `python3 -m unittest discover -s install-reality/tests -v`.
2. Run `python3 install-reality/reality_installer.py --help`.
3. Summarize artifacts and next actions.
