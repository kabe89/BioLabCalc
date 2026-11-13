#!/usr/bin/env python3
"""
Sync BioLabCalc documentation wiki to GitHub Wiki repository.
Synchronizes all markdown files from the local 'wiki/' directory
to the remote 'BioLabCalc.wiki.git' repository.
"""

import argparse
import os
import shutil
import stat
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIKI_SRC = os.path.join(REPO_ROOT, "wiki")
DEFAULT_REPO_SLUG = os.environ.get("GITHUB_REPOSITORY", "kabe89/BioLabCalc")
DEFAULT_REMOTE = f"https://github.com/{DEFAULT_REPO_SLUG}.wiki.git"
CLONE_DIR = os.path.join(REPO_ROOT, ".wiki_clone")


def run_cmd(cmd, cwd=None):
    clean_env = os.environ.copy()
    clean_env.pop("GIT_DIR", None)
    clean_env.pop("GIT_WORK_TREE", None)
    print(f"--> Running: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    res = subprocess.run(cmd, cwd=cwd, env=clean_env, shell=isinstance(cmd, str), capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[!] Error: command failed with code {res.returncode}")
        if res.stdout:
            print(res.stdout)
        if res.stderr:
            print(res.stderr)
        return False, res.stdout, res.stderr
    return True, res.stdout, res.stderr


def safe_remove(path):
    try:
        os.chmod(path, stat.S_IWRITE)
    except Exception:
        pass
    if os.path.isdir(path):
        def _on_error(func, p, exc_info):
            try:
                os.chmod(p, stat.S_IWRITE)
                func(p)
            except Exception:
                pass
        shutil.rmtree(path, onerror=_on_error)
    else:
        try:
            os.remove(path)
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Synchronize local wiki/ directory to GitHub Wiki repository.")
    parser.add_argument("--remote", default=DEFAULT_REMOTE, help=f"Remote wiki git URL (default: {DEFAULT_REMOTE})")
    parser.add_argument("--message", default="docs(wiki): synchronize wiki documentation", help="Commit message")
    parser.add_argument("--dry-run", action="store_true", help="Stage changes and show diff without pushing")
    args = parser.parse_args()

    if not os.path.isdir(WIKI_SRC):
        print(f"[!] Source wiki directory not found at: {WIKI_SRC}")
        sys.exit(1)

    # 1. Verify wiki integrity first
    verify_script = os.path.join(REPO_ROOT, "scripts", "verify_wiki.py")
    if os.path.isfile(verify_script):
        print("[*] Running verify_wiki.py audit...")
        ok, out, _ = run_cmd([sys.executable, verify_script])
        if not ok:
            print("[!] Wiki verification failed. Aborting sync.")
            sys.exit(1)
        print("[+] Wiki verification passed.")

    # 2. Clone or pull remote wiki repo
    if not os.path.isdir(os.path.join(CLONE_DIR, ".git")):
        print(f"[*] Cloning wiki repo from {args.remote} to {CLONE_DIR}...")
        if os.path.exists(CLONE_DIR):
            shutil.rmtree(CLONE_DIR, ignore_errors=True)
        ok, _, err = run_cmd(["git", "clone", args.remote, CLONE_DIR])
        if not ok:
            print("[!] Failed to clone remote wiki repository.")
            sys.exit(1)
    else:
        print(f"[*] Updating existing clone in {CLONE_DIR}...")
        ok, _, err = run_cmd(["git", "fetch", "origin", "master"], cwd=CLONE_DIR)
        if ok:
            run_cmd(["git", "reset", "--hard", "origin/master"], cwd=CLONE_DIR)
        else:
            print("[!] Warning: failed to fetch latest changes; proceeding with local clone.")

    # 3. Synchronize files from wiki/ to clone
    # Remove existing non-hidden files in clone directory
    for item in os.listdir(CLONE_DIR):
        if item == ".git":
            continue
        safe_remove(os.path.join(CLONE_DIR, item))

    # Copy files from wiki/ into clone directory
    copied_count = 0
    for root, dirs, files in os.walk(WIKI_SRC):
        rel_dir = os.path.relpath(root, WIKI_SRC)
        dest_dir = CLONE_DIR if rel_dir == "." else os.path.join(CLONE_DIR, rel_dir)
        os.makedirs(dest_dir, exist_ok=True)
        for f in files:
            src_f = os.path.join(root, f)
            dest_f = os.path.join(dest_dir, f)
            shutil.copy2(src_f, dest_f)
            copied_count += 1

    print(f"[+] Synchronized {copied_count} files into wiki repository working tree.")

    # 4. Check for staged differences
    run_cmd(["git", "add", "-A"], cwd=CLONE_DIR)
    ok, status_out, _ = run_cmd(["git", "status", "--porcelain"], cwd=CLONE_DIR)
    if not status_out.strip():
        print("[+] Remote wiki repository is already up to date. No changes to push.")
        return

    print("[*] Detected changes to push:")
    print(status_out)

    if args.dry_run:
        print("[*] Dry run mode enabled. Changes staged locally in .wiki_clone, skipping push.")
        return

    # 5. Commit and push
    bot_name = os.environ.get("GIT_AUTHOR_NAME", "github-actions[bot]")
    bot_email = os.environ.get("GIT_AUTHOR_EMAIL", "github-actions[bot]@users.noreply.github.com")
    run_cmd(["git", "config", "user.name", bot_name], cwd=CLONE_DIR)
    run_cmd(["git", "config", "user.email", bot_email], cwd=CLONE_DIR)
    ok, _, _ = run_cmd(["git", "commit", "-m", args.message], cwd=CLONE_DIR)
    if not ok:
        print("[!] Commit failed.")
        sys.exit(1)

    print("[*] Pushing to remote wiki repository (origin master)...")
    ok, push_out, push_err = run_cmd(["git", "push", "origin", "master"], cwd=CLONE_DIR)
    if not ok:
        print("[!] Push failed. You may need to verify your Git credentials or PAT permissions for github.com.")
        sys.exit(1)

    print("[+] Successfully pushed wiki documentation to GitHub Wiki!")
    print(f"[+] View the live wiki at: https://github.com/{DEFAULT_REPO_SLUG}/wiki")


if __name__ == "__main__":
    main()
