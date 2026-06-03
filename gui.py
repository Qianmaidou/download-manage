#!/usr/bin/env python3
"""下载文件夹整理工具 — GUI 可视化界面。

基于 Tkinter 的可视化窗口，提供预览、整理、撤销、定时自动整理等功能。
与 CLI (organize.py) 共享 lib/ 模块。

用法:
    python gui.py
"""

import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# 确保项目根目录在 sys.path 中
if getattr(sys, "frozen", False):
    app_dir = Path(sys.executable).parent
else:
    app_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(app_dir))

import tkinter as tk
from tkinter import ttk, messagebox

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


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class PreviewItem:
    """预览条目，描述一个文件/文件夹的分类结果。"""
    path: Path
    name: str
    is_folder: bool
    cat_key: str
    cat_name: str
    op_type: str  # "move" | "dedup" | "rename" | "skip"


# ---------------------------------------------------------------------------
# 主 GUI 类
# ---------------------------------------------------------------------------

class OrganizeGUI:
    """下载文件夹整理工具 GUI 主窗口。"""

    # 状态颜色
    COLOR_READY = "#27ae60"      # 绿色 — 就绪
    COLOR_RUNNING = "#f39c12"    # 黄色 — 运行中
    COLOR_ERROR = "#e74c3c"      # 红色 — 错误

    # 日志颜色标签
    TAG_MOVE = "move"
    TAG_DEDUP = "dedup"
    TAG_SKIP = "skip"
    TAG_ERROR = "error"
    TAG_INFO = "info"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("下载文件夹整理工具")

        # 窗口大小
        self.root.geometry("920x660")
        self.root.minsize(720, 500)

        # 居中显示
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"+{x}+{y}")

        # 配置网格权重（使 Treeview / Text 区域可拉伸）
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)  # notebook 行可拉伸

        # 成员变量
        self.config: Dict[str, Any] = {}
        self.ext_map: Dict[str, str] = {}
        self.downloads: Optional[Path] = None
        self.folder_category: Optional[str] = None
        self.ignored_patterns: List[str] = []
        self.categories_config: Dict[str, Any] = {}
        self.category_names: set = set()
        self.history_mgr: Optional[HistoryManager] = None

        # 预览数据缓存
        self.preview_items: List[PreviewItem] = []

        # 运行状态
        self._running = False
        self._stop_requested = False

        # 定时器
        self._timer_id: Optional[str] = None
        self._next_fire_at: float = 0.0
        self._countdown_id: Optional[str] = None
        self.auto_enabled = tk.BooleanVar(value=False)
        self.auto_interval = tk.StringVar(value="30 分钟")

        # 上次整理时间
        self.last_organize_time = tk.StringVar(value="—")

        # 加载配置
        self._load_config()

        # 构建界面
        self._build_ui()

        # 读取上次整理时间
        self._refresh_last_time()

        # 窗口关闭协议
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 快捷键
        self._bind_shortcuts()

    # ------------------------------------------------------------------
    # 配置加载
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        """加载配置文件，初始化成员变量。"""
        try:
            self.config = load_config()
        except Exception as e:
            messagebox.showerror("配置错误", f"无法加载配置文件:\n{e}")
            sys.exit(1)

        self.ext_map = build_extension_map(self.config)
        self.downloads = get_downloads_path(self.config)
        self.folder_category = get_folder_category(self.config)
        self.ignored_patterns = get_ignored_patterns(self.config)
        self.categories_config = self.config["categories"]
        self.category_names = {cat["name"] for cat in self.categories_config.values()}

        # 历史记录管理器
        history_path = app_dir / self.config.get("history_file", "history.json")
        self.history_mgr = HistoryManager(history_path)

    # ------------------------------------------------------------------
    # 界面构建
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """构建所有界面组件。"""
        # --- 信息栏 ---
        self._build_info_bar()

        # --- 按钮栏 ---
        self._build_button_bar()

        # --- 选项卡 (Notebook) ---
        self._build_notebook()

        # --- 自动整理设置 ---
        self._build_auto_panel()

        # --- 状态栏 ---
        self._build_status_bar()

    def _build_info_bar(self) -> None:
        """顶部信息栏：下载路径、状态、上次整理时间。"""
        frame = ttk.Frame(self.root, padding=(10, 8))
        frame.grid(row=0, column=0, sticky="ew")
        frame.columnconfigure(1, weight=1)

        # 下载文件夹路径
        ttk.Label(frame, text="下载文件夹:").grid(row=0, column=0, sticky="w")
        download_text = str(self.downloads) if self.downloads else "未设置"
        ttk.Label(frame, text=download_text, foreground="gray").grid(
            row=0, column=1, sticky="w", padx=(5, 0)
        )

        # 状态指示器
        self._status_dot = tk.Canvas(frame, width=12, height=12, highlightthickness=0)
        self._status_dot.grid(row=0, column=2, padx=(20, 4))
        self._draw_status_dot(self.COLOR_READY)

        self._status_label = ttk.Label(frame, text="就绪")
        self._status_label.grid(row=0, column=3, padx=(0, 20))

        # 上次整理时间
        ttk.Label(frame, text="上次整理:").grid(row=0, column=4)
        ttk.Label(frame, textvariable=self.last_organize_time, foreground="gray").grid(
            row=0, column=5, padx=(5, 0)
        )

    def _build_button_bar(self) -> None:
        """操作按钮栏：预览、整理、删除选中、撤销、停止。"""
        frame = ttk.Frame(self.root, padding=(10, 4))
        frame.grid(row=1, column=0, sticky="ew")

        self.btn_preview = ttk.Button(frame, text="🔍 预览", command=self._on_preview)
        self.btn_preview.pack(side="left", padx=(0, 6))

        self.btn_organize = ttk.Button(frame, text="▶ 立即整理", command=self._on_organize)
        self.btn_organize.pack(side="left", padx=(0, 6))

        self.btn_undo = ttk.Button(frame, text="↩ 撤销", command=self._on_undo)
        self.btn_undo.pack(side="left", padx=(0, 6))

        self.btn_delete = ttk.Button(frame, text="🗑 删除选中", command=self._on_delete_selected)
        self.btn_delete.pack(side="left", padx=(0, 6))

        self.btn_stop = ttk.Button(frame, text="⏹ 停止", command=self._on_stop, state="disabled")
        self.btn_stop.pack(side="left")

    def _build_notebook(self) -> None:
        """选项卡：文件预览 + 操作日志。"""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 4))

        # --- Tab 1: 文件预览 ---
        tab_preview = ttk.Frame(self.notebook)
        self.notebook.add(tab_preview, text=" 文件预览 ")
        tab_preview.columnconfigure(0, weight=1)
        tab_preview.rowconfigure(0, weight=1)

        # Treeview
        columns = ("name", "type", "category", "action")
        self.tree = ttk.Treeview(
            tab_preview, columns=columns, show="headings",
            selectmode="extended",
        )
        self.tree.heading("name", text="文件名")
        self.tree.heading("type", text="类型")
        self.tree.heading("category", text="目标分类")
        self.tree.heading("action", text="操作")

        self.tree.column("name", width=320, minwidth=150)
        self.tree.column("type", width=60, minwidth=50, anchor="center")
        self.tree.column("category", width=100, minwidth=70, anchor="center")
        self.tree.column("action", width=120, minwidth=80, anchor="center")

        # 右键菜单
        self._tree_menu = tk.Menu(self.tree, tearoff=0)
        self._tree_menu.add_command(label="🗑 删除选中", command=self._on_delete_selected)
        self._tree_menu.add_command(label="🔍 全选", command=self._on_select_all)
        self.tree.bind("<Button-3>", self._on_tree_right_click)
        self.tree.bind("<Button-2>", self._on_tree_right_click)  # 触控板右键

        # 滚动条
        tree_scroll = ttk.Scrollbar(tab_preview, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll.grid(row=0, column=1, sticky="ns")

        # 统计摘要栏
        self._stats_frame = ttk.Frame(tab_preview, padding=(0, 6))
        self._stats_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        self._stats_labels: Dict[str, ttk.Label] = {}

        # --- Tab 2: 操作日志 ---
        tab_log = ttk.Frame(self.notebook)
        self.notebook.add(tab_log, text=" 操作日志 ")
        tab_log.columnconfigure(0, weight=1)
        tab_log.rowconfigure(0, weight=1)

        self.log_text = tk.Text(
            tab_log, state="disabled", wrap="word",
            font=("Consolas", 9),
        )
        log_scroll = ttk.Scrollbar(tab_log, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)

        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll.grid(row=0, column=1, sticky="ns")

        # 日志颜色标签
        self.log_text.tag_configure(self.TAG_MOVE, foreground="#27ae60")
        self.log_text.tag_configure(self.TAG_DEDUP, foreground="#2980b9")
        self.log_text.tag_configure(self.TAG_SKIP, foreground="#95a5a6")
        self.log_text.tag_configure(self.TAG_ERROR, foreground="#e74c3c")
        self.log_text.tag_configure(self.TAG_INFO, foreground="#2c3e50", font=("Consolas", 9, "bold"))

    def _build_auto_panel(self) -> None:
        """自动整理设置面板。"""
        frame = ttk.Frame(self.root, padding=(10, 4))
        frame.grid(row=3, column=0, sticky="ew")

        # 启用复选框
        ttk.Checkbutton(
            frame, text="启用自动整理",
            variable=self.auto_enabled,
            command=self._on_auto_toggle,
        ).pack(side="left", padx=(0, 16))

        # 间隔选择
        ttk.Label(frame, text="间隔:").pack(side="left")
        intervals = ["15 分钟", "30 分钟", "1 小时", "2 小时", "6 小时", "12 小时", "24 小时"]
        combo = ttk.Combobox(
            frame, textvariable=self.auto_interval,
            values=intervals, state="readonly", width=10,
        )
        combo.pack(side="left", padx=(4, 16))

        # 倒计时
        self._countdown_label = ttk.Label(frame, text="下次: —")
        self._countdown_label.pack(side="left")

    def _build_status_bar(self) -> None:
        """底部状态栏。"""
        frame = ttk.Frame(self.root, padding=(10, 4))
        frame.grid(row=4, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)

        self._status_text = tk.StringVar(value="就绪")
        ttk.Label(frame, textvariable=self._status_text).grid(row=0, column=0, sticky="w")

        # 进度条（初始隐藏）
        self._progress = ttk.Progressbar(
            frame, mode="indeterminate", length=120,
        )

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _draw_status_dot(self, color: str) -> None:
        """绘制状态圆点。"""
        self._status_dot.delete("all")
        self._status_dot.create_oval(2, 2, 10, 10, fill=color, outline="")

    def _set_status(self, text: str, color: str = COLOR_READY) -> None:
        """更新状态指示器和文字。"""
        self._draw_status_dot(color)
        self._status_label.config(text=text)

    def _set_running(self, running: bool) -> None:
        """设置运行状态，控制按钮启用/禁用。"""
        self._running = running
        if running:
            self.btn_preview.config(state="disabled")
            self.btn_organize.config(state="disabled")
            self.btn_undo.config(state="disabled")
            self.btn_delete.config(state="disabled")
            self.btn_stop.config(state="normal")
            self._progress.grid(row=0, column=1, sticky="e", padx=(10, 0))
            self._progress.start(10)
        else:
            self.btn_preview.config(state="normal")
            self.btn_organize.config(state="normal")
            self.btn_undo.config(state="normal")
            self.btn_delete.config(state="normal")
            self.btn_stop.config(state="disabled")
            self._progress.stop()
            self._progress.grid_forget()
            self._stop_requested = False

    def _refresh_last_time(self) -> None:
        """从历史记录读取上次整理时间。"""
        if self.history_mgr:
            last = self.history_mgr.get_last_operation()
            if last:
                self.last_organize_time.set(last.get("time", "—"))
            else:
                self.last_organize_time.set("—")

    def _log(self, message: str, tag: str = TAG_INFO) -> None:
        """追加日志到操作日志 Tab。"""
        self.log_text.config(state="normal")
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] ", (tag,))
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _bind_shortcuts(self) -> None:
        """绑定快捷键。"""
        self.root.bind("<Control-p>", lambda e: self._on_preview())
        self.root.bind("<Control-P>", lambda e: self._on_preview())
        self.root.bind("<Control-o>", lambda e: self._on_organize())
        self.root.bind("<Control-O>", lambda e: self._on_organize())
        self.root.bind("<Control-z>", lambda e: self._on_undo())
        self.root.bind("<Control-Z>", lambda e: self._on_undo())
        self.root.bind("<Control-a>", lambda e: self._on_select_all())
        self.root.bind("<Control-A>", lambda e: self._on_select_all())
        self.root.bind("<Delete>", lambda e: self._on_delete_selected())

    def _on_close(self) -> None:
        """窗口关闭处理。"""
        if self._running:
            if not messagebox.askyesno("确认退出", "整理正在进行中，确定要退出吗？"):
                return
            self._stop_requested = True
        # 取消定时器
        if self._timer_id:
            self.root.after_cancel(self._timer_id)
        if self._countdown_id:
            self.root.after_cancel(self._countdown_id)
        self.root.destroy()

    # ------------------------------------------------------------------
    # 扫描和分类（核心复用逻辑）
    # ------------------------------------------------------------------

    def _scan_and_classify(self) -> List[PreviewItem]:
        """扫描下载文件夹并分类所有项目。

        Returns:
            PreviewItem 列表。
        """
        if not self.downloads or not self.downloads.exists():
            return []

        all_items = sorted(
            [p for p in self.downloads.iterdir() if p.is_dir()],
            key=lambda p: p.name.lower(),
        ) + sorted(
            [p for p in self.downloads.iterdir() if p.is_file()],
            key=lambda p: p.name.lower(),
        )

        items: List[PreviewItem] = []
        for item in all_items:
            # 跳过分类目录自身
            if item.is_dir() and item.name in self.category_names:
                continue

            cat_key = classify(
                item, self.ext_map, self.folder_category, self.ignored_patterns
            )

            if cat_key is None:
                items.append(PreviewItem(
                    path=item, name=item.name,
                    is_folder=item.is_dir(),
                    cat_key="skipped", cat_name="忽略",
                    op_type="skip",
                ))
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
                items.append(PreviewItem(
                    path=item, name=item.name,
                    is_folder=item.is_dir(),
                    cat_key=cat_key, cat_name=cat_name,
                    op_type=op_type,
                ))

        return items

    def _populate_treeview(self, items: List[PreviewItem]) -> None:
        """填充 Treeview 表格。

        Args:
            items: PreviewItem 列表。
        """
        # 清空
        for row in self.tree.get_children():
            self.tree.delete(row)

        # 填充（用索引作为 iid，方便删除时查找 PreviewItem）
        for i, item in enumerate(items):
            op_text = {
                "move": f"→ {item.cat_name}/",
                "dedup": "去重删除",
                "rename": f"→ {item.cat_name}/ (重命名)",
                "skip": "跳过",
            }.get(item.op_type, item.op_type)

            type_text = "文件夹" if item.is_folder else "文件"

            self.tree.insert("", "end", iid=str(i), values=(
                item.name, type_text, item.cat_name, op_text,
            ))

    def _update_stats(self, items: List[PreviewItem]) -> None:
        """更新统计摘要标签。

        Args:
            items: PreviewItem 列表。
        """
        # 清除旧标签
        for label in self._stats_frame.winfo_children():
            label.destroy()
        self._stats_labels.clear()

        from collections import Counter
        cat_counts = Counter()
        skipped = 0
        for item in items:
            if item.cat_key == "skipped":
                skipped += 1
            else:
                cat_counts[item.cat_name] += 1

        # 按分类顺序展示
        for cat_key, cat_info in self.categories_config.items():
            name = cat_info.get("name", cat_key)
            count = cat_counts.get(name, 0)
            lbl = ttk.Label(
                self._stats_frame,
                text=f"[{name}: {count}]",
                foreground="#2c3e50",
            )
            lbl.pack(side="left", padx=(0, 10))
            self._stats_labels[name] = lbl

        if skipped > 0:
            ttk.Label(
                self._stats_frame, text=f"[忽略: {skipped}]", foreground="#95a5a6",
            ).pack(side="left", padx=(0, 10))

        total = len([i for i in items if i.cat_key != "skipped"])
        ttk.Label(
            self._stats_frame, text=f"共 {total} 项", foreground="#7f8c8d",
        ).pack(side="left")

    # ------------------------------------------------------------------
    # 预览
    # ------------------------------------------------------------------

    def _on_preview(self) -> None:
        """预览按钮回调：扫描并展示分类结果。"""
        if not self.downloads or not self.downloads.exists():
            messagebox.showwarning("错误", "下载文件夹不存在。")
            return

        self._status_text.set("正在扫描...")
        self._set_status("扫描中", self.COLOR_RUNNING)
        self.root.update_idletasks()

        try:
            self.preview_items = self._scan_and_classify()
        except Exception as e:
            self._log(f"扫描失败: {e}", self.TAG_ERROR)
            self._set_status("错误", self.COLOR_ERROR)
            self._status_text.set("扫描出错")
            return

        self._populate_treeview(self.preview_items)
        self._update_stats(self.preview_items)
        self.notebook.select(0)  # 切换到文件预览 Tab

        total = sum(1 for i in self.preview_items if i.cat_key != "skipped")
        skipped = sum(1 for i in self.preview_items if i.cat_key == "skipped")
        self._log(f"预览完成: {total} 项待整理, {skipped} 项忽略", self.TAG_INFO)
        self._set_status("就绪", self.COLOR_READY)
        self._status_text.set("就绪")

    # ------------------------------------------------------------------
    # 右键菜单 + 删除选中
    # ------------------------------------------------------------------

    def _on_tree_right_click(self, event) -> None:
        """Treeview 右键菜单。"""
        # 先选中右键所在的行
        row = self.tree.identify_row(event.y)
        if row:
            if row not in self.tree.selection():
                self.tree.selection_set(row)
        # 显示菜单
        try:
            self._tree_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._tree_menu.grab_release()

    def _on_select_all(self) -> None:
        """全选 Treeview 中所有行。"""
        all_rows = self.tree.get_children()
        self.tree.selection_set(all_rows)

    def _on_delete_selected(self) -> None:
        """删除选中的文件/文件夹。"""
        if self._running:
            return

        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("提示", "请先在文件预览中选中要删除的文件。\n\n"
                                "提示：可以按住 Ctrl 或 Shift 多选，"
                                "也可以右键点击文件。")
            return

        # 收集要删除的 PreviewItem
        items_to_delete: List[PreviewItem] = []
        names: List[str] = []
        for iid in selection:
            try:
                idx = int(iid)
                item = self.preview_items[idx]
                items_to_delete.append(item)
                names.append(item.name)
            except (ValueError, IndexError):
                continue

        if not items_to_delete:
            return

        # 确认对话框
        count = len(items_to_delete)
        folders = sum(1 for i in items_to_delete if i.is_folder)
        file_count = count - folders
        detail = "\n\n".join(names[:10])
        if count > 10:
            detail += f"\n... 等共 {count} 项"

        msg = f"确认删除以下 {count} 项？\n\n{detail}\n\n"
        if folders > 0:
            msg += f"⚠ 包含 {folders} 个文件夹，将连同内容一起删除！\n\n"
        msg += "此操作不可撤销，确认删除？"

        if not messagebox.askyesno("确认删除", msg, icon="warning"):
            return

        # 执行删除
        deleted = 0
        errors = 0
        for item in items_to_delete:
            try:
                if item.is_folder:
                    import shutil
                    shutil.rmtree(item.path)
                else:
                    item.path.unlink()
                deleted += 1
                self._log(f"已删除 {item.name}", self.TAG_DEDUP)
            except (PermissionError, OSError) as e:
                errors += 1
                self._log(f"删除失败 {item.name}: {e}", self.TAG_ERROR)

        # 刷新预览
        self._log(f"删除完成: {deleted} 项" + (f", {errors} 项失败" if errors else ""), self.TAG_INFO)
        self._on_preview()

    # ------------------------------------------------------------------
    # 整理
    # ------------------------------------------------------------------

    def _on_organize(self) -> None:
        """立即整理按钮回调。"""
        if self._running:
            return

        # 如果没有预览数据，先扫描
        if not self.preview_items:
            self._on_preview()
            if not self.preview_items:
                return

        total = sum(1 for i in self.preview_items if i.cat_key != "skipped")
        if total == 0:
            messagebox.showinfo("整理", "没有需要整理的文件。")
            return

        if not messagebox.askyesno("确认整理", f"将对 {total} 项执行整理操作，是否继续？"):
            return

        self._set_running(True)
        self._set_status("整理中", self.COLOR_RUNNING)
        self._status_text.set(f"整理中 (0/{total})...")
        self._log(f"开始整理: {total} 项", self.TAG_INFO)

        thread = threading.Thread(
            target=self._run_organize_thread,
            args=(self.preview_items,),
            daemon=True,
        )
        thread.start()

    def _run_organize_thread(self, items: List[PreviewItem]) -> None:
        """后台线程：执行实际文件移动。"""
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

                if item.is_folder:
                    result, op_type = move_folder(item.path, dest_dir)
                else:
                    result, op_type = safe_move(item.path, dest_dir)

                if op_type == "dedup":
                    report.record_dedup(item.cat_key)
                else:
                    report.record_move(item.cat_key, is_folder=item.is_folder)

                record.add_move(item.path, result, op_type)
                done += 1

                # 进度回主线程
                self.root.after(
                    0, self._on_progress_update, done, total,
                    item.name, item.cat_name, op_type,
                )

            except (PermissionError, OSError) as e:
                report.record_error(item.name, str(e))
                self.root.after(0, self._log, f"错误: {item.name} — {e}", self.TAG_ERROR)

        # 保存历史
        if record.count > 0:
            self.history_mgr.save_record(record)

        # 完成回调
        self.root.after(0, self._on_organize_done, report)

    def _on_progress_update(
        self, done: int, total: int, name: str, cat_name: str, op_type: str
    ) -> None:
        """整理进度更新（主线程）。"""
        self._status_text.set(f"整理中 ({done}/{total})...")
        op_label = {"move": "→", "dedup": "去重", "rename": "重命名→"}.get(op_type, op_type)
        self._log(f"{op_label} {name} → {cat_name}/",
                  self.TAG_DEDUP if op_type == "dedup" else self.TAG_MOVE)

    def _on_organize_done(self, report: Report) -> None:
        """整理完成回调（主线程）。"""
        self._set_running(False)
        self._set_status("就绪", self.COLOR_READY)
        self._status_text.set("就绪")
        self._refresh_last_time()

        self._log(f"整理完成: 移动 {report.total_moved} 项"
                  + (f", 去重 {report.total_dedup} 项" if report.total_dedup else ""),
                  self.TAG_INFO)

        # 刷新预览
        self._on_preview()

        # 定时器：调度下一次
        if self.auto_enabled.get():
            self._schedule_next()

    def _on_organize_stopped(self, done: int, total: int) -> None:
        """整理被停止回调（主线程）。"""
        self._set_running(False)
        self._set_status("就绪", self.COLOR_READY)
        self._status_text.set("已停止")
        self._log(f"整理已停止 (已完成 {done}/{total})", self.TAG_INFO)
        self._on_preview()

    # ------------------------------------------------------------------
    # 撤销
    # ------------------------------------------------------------------

    def _on_undo(self) -> None:
        """撤销按钮回调。"""
        if self._running:
            return

        last = self.history_mgr.get_last_operation()
        if last is None:
            messagebox.showinfo("撤销", "没有可撤销的操作。")
            return

        moves = last.get("moves", [])
        deleted = last.get("deleted", [])
        time_str = last.get("time", "未知时间")

        if not moves:
            messagebox.showinfo("撤销", "没有可撤销的操作。")
            return

        msg = f"将撤销 {time_str} 的整理操作\n\n"
        msg += f"涉及 {len(moves)} 项移动\n"
        if deleted:
            msg += f"注意: {len(deleted)} 项去重文件无法恢复\n"
        msg += "\n确认撤销？"

        if not messagebox.askyesno("确认撤销", msg):
            return

        self._set_running(True)
        self._set_status("撤销中", self.COLOR_RUNNING)
        self._status_text.set("正在撤销...")
        self._log(f"开始撤销: {len(moves)} 项", self.TAG_INFO)

        thread = threading.Thread(
            target=self._run_undo_thread,
            args=(last,),
            daemon=True,
        )
        thread.start()

    def _run_undo_thread(self, last_op: dict) -> None:
        """后台线程：执行撤销。"""
        import shutil
        moves = last_op.get("moves", [])
        deleted = last_op.get("deleted", [])
        success = 0
        failed = 0

        for entry in reversed(moves):
            if self._stop_requested:
                break

            op_type = entry.get("type", "")
            src_str = entry.get("from", "")
            dest_str = entry.get("to", "")

            if not src_str or not dest_str:
                continue

            if op_type == "dedup":
                continue

            src = Path(src_str)
            dest = Path(dest_str)

            try:
                if dest.exists():
                    ensure_dir(src.parent)
                    shutil.move(str(dest), str(src))
                    success += 1
                    self.root.after(0, self._log, f"恢复 {dest.name} → {src.parent.name}/", self.TAG_MOVE)
                else:
                    failed += 1
                    self.root.after(0, self._log, f"跳过 {dest.name} — 文件不存在", self.TAG_SKIP)
            except (PermissionError, OSError) as e:
                failed += 1
                self.root.after(0, self._log, f"错误 {dest.name}: {e}", self.TAG_ERROR)

        # 移除历史记录
        self.history_mgr.pop_last_operation()

        # 清理空目录
        self._cleanup_empty_dirs()

        self.root.after(0, self._on_undo_done, success, failed, len(deleted))

    def _on_undo_done(self, success: int, failed: int, lost: int) -> None:
        """撤销完成回调（主线程）。"""
        self._set_running(False)
        self._set_status("就绪", self.COLOR_READY)
        self._status_text.set("就绪")
        self._refresh_last_time()

        msg = f"撤销完成: {success} 项已恢复"
        if failed:
            msg += f", {failed} 项失败"
        if lost:
            msg += f", {lost} 项无法恢复"
        self._log(msg, self.TAG_INFO)

        messagebox.showinfo("撤销完成", msg)
        self._on_preview()

    def _cleanup_empty_dirs(self) -> None:
        """清理空的分类目录。"""
        if not self.downloads or not self.downloads.exists():
            return
        for item in self.downloads.iterdir():
            if item.is_dir() and item.name in self.category_names:
                try:
                    if not any(item.iterdir()):
                        item.rmdir()
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # 停止
    # ------------------------------------------------------------------

    def _on_stop(self) -> None:
        """停止按钮回调：取消当前操作和定时器。"""
        self._stop_requested = True
        # 取消定时器
        if self._timer_id:
            self.root.after_cancel(self._timer_id)
            self._timer_id = None
        if self._countdown_id:
            self.root.after_cancel(self._countdown_id)
            self._countdown_id = None
        self.auto_enabled.set(False)
        self._countdown_label.config(text="下次: —")
        self._log("已停止", self.TAG_INFO)

    # ------------------------------------------------------------------
    # 自动整理定时器
    # ------------------------------------------------------------------

    def _on_auto_toggle(self) -> None:
        """自动整理开关回调。"""
        if self.auto_enabled.get():
            self._log("自动整理已启用", self.TAG_INFO)
            self._schedule_next()
        else:
            self._log("自动整理已禁用", self.TAG_INFO)
            if self._timer_id:
                self.root.after_cancel(self._timer_id)
                self._timer_id = None
            if self._countdown_id:
                self.root.after_cancel(self._countdown_id)
                self._countdown_id = None
            self._countdown_label.config(text="下次: —")

    def _get_interval_seconds(self) -> int:
        """解析自动整理间隔为秒数。"""
        value = self.auto_interval.get()
        mapping = {
            "15 分钟": 15 * 60,
            "30 分钟": 30 * 60,
            "1 小时": 60 * 60,
            "2 小时": 2 * 60 * 60,
            "6 小时": 6 * 60 * 60,
            "12 小时": 12 * 60 * 60,
            "24 小时": 24 * 60 * 60,
        }
        return mapping.get(value, 30 * 60)

    def _schedule_next(self) -> None:
        """调度下一次自动整理。"""
        if not self.auto_enabled.get():
            return
        interval_s = self._get_interval_seconds()
        self._next_fire_at = time.time() + interval_s
        self._timer_id = self.root.after(interval_s * 1000, self._auto_fire)
        self._update_countdown()

    def _auto_fire(self) -> None:
        """定时器触发：自动执行整理。"""
        if not self.auto_enabled.get():
            return
        self._log("自动整理触发", self.TAG_INFO)
        # 先预览再整理
        self.preview_items = self._scan_and_classify()
        if not self.preview_items:
            self._schedule_next()
            return
        total = sum(1 for i in self.preview_items if i.cat_key != "skipped")
        if total == 0:
            self._log("自动整理: 无需整理", self.TAG_INFO)
            self._schedule_next()
            return

        self._set_running(True)
        self._set_status("自动整理中", self.COLOR_RUNNING)
        self._status_text.set(f"自动整理中 (0/{total})...")
        self._log(f"自动整理开始: {total} 项", self.TAG_INFO)

        thread = threading.Thread(
            target=self._run_organize_thread,
            args=(self.preview_items,),
            daemon=True,
        )
        thread.start()

    def _update_countdown(self) -> None:
        """每秒更新倒计时显示。"""
        if not self.auto_enabled.get():
            return
        remaining = int(self._next_fire_at - time.time())
        if remaining <= 0:
            self._countdown_label.config(text="执行中...")
            return
        mins, secs = divmod(remaining, 60)
        if mins >= 60:
            hours, mins = divmod(mins, 60)
            self._countdown_label.config(text=f"下次: {hours}h{mins:02d}m")
        else:
            self._countdown_label.config(text=f"下次: {mins:02d}:{secs:02d}")
        self._countdown_id = self.root.after(1000, self._update_countdown)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main() -> None:
    """GUI 主入口。"""
    # Windows 编码修复
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    root = tk.Tk()
    app = OrganizeGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
