#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Minimal restored GUI for the surviving WeChatMsg source tree.

This app rebuilds the practical workflow that still exists in the repo:
1. Scan running WeChat accounts
2. Decrypt local databases
3. Load a decrypted database
4. Browse contacts
5. Export chats or extract self-sent messages
"""

from __future__ import annotations

import json
import os
import threading
import traceback
import ctypes
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from typing import Callable

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from exporter import AiTxtExporter, DocxExporter, ExcelExporter, HtmlExporter, MarkdownExporter, TxtExporter
from exporter.config import FileType
from wxManager import DatabaseConnection
from wxManager.decrypt import get_info_v3, get_info_v4
from wxManager.decrypt.common import WeChatInfo
from wxManager.decrypt.decrypt_dat import get_decode_code_v4
from wxManager.decrypt import decrypt_v3, decrypt_v4


EXPORTER_MAP = {
    "html": (HtmlExporter, FileType.HTML),
    "txt": (TxtExporter, FileType.TXT),
    "ai_txt": (AiTxtExporter, FileType.AI_TXT),
    "markdown": (MarkdownExporter, FileType.MARKDOWN),
    "xlsx": (ExcelExporter, FileType.XLSX),
}

if DocxExporter is not None:
    EXPORTER_MAP["docx"] = (DocxExporter, FileType.DOCX)


@dataclass
class LoadedDatabase:
    db_dir: str
    db_version: int
    database: object
    contacts: list


class RestoredWeChatApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("WeChatMsg Restored GUI")
        self.root.geometry("1200x760")

        self.log_queue: Queue[str] = Queue()
        self.loaded_db: LoadedDatabase | None = None
        self.detected_accounts: list[WeChatInfo] = []
        self.visible_contacts: list = []

        self.scan_version_var = tk.StringVar(value="4")
        self.decrypt_output_var = tk.StringVar(
            value=str((Path.cwd() / "restored_output").resolve())
        )
        self.db_dir_var = tk.StringVar()
        self.db_version_var = tk.StringVar(value="4")
        self.contact_filter_var = tk.StringVar()
        self.export_format_var = tk.StringVar(value="html")
        self.export_output_var = tk.StringVar(
            value=str((Path.cwd() / "exports").resolve())
        )
        self.sent_export_kind_var = tk.StringVar(value="txt")

        self._build_layout()
        self.root.after(150, self._drain_logs)

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=3)
        self.root.columnconfigure(1, weight=4)
        self.root.rowconfigure(1, weight=1)

        top = ttk.Frame(self.root, padding=12)
        top.grid(row=0, column=0, columnspan=2, sticky="nsew")
        top.columnconfigure(1, weight=1)
        top.columnconfigure(4, weight=1)

        ttk.Label(top, text="Scan version").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            top,
            textvariable=self.scan_version_var,
            values=("4", "3"),
            width=8,
            state="readonly",
        ).grid(row=0, column=1, sticky="w", padx=(6, 12))

        ttk.Button(top, text="Scan accounts", command=self.scan_accounts).grid(
            row=0, column=2, sticky="w"
        )

        ttk.Label(top, text="Decrypt output root").grid(
            row=0, column=3, sticky="e", padx=(18, 6)
        )
        ttk.Entry(top, textvariable=self.decrypt_output_var).grid(
            row=0, column=4, sticky="ew"
        )
        ttk.Button(top, text="Browse", command=self.pick_decrypt_output).grid(
            row=0, column=5, sticky="w", padx=(6, 0)
        )

        left = ttk.LabelFrame(self.root, text="Accounts and database", padding=12)
        left.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=(0, 6))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        ttk.Label(left, text="Detected accounts").grid(row=0, column=0, sticky="w")

        self.account_list = tk.Listbox(left, exportselection=False, height=10)
        self.account_list.grid(row=1, column=0, sticky="nsew", pady=(6, 8))

        account_actions = ttk.Frame(left)
        account_actions.grid(row=2, column=0, sticky="ew")
        account_actions.columnconfigure(0, weight=1)
        account_actions.columnconfigure(1, weight=1)
        ttk.Button(
            account_actions,
            text="Decrypt selected account",
            command=self.decrypt_selected_account,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(
            account_actions,
            text="Copy detected path to DB field",
            command=self.copy_detected_db_dir,
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        db_box = ttk.LabelFrame(left, text="Open decrypted database", padding=12)
        db_box.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        db_box.columnconfigure(1, weight=1)

        ttk.Label(db_box, text="DB dir").grid(row=0, column=0, sticky="w")
        ttk.Entry(db_box, textvariable=self.db_dir_var).grid(
            row=0, column=1, sticky="ew", padx=(6, 6)
        )
        ttk.Button(db_box, text="Browse", command=self.pick_db_dir).grid(
            row=0, column=2, sticky="w"
        )

        ttk.Label(db_box, text="DB version").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(
            db_box,
            textvariable=self.db_version_var,
            values=("4", "3"),
            width=8,
            state="readonly",
        ).grid(row=1, column=1, sticky="w", padx=(6, 0), pady=(8, 0))
        ttk.Button(db_box, text="Load contacts", command=self.load_database).grid(
            row=1, column=2, sticky="e", pady=(8, 0)
        )

        right = ttk.LabelFrame(self.root, text="Contacts and export", padding=12)
        right.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=(0, 6))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        filter_row = ttk.Frame(right)
        filter_row.grid(row=0, column=0, sticky="ew")
        filter_row.columnconfigure(1, weight=1)
        ttk.Label(filter_row, text="Filter").grid(row=0, column=0, sticky="w")
        ttk.Entry(filter_row, textvariable=self.contact_filter_var).grid(
            row=0, column=1, sticky="ew", padx=(6, 0)
        )
        self.contact_filter_var.trace_add("write", lambda *_: self.refresh_contacts())

        self.contact_list = tk.Listbox(right, exportselection=False)
        self.contact_list.grid(row=1, column=0, sticky="nsew", pady=(8, 8))

        export_box = ttk.LabelFrame(right, text="Export", padding=12)
        export_box.grid(row=2, column=0, sticky="ew")
        export_box.columnconfigure(1, weight=1)

        ttk.Label(export_box, text="Output dir").grid(row=0, column=0, sticky="w")
        ttk.Entry(export_box, textvariable=self.export_output_var).grid(
            row=0, column=1, sticky="ew", padx=(6, 6)
        )
        ttk.Button(export_box, text="Browse", command=self.pick_export_output).grid(
            row=0, column=2, sticky="w"
        )

        ttk.Label(export_box, text="Format").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(
            export_box,
            textvariable=self.export_format_var,
            values=tuple(EXPORTER_MAP.keys()),
            width=12,
            state="readonly",
        ).grid(row=1, column=1, sticky="w", padx=(6, 0), pady=(8, 0))

        export_buttons = ttk.Frame(export_box)
        export_buttons.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        export_buttons.columnconfigure(0, weight=1)
        export_buttons.columnconfigure(1, weight=1)
        export_buttons.columnconfigure(2, weight=1)
        ttk.Button(
            export_buttons,
            text="Export selected chat",
            command=self.export_selected_contact,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(
            export_buttons,
            text="Export all contacts",
            command=self.export_all_contacts,
        ).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(
            export_buttons,
            text="Extract my sent messages",
            command=self.export_sent_messages,
        ).grid(row=0, column=2, sticky="ew", padx=(4, 0))

        ttk.Label(export_box, text="Sent export").grid(
            row=3, column=0, sticky="w", pady=(10, 0)
        )
        ttk.Combobox(
            export_box,
            textvariable=self.sent_export_kind_var,
            values=("txt", "json"),
            width=12,
            state="readonly",
        ).grid(row=3, column=1, sticky="w", padx=(6, 0), pady=(10, 0))

        log_frame = ttk.LabelFrame(self.root, text="Log", padding=12)
        log_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=12, pady=(0, 12))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, height=12, wrap="word")
        self.log_text.grid(row=0, column=0, sticky="nsew")

    def log(self, text: str) -> None:
        self.log_queue.put(f"[{datetime.now().strftime('%H:%M:%S')}] {text}")

    @staticmethod
    def is_admin() -> bool:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def _drain_logs(self) -> None:
        while True:
            try:
                line = self.log_queue.get_nowait()
            except Empty:
                break
            self.log_text.insert("end", line + "\n")
            self.log_text.see("end")
        self.root.after(150, self._drain_logs)

    def run_async(self, title: str, func: Callable[[], None]) -> None:
        def runner() -> None:
            self.log(f"{title} started")
            try:
                func()
                self.log(f"{title} finished")
            except Exception as exc:
                self.log(f"{title} failed: {exc}")
                self.log(traceback.format_exc())
                err_text = f"{title} failed:\n{exc}"
                self.root.after(
                    0,
                    lambda title=title, err_text=err_text: messagebox.showerror(title, err_text),
                )

        threading.Thread(target=runner, daemon=True).start()

    def pick_decrypt_output(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.decrypt_output_var.set(path)

    def pick_db_dir(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.db_dir_var.set(path)

    def pick_export_output(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.export_output_var.set(path)

    def scan_accounts(self) -> None:
        version = self.scan_version_var.get()
        def task() -> None:
            if version == "3":
                accounts = get_info_v3({})
            else:
                accounts = get_info_v4()
            self.detected_accounts = accounts
            self.root.after(0, self.refresh_account_list)
            self.log(f"Detected {len(accounts)} running WeChat {version} account(s)")

        self.run_async("Scan accounts", task)

    def refresh_account_list(self) -> None:
        self.account_list.delete(0, "end")
        for info in self.detected_accounts:
            status = "key ok" if info.key else f"no key err={info.errcode}"
            label = (
                f"{info.nick_name or 'Unknown'} | wxid={info.wxid or 'unknown'} | "
                f"{status} | dir={info.wx_dir or 'n/a'}"
            )
            self.account_list.insert("end", label)

    def get_selected_account(self) -> WeChatInfo | None:
        selection = self.account_list.curselection()
        if not selection:
            messagebox.showwarning("No account", "Select a detected account first.")
            return None
        return self.detected_accounts[selection[0]]

    def copy_detected_db_dir(self) -> None:
        info = self.get_selected_account()
        if not info:
            return
        account_root = Path(self.decrypt_output_var.get()) / (info.wxid or "unknown")
        db_dir = account_root / "db_storage"
        self.db_dir_var.set(str(db_dir))
        self.db_version_var.set("4")
        self.log(f"Prepared DB dir: {db_dir}")

    def decrypt_selected_account(self) -> None:
        info = self.get_selected_account()
        if not info:
            return

        output_root = Path(self.decrypt_output_var.get())
        if not output_root:
            messagebox.showwarning("Missing output", "Pick a decrypt output root first.")
            return

        def task() -> None:
            if not info.key:
                reason = (
                    "Detected account has no decrypt key.\n\n"
                    f"wxid: {info.wxid or 'unknown'}\n"
                    f"version: {info.version or 'unknown'}\n"
                    f"db dir: {info.wx_dir or 'unknown'}\n"
                    f"errcode: {info.errcode}\n"
                    f"errmsg: {getattr(info, 'errmsg', '') or 'n/a'}\n"
                    f"admin: {'yes' if self.is_admin() else 'no'}\n\n"
                    "Most common causes:\n"
                    "1. This Python process is not running as Administrator.\n"
                    "2. The current WeChat 4 build changed its memory layout and the key scan missed.\n"
                    "3. WeChat was not fully logged in when scanned.\n\n"
                    "Try closing this window, reopening a terminal as Administrator, then run:\n"
                    "python restored_gui.py"
                )
                raise RuntimeError(reason)

            account_root = output_root / (info.wxid or "unknown")
            account_root.mkdir(parents=True, exist_ok=True)
            self.log(f"Decrypting account into: {account_root}")

            scan_version = self.scan_version_var.get()
            if scan_version == "3":
                decrypt_v3.decrypt_db_files(info.key, src_dir=info.wx_dir, dest_dir=str(account_root))
                me_info = {
                    "username": info.wxid,
                    "nickname": info.nick_name,
                    "wx_dir": info.wx_dir,
                    "xor_key": 0,
                }
                db_dir = account_root / "Msg"
                db_dir.mkdir(parents=True, exist_ok=True)
                with open(db_dir / "info.json", "w", encoding="utf-8") as f:
                    json.dump(me_info, f, ensure_ascii=False, indent=2)
                self.root.after(0, lambda: self.db_version_var.set("3"))
            else:
                decrypt_v4.decrypt_db_files(info.key, src_dir=info.wx_dir, dest_dir=str(account_root))
                me_info = {
                    "username": info.wxid,
                    "nickname": info.nick_name,
                    "wx_dir": info.wx_dir,
                    "xor_key": get_decode_code_v4(info.wx_dir),
                }
                db_dir = account_root / "db_storage"
                db_dir.mkdir(parents=True, exist_ok=True)
                with open(db_dir / "info.json", "w", encoding="utf-8") as f:
                    json.dump(me_info, f, ensure_ascii=False, indent=2)
                self.root.after(0, lambda: self.db_version_var.set("4"))

            self.root.after(0, lambda: self.db_dir_var.set(str(db_dir)))
            self.log(f"Decrypted DB ready at: {db_dir}")

        self.run_async("Decrypt account", task)

    def load_database(self) -> None:
        db_dir = self.db_dir_var.get().strip()
        if not db_dir:
            messagebox.showwarning("Missing DB", "Pick a decrypted DB directory first.")
            return

        db_version = int(self.db_version_var.get())

        def task() -> None:
            conn = DatabaseConnection(db_dir, db_version)
            database = conn.get_interface()
            if database is None:
                raise RuntimeError("Failed to initialize the database interface.")

            contacts = list(database.get_contacts())
            contacts.sort(key=lambda c: (c.is_chatroom(), c.remark.lower(), c.wxid.lower()))
            self.loaded_db = LoadedDatabase(
                db_dir=db_dir,
                db_version=db_version,
                database=database,
                contacts=contacts,
            )
            self.root.after(0, self.refresh_contacts)
            self.log(f"Loaded {len(contacts)} contact(s) from {db_dir}")

        self.run_async("Load database", task)

    def refresh_contacts(self) -> None:
        self.contact_list.delete(0, "end")
        self.visible_contacts = []

        if not self.loaded_db:
            return

        needle = self.contact_filter_var.get().strip().lower()
        for contact in self.loaded_db.contacts:
            label = self.contact_label(contact)
            if needle and needle not in label.lower() and needle not in contact.wxid.lower():
                continue
            self.visible_contacts.append(contact)
            self.contact_list.insert("end", label)

    @staticmethod
    def contact_label(contact) -> str:
        flags = []
        if contact.is_chatroom():
            flags.append("chatroom")
        if contact.is_public():
            flags.append("public")
        if contact.is_open_im():
            flags.append("openim")
        suffix = f" [{' '.join(flags)}]" if flags else ""
        return f"{contact.remark} ({contact.wxid}){suffix}"

    def get_selected_contact(self):
        if not self.loaded_db:
            messagebox.showwarning("No database", "Load a database first.")
            return None
        selection = self.contact_list.curselection()
        if not selection:
            messagebox.showwarning("No contact", "Select a contact first.")
            return None
        return self.visible_contacts[selection[0]]

    def export_selected_contact(self) -> None:
        contact = self.get_selected_contact()
        if not contact:
            return
        self.run_async("Export selected chat", lambda: self._export_contact(contact))

    def export_all_contacts(self) -> None:
        if not self.loaded_db:
            messagebox.showwarning("No database", "Load a database first.")
            return

        def task() -> None:
            for index, contact in enumerate(self.loaded_db.contacts, start=1):
                self.log(f"Exporting {index}/{len(self.loaded_db.contacts)}: {contact.remark}")
                self._export_contact(contact, log_each=False)

        self.run_async("Export all contacts", task)

    def _export_contact(self, contact, log_each: bool = True) -> None:
        if not self.loaded_db:
            raise RuntimeError("Database is not loaded.")

        fmt = self.export_format_var.get()
        if fmt not in EXPORTER_MAP:
            raise RuntimeError(f"Unsupported export format: {fmt}")

        exporter_cls, file_type = EXPORTER_MAP[fmt]
        output_dir = self.export_output_var.get().strip()
        os.makedirs(output_dir, exist_ok=True)

        exporter = exporter_cls(
            self.loaded_db.database,
            contact,
            output_dir=output_dir,
            type_=file_type,
            message_types=None,
            time_range=None,
            group_members=None,
        )
        exporter.start()

        if log_each:
            self.log(f"Exported {contact.remark} to {fmt} in {output_dir}")

    def export_sent_messages(self) -> None:
        contact = self.get_selected_contact()
        if not contact:
            return
        self.run_async(
            "Extract self-sent messages",
            lambda: self._export_sent_messages(contact),
        )

    def _export_sent_messages(self, contact) -> None:
        if not self.loaded_db:
            raise RuntimeError("Database is not loaded.")

        kind = self.sent_export_kind_var.get()
        output_dir = Path(self.export_output_var.get().strip())
        output_dir.mkdir(parents=True, exist_ok=True)

        messages = self.loaded_db.database.get_messages(contact.wxid, time_range=None)
        sent_messages = [msg for msg in messages if getattr(msg, "is_sender", False)]

        base_name = self._safe_filename(f"{contact.remark}_self_sent")
        if kind == "json":
            file_path = output_dir / f"{base_name}.json"
            payload = []
            for msg in sent_messages:
                item = msg.to_json()
                item["text"] = msg.to_text()
                item["str_time"] = msg.str_time
                item["talker_id"] = msg.talker_id
                item["sender_id"] = msg.sender_id
                payload.append(item)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        else:
            file_path = output_dir / f"{base_name}.txt"
            with open(file_path, "w", encoding="utf-8") as f:
                for msg in sent_messages:
                    f.write(f"{msg.str_time}\t{msg.display_name}\n")
                    f.write(f"{msg.to_text()}\n\n")

        self.log(f"Extracted {len(sent_messages)} self-sent messages to {file_path}")

    @staticmethod
    def _safe_filename(name: str) -> str:
        bad = '<>:"/\\|?*'
        for char in bad:
            name = name.replace(char, "_")
        return name.strip().rstrip(".") or "output"


def main() -> None:
    root = tk.Tk()
    app = RestoredWeChatApp(root)
    app.log("Restored GUI ready")
    app.log("For WeChat 4, keep the official client running before scanning.")
    app.log("For WeChat 3, load an already decrypted Msg directory manually.")
    app.log(f"Administrator: {'yes' if app.is_admin() else 'no'}")
    root.mainloop()


if __name__ == "__main__":
    main()
