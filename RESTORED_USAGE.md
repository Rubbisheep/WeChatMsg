# Restored Usage

This repo no longer contains the original packaged desktop application, but it still contains the core decryption, parsing, contact loading, and export logic.

A replacement desktop entrypoint is now available at:

- `restored_gui.py`

## What the restored GUI supports

- Scan running WeChat 4 accounts
- Decrypt a selected account into a local output directory
- Load an already decrypted database directory
- Browse contacts and chatrooms
- Export one contact or all contacts
- Extra helper: export only self-sent messages as TXT or JSON

## Current limits

- WeChat 4 automatic scan is restored
- WeChat 3 automatic scan is not fully restored because the deleted project also removed `version_list.json`
- You can still use WeChat 3 if you already have a decrypted `Msg` directory and load it manually

## How to install dependencies

Use a virtual environment if possible.

```powershell
cd d:\code\ClaudeCode\WeChatMsg
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If `pip` fails on `Crypto~=1.4.1`, install the rest first and keep `pycryptodome`.

## How to start the restored GUI

```powershell
cd d:\code\ClaudeCode\WeChatMsg
python restored_gui.py
```

## Suggested workflow for WeChat 4

1. Start the official Windows WeChat 4 client and log in.
2. Run `python restored_gui.py`.
3. Click `Scan accounts`.
4. Select the detected account.
5. Pick `Decrypt output root`.
6. Click `Decrypt selected account`.
7. Click `Load contacts`.
8. Select a contact or chatroom.
9. Choose an export format and output directory.
10. Click `Export selected chat` or `Extract my sent messages`.

## Manual workflow for an already decrypted database

If you already have decrypted output:

- WeChat 4: point `DB dir` to `...\wxid_xxx\db_storage`
- WeChat 3: point `DB dir` to `...\wxid_xxx\Msg`

Then set the matching `DB version` and click `Load contacts`.
