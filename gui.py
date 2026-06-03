#!/usr/bin/env python3
"""下载文件夹整理工具 — GUI v3.0 (CustomTkinter)"""

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

import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
import tkinter as tk

from lib.classifier import classify, get_category_name
from lib.config_loader import (
    build_extension_map, get_downloads_path, get_folder_category,
    get_ignored_patterns, load_config,
)
from lib.file_ops import ensure_dir, move_folder, safe_move
from lib.history import HistoryManager, OperationRecord
from lib.reporter import Report

# ── 主题 ──────────────────────────────────────────────────
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

C = {
    "primary":   "#2563EB",
    "primary_h": "#1D4ED8",
    "light_bg":  "#DBEAFE",
    "page_bg":   "#F8FAFC",
    "card":      "#FFFFFF",
    "border":    "#E2E8F0",
    "text":      "#1E293B",
    "text_s":    "#64748B",
    "success":   "#10B981",
    "warning":   "#F59E0B",
    "error":     "#EF4444",
    "sidebar_bg":"#F1F5F9",
    "sidebar_s": "#2563EB",
    "sidebar_t": "#64748B",
}


@dataclass
class PreviewItem:
    path: Path
    name: str
    is_folder: bool
    cat_key: str
    cat_name: str
    op_type: str


class OrganizeGUI:
    """v3.0 — CustomTkinter 现代界面"""

    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("下载文件夹整理工具")
        self.root.geometry("960x680")
        self.root.minsize(800, 540)

        # ── 全局字体 ──
        self.root.option_add("*Listbox.font", ("Microsoft YaHei UI", 15))
        # ── 异常处理 ──
        self.root.report_callback_exception = self._handle_exception

        # ── 数据 ──
        self._load_config()
        self.preview_items: List[PreviewItem] = []
        self._running = False
        self._stop_requested = False
        self._active_page = 0
        self.last_organize_time = tk.StringVar(value="—")

        # ── 构建界面（严格顺序） ──
        self._build_root_grid()
        self._build_sidebar()
        self._build_pages()
        self._switch_page(0)
        self._build_statusbar()
        self._bind_keys()
        self._refresh_last_time()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._center()

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
        self.downloads = get_downloads_path(self.config)
        self.folder_category = get_folder_category(self.config)
        self.ignored_patterns = get_ignored_patterns(self.config)
        self.categories_config = self.config["categories"]
        self.category_names = {c["name"] for c in self.categories_config.values()}
        self.history_mgr = HistoryManager(APP_DIR / self.config.get("history_file", "history.json"))

    def _save_downloads_path(self, path_str: str):
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

    # ══════════════════════════════════════════════════════════
    # 根布局
    # ══════════════════════════════════════════════════════════
    def _build_root_grid(self):
        self.root.grid_columnconfigure(0, weight=0)  # sidebar
        self.root.grid_columnconfigure(1, weight=1)  # content
        self.root.grid_rowconfigure(0, weight=1)     # main area
        self.root.grid_rowconfigure(1, weight=0)     # statusbar

    # ══════════════════════════════════════════════════════════
    # 侧边栏（浅色）
    # ══════════════════════════════════════════════════════════
    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self.root, width=90, fg_color=C["sidebar_bg"],
                                     corner_radius=0, border_width=0)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="ns")
        self.sidebar.grid_propagate(False)

        nav_items = [("📋", "整理"), ("📁", "浏览"), ("📝", "日志")]
        self._nav_btns = []
        for i, (icon, text) in enumerate(nav_items):
            btn = ctk.CTkButton(
                self.sidebar, text=f"{icon}  {text}",
                font=ctk.CTkFont(size=16), anchor="w",
                fg_color="transparent", text_color=C["sidebar_t"],
                hover_color=C["light_bg"], corner_radius=8,
                height=46, width=80,
                command=lambda idx=i: self._switch_page(idx),
            )
            btn.pack(pady=3, padx=4)
            self._nav_btns.append(btn)

    # ══════════════════════════════════════════════════════════
    # 页面容器
    # ══════════════════════════════════════════════════════════
    def _build_pages(self):
        container = ctk.CTkFrame(self.root, fg_color=C["page_bg"], corner_radius=0)
        container.grid(row=0, column=1, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)

        self._pages: List[ctk.CTkFrame] = [
            self._build_pending_page(container),
            self._build_browse_page(container),
            self._build_log_page(container),
        ]

    def _switch_page(self, index: int):
        self._active_page = index
        # 侧边栏高亮
        for i, btn in enumerate(self._nav_btns):
            if i == index:
                btn.configure(fg_color=C["sidebar_s"], text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color=C["sidebar_t"])
        # 页面切换
        for p in self._pages:
            p.grid_remove()
        self._pages[index].grid(row=0, column=0, sticky="nsew")
        # 浏览页自动刷新
        if index == 1:
            self._refresh_cat_list()

    # ══════════════════════════════════════════════════════════
    # 页面 1: 待整理
    # ══════════════════════════════════════════════════════════
    def _build_pending_page(self, parent) -> ctk.CTkFrame:
        page = ctk.CTkFrame(parent, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(2, weight=1)

        # ── 路径栏 ──
        path_card = ctk.CTkFrame(page, fg_color=C["card"], corner_radius=10,
                                  border_width=1, border_color=C["border"])
        path_card.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))
        path_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(path_card, text="下载文件夹", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=C["text"]).grid(row=0, column=0, sticky="w", padx=16, pady=12)
        self._path_label = ctk.CTkLabel(path_card, text="", font=ctk.CTkFont(size=16),
                                         text_color=C["text_s"], anchor="w")
        self._path_label.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        self._update_path_label()

        ctk.CTkButton(path_card, text="更改...", width=70, height=30,
                      font=ctk.CTkFont(size=16), fg_color=C["primary"],
                      hover_color=C["primary_h"], corner_radius=6,
                      command=self._on_change_path).grid(row=0, column=2, padx=(0, 6), pady=12)
        ctk.CTkButton(path_card, text="重置", width=56, height=30,
                      font=ctk.CTkFont(size=16), fg_color="transparent",
                      text_color=C["text_s"], hover_color=C["border"],
                      border_width=1, border_color=C["border"], corner_radius=6,
                      command=self._on_reset_path).grid(row=0, column=3, padx=(0, 12), pady=12)

        # ── 统计标签栏 ──
        self._p_stats = ctk.CTkFrame(page, fg_color="transparent")
        self._p_stats.grid(row=1, column=0, sticky="ew", padx=20, pady=(4, 2))

        # ── Treeview ──
        tree_card = ctk.CTkFrame(page, fg_color=C["card"], corner_radius=10,
                                  border_width=1, border_color=C["border"])
        tree_card.grid(row=2, column=0, sticky="nsew", padx=20, pady=(4, 8))
        tree_card.grid_columnconfigure(0, weight=1)
        tree_card.grid_rowconfigure(0, weight=1)

        self._build_treeview(tree_card)
        self._setup_tree_menu(self.p_tree)

        # ── 按钮栏 ──
        btn_frame = ctk.CTkFrame(page, fg_color="transparent")
        btn_frame.grid(row=3, column=0, sticky="e", padx=20, pady=(0, 12))

        self.btn_preview = ctk.CTkButton(btn_frame, text="🔍 预览", width=100, height=34,
                                          font=ctk.CTkFont(size=16), fg_color="transparent",
                                          text_color=C["text"], hover_color=C["border"],
                                          border_width=1, border_color=C["border"],
                                          corner_radius=6, command=self._on_preview)
        self.btn_preview.pack(side="left", padx=(0, 8))
        self.btn_organize = ctk.CTkButton(btn_frame, text="▶ 立即整理", width=110, height=34,
                                           font=ctk.CTkFont(size=16, weight="bold"),
                                           fg_color=C["primary"], hover_color=C["primary_h"],
                                           corner_radius=6, command=self._on_organize)
        self.btn_organize.pack(side="left", padx=(0, 8))
        self.btn_del_pen = ctk.CTkButton(btn_frame, text="🗑 删除选中", width=100, height=34,
                                          font=ctk.CTkFont(size=16), fg_color="transparent",
                                          text_color=C["error"], hover_color="#FEE2E2",
                                          border_width=1, border_color=C["error"],
                                          corner_radius=6,
                                          command=lambda: self._on_delete_tree("pending"))
        self.btn_del_pen.pack(side="left", padx=(0, 8))
        self.btn_undo = ctk.CTkButton(btn_frame, text="↩ 撤销", width=80, height=34,
                                       font=ctk.CTkFont(size=16), fg_color="transparent",
                                       text_color=C["text"], hover_color=C["border"],
                                       border_width=1, border_color=C["border"],
                                       corner_radius=6, command=self._on_undo)
        self.btn_undo.pack(side="left")

        return page

    def _build_treeview(self, parent):
        """创建标准 Treeview 组件"""
        columns = ("name", "type", "category", "action")
        self.p_tree = ttk.Treeview(parent, columns=columns, show="headings", selectmode="extended")
        self.p_tree.heading("name", text="文件名");   self.p_tree.column("name", width=340, minwidth=140)
        self.p_tree.heading("type", text="类型");     self.p_tree.column("type", width=56, minwidth=50, anchor="center")
        self.p_tree.heading("category", text="目标分类"); self.p_tree.column("category", width=90, minwidth=70, anchor="center")
        self.p_tree.heading("action", text="操作");   self.p_tree.column("action", width=100, minwidth=80, anchor="center")

        scroll = ttk.Scrollbar(parent, orient="vertical", command=self.p_tree.yview)
        self.p_tree.configure(yscrollcommand=scroll.set)
        self.p_tree.grid(row=0, column=0, sticky="nsew", padx=(16, 0), pady=16)
        scroll.grid(row=0, column=1, sticky="ns", padx=(0, 12), pady=16)

        # 样式
        style = ttk.Style()
        style.configure("Treeview", rowheight=50, font=("Microsoft YaHei UI", 16),
                        background=C["card"], fieldbackground=C["card"], borderwidth=0)
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 16, "bold"),
                        background=C["page_bg"], borderwidth=0)
        style.map("Treeview", background=[("selected", C["light_bg"])], foreground=[("selected", C["primary"])])

    def _setup_tree_menu(self, tree):
        menu = tk.Menu(tree, tearoff=0, bg=C["card"], fg=C["text"], activebackground=C["light_bg"])
        menu.add_command(label="🗑 删除选中", command=lambda: self._on_delete_tree("pending"))
        menu.add_command(label="🔍 全选", command=lambda: tree.selection_set(tree.get_children()))
        tree.bind("<Button-3>", lambda e: self._tree_right_click(e, tree, menu))
        tree.bind("<Button-2>", lambda e: self._tree_right_click(e, tree, menu))
        self._p_menu = menu

    def _tree_right_click(self, event, tree, menu):
        row = tree.identify_row(event.y)
        if row and row not in tree.selection():
            tree.selection_set(row)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _update_path_label(self):
        self._path_label.configure(text=str(self.downloads) if self.downloads else "未设置")

    def _on_change_path(self):
        path = filedialog.askdirectory(title="选择下载文件夹", initialdir=str(self.downloads))
        if path:
            self.downloads = Path(path)
            self._save_downloads_path(str(self.downloads))
            self._update_path_label()
            self._log(f"路径已更改: {self.downloads}", "info")
            self._on_preview()

    def _on_reset_path(self):
        self._save_downloads_path("auto")
        self.config["downloads_path"] = "auto"
        self.downloads = get_downloads_path(self.config)
        self._update_path_label()
        self._log(f"已恢复自动检测: {self.downloads}", "info")
        self._on_preview()

    # ══════════════════════════════════════════════════════════
    # 页面 2: 浏览分类
    # ══════════════════════════════════════════════════════════
    def _build_browse_page(self, parent) -> ctk.CTkFrame:
        page = ctk.CTkFrame(parent, fg_color="transparent")
        page.grid_columnconfigure(1, weight=1)
        page.grid_rowconfigure(0, weight=1)

        # 左侧 — 分类列表
        left_card = ctk.CTkFrame(page, fg_color=C["card"], corner_radius=10,
                                  border_width=1, border_color=C["border"])
        left_card.grid(row=0, column=0, sticky="ns", padx=(20, 8), pady=20)
        left_card.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(left_card, text="分类目录", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=C["text"]).grid(row=0, column=0, sticky="w", padx=14, pady=(14, 6))

        self._cat_listbox = tk.Listbox(left_card, width=20, bg=C["card"], fg=C["text"],
                                        selectbackground=C["light_bg"], selectforeground=C["primary"],
                                        activestyle="none", borderwidth=0, highlightthickness=0,
                                        font=("Microsoft YaHei UI", 16))
        self._cat_listbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 14))
        self._cat_listbox.bind("<<ListboxSelect>>", self._on_cat_select)

        # 右侧 — 文件列表
        right_card = ctk.CTkFrame(page, fg_color=C["card"], corner_radius=10,
                                   border_width=1, border_color=C["border"])
        right_card.grid(row=0, column=1, sticky="nsew", padx=(8, 20), pady=20)
        right_card.grid_columnconfigure(0, weight=1)
        right_card.grid_rowconfigure(0, weight=1)

        b_cols = ("name", "size", "modified")
        self.b_tree = ttk.Treeview(right_card, columns=b_cols, show="headings", selectmode="extended")
        self.b_tree.heading("name", text="文件名");     self.b_tree.column("name", width=280, minwidth=120)
        self.b_tree.heading("size", text="大小");       self.b_tree.column("size", width=80, minwidth=60, anchor="e")
        self.b_tree.heading("modified", text="修改日期"); self.b_tree.column("modified", width=130, minwidth=90, anchor="center")

        b_scroll = ttk.Scrollbar(right_card, orient="vertical", command=self.b_tree.yview)
        self.b_tree.configure(yscrollcommand=b_scroll.set)
        self.b_tree.grid(row=0, column=0, sticky="nsew", padx=(16, 0), pady=16)
        b_scroll.grid(row=0, column=1, sticky="ns", padx=(0, 12), pady=16)

        self._setup_tree_menu(self.b_tree)
        # Patch menu entries for browse mode
        self._b_menu = tk.Menu(self.b_tree, tearoff=0, bg=C["card"], fg=C["text"], activebackground=C["light_bg"])
        self._b_menu.add_command(label="🗑 删除选中", command=lambda: self._on_delete_tree("browse"))
        self._b_menu.add_command(label="🔍 全选", command=lambda: self.b_tree.selection_set(self.b_tree.get_children()))
        self.b_tree.bind("<Button-3>", lambda e: self._tree_right_click(e, self.b_tree, self._b_menu))
        self.b_tree.bind("<Button-2>", lambda e: self._tree_right_click(e, self.b_tree, self._b_menu))

        # 按钮
        self.btn_del_brw = ctk.CTkButton(right_card, text="🗑 删除选中", width=100, height=32,
                                          font=ctk.CTkFont(size=16), fg_color="transparent",
                                          text_color=C["error"], hover_color="#FEE2E2",
                                          border_width=1, border_color=C["error"], corner_radius=6,
                                          command=lambda: self._on_delete_tree("browse"))
        self.btn_del_brw.grid(row=1, column=0, sticky="e", padx=(0, 16), pady=(0, 12))

        return page

    def _refresh_cat_list(self):
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
                size, mtime = "—", "—"
            icon = "📁" if item.is_dir() else "📄"
            self.b_tree.insert("", "end", iid=str(i), values=(f"{icon} {item.name}", size, mtime))

    @staticmethod
    def _fmt_size(size: int) -> str:
        if size >= 1_000_000_000: return f"{size/1_000_000_000:.1f} GB"
        if size >= 1_000_000: return f"{size/1_000_000:.1f} MB"
        if size >= 1_000: return f"{size/1_000:.1f} KB"
        return f"{size} B"

    # ══════════════════════════════════════════════════════════
    # 页面 3: 操作日志
    # ══════════════════════════════════════════════════════════
    def _build_log_page(self, parent) -> ctk.CTkFrame:
        page = ctk.CTkFrame(parent, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(0, weight=1)

        card = ctk.CTkFrame(page, fg_color=C["card"], corner_radius=10,
                             border_width=1, border_color=C["border"])
        card.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(0, weight=1)

        self.log_text = ctk.CTkTextbox(card, font=("Consolas", 16), fg_color=C["card"],
                                        text_color=C["text"], border_width=0, corner_radius=0,
                                        wrap="word")
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self.log_text.configure(state="disabled")

        return page

    # ══════════════════════════════════════════════════════════
    # 底部状态栏
    # ══════════════════════════════════════════════════════════
    def _build_statusbar(self):
        bar = ctk.CTkFrame(self.root, height=36, fg_color=C["card"],
                            corner_radius=0, border_width=1, border_color=C["border"])
        bar.grid(row=1, column=1, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(3, weight=1)

        self._status_text = tk.StringVar(value="就绪")
        ctk.CTkLabel(bar, textvariable=self._status_text, font=ctk.CTkFont(size=16),
                     text_color=C["text_s"]).grid(row=0, column=0, sticky="w", padx=(16, 0))

        ctk.CTkLabel(bar, text="上次整理:", font=ctk.CTkFont(size=16),
                     text_color=C["text_s"]).grid(row=0, column=2, padx=(0, 4))
        ctk.CTkLabel(bar, textvariable=self.last_organize_time, font=ctk.CTkFont(size=16),
                     text_color=C["text_s"]).grid(row=0, column=3, padx=(0, 16))

        self._progress = ctk.CTkProgressBar(bar, width=100, height=10, corner_radius=5,
                                             fg_color=C["border"], progress_color=C["primary"])

    # ══════════════════════════════════════════════════════════
    # 运行状态控制
    # ══════════════════════════════════════════════════════════
    def _set_running(self, running: bool):
        self._running = running
        state = "disabled" if running else "normal"
        for btn in (self.btn_preview, self.btn_organize, self.btn_undo, self.btn_del_pen, self.btn_del_brw):
            btn.configure(state=state)
        if running:
            self._progress.grid(row=0, column=6, padx=(0, 16))
            self._progress.start()
        else:
            self._progress.stop()
            self._progress.grid_forget()
            self._stop_requested = False

    def _log(self, msg: str, tag: str = "info"):
        self.log_text.configure(state="normal")
        ts = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] ", "info")
        self.log_text.insert("end", f"{msg}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

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
        self.root.bind("<Control-a>", lambda e: self._select_all())
        self.root.bind("<Control-A>", lambda e: self._select_all())
        self.root.bind("<Delete>", lambda e: self._on_delete_current())

    def _select_all(self):
        tree = self.p_tree if self._active_page == 0 else (self.b_tree if self._active_page == 1 else None)
        if tree: tree.selection_set(tree.get_children())

    def _on_delete_current(self):
        if self._active_page == 0:   self._on_delete_tree("pending")
        elif self._active_page == 1: self._on_delete_tree("browse")

    def _center(self):
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _handle_exception(self, exc_type, exc_val, exc_tb):
        import traceback
        msg = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
        self._log(f"异常:\n{msg}", "error")
        messagebox.showerror("程序错误", f"{exc_val}")

    def _on_close(self):
        if self._running:
            if not messagebox.askyesno("确认退出", "整理正在进行中，确定退出？"):
                return
        self.root.destroy()

    def _refresh_last_time(self):
        last = self.history_mgr.get_last_operation()
        self.last_organize_time.set(last["time"] if last else "—")

    # ══════════════════════════════════════════════════════════
    # 删除
    # ══════════════════════════════════════════════════════════
    def _on_delete_tree(self, source: str):
        if self._running: return

        if source == "pending":
            tree = self.p_tree
            items_list = self.preview_items
            is_dir_check = lambda p: p.is_dir()
            get_path = lambda i: i.path
            refresh = self._on_preview
        else:
            sel = self._cat_listbox.curselection()
            if not sel: return
            cat_name = self._cat_listbox.get(sel[0]).strip().split("  (")[0]
            cat_dir = self.downloads / cat_name
            if not cat_dir.exists(): return
            items_list = sorted(cat_dir.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            tree = self.b_tree
            is_dir_check = lambda p: p.is_dir()
            get_path = lambda p: p
            refresh = self._on_cat_select

        selection = tree.selection()
        if not selection: return

        to_delete = []
        for iid in selection:
            try:
                to_delete.append(get_path(items_list[int(iid)]))
            except (ValueError, IndexError):
                continue
        if not to_delete: return

        deleted, errors = 0, 0
        for path in to_delete:
            try:
                (shutil.rmtree if is_dir_check(path) else path.unlink)(path)
                deleted += 1
                self._log(f"已删除 {path.name}", "dedup")
            except (PermissionError, OSError) as e:
                errors += 1
                self._log(f"删除失败 {path.name}: {e}", "error")

        self._log(f"删除: {deleted} 项" + (f", {errors} 失败" if errors else ""), "info")

        if source == "browse":
            # 保留分类选中状态，直接刷新右侧文件列表
            self._refresh_cat_list()
            self._cat_listbox.selection_set(sel[0])
            self._cat_listbox.see(sel[0])
            self._on_cat_select()
        else:
            self._refresh_cat_list()
            refresh()

    # ══════════════════════════════════════════════════════════
    # 预览
    # ══════════════════════════════════════════════════════════
    def _on_preview(self):
        if not self.downloads or not self.downloads.exists():
            self._log("错误: 下载文件夹不存在", "error")
            messagebox.showwarning("路径错误", f"文件夹不存在:\n{self.downloads}\n\n请点击 [更改...] 选择正确路径。")
            return

        self._switch_page(0)
        self._status_text.set("正在扫描...")
        self.root.update_idletasks()

        try:
            self.preview_items = self._scan_and_classify()
        except Exception as e:
            self._log(f"扫描失败: {e}", "error")
            messagebox.showerror("错误", str(e))
            return

        for row in self.p_tree.get_children():
            self.p_tree.delete(row)
        for i, item in enumerate(self.preview_items):
            op = {"move": f"→ {item.cat_name}/", "dedup": "去重", "rename": f"→ {item.cat_name}/(重命名)", "skip": "跳过"}[item.op_type]
            self.p_tree.insert("", "end", iid=str(i), values=(item.name, "文件夹" if item.is_folder else "文件", item.cat_name, op))

        # 统计
        for w in self._p_stats.winfo_children():
            w.destroy()
        counts = Counter(i.cat_name for i in self.preview_items if i.cat_key != "skipped")
        skipped = sum(1 for i in self.preview_items if i.cat_key == "skipped")
        for _, cat_info in self.categories_config.items():
            name, n = cat_info["name"], counts.get(cat_info["name"], 0)
            ctk.CTkLabel(self._p_stats, text=f"[{name}: {n}]", font=ctk.CTkFont(size=16),
                         text_color=C["text"]).pack(side="left", padx=(0, 12))
        if skipped:
            ctk.CTkLabel(self._p_stats, text=f"[忽略: {skipped}]", font=ctk.CTkFont(size=16),
                         text_color=C["text_s"]).pack(side="left", padx=(0, 12))
        ctk.CTkLabel(self._p_stats, text=f"共 {sum(counts.values())} 项", font=ctk.CTkFont(size=16),
                     text_color=C["text_s"]).pack(side="left")

        self._status_text.set("就绪")
        self._log(f"预览: {sum(counts.values())} 项待整理, {skipped} 忽略", "info")

    def _scan_and_classify(self) -> List[PreviewItem]:
        if not self.downloads or not self.downloads.exists():
            return []
        dirs = sorted([p for p in self.downloads.iterdir() if p.is_dir()], key=lambda p: p.name.lower())
        files = sorted([p for p in self.downloads.iterdir() if p.is_file()], key=lambda p: p.name.lower())
        result = []
        for item in dirs + files:
            if item.is_dir() and item.name in self.category_names:
                continue
            cat_key = classify(item, self.ext_map, self.folder_category, self.ignored_patterns)
            if cat_key is None:
                result.append(PreviewItem(item, item.name, item.is_dir(), "skipped", "忽略", "skip"))
            else:
                cat_name = get_category_name(cat_key, self.categories_config)
                dest_dir = self.downloads / cat_name
                op = "move"
                if dest_dir.exists() and (dest_dir / item.name).exists():
                    try:
                        from lib.file_ops import resolve_destination
                        _, op = resolve_destination(item, dest_dir)
                    except Exception:
                        pass
                result.append(PreviewItem(item, item.name, item.is_dir(), cat_key, cat_name, op))
        return result

    # ══════════════════════════════════════════════════════════
    # 整理
    # ══════════════════════════════════════════════════════════
    def _on_organize(self):
        if self._running: return
        if not self.preview_items:
            self._on_preview()
        if not self.preview_items:
            messagebox.showinfo("提示", "请先点击预览扫描文件。")
            return
        total = sum(1 for i in self.preview_items if i.cat_key != "skipped")
        if total == 0:
            messagebox.showinfo("提示", "没有需要整理的文件。")
            return
        if not messagebox.askyesno("确认", f"将对 {total} 项执行整理，是否继续？"):
            return

        self._set_running(True)
        self._status_text.set(f"整理中 (0/{total})...")
        self._log(f"开始整理: {total} 项", "info")
        threading.Thread(target=self._run_organize, args=(self.preview_items,), daemon=True).start()

    def _run_organize(self, items: List[PreviewItem]):
        report = Report(self.categories_config)
        record = OperationRecord()
        total = sum(1 for i in items if i.cat_key != "skipped")
        done = 0
        for item in items:
            if self._stop_requested:
                self.root.after(0, lambda: self._on_organize_stopped(done, total)); return
            if item.cat_key == "skipped":
                report.record_skip(item.name, ""); continue
            dest_dir = self.downloads / item.cat_name
            try:
                ensure_dir(dest_dir)
                result, op_type = (move_folder(item.path, dest_dir) if item.is_folder else safe_move(item.path, dest_dir))
                (report.record_dedup(item.cat_key) if op_type == "dedup" else report.record_move(item.cat_key, is_folder=item.is_folder))
                record.add_move(item.path, result, op_type)
                done += 1
                self.root.after(0, lambda d=done, n=item.name, c=item.cat_name, o=op_type: self._on_progress(d, total, n, c, o))
            except (PermissionError, OSError) as e:
                report.record_error(item.name, str(e))
                self.root.after(0, lambda m=f"错误 {item.name}: {e}": self._log(m, "error"))
        if record.count > 0:
            self.history_mgr.save_record(record)
        self.root.after(0, lambda: self._on_organize_done(report))

    def _on_progress(self, done, total, name, cat_name, op_type):
        self._status_text.set(f"整理中 ({done}/{total})...")
        lbl = {"move": "→", "dedup": "去重", "rename": "重命名→"}.get(op_type, op_type)
        self._log(f"{lbl} {name} → {cat_name}/", "dedup" if op_type == "dedup" else "move")

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
        if self._running: return
        last = self.history_mgr.get_last_operation()
        if not last or not last.get("moves"):
            messagebox.showinfo("提示", "没有可撤销的操作。"); return
        moves = last["moves"]
        if not messagebox.askyesno("确认撤销", f"撤销 {last.get('time','?')} 的整理？\n\n{len(moves)} 项将被恢复"):
            return
        self._set_running(True)
        self._status_text.set("撤销中...")
        self._log(f"撤销: {len(moves)} 项", "info")
        threading.Thread(target=self._run_undo, args=(last,), daemon=True).start()

    def _run_undo(self, last_op: dict):
        moves = last_op.get("moves", [])
        success, failed = 0, 0
        for entry in reversed(moves):
            if self._stop_requested: break
            op_type, src_str, dest_str = entry.get("type",""), entry.get("from",""), entry.get("to","")
            if not src_str or not dest_str or op_type == "dedup": continue
            src, dest = Path(src_str), Path(dest_str)
            try:
                if dest.exists():
                    ensure_dir(src.parent)
                    shutil.move(str(dest), str(src))
                    success += 1
                    self.root.after(0, lambda m=f"恢复 {dest.name}": self._log(m, "move"))
                else: failed += 1
            except (PermissionError, OSError) as e:
                failed += 1
                self.root.after(0, lambda m=f"撤销失败 {dest.name}: {e}": self._log(m, "error"))
        self.history_mgr.pop_last_operation()
        self._cleanup_empty()
        self.root.after(0, lambda: self._on_undo_done(success, failed))

    def _on_undo_done(self, success, failed):
        self._set_running(False)
        self._status_text.set("就绪")
        self._refresh_last_time()
        msg = f"撤销完成: {success} 项恢复" + (f", {failed} 失败" if failed else "")
        self._log(msg, "info")
        self._on_preview()
        self._refresh_cat_list()

    def _cleanup_empty(self):
        if not self.downloads or not self.downloads.exists(): return
        for item in self.downloads.iterdir():
            if item.is_dir() and item.name in self.category_names:
                try:
                    if not any(item.iterdir()): item.rmdir()
                except OSError: pass


# ── 入口 ────────────────────────────────────────────────────
def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass
    app = OrganizeGUI()
    app.root.mainloop()


if __name__ == "__main__":
    main()
