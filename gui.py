#!/usr/bin/env python3
"""下载文件夹整理工具 — GUI v2.0

蓝色主题 + 侧边栏导航 + 分类浏览 + 自定义路径。
"""

import json
import os
import shutil
import sys
import threading
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from lib.classifier import classify, get_category_name
from lib.config_loader import (
    build_extension_map,
    get_downloads_path,
    get_folder_category,
    get_ignored_patterns,
    load_config,
)
from lib.file_ops import ensure_dir, move_folder, safe_move
from lib.history import HistoryManager, OperationRecord
from lib.reporter import Report

# ── 主题色 ──────────────────────────────────────────────────
C = {
    "primary":    "#2563EB",
    "primary_h":  "#1D4ED8",
    "light_bg":   "#DBEAFE",
    "sidebar":    "#1E293B",
    "sidebar_t":  "#94A3B8",
    "sidebar_s":  "#FFFFFF",
    "page_bg":    "#F8FAFC",
    "card":       "#FFFFFF",
    "border":     "#E2E8F0",
    "text":       "#1E293B",
    "text_s":     "#64748B",
    "success":    "#10B981",
    "warning":    "#F59E0B",
    "error":      "#EF4444",
}


# ── 数据类 ──────────────────────────────────────────────────
@dataclass
class PreviewItem:
    path: Path
    name: str
    is_folder: bool
    cat_key: str
    cat_name: str
    op_type: str


# ── 主窗口 ──────────────────────────────────────────────────
class OrganizeGUI:
    """下载文件夹整理工具 — GUI v2.0"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("下载文件夹整理工具")
        self.root.geometry("960x680")
        self.root.minsize(800, 540)
        self.root.configure(bg=C["page_bg"])
        self._center_window()
        self.root.report_callback_exception = self._handle_exception

        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        # ── 数据 ──
        self._load_config()
        self.preview_items: List[PreviewItem] = []
        self._running = False
        self._stop_requested = False
        self.last_organize_time = tk.StringVar(value="—")

        # ── 构建界面 ──
        self._apply_theme()
        self._build_sidebar()
        self._build_pages()
        self._switch_page(0)  # 默认显示待整理页
        self._build_statusbar()
        self._bind_keys()
        self._refresh_last_time()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ══════════════════════════════════════════════════════════
    # 配置
    # ══════════════════════════════════════════════════════════
    def _load_config(self):
        try:
            self.config = load_config()
        except Exception as e:
            messagebox.showerror("配置错误", str(e))
            sys.exit(1)
        self.ext_map = build_extension_map(self.config)
        self._detect_downloads()
        self.folder_category = get_folder_category(self.config)
        self.ignored_patterns = get_ignored_patterns(self.config)
        self.categories_config = self.config["categories"]
        self.category_names = {c["name"] for c in self.categories_config.values()}
        self.history_mgr = HistoryManager(APP_DIR / self.config.get("history_file", "history.json"))

    def _detect_downloads(self):
        self.downloads = get_downloads_path(self.config)

    def _save_downloads_path(self, path_str: str):
        """保存自定义下载路径到 config.json"""
        cfg_path = APP_DIR / "config.json"
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cfg["downloads_path"] = path_str
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            self.config["downloads_path"] = path_str
        except Exception as e:
            self._log(f"保存路径失败: {e}", "error")

    def _refresh_last_time(self):
        last = self.history_mgr.get_last_operation()
        self.last_organize_time.set(last["time"] if last else "—")

    # ══════════════════════════════════════════════════════════
    # 主题
    # ══════════════════════════════════════════════════════════
    def _apply_theme(self):
        style = ttk.Style()
        style.theme_use("clam")

        # 通用字体
        F = ("Microsoft YaHei UI", 9)

        # ── 全局 ──
        style.configure(".", font=F, background=C["page_bg"], foreground=C["text"])

        # ── Frame ──
        style.configure("Card.TFrame", background=C["card"], relief="solid", borderwidth=1)
        style.configure("Page.TFrame", background=C["page_bg"])

        # ── Label ──
        style.configure("Path.TLabel", foreground=C["text_s"], background=C["card"], font=("Consolas", 9))
        style.configure("Section.TLabel", foreground=C["text"], background=C["page_bg"], font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Stat.TLabel", foreground=C["text"], background=C["card"], font=F)

        # ── Button ──
        style.configure("Primary.TButton",
            background=C["primary"], foreground="white", borderwidth=0,
            padding=(16, 6), font=F,
        )
        style.map("Primary.TButton",
            background=[("active", C["primary_h"]), ("disabled", C["border"])],
            foreground=[("disabled", C["text_s"])],
        )
        style.configure("TButton",
            padding=(12, 5), font=F,
        )
        style.configure("Small.TButton", padding=(8, 3), font=F)

        # ── Treeview ──
        style.configure("Treeview",
            background=C["card"], fieldbackground=C["card"],
            foreground=C["text"], rowheight=28, borderwidth=0, font=F,
        )
        style.configure("Treeview.Heading",
            background=C["page_bg"], foreground=C["text_s"],
            font=("Microsoft YaHei UI", 9, "bold"), borderwidth=0, padding=(8, 4),
        )
        style.map("Treeview",
            background=[("selected", C["light_bg"])],
            foreground=[("selected", C["primary"])],
        )
        style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

        # ── Scrollbar ──
        style.configure("TScrollbar", background=C["card"], troughcolor=C["page_bg"], borderwidth=0)

        # ── Listbox ── (tk, not ttk)
        self.root.option_add("*Listbox.font", F)
        self.root.option_add("*Listbox.background", C["card"])
        self.root.option_add("*Listbox.foreground", C["text"])
        self.root.option_add("*Listbox.selectBackground", C["light_bg"])
        self.root.option_add("*Listbox.selectForeground", C["primary"])
        self.root.option_add("*Listbox.borderWidth", 0)
        self.root.option_add("*Listbox.highlightThickness", 0)

    # ══════════════════════════════════════════════════════════
    # 侧边栏
    # ══════════════════════════════════════════════════════════
    def _build_sidebar(self):
        self.sidebar = tk.Frame(self.root, bg=C["sidebar"], width=72)
        self.sidebar.grid(row=0, column=0, rowspan=3, sticky="ns")
        self.sidebar.grid_propagate(False)

        # 标题
        tk.Label(self.sidebar, text="DM", bg=C["sidebar"], fg=C["primary"],
                 font=("Consolas", 16, "bold")).pack(pady=(16, 24))

        nav_items = [
            ("📋", "待整理"),
            ("📁", "浏览"),
            ("📝", "日志"),
        ]
        self._nav_btns = []
        for i, (icon, text) in enumerate(nav_items):
            btn = tk.Frame(self.sidebar, bg=C["sidebar"], cursor="hand2", padx=0, pady=10)
            btn.pack(fill="x")
            btn._icon = tk.Label(btn, text=icon, bg=C["sidebar"], fg=C["sidebar_t"],
                                 font=("Segoe UI", 18), anchor="center")
            btn._icon.pack()
            btn._text = tk.Label(btn, text=text, bg=C["sidebar"], fg=C["sidebar_t"],
                                 font=("Microsoft YaHei UI", 9), anchor="center")
            btn._text.pack()
            btn._index = i
            btn._bar = tk.Frame(btn, bg=C["sidebar"], width=3)
            # bind events
            for w in (btn, btn._icon, btn._text):
                w.bind("<Button-1>", lambda e, idx=i: self._switch_page(idx))
                w.bind("<Enter>", lambda e, b=btn: self._nav_hover(b, True))
                w.bind("<Leave>", lambda e, b=btn: self._nav_hover(b, False))
            self._nav_btns.append(btn)

    def _nav_hover(self, btn: tk.Frame, enter: bool):
        if btn._index == getattr(self, "_active_page", -1):
            return
        color = "#334155" if enter else C["sidebar"]
        btn.configure(bg=color)
        btn._icon.configure(bg=color)
        btn._text.configure(bg=color)

    def _switch_page(self, index: int):
        self._active_page = index
        for i, btn in enumerate(self._nav_btns):
            if i == index:
                btn.configure(bg="#1E3A5F")
                btn._icon.configure(bg="#1E3A5F", fg=C["primary"])
                btn._text.configure(bg="#1E3A5F", fg=C["sidebar_s"])
                btn._bar.configure(bg=C["primary"])
                btn._bar.place(x=0, y=6, width=3, height=44)
            else:
                btn.configure(bg=C["sidebar"])
                btn._icon.configure(bg=C["sidebar"], fg=C["sidebar_t"])
                btn._text.configure(bg=C["sidebar"], fg=C["sidebar_t"])
                btn._bar.place_forget()

        for p in self._pages:
            p.place_forget()
        self._pages[index].place(x=0, y=0, relwidth=1, relheight=1)

    # ══════════════════════════════════════════════════════════
    # 三个页面
    # ══════════════════════════════════════════════════════════
    def _build_pages(self):
        container = tk.Frame(self.root, bg=C["page_bg"])
        container.grid(row=0, column=1, sticky="nsew", padx=(0, 0), pady=(0, 0))
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        self._pages: List[tk.Frame] = []
        self._pages.append(self._build_pending_page(container))
        self._pages.append(self._build_browse_page(container))
        self._pages.append(self._build_log_page(container))

    # ── 页面 1: 待整理 ─────────────────────────────────────
    def _build_pending_page(self, parent) -> tk.Frame:
        page = tk.Frame(parent, bg=C["page_bg"])
        page.place(x=0, y=0, relwidth=1, relheight=1)
        page.columnconfigure(0, weight=1)
        page.rowconfigure(2, weight=1)

        # 路径栏
        path_card = tk.Frame(page, bg=C["card"], highlightbackground=C["border"],
                             highlightthickness=1, padx=16, pady=12)
        path_card.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 8))
        path_card.columnconfigure(1, weight=1)

        tk.Label(path_card, text="下载文件夹", bg=C["card"], fg=C["text"],
                 font=("Microsoft YaHei UI", 10, "bold")).grid(row=0, column=0, sticky="w")
        self._path_label = tk.Label(path_card, text="", bg=C["card"], fg=C["text_s"],
                                     font=("Consolas", 9), anchor="w")
        self._path_label.grid(row=0, column=1, sticky="ew", padx=(12, 8))
        self._update_path_label()

        ttk.Button(path_card, text="更改...", command=self._on_change_path,
                   style="Small.TButton").grid(row=0, column=2, padx=(0, 4))
        ttk.Button(path_card, text="重置", command=self._on_reset_path,
                   style="Small.TButton").grid(row=0, column=3)

        # Treeview 卡片
        tree_card = tk.Frame(page, bg=C["card"], highlightbackground=C["border"],
                             highlightthickness=1, padx=16, pady=12)
        tree_card.grid(row=2, column=0, sticky="nsew", padx=20, pady=(4, 8))
        tree_card.rowconfigure(0, weight=1)
        tree_card.columnconfigure(0, weight=1)

        columns = ("name", "type", "category", "action")
        self.p_tree = ttk.Treeview(tree_card, columns=columns, show="headings", selectmode="extended")
        self.p_tree.heading("name", text="文件名")
        self.p_tree.heading("type", text="类型")
        self.p_tree.heading("category", text="目标分类")
        self.p_tree.heading("action", text="操作")
        self.p_tree.column("name", width=340, minwidth=140)
        self.p_tree.column("type", width=56, minwidth=50, anchor="center")
        self.p_tree.column("category", width=90, minwidth=70, anchor="center")
        self.p_tree.column("action", width=100, minwidth=80, anchor="center")

        p_scroll = ttk.Scrollbar(tree_card, orient="vertical", command=self.p_tree.yview)
        self.p_tree.configure(yscrollcommand=p_scroll.set)
        self.p_tree.grid(row=0, column=0, sticky="nsew")
        p_scroll.grid(row=0, column=1, sticky="ns")

        # 右键菜单
        self._p_menu = tk.Menu(self.p_tree, tearoff=0)
        self._p_menu.add_command(label="🗑 删除选中", command=lambda: self._on_delete_tree("pending"))
        self._p_menu.add_command(label="🔍 全选", command=lambda: self.p_tree.selection_set(self.p_tree.get_children()))
        self.p_tree.bind("<Button-3>", self._on_p_tree_right_click)
        self.p_tree.bind("<Button-2>", self._on_p_tree_right_click)

        # 统计 + 按钮栏
        bottom = tk.Frame(page, bg=C["page_bg"])
        bottom.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 4))
        bottom.columnconfigure(0, weight=1)

        self._p_stats = tk.Frame(bottom, bg=C["page_bg"])
        self._p_stats.grid(row=0, column=0, sticky="w")

        btn_frame = tk.Frame(bottom, bg=C["page_bg"])
        btn_frame.grid(row=0, column=1, sticky="e")

        self.btn_preview = ttk.Button(btn_frame, text="🔍 预览", command=self._on_preview)
        self.btn_preview.pack(side="left", padx=(0, 6))
        self.btn_organize = ttk.Button(btn_frame, text="▶ 立即整理", command=self._on_organize)
        self.btn_organize.pack(side="left", padx=(0, 6))
        self.btn_del_pen = ttk.Button(btn_frame, text="🗑 删除选中", command=lambda: self._on_delete_tree("pending"))
        self.btn_del_pen.pack(side="left", padx=(0, 6))
        self.btn_undo = ttk.Button(btn_frame, text="↩ 撤销", command=self._on_undo)
        self.btn_undo.pack(side="left")

        return page

    def _update_path_label(self):
        self._path_label.config(text=str(self.downloads) if self.downloads else "未设置")

    def _on_change_path(self):
        path = filedialog.askdirectory(title="选择下载文件夹", initialdir=str(self.downloads))
        if path:
            self.downloads = Path(path)
            self._save_downloads_path(str(self.downloads))
            self._update_path_label()
            self._log(f"下载路径已更改: {self.downloads}", "info")
            self._on_preview()

    def _on_reset_path(self):
        self.config["downloads_path"] = "auto"
        self._save_downloads_path("auto")
        self._detect_downloads()
        self._update_path_label()
        self._log(f"已恢复自动检测: {self.downloads}", "info")
        self._on_preview()

    def _on_p_tree_right_click(self, event):
        row = self.p_tree.identify_row(event.y)
        if row and row not in self.p_tree.selection():
            self.p_tree.selection_set(row)
        try:
            self._p_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._p_menu.grab_release()

    # ── 页面 2: 浏览分类 ─────────────────────────────────────
    def _build_browse_page(self, parent) -> tk.Frame:
        page = tk.Frame(parent, bg=C["page_bg"])
        page.place(x=0, y=0, relwidth=1, relheight=1)
        page.columnconfigure(0, weight=1)
        page.rowconfigure(0, weight=1)

        # 使用 PanedWindow 分割左右
        pw = tk.Frame(page, bg=C["page_bg"])
        pw.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        pw.columnconfigure(1, weight=1)
        pw.rowconfigure(0, weight=1)

        # 左侧 — 分类列表
        left_card = tk.Frame(pw, bg=C["card"], highlightbackground=C["border"],
                             highlightthickness=1, padx=8, pady=8)
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left_card.rowconfigure(1, weight=1)

        tk.Label(left_card, text="分类目录", bg=C["card"], fg=C["text"],
                 font=("Microsoft YaHei UI", 10, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 6))

        self._cat_listbox = tk.Listbox(left_card, width=18, bg=C["card"], fg=C["text"],
                                        selectbackground=C["light_bg"], selectforeground=C["primary"],
                                        activestyle="none", borderwidth=0, highlightthickness=0)
        self._cat_listbox.grid(row=1, column=0, sticky="nsew")
        self._cat_listbox.bind("<<ListboxSelect>>", self._on_cat_select)

        # 右侧 — 文件列表
        right_card = tk.Frame(pw, bg=C["card"], highlightbackground=C["border"],
                              highlightthickness=1, padx=12, pady=12)
        right_card.grid(row=0, column=1, sticky="nsew")
        right_card.columnconfigure(0, weight=1)
        right_card.rowconfigure(0, weight=1)

        b_columns = ("name", "size", "modified")
        self.b_tree = ttk.Treeview(right_card, columns=b_columns, show="headings", selectmode="extended")
        self.b_tree.heading("name", text="文件名")
        self.b_tree.heading("size", text="大小")
        self.b_tree.heading("modified", text="修改日期")
        self.b_tree.column("name", width=300, minwidth=120)
        self.b_tree.column("size", width=80, minwidth=60, anchor="e")
        self.b_tree.column("modified", width=120, minwidth=90, anchor="center")

        b_scroll = ttk.Scrollbar(right_card, orient="vertical", command=self.b_tree.yview)
        self.b_tree.configure(yscrollcommand=b_scroll.set)
        self.b_tree.grid(row=0, column=0, sticky="nsew")
        b_scroll.grid(row=0, column=1, sticky="ns")

        # 右键 + 按钮
        self._b_menu = tk.Menu(self.b_tree, tearoff=0)
        self._b_menu.add_command(label="🗑 删除选中", command=lambda: self._on_delete_tree("browse"))
        self.b_tree.bind("<Button-3>", self._on_b_tree_right_click)
        self.b_tree.bind("<Button-2>", self._on_b_tree_right_click)

        self.btn_del_brw = ttk.Button(right_card, text="🗑 删除选中",
                                       command=lambda: self._on_delete_tree("browse"))
        self.btn_del_brw.grid(row=1, column=0, sticky="e", pady=(8, 0))

        return page

    def _refresh_cat_list(self):
        """刷新分类列表"""
        self._cat_listbox.delete(0, "end")
        if not self.downloads or not self.downloads.exists():
            return
        for cat_key, cat_info in self.categories_config.items():
            name = cat_info.get("name", cat_key)
            cat_dir = self.downloads / name
            count = sum(1 for _ in cat_dir.iterdir()) if cat_dir.exists() else 0
            self._cat_listbox.insert("end", f"  {name}  ({count})")

    def _on_cat_select(self, event=None):
        sel = self._cat_listbox.curselection()
        if not sel:
            return
        text = self._cat_listbox.get(sel[0])
        cat_name = text.strip().split("  (")[0]
        cat_dir = self.downloads / cat_name

        # 清空
        for row in self.b_tree.get_children():
            self.b_tree.delete(row)

        if not cat_dir.exists():
            return

        items = sorted(cat_dir.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        for i, item in enumerate(items):
            try:
                st = item.stat()
                size = self._fmt_size(st.st_size)
                mtime = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
            except OSError:
                size = "—"
                mtime = "—"
            type_tag = "📁" if item.is_dir() else "📄"
            self.b_tree.insert("", "end", iid=str(i), values=(f"{type_tag} {item.name}", size, mtime))

    def _on_b_tree_right_click(self, event):
        row = self.b_tree.identify_row(event.y)
        if row and row not in self.b_tree.selection():
            self.b_tree.selection_set(row)
        try:
            self._b_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._b_menu.grab_release()

    @staticmethod
    def _fmt_size(size: int) -> str:
        if size >= 1_000_000_000:
            return f"{size / 1_000_000_000:.1f} GB"
        if size >= 1_000_000:
            return f"{size / 1_000_000:.1f} MB"
        if size >= 1_000:
            return f"{size / 1_000:.1f} KB"
        return f"{size} B"

    # ── 页面 3: 操作日志 ─────────────────────────────────────
    def _build_log_page(self, parent) -> tk.Frame:
        page = tk.Frame(parent, bg=C["page_bg"])
        page.place(x=0, y=0, relwidth=1, relheight=1)

        card = tk.Frame(page, bg=C["card"], highlightbackground=C["border"],
                        highlightthickness=1, padx=12, pady=12)
        card.place(x=20, y=20, relwidth=1, relheight=1, width=-40, height=-40)
        card.rowconfigure(0, weight=1)
        card.columnconfigure(0, weight=1)

        self.log_text = tk.Text(card, state="disabled", wrap="word", font=("Consolas", 9),
                                bg=C["card"], fg=C["text"], borderwidth=0, padx=8, pady=8)
        log_scroll = ttk.Scrollbar(card, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll.grid(row=0, column=1, sticky="ns")

        # 颜色标签
        self.log_text.tag_configure("move", foreground=C["success"])
        self.log_text.tag_configure("dedup", foreground=C["primary"])
        self.log_text.tag_configure("skip", foreground=C["text_s"])
        self.log_text.tag_configure("error", foreground=C["error"])
        self.log_text.tag_configure("info", foreground=C["text"], font=("Consolas", 9, "bold"))

        return page

    # ══════════════════════════════════════════════════════════
    # 底部状态栏
    # ══════════════════════════════════════════════════════════
    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg=C["card"], height=36, highlightbackground=C["border"], highlightthickness=1)
        bar.grid(row=2, column=1, sticky="ew")
        bar.grid_propagate(False)
        bar.columnconfigure(1, weight=1)

        self._status_dot = tk.Canvas(bar, width=10, height=10, highlightthickness=0, bg=C["card"])
        self._status_dot.grid(row=0, column=0, padx=(16, 6))
        self._draw_dot(C["success"])

        self._status_label = tk.Label(bar, text="就绪", bg=C["card"], fg=C["text"], font=("Microsoft YaHei UI", 9))
        self._status_label.grid(row=0, column=1, sticky="w")

        self._status_text = tk.StringVar(value="就绪")
        tk.Label(bar, textvariable=self._status_text, bg=C["card"], fg=C["text_s"],
                 font=("Microsoft YaHei UI", 9)).grid(row=0, column=2, padx=(20, 0))

        tk.Label(bar, text="上次整理:", bg=C["card"], fg=C["text_s"],
                 font=("Microsoft YaHei UI", 9)).grid(row=0, column=3, padx=(40, 4))
        tk.Label(bar, textvariable=self.last_organize_time, bg=C["card"], fg=C["text_s"],
                 font=("Microsoft YaHei UI", 9)).grid(row=0, column=4, padx=(0, 16))

        self._progress = ttk.Progressbar(bar, mode="indeterminate", length=100)

    def _draw_dot(self, color: str):
        self._status_dot.delete("all")
        self._status_dot.create_oval(1, 1, 9, 9, fill=color, outline="")

    def _set_running(self, running: bool):
        self._running = running
        state = "disabled" if running else "normal"
        self.btn_preview.config(state=state)
        self.btn_organize.config(state=state)
        self.btn_undo.config(state=state)
        self.btn_del_pen.config(state=state)
        self.btn_del_brw.config(state=state)
        if running:
            self._progress.grid(row=0, column=5, padx=(0, 16))
            self._progress.start(10)
        else:
            self._progress.stop()
            self._progress.grid_forget()
            self._stop_requested = False

    def _log(self, msg: str, tag: str = "info"):
        self.log_text.config(state="normal")
        ts = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] ", tag)
        self.log_text.insert("end", f"{msg}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    # ══════════════════════════════════════════════════════════
    # 快捷键
    # ══════════════════════════════════════════════════════════
    def _bind_keys(self):
        self.root.bind("<Control-p>", lambda e: self._on_preview())
        self.root.bind("<Control-P>", lambda e: self._on_preview())
        self.root.bind("<Control-o>", lambda e: self._on_organize())
        self.root.bind("<Control-O>", lambda e: self._on_organize())
        self.root.bind("<Control-z>", lambda e: self._on_undo())
        self.root.bind("<Control-Z>", lambda e: self._on_undo())
        self.root.bind("<Control-a>", lambda e: self._select_all_current())
        self.root.bind("<Control-A>", lambda e: self._select_all_current())
        self.root.bind("<Delete>", lambda e: self._on_delete_current())

    def _select_all_current(self):
        tree = self._current_tree()
        if tree:
            tree.selection_set(tree.get_children())

    def _on_delete_current(self):
        if self._active_page == 0:
            self._on_delete_tree("pending")
        elif self._active_page == 1:
            self._on_delete_tree("browse")

    def _current_tree(self):
        if self._active_page == 0:
            return self.p_tree
        elif self._active_page == 1:
            return self.b_tree
        return None

    def _center_window(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")

    def _handle_exception(self, exc_type, exc_val, exc_tb):
        """全局异常处理 — 弹出错误框避免静默崩溃"""
        import traceback
        msg = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
        self._log(f"未捕获异常:\n{msg}", "error")
        messagebox.showerror("程序错误", f"{exc_val}\n\n详情请查看操作日志")

    def _on_close(self):
        if self._running:
            if not messagebox.askyesno("确认退出", "整理正在进行中，确定退出？"):
                return
            self._stop_requested = True
        self.root.destroy()

    # ══════════════════════════════════════════════════════════
    # 通用删除
    # ══════════════════════════════════════════════════════════
    def _on_delete_tree(self, source: str):
        """统一删除入口 — source: 'pending' | 'browse'"""
        if self._running:
            return

        if source == "pending":
            tree = self.p_tree
            items_list = self.preview_items
            is_folder_check = lambda i: i.is_folder
            get_path = lambda i: i.path
            refresh = self._on_preview
        else:
            tree = self.b_tree
            # 获取当前选中分类目录
            sel = self._cat_listbox.curselection()
            if not sel:
                return
            text = self._cat_listbox.get(sel[0])
            cat_name = text.strip().split("  (")[0]
            cat_dir = self.downloads / cat_name
            if not cat_dir.exists():
                return
            all_items = sorted(cat_dir.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            items_list = list(all_items)
            is_folder_check = lambda p: p.is_dir()
            get_path = lambda p: p
            refresh = self._on_cat_select

        selection = tree.selection()
        if not selection:
            return

        # 收集要删除的路径
        to_delete: List[Path] = []
        for iid in selection:
            try:
                idx = int(iid)
                path = get_path(items_list[idx])
                to_delete.append(path)
            except (ValueError, IndexError):
                continue

        if not to_delete:
            return

        # 直接删除
        deleted, errors = 0, 0
        for path in to_delete:
            try:
                if is_folder_check(path):
                    shutil.rmtree(path)
                else:
                    path.unlink()
                deleted += 1
                self._log(f"已删除 {path.name}", "dedup")
            except (PermissionError, OSError) as e:
                errors += 1
                self._log(f"删除失败 {path.name}: {e}", "error")

        self._log(f"删除完成: {deleted} 项" + (f", {errors} 失败" if errors else ""), "info")

        # 刷新
        self._refresh_cat_list()
        refresh()

    # ══════════════════════════════════════════════════════════
    # 预览
    # ══════════════════════════════════════════════════════════
    def _on_preview(self):
        if not self.downloads or not self.downloads.exists():
            self._log("错误: 下载文件夹不存在，请检查路径设置", "error")
            self._status_text.set("路径无效")
            messagebox.showwarning("路径错误", f"下载文件夹不存在:\n{self.downloads}\n\n请在顶部点击 [更改...] 选择正确的文件夹。")
            return

        self._switch_page(0)
        self._status_text.set("正在扫描...")
        self.root.update_idletasks()

        try:
            self.preview_items = self._scan_and_classify()
        except Exception as e:
            self._log(f"扫描失败: {e}", "error")
            self._status_text.set("扫描出错")
            messagebox.showerror("扫描错误", str(e))
            return
            return

        # 填充 Treeview
        for row in self.p_tree.get_children():
            self.p_tree.delete(row)
        for i, item in enumerate(self.preview_items):
            op_text = {"move": f"→ {item.cat_name}/", "dedup": "去重", "rename": f"→ {item.cat_name}/(重命名)", "skip": "跳过"}.get(item.op_type, item.op_type)
            self.p_tree.insert("", "end", iid=str(i), values=(item.name, "文件夹" if item.is_folder else "文件", item.cat_name, op_text))

        # 统计
        for w in self._p_stats.winfo_children():
            w.destroy()
        counts = Counter(i.cat_name for i in self.preview_items if i.cat_key != "skipped")
        skipped = sum(1 for i in self.preview_items if i.cat_key == "skipped")
        for cat_key, cat_info in self.categories_config.items():
            name = cat_info.get("name", cat_key)
            n = counts.get(name, 0)
            tk.Label(self._p_stats, text=f"[{name}: {n}]", bg=C["page_bg"], fg=C["text"],
                     font=("Microsoft YaHei UI", 9)).pack(side="left", padx=(0, 10))
        if skipped:
            tk.Label(self._p_stats, text=f"[忽略: {skipped}]", bg=C["page_bg"], fg=C["text_s"],
                     font=("Microsoft YaHei UI", 9)).pack(side="left", padx=(0, 10))
        total = sum(counts.values())
        tk.Label(self._p_stats, text=f"共 {total} 项", bg=C["page_bg"], fg=C["text_s"],
                 font=("Microsoft YaHei UI", 9)).pack(side="left")

        self._status_text.set("就绪")
        self._log(f"预览: {total} 项待整理, {skipped} 忽略", "info")

    def _scan_and_classify(self) -> List[PreviewItem]:
        if not self.downloads or not self.downloads.exists():
            return []
        all_items = sorted([p for p in self.downloads.iterdir() if p.is_dir()], key=lambda p: p.name.lower()) + \
                    sorted([p for p in self.downloads.iterdir() if p.is_file()], key=lambda p: p.name.lower())
        result = []
        for item in all_items:
            if item.is_dir() and item.name in self.category_names:
                continue
            cat_key = classify(item, self.ext_map, self.folder_category, self.ignored_patterns)
            if cat_key is None:
                result.append(PreviewItem(item, item.name, item.is_dir(), "skipped", "忽略", "skip"))
            else:
                cat_name = get_category_name(cat_key, self.categories_config)
                dest_dir = self.downloads / cat_name
                op_type = "move"
                if dest_dir.exists() and (dest_dir / item.name).exists():
                    try:
                        from lib.file_ops import resolve_destination
                        _, op_type = resolve_destination(item, dest_dir)
                    except Exception:
                        pass
                result.append(PreviewItem(item, item.name, item.is_dir(), cat_key, cat_name, op_type))
        return result

    # ══════════════════════════════════════════════════════════
    # 整理
    # ══════════════════════════════════════════════════════════
    def _on_organize(self):
        if self._running:
            return
        if not self.preview_items:
            self._on_preview()
        if not self.preview_items:
            messagebox.showinfo("提示", "请先点击 [预览] 扫描文件。")
            return
        total = sum(1 for i in self.preview_items if i.cat_key != "skipped")
        if total == 0:
            messagebox.showinfo("提示", "没有需要整理的文件，下载文件夹可能已是最新状态。")
            return
        if not messagebox.askyesno("确认", f"将对 {total} 项执行整理，是否继续？"):
            return

        self._set_running(True)
        self._status_text.set(f"整理中 (0/{total})...")
        self._log(f"开始整理: {total} 项", "info")
        threading.Thread(target=self._run_organize_thread, args=(self.preview_items,), daemon=True).start()

    def _run_organize_thread(self, items: List[PreviewItem]):
        report = Report(self.categories_config)
        record = OperationRecord()
        total = sum(1 for i in items if i.cat_key != "skipped")
        done = 0
        for item in items:
            if self._stop_requested:
                self.root.after(0, self._on_organize_stopped, done, total)
                return
            if item.cat_key == "skipped":
                report.record_skip(item.name, "")
                continue
            dest_dir = self.downloads / item.cat_name
            try:
                ensure_dir(dest_dir)
                result, op_type = (move_folder(item.path, dest_dir) if item.is_folder else safe_move(item.path, dest_dir))
                if op_type == "dedup":
                    report.record_dedup(item.cat_key)
                else:
                    report.record_move(item.cat_key, is_folder=item.is_folder)
                record.add_move(item.path, result, op_type)
                done += 1
                self.root.after(0, self._on_progress, done, total, item.name, item.cat_name, op_type)
            except (PermissionError, OSError) as e:
                report.record_error(item.name, str(e))
                self.root.after(0, self._log, f"错误 {item.name}: {e}", "error")
        if record.count > 0:
            self.history_mgr.save_record(record)
        self.root.after(0, self._on_organize_done, report)

    def _on_progress(self, done, total, name, cat_name, op_type):
        self._status_text.set(f"整理中 ({done}/{total})...")
        label = {"move": "→", "dedup": "去重", "rename": "重命名→"}.get(op_type, op_type)
        self._log(f"{label} {name} → {cat_name}/", "dedup" if op_type == "dedup" else "move")

    def _on_organize_done(self, report: Report):
        self._set_running(False)
        self._status_text.set("就绪")
        self._refresh_last_time()
        self._log(f"整理完成: {report.total_moved} 项" + (f", 去重 {report.total_dedup}" if report.total_dedup else ""), "info")
        self._on_preview()
        self._refresh_cat_list()

    def _on_organize_stopped(self, done, total):
        self._set_running(False)
        self._status_text.set("已停止")
        self._log(f"已停止 ({done}/{total})", "info")
        self._on_preview()

    # ══════════════════════════════════════════════════════════
    # 撤销
    # ══════════════════════════════════════════════════════════
    def _on_undo(self):
        if self._running:
            return
        last = self.history_mgr.get_last_operation()
        if not last or not last.get("moves"):
            messagebox.showinfo("提示", "没有可撤销的操作。")
            return
        moves = last["moves"]
        time_str = last.get("time", "?")
        msg = f"撤销 {time_str} 的整理？\n\n{len(moves)} 项将被恢复"
        if not messagebox.askyesno("确认撤销", msg):
            return
        self._set_running(True)
        self._status_text.set("撤销中...")
        self._log(f"撤销: {len(moves)} 项", "info")
        threading.Thread(target=self._run_undo_thread, args=(last,), daemon=True).start()

    def _run_undo_thread(self, last_op: dict):
        moves = last_op.get("moves", [])
        success, failed = 0, 0
        for entry in reversed(moves):
            if self._stop_requested:
                break
            op_type = entry.get("type", "")
            src_str, dest_str = entry.get("from", ""), entry.get("to", "")
            if not src_str or not dest_str or op_type == "dedup":
                continue
            src, dest = Path(src_str), Path(dest_str)
            try:
                if dest.exists():
                    ensure_dir(src.parent)
                    shutil.move(str(dest), str(src))
                    success += 1
                    self.root.after(0, self._log, f"恢复 {dest.name}", "move")
                else:
                    failed += 1
            except (PermissionError, OSError) as e:
                failed += 1
                self.root.after(0, self._log, f"撤销失败 {dest.name}: {e}", "error")
        self.history_mgr.pop_last_operation()
        self._cleanup_empty()
        self.root.after(0, self._on_undo_done, success, failed)

    def _on_undo_done(self, success, failed):
        self._set_running(False)
        self._status_text.set("就绪")
        self._refresh_last_time()
        msg = f"撤销完成: {success} 项恢复" + (f", {failed} 失败" if failed else "")
        self._log(msg, "info")
        self._on_preview()
        self._refresh_cat_list()

    def _cleanup_empty(self):
        if not self.downloads or not self.downloads.exists():
            return
        for item in self.downloads.iterdir():
            if item.is_dir() and item.name in self.category_names:
                try:
                    if not any(item.iterdir()):
                        item.rmdir()
                except OSError:
                    pass


# ── 入口 ────────────────────────────────────────────────────
def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    root = tk.Tk()
    OrganizeGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
