#!/usr/bin/env python3
"""Tkinter UI for editing Langrisser FX Korean dialogue."""

from __future__ import annotations

from dataclasses import replace
from copy import deepcopy
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from dialogue_core import (
    BASE_COOKED_NAME,
    BASE_DIR,
    MAX_DIALOGUE_SAFE_VISIBLE_WIDTH_PX,
    DialogueError,
    DialogueRecord,
    load_records,
    suggested_output_folder,
    validate_record,
    verify_base_folder,
)
from project_core import (
    build_disc as build_translation_disc,
    load_project as load_translation_project,
    save_project as save_translation_project,
    validate_project as validate_translation_project,
)
from condition_core import (
    ConditionRecord,
    MAX_WIDTH_PX as CONDITION_MAX_WIDTH_PX,
    condition_display_line_widths,
    load_condition_records,
    validate_condition_text,
)
from narration_core import (
    NARRATION_MAX_LINES,
    NARRATION_SAFE_WIDTH_PX,
    NarrationRecord,
    load_narration_records,
    narration_line_widths,
    validate_narration_text,
)
from epilogue_core import (
    EpilogueRecord,
    load_epilogue_records,
    validate_epilogue_text,
)
from subtitle_core import (
    SubtitleCue,
    SubtitleError,
    apply_subtitle_edits,
    delete_subtitle_edit,
    insert_subtitle_edit,
    move_subtitle_edit,
    glyph_advance,
    load_subtitle_cues,
    next_custom_id,
    subtitle_edit_row,
    subtitle_display_rows,
    subtitle_overlap_ids,
    validate_subtitle_cues,
)
from movie_media import movie_titles
from movie_preview import MoviePreview
from subtitle_history import SubtitleHistory
from name_token_help import TextNameTooltip


HERE = Path(__file__).resolve().parent
DEFAULT_PROJECT = HERE / "사용자_대사수정.json"


def narration_filter_values(
    records: tuple[NarrationRecord, ...] | list[NarrationRecord],
) -> tuple[str, ...]:
    """Return every presentation label once, in the catalogue order."""
    return ("전체", *dict.fromkeys(row.label for row in records))


class DialogueEditor(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("랑그릿사 FX 한글 번역 편집기")
        self.geometry("1280x820")
        self.minsize(1050, 680)
        self.option_add("*Font", ("맑은 고딕", 10))
        self.records: list[DialogueRecord] = []
        self.by_id: dict[str, DialogueRecord] = {}
        self.texts: dict[str, str] = {}
        self.current_id: str | None = None
        self.visible_ids: list[str] = []
        self.subtitle_base: tuple[SubtitleCue, ...] = ()
        self.subtitle_base_by_id: dict[str, SubtitleCue] = {}
        self.subtitle_edits: dict[str, dict] = {}
        self.current_subtitle_id: str | None = None
        self.subtitle_history = SubtitleHistory()
        self._subtitle_checkpoint = None
        self._subtitle_loading = False
        self.narration_base: tuple[NarrationRecord, ...] = ()
        self.narration_by_id: dict[str, NarrationRecord] = {}
        self.narration_edits: dict[str, str] = {}
        self.current_narration_id: str | None = None
        self.condition_base: tuple[ConditionRecord, ...] = ()
        self.condition_by_id: dict[str, ConditionRecord] = {}
        self.condition_edits: dict[str, str] = {}
        self.current_condition_id: str | None = None
        self.epilogue_base: tuple[EpilogueRecord, ...] = ()
        self.epilogue_by_id: dict[str, EpilogueRecord] = {}
        self.epilogue_edits: dict[str, str] = {}
        self.current_aftermath_id: str | None = None
        self.project_path = DEFAULT_PROJECT
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.busy = False
        self._cached_base_folder: str | None = None
        self._cached_base_image: bytes | None = None
        self._build_ui()
        self.after(50, self._poll_events)
        self.after(80, self._initial_load)

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self, padding=8)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="편집 파일 열기", command=self.open_project).pack(side="left")
        ttk.Button(toolbar, text="저장", command=self.save_project).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="다른 이름 저장", command=self.save_project_as).pack(side="left", padx=(6, 0))
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(toolbar, text="전체 검사", command=self.run_validation).pack(side="left")
        ttk.Button(toolbar, text="새 CUE 만들기", command=self.run_build).pack(side="left", padx=(6, 0))
        ttk.Label(toolbar, text="기준 이미지:").pack(side="left", padx=(18, 4))
        self.base_var = tk.StringVar(value=str(BASE_DIR))
        ttk.Entry(toolbar, textvariable=self.base_var).pack(side="left", fill="x", expand=True)
        ttk.Button(toolbar, text="폴더", command=self.choose_base).pack(side="left", padx=(5, 0))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8)
        dialogue_tab = ttk.Frame(self.notebook)
        subtitle_tab = ttk.Frame(self.notebook)
        narration_tab = ttk.Frame(self.notebook)
        condition_tab = ttk.Frame(self.notebook)
        epilogue_tab = ttk.Frame(self.notebook)
        self.notebook.add(dialogue_tab, text="대사")
        self.notebook.add(subtitle_tab, text="영상 자막")
        self.notebook.add(narration_tab, text="나레이션")
        self.notebook.add(condition_tab, text="승리·패배조건")
        self.notebook.add(epilogue_tab, text="엔딩 후 캐릭터 후일담")
        self.notebook.bind("<<NotebookTabChanged>>", self._tab_changed)

        filters = ttk.Frame(dialogue_tab, padding=(0, 0, 0, 8))
        filters.pack(fill="x")
        ttk.Label(filters, text="시나리오").pack(side="left")
        self.scenario_var = tk.StringVar(value="전체")
        self.scenario_combo = ttk.Combobox(
            filters,
            textvariable=self.scenario_var,
            values=["전체"] + [str(index) for index in range(1, 71)],
            width=7,
            state="readonly",
        )
        self.scenario_combo.pack(side="left", padx=(5, 12))
        self.scenario_combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_list())
        ttk.Label(filters, text="검색").pack(side="left")
        self.search_var = tk.StringVar()
        search = ttk.Entry(filters, textvariable=self.search_var)
        search.pack(side="left", fill="x", expand=True, padx=(5, 12))
        search.bind("<KeyRelease>", lambda _event: self.refresh_list())
        self.changed_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            filters,
            text="수정한 대사만",
            variable=self.changed_only,
            command=self.refresh_list,
        ).pack(side="left")

        paned = ttk.Panedwindow(dialogue_tab, orient="horizontal")
        paned.pack(fill="both", expand=True)
        left = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left, weight=2)
        paned.add(right, weight=5)

        self.tree = ttk.Treeview(left, columns=("scenario", "state", "text"), show="headings")
        self.tree.heading("scenario", text="화")
        self.tree.heading("state", text="상태")
        self.tree.heading("text", text="현재 한글")
        self.tree.column("scenario", width=42, stretch=False, anchor="center")
        self.tree.column("state", width=58, stretch=False, anchor="center")
        self.tree.column("text", width=330)
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._select_record)

        header = ttk.Frame(right)
        header.pack(fill="x", padx=(10, 0))
        self.id_var = tk.StringVar(value="대사를 선택하세요")
        ttk.Label(header, textvariable=self.id_var, font=("맑은 고딕", 11, "bold")).pack(side="left")
        ttk.Button(header, text="기본 한글로 복원", command=self.restore_current).pack(side="right")

        text_paned = ttk.Panedwindow(right, orient="vertical")
        text_paned.pack(fill="both", expand=True, padx=(10, 0), pady=(8, 0))
        source_box = ttk.LabelFrame(text_paned, text="일본어 원문 (읽기 전용)")
        edit_box = ttk.LabelFrame(text_paned, text="한글 수정")
        text_paned.add(source_box, weight=2)
        text_paned.add(edit_box, weight=3)
        self.source = tk.Text(source_box, wrap="word", height=8, undo=False, bg="#f2f2f2")
        self.source.pack(fill="both", expand=True, padx=6, pady=6)
        self.source.configure(state="disabled")
        self.editor = tk.Text(edit_box, wrap="word", height=13, undo=True, maxundo=-1)
        self.editor.pack(fill="both", expand=True, padx=6, pady=6)
        self.editor.bind("<KeyRelease>", self._editor_changed)

        tokens = ttk.Frame(right, padding=(10, 7, 0, 0))
        tokens.pack(fill="x")
        ttk.Label(tokens, text="삽입:").pack(side="left")
        ttk.Button(tokens, text="줄바꿈", command=lambda: self._insert("\n")).pack(side="left", padx=(5, 0))
        ttk.Button(tokens, text="{page}", command=lambda: self._insert("{page}")).pack(side="left", padx=(5, 0))
        ttk.Label(tokens, text="이름 토큰은 기존 토큰을 지우지 말고 위치만 옮기세요.").pack(side="left", padx=12)

        self.detail_var = tk.StringVar()
        ttk.Label(right, textvariable=self.detail_var, padding=(10, 6, 0, 0)).pack(fill="x")
        self.validation_var = tk.StringVar()
        self.validation_label = ttk.Label(right, textvariable=self.validation_var, padding=(10, 2, 0, 0), wraplength=760)
        self.validation_label.pack(fill="x")

        self._build_subtitle_tab(subtitle_tab)
        self._build_narration_tab(narration_tab)
        self._build_condition_tab(condition_tab)
        self._build_aftermath_tab(epilogue_tab)

        self.name_token_tooltips = [TextNameTooltip(widget) for widget in (
            self.source, self.editor,
            self.subtitle_source, self.subtitle_editor,
            self.narration_source, self.narration_editor,
            self.condition_source, self.condition_editor,
            self.aftermath_source, self.aftermath_editor,
        )]

        self.status_var = tk.StringVar(value="불러오는 중…")
        ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w", padding=5).pack(fill="x", side="bottom")

    def _build_subtitle_tab(self, parent: ttk.Frame) -> None:
        controls = ttk.Frame(parent, padding=(0, 8, 0, 8))
        controls.pack(fill="x")
        ttk.Label(controls, text="영상").pack(side="left")
        self.subtitle_movie_var = tk.StringVar()
        self.subtitle_movie_combo = ttk.Combobox(
            controls,
            textvariable=self.subtitle_movie_var,
            state="readonly",
            width=28,
        )
        self.subtitle_movie_combo.pack(side="left", padx=(5, 12))
        self.subtitle_movie_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.refresh_subtitle_list(),
        )
        ttk.Button(
            controls, text="자막 추가", command=self.add_subtitle
        ).pack(side="left")
        ttk.Button(
            controls, text="기본값으로 복원", command=self.restore_subtitle
        ).pack(side="left", padx=(6, 0))
        ttk.Button(controls, text="원본 영상 전체 추출", command=self.extract_movies).pack(side="left", padx=(6, 0))
        ttk.Label(
            controls,
            text="30개 영상 · 자막 12×12 · 최대 2줄/240px",
        ).pack(side="left", padx=(16, 0))

        paned = ttk.Panedwindow(parent, orient="horizontal")
        paned.pack(fill="both", expand=True)
        left = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left, weight=3)
        paned.add(right, weight=5)

        self.movie_preview = MoviePreview(
            left, lambda: self.subtitle_rows(validate=False), self.select_playing_subtitle)
        self.movie_preview.pack(fill="both", expand=True)
        list_box = ttk.Frame(left)
        list_box.pack(fill="both", expand=True)

        self.subtitle_tree = ttk.Treeview(
            list_box, columns=("time", "text"), show="headings", height=5,
            selectmode="browse",
        )
        self.subtitle_tree.heading("time", text="시작–끝")
        self.subtitle_tree.heading("text", text="한글 자막")
        self.subtitle_tree.column("time", width=125, stretch=False)
        self.subtitle_tree.column("text", width=390)
        self.subtitle_tree.tag_configure(
            "subtitle_overlap", foreground="#d00000"
        )
        subtitle_scroll = ttk.Scrollbar(
            list_box, orient="vertical", command=self.subtitle_tree.yview
        )
        self.subtitle_tree.configure(yscrollcommand=subtitle_scroll.set)
        self.subtitle_tree.pack(side="left", fill="both", expand=True)
        subtitle_scroll.pack(side="right", fill="y")
        self.subtitle_tree.bind("<<TreeviewSelect>>", self._select_subtitle)
        self.subtitle_tree.bind("<Delete>", self.delete_subtitle)
        self.subtitle_tree.bind("<Prior>", lambda _event: self.move_subtitle(-1))
        self.subtitle_tree.bind("<Next>", lambda _event: self.move_subtitle(1))

        actions = ttk.Frame(left, padding=(0, 4))
        actions.pack(fill="x", before=list_box)
        self.subtitle_delete_button = ttk.Button(actions, text="삭제 (Del)", command=self.delete_subtitle)
        self.subtitle_delete_button.pack(side="left")
        self.subtitle_up_button = ttk.Button(actions, text="▲ 위로 (Page Up)", command=lambda: self.move_subtitle(-1))
        self.subtitle_up_button.pack(side="left", padx=4)
        self.subtitle_down_button = ttk.Button(actions, text="▼ 아래로 (Page Down)", command=lambda: self.move_subtitle(1))
        self.subtitle_down_button.pack(side="left")
        history_bar = ttk.Frame(left)
        history_bar.pack(fill="x", before=list_box)
        ttk.Button(history_bar, text="되돌리기 (Ctrl+Z)", command=self.undo_subtitle).pack(side="left")
        ttk.Label(history_bar, text="목록 이동은 재생 시간을 바꾸지 않습니다.").pack(side="left", padx=5)

        self.subtitle_id_var = tk.StringVar(value="자막을 선택하세요")
        ttk.Label(
            right,
            textvariable=self.subtitle_id_var,
            font=("맑은 고딕", 11, "bold"),
        ).pack(fill="x", padx=(10, 0), pady=(4, 8))

        timing = ttk.Frame(right)
        timing.pack(fill="x", padx=(10, 0))
        ttk.Label(timing, text="시작(초)").pack(side="left")
        self.subtitle_start_var = tk.StringVar()
        start_entry = ttk.Entry(
            timing, textvariable=self.subtitle_start_var, width=12
        )
        start_entry.pack(side="left", padx=(5, 14))
        ttk.Label(timing, text="끝(초)").pack(side="left")
        self.subtitle_end_var = tk.StringVar()
        end_entry = ttk.Entry(
            timing, textvariable=self.subtitle_end_var, width=12
        )
        end_entry.pack(side="left", padx=(5, 14))
        ttk.Label(timing, text="60fps 기준으로 빌드 시 프레임 정수로 변환").pack(side="left")
        start_entry.bind("<KeyRelease>", self._subtitle_changed)
        end_entry.bind("<KeyRelease>", self._subtitle_changed)
        self.subtitle_start_entry, self.subtitle_end_entry = start_entry, end_entry
        self.subtitle_start_var.trace_add("write", self._subtitle_time_changed)
        self.subtitle_end_var.trace_add("write", self._subtitle_time_changed)

        source_box = ttk.LabelFrame(right, text="일본어 문안 (기존 검토 초안 · 읽기 전용)")
        source_box.pack(fill="both", expand=False, padx=(10, 0), pady=(10, 6))
        self.subtitle_source = tk.Text(
            source_box, wrap="word", height=5, undo=False, bg="#f2f2f2"
        )
        self.subtitle_source.pack(fill="both", expand=True, padx=6, pady=6)
        self.subtitle_source.configure(state="disabled")

        edit_box = ttk.LabelFrame(right, text="한글 자막 (한 줄 또는 두 줄)")
        edit_box.pack(fill="both", expand=True, padx=(10, 0))
        self.subtitle_editor = tk.Text(
            edit_box, wrap="none", height=8, undo=True, maxundo=-1
        )
        self.subtitle_editor.pack(fill="both", expand=True, padx=6, pady=6)
        self.subtitle_editor.bind("<KeyRelease>", self._subtitle_changed)
        self.subtitle_editor.bind("<<Modified>>", self._subtitle_text_modified)

        self.subtitle_validation_var = tk.StringVar()
        self.subtitle_validation_label = ttk.Label(
            right,
            textvariable=self.subtitle_validation_var,
            padding=(10, 7, 0, 0),
            wraplength=750,
        )
        self.subtitle_validation_label.pack(fill="x")
        # Run before Text/Entry class bindings so one keypress cannot undo
        # both the widget's private buffer and the subtitle command history.
        tag = f"SubtitleHistory-{id(self)}"
        self.bind_class(tag, "<Control-z>", self.undo_subtitle)
        self.bind_class(tag, "<Control-Z>", self.undo_subtitle)
        self.bind_class(tag, "<Control-y>", self.redo_subtitle)
        def bind_history(widget):
            widget.bindtags((tag, *widget.bindtags()))
            for child in widget.winfo_children():
                bind_history(child)
        bind_history(parent)
        self._update_subtitle_actions()

    def _build_narration_tab(self, parent: ttk.Frame) -> None:
        controls = ttk.Frame(parent, padding=(0, 8, 0, 8))
        controls.pack(fill="x")
        ttk.Label(controls, text="시나리오/연출").pack(side="left")
        self.narration_filter_var = tk.StringVar(value="전체")
        self.narration_filter_combo = ttk.Combobox(
            controls,
            textvariable=self.narration_filter_var,
            state="readonly",
            width=28,
        )
        self.narration_filter_combo.pack(side="left", padx=(5, 12))
        self.narration_filter_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.refresh_narration_list(),
        )
        ttk.Label(
            controls,
            text=(
                "전체 95개 시나리오·연출 나레이션 편집 영역입니다. "
                "각 문자 코드는 1:1로 소유하며 공백 코드도 서로 돌려쓰지 않습니다."
            ),
        ).pack(side="left")
        paned = ttk.Panedwindow(parent, orient="horizontal")
        paned.pack(fill="both", expand=True)
        left = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left, weight=2)
        paned.add(right, weight=5)
        self.narration_tree = ttk.Treeview(
            left, columns=("label", "scene", "state", "text"), show="headings"
        )
        self.narration_tree.heading("label", text="시나리오/연출")
        self.narration_tree.heading("scene", text="장면")
        self.narration_tree.heading("state", text="상태")
        self.narration_tree.heading("text", text="현재 문안")
        self.narration_tree.column("label", width=115, stretch=False)
        self.narration_tree.column("scene", width=55, stretch=False, anchor="center")
        self.narration_tree.column("state", width=58, stretch=False, anchor="center")
        self.narration_tree.column("text", width=360)
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.narration_tree.yview)
        self.narration_tree.configure(yscrollcommand=scroll.set)
        self.narration_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.narration_tree.bind("<<TreeviewSelect>>", self._select_narration)

        header = ttk.Frame(right)
        header.pack(fill="x", padx=(10, 0))
        self.narration_id_var = tk.StringVar(value="나레이션을 선택하세요")
        ttk.Label(
            header, textvariable=self.narration_id_var,
            font=("맑은 고딕", 11, "bold"),
        ).pack(side="left")
        ttk.Button(
            header, text="기준 문안으로 복원", command=self.restore_narration
        ).pack(side="right")
        source_box = ttk.LabelFrame(right, text="일본어 원문 (읽기 전용)")
        source_box.pack(fill="both", expand=False, padx=(10, 0), pady=(8, 6))
        self.narration_source = tk.Text(
            source_box, wrap="word", height=7, undo=False, bg="#f2f2f2"
        )
        self.narration_source.pack(fill="both", expand=True, padx=6, pady=6)
        self.narration_source.configure(state="disabled")
        edit_box = ttk.LabelFrame(
            right, text=f"한글 나레이션 (화면당 최대 {NARRATION_MAX_LINES}줄·{NARRATION_SAFE_WIDTH_PX}px)"
        )
        edit_box.pack(fill="both", expand=True, padx=(10, 0))
        self.narration_editor = tk.Text(
            edit_box, wrap="none", height=12, undo=True, maxundo=-1
        )
        self.narration_editor.pack(fill="both", expand=True, padx=6, pady=6)
        self.narration_editor.bind("<KeyRelease>", self._narration_changed)
        self.narration_validation_var = tk.StringVar()
        self.narration_validation_label = ttk.Label(
            right, textvariable=self.narration_validation_var,
            padding=(10, 7, 0, 0), wraplength=750,
        )
        self.narration_validation_label.pack(fill="x")

    def _build_condition_tab(self, parent: ttk.Frame) -> None:
        controls = ttk.Frame(parent, padding=(0, 8, 0, 8))
        controls.pack(fill="x")
        ttk.Label(controls, text="시나리오/프레젠테이션").pack(side="left")
        self.condition_filter_var = tk.StringVar(value="전체")
        self.condition_filter_combo = ttk.Combobox(
            controls,
            textvariable=self.condition_filter_var,
            state="readonly",
            width=28,
        )
        self.condition_filter_combo.pack(side="left", padx=(5, 12))
        self.condition_filter_combo.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.refresh_condition_list(),
        )
        ttk.Label(
            controls,
            text=(
                "조건 화면 문자표를 문맥별로 분리하며 2화 조건 전용 코드는 "
                "본문이나 대사에서 재사용할 수 없습니다."
            ),
        ).pack(side="left")
        paned = ttk.Panedwindow(parent, orient="horizontal")
        paned.pack(fill="both", expand=True)
        left = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left, weight=3)
        paned.add(right, weight=5)
        self.condition_tree = ttk.Treeview(
            left, columns=("label", "kind", "state", "text"), show="headings"
        )
        self.condition_tree.heading("label", text="화/저장 위치")
        self.condition_tree.heading("kind", text="종류")
        self.condition_tree.heading("state", text="상태")
        self.condition_tree.heading("text", text="현재 한글")
        self.condition_tree.column("label", width=125, stretch=False)
        self.condition_tree.column("kind", width=55, stretch=False, anchor="center")
        self.condition_tree.column("state", width=55, stretch=False, anchor="center")
        self.condition_tree.column("text", width=350)
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.condition_tree.yview)
        self.condition_tree.configure(yscrollcommand=scroll.set)
        self.condition_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.condition_tree.bind("<<TreeviewSelect>>", self._select_condition)
        header = ttk.Frame(right)
        header.pack(fill="x", padx=(10, 0))
        self.condition_id_var = tk.StringVar(value="승리·패배조건을 선택하세요")
        ttk.Label(
            header, textvariable=self.condition_id_var,
            font=("맑은 고딕", 11, "bold"),
        ).pack(side="left")
        ttk.Button(
            header, text="기본 한글로 복원", command=self.restore_condition
        ).pack(side="right")
        source_box = ttk.LabelFrame(right, text="일본어 원문 (읽기 전용)")
        source_box.pack(fill="both", expand=False, padx=(10, 0), pady=(8, 6))
        self.condition_source = tk.Text(
            source_box, wrap="word", height=7, undo=False, bg="#f2f2f2"
        )
        self.condition_source.pack(fill="both", expand=True, padx=6, pady=6)
        self.condition_source.configure(state="disabled")
        edit_box = ttk.LabelFrame(right, text="한글 조건 (최대 4줄)")
        edit_box.pack(fill="both", expand=True, padx=(10, 0))
        self.condition_editor = tk.Text(
            edit_box, wrap="none", height=12, undo=True, maxundo=-1
        )
        self.condition_editor.pack(fill="both", expand=True, padx=6, pady=6)
        self.condition_editor.bind("<KeyRelease>", self._condition_changed)
        self.condition_validation_var = tk.StringVar()
        self.condition_validation_label = ttk.Label(
            right, textvariable=self.condition_validation_var,
            padding=(10, 7, 0, 0), wraplength=750,
        )
        self.condition_validation_label.pack(fill="x")

    def _build_aftermath_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent,
            text=(
                "엔딩 뒤에 표시되는 실제 캐릭터 후일담 134개입니다. "
                "전투 중 캐릭터 사망 시 나오는 대사가 아닙니다. "
                "게임의 실제 엔딩 자원 다섯 표에 같은 문안을 안전하게 반영하며 "
                "글리프는 중복 소유하지 않습니다."
            ),
            padding=(0, 8, 0, 8),
        ).pack(fill="x")
        paned = ttk.Panedwindow(parent, orient="horizontal")
        paned.pack(fill="both", expand=True)
        left = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left, weight=2)
        paned.add(right, weight=5)
        self.aftermath_tree = ttk.Treeview(
            left, columns=("number", "state", "text"), show="headings"
        )
        self.aftermath_tree.heading("number", text="번호")
        self.aftermath_tree.heading("state", text="상태")
        self.aftermath_tree.heading("text", text="현재 문안")
        self.aftermath_tree.column("number", width=54, stretch=False, anchor="center")
        self.aftermath_tree.column("state", width=58, stretch=False, anchor="center")
        self.aftermath_tree.column("text", width=390)
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.aftermath_tree.yview)
        self.aftermath_tree.configure(yscrollcommand=scroll.set)
        self.aftermath_tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.aftermath_tree.bind("<<TreeviewSelect>>", self._select_aftermath)
        header = ttk.Frame(right)
        header.pack(fill="x", padx=(10, 0))
        self.aftermath_id_var = tk.StringVar(value="후일담을 선택하세요")
        ttk.Label(
            header, textvariable=self.aftermath_id_var,
            font=("맑은 고딕", 11, "bold"),
        ).pack(side="left")
        ttk.Button(
            header, text="기준 문안으로 복원", command=self.restore_aftermath
        ).pack(side="right")
        source_box = ttk.LabelFrame(right, text="일본어 원문 (읽기 전용)")
        source_box.pack(fill="both", expand=False, padx=(10, 0), pady=(8, 6))
        self.aftermath_source = tk.Text(
            source_box, wrap="word", height=7, undo=False, bg="#f2f2f2"
        )
        self.aftermath_source.pack(fill="both", expand=True, padx=6, pady=6)
        self.aftermath_source.configure(state="disabled")
        edit_box = ttk.LabelFrame(right, text="한글 엔딩 후일담 (화면당 최대 4줄)")
        edit_box.pack(fill="both", expand=True, padx=(10, 0))
        self.aftermath_editor = tk.Text(
            edit_box, wrap="word", height=12, undo=True, maxundo=-1
        )
        self.aftermath_editor.pack(fill="both", expand=True, padx=6, pady=6)
        self.aftermath_editor.bind("<KeyRelease>", self._aftermath_changed)
        self.aftermath_validation_var = tk.StringVar()
        self.aftermath_validation_label = ttk.Label(
            right, textvariable=self.aftermath_validation_var,
            padding=(10, 7, 0, 0), wraplength=750,
        )
        self.aftermath_validation_label.pack(fill="x")

    def _initial_load(self) -> None:
        try:
            self.records = load_records()
            self.by_id = {row.id: row for row in self.records}
            self.subtitle_base = load_subtitle_cues()
            self.subtitle_base_by_id = {row.id: row for row in self.subtitle_base}
            self.narration_base = load_narration_records()
            self.narration_by_id = {
                row.id: row for row in self.narration_base
            }
            self.condition_base = load_condition_records()
            self.condition_by_id = {
                row.id: row for row in self.condition_base
            }
            self.epilogue_base = load_epilogue_records()
            self.epilogue_by_id = {
                row.id: row for row in self.epilogue_base
            }
            project = load_translation_project(self.project_path, self.records)
            self.texts = project.dialogue_edits
            self.subtitle_edits = project.subtitle_edits
            self.narration_edits = project.narration_edits
            self.condition_edits = project.condition_edits
            self.epilogue_edits = project.epilogue_edits
            self.title(f"랑그릿사 FX 한글 번역 편집기 - {self.project_path.name}")
            self.refresh_list()
            self._refresh_subtitle_movies()
            self.refresh_subtitle_list(commit=False)
            self.subtitle_history.reset()
            self._subtitle_checkpoint = self._subtitle_snapshot()
            self._refresh_narration_filters()
            self.refresh_narration_list(commit=False)
            self._refresh_condition_filters()
            self.refresh_condition_list(commit=False)
            self.refresh_aftermath_list(commit=False)
            self.status_var.set(
                f"1~70화 대사 {len(self.records)}개 · 영상 자막 "
                f"{len(self.subtitle_base)}개 · 나레이션 "
                f"{len(self.narration_base)}개 · 엔딩 후일담 "
                f"{len(self.epilogue_base)}개 · 승패조건 "
                f"{len(self.condition_base)}개 로드 완료"
            )
        except Exception as exc:
            messagebox.showerror("불러오기 실패", str(exc), parent=self)
            self.status_var.set("불러오기 실패")

    def text_for(self, record: DialogueRecord) -> str:
        return self.texts.get(record.id, record.base_text)

    def _commit_editor(self) -> None:
        if not self.current_id:
            return
        value = self.editor.get("1.0", "end-1c")
        record = self.by_id[self.current_id]
        if value == record.base_text:
            self.texts.pop(record.id, None)
        else:
            self.texts[record.id] = value

    def refresh_list(self) -> None:
        self._commit_editor()
        selected = self.current_id
        query = self.search_var.get().strip().lower()
        scenario = self.scenario_var.get()
        self.tree.delete(*self.tree.get_children())
        self.visible_ids = []
        for row in self.records:
            if scenario != "전체" and row.scenario != int(scenario):
                continue
            text = self.text_for(row)
            changed = text != row.base_text
            if self.changed_only.get() and not changed:
                continue
            haystack = f"{row.id} {row.source_text} {text}".lower()
            if query and query not in haystack:
                continue
            snippet = text.replace("\n", " / ").replace("{page}", " // ")
            self.tree.insert("", "end", iid=row.id, values=(row.scenario, "수정" if changed else "기본", snippet[:80]))
            self.visible_ids.append(row.id)
        if selected and self.tree.exists(selected):
            self.tree.selection_set(selected)
            self.tree.see(selected)

    def _select_record(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        new_id = selection[0]
        if new_id == self.current_id:
            return
        self._commit_aftermath_editor()
        self.current_aftermath_id = None
        self._commit_editor()
        self.current_id = new_id
        row = self.by_id[new_id]
        self.id_var.set(f"{row.id}  (시나리오 {row.scenario})")
        self.source.configure(state="normal")
        self.source.delete("1.0", "end")
        self.source.insert("1.0", row.source_text)
        self.source.configure(state="disabled")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", self.text_for(row))
        self.editor.edit_reset()
        self._update_validation()

    def _editor_changed(self, _event=None) -> None:
        self._commit_editor()
        self._update_validation()
        if self.current_id and self.tree.exists(self.current_id):
            row = self.by_id[self.current_id]
            text = self.text_for(row)
            self.tree.item(
                row.id,
                values=(row.scenario, "수정" if text != row.base_text else "기본", text.replace("\n", " / ").replace("{page}", " // ")[:80]),
            )
            if self.aftermath_tree.exists(row.id):
                self.aftermath_tree.item(
                    row.id,
                    values=(
                        "수정" if text != row.base_text else "기본",
                        text.replace("\n", " / ").replace("{page}", " // ")[:100],
                    ),
                )

    def _base_image_bytes(self) -> bytes | None:
        try:
            folder = self.base_var.get()
            if folder == self._cached_base_folder and self._cached_base_image is not None:
                return self._cached_base_image
            # Live byte-count feedback for Scenario 1 needs its dictionaries,
            # but hashing all three disc files on every first selection would
            # freeze the UI.  Full validation/build performs the pinned hash
            # checks; this preview only reads the known cooked filename.
            cooked = Path(folder) / BASE_COOKED_NAME
            if not cooked.is_file():
                return None
            self._cached_base_folder = folder
            self._cached_base_image = cooked.read_bytes()
            return self._cached_base_image
        except Exception:
            return None

    def _update_validation(self) -> None:
        if not self.current_id:
            return
        row = self.by_id[self.current_id]
        image = self._base_image_bytes() if row.scenario == 1 else None
        result = validate_record(row, self.text_for(row), image)
        capacity = (
            "전체 묶음에서 계산"
            if row.scenario == 2 or result.capacity < 0
            else f"{result.capacity}바이트"
        )
        encoded_label = "기준판 유지" if result.encoded_bytes < 0 else f"인코딩 {result.encoded_bytes}바이트"
        self.detail_var.set(
            f"{encoded_label} / 용량 {capacity}   |   최대 줄 폭 "
            f"{result.max_line_width_px}px / {MAX_DIALOGUE_SAFE_VISIBLE_WIDTH_PX}px"
        )
        if result.ok:
            self.validation_var.set("검사 통과" + (" · 수정됨" if self.text_for(row) != row.base_text else ""))
            self.validation_label.configure(foreground="#087f23")
        else:
            self.validation_var.set("오류: " + " / ".join(result.errors))
            self.validation_label.configure(foreground="#b00020")

    def _insert(self, value: str) -> None:
        if self.current_id:
            self.editor.insert("insert", value)
            self._editor_changed()
            self.editor.focus_set()

    def restore_current(self) -> None:
        if not self.current_id:
            return
        row = self.by_id[self.current_id]
        self.texts.pop(row.id, None)
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", row.base_text)
        self._editor_changed()

    def subtitle_rows(self, *, validate: bool = False) -> tuple[SubtitleCue, ...]:
        return apply_subtitle_edits(
            self.subtitle_base, self.subtitle_edits, validate=validate
        )

    def _refresh_subtitle_movies(self) -> None:
        movies: dict[int, str] = movie_titles()
        for row in self.subtitle_rows(validate=False):
            movies.setdefault(row.movie_id, row.movie_title)
        self.subtitle_movie_labels = {
            movie_id: f"{movie_id:03d} · {title}"
            for movie_id, title in sorted(movies.items())
        }
        values = list(self.subtitle_movie_labels.values())
        self.subtitle_movie_combo.configure(values=values)
        if values and self.subtitle_movie_var.get() not in values:
            self.subtitle_movie_var.set(values[0])

    def _selected_subtitle_movie(self) -> int | None:
        value = self.subtitle_movie_var.get()
        if not value:
            return None
        try:
            return int(value.split("·", 1)[0].strip())
        except ValueError:
            return None

    def refresh_subtitle_list(self, *, commit: bool = True) -> None:
        if commit:
            self._commit_subtitle_editor()
        selected = self.current_subtitle_id
        movie_id = self._selected_subtitle_movie()
        if movie_id is not None:
            self.movie_preview.open_movie(movie_id)
        self.subtitle_tree.delete(*self.subtitle_tree.get_children())
        rows = subtitle_display_rows(self.subtitle_rows(validate=False))
        overlap_ids = subtitle_overlap_ids(rows)
        for row in rows:
            if movie_id is not None and row.movie_id != movie_id:
                continue
            state = " +" if row.added else (
                " *" if row.id in self.subtitle_edits else ""
            )
            text = " / ".join(row.ko)
            self.subtitle_tree.insert(
                "", "end", iid=row.id,
                values=(f"{row.start:7.3f}–{row.end:7.3f}{state}", text),
                tags=(("subtitle_overlap",) if row.id in overlap_ids else ()),
            )
        if selected and self.subtitle_tree.exists(selected):
            self.subtitle_tree.selection_set(selected)
            self.subtitle_tree.see(selected)
        else:
            self._subtitle_loading = True
            self.current_subtitle_id = None
            self.subtitle_id_var.set("자막을 선택하세요")
            self.subtitle_source.configure(state="normal")
            self.subtitle_source.delete("1.0", "end")
            self.subtitle_source.configure(state="disabled")
            self.subtitle_editor.delete("1.0", "end")
            self.subtitle_start_var.set("")
            self.subtitle_end_var.set("")
            self.subtitle_validation_var.set("")
            self.subtitle_editor.edit_modified(False)
            self.movie_preview.selected_cue = None
            self._subtitle_loading = False
        self._update_subtitle_actions()

    def _subtitle_row(self, cue_id: str) -> SubtitleCue:
        rows = {row.id: row for row in self.subtitle_rows(validate=False)}
        if cue_id not in rows:
            raise SubtitleError(f"자막 ID를 찾을 수 없습니다: {cue_id}")
        return rows[cue_id]

    def _select_subtitle(self, _event=None) -> None:
        selection = self.subtitle_tree.selection()
        if not selection:
            return
        new_id = selection[0]
        if new_id == self.current_subtitle_id:
            return
        if not self._commit_subtitle_editor():
            if self.current_subtitle_id and self.subtitle_tree.exists(self.current_subtitle_id):
                self.subtitle_tree.selection_set(self.current_subtitle_id)
            return
        self._subtitle_loading = True
        self.current_subtitle_id = new_id
        row = self._subtitle_row(new_id)
        self.movie_preview.set_cue(row)
        suffix = " · 추가됨" if row.added else ""
        self.subtitle_id_var.set(
            f"{row.id}  (영상 {row.movie_id:03d} · {row.movie_title}{suffix})"
        )
        self.subtitle_start_var.set(f"{row.start:.3f}")
        self.subtitle_end_var.set(f"{row.end:.3f}")
        self.subtitle_source.configure(state="normal")
        self.subtitle_source.delete("1.0", "end")
        source = row.ja
        if row.speaker:
            source = f"[{row.speaker}]\n{source}"
        self.subtitle_source.insert("1.0", source)
        self.subtitle_source.configure(state="disabled")
        self.subtitle_editor.delete("1.0", "end")
        self.subtitle_editor.insert("1.0", "\n".join(row.ko))
        self.subtitle_editor.edit_reset()
        self.subtitle_editor.edit_modified(False)
        self._subtitle_loading = False
        self._update_subtitle_validation()
        self.subtitle_history.break_group()
        self._subtitle_checkpoint = self._subtitle_snapshot()
        self._update_subtitle_actions()

    def _commit_subtitle_editor(self) -> bool:
        if not self.current_subtitle_id:
            return True
        try:
            start = float(self.subtitle_start_var.get().strip())
            end = float(self.subtitle_end_var.get().strip())
        except ValueError:
            self.subtitle_validation_var.set("오류: 시작과 끝은 초 단위 숫자여야 합니다.")
            self.subtitle_validation_label.configure(foreground="#b00020")
            return False
        row = self._subtitle_row(self.current_subtitle_id)
        lines = tuple(self.subtitle_editor.get("1.0", "end-1c").split("\n"))
        changed = replace(row, start=start, end=end, ko=lines)
        original = self.subtitle_base_by_id.get(row.id)
        if original is not None and (
            changed.start == original.start
            and changed.end == original.end
            and changed.ko == original.ko
            and changed.ja == original.ja
            and changed.speaker == original.speaker
            and changed.list_order == original.list_order
        ):
            self.subtitle_edits.pop(row.id, None)
        else:
            self.subtitle_edits[row.id] = subtitle_edit_row(changed)
        return True

    def _update_subtitle_validation(self) -> None:
        if not self.current_subtitle_id:
            return
        try:
            if not self._commit_subtitle_editor():
                return
            rows = self.subtitle_rows(validate=False)
            row = next(item for item in rows
                       if item.id == self.current_subtitle_id)
            # Validate this row without making a temporary overlap block list
            # selection.  Whole-project save/build still validates all rows.
            validate_subtitle_cues((row,))
            widths = [
                sum(glyph_advance(character) for character in line)
                for line in row.ko
            ]
            changed = row.id in self.subtitle_edits
            details = (
                (" · 수정됨" if changed else "")
                + f" · 프레임 {round(row.start * 60)}–{round(row.end * 60)}"
                + " · 줄 폭 " + ", ".join(f"{width}px" for width in widths)
                + " / 240px"
            )
            if row.id in subtitle_overlap_ids(rows):
                self.subtitle_validation_var.set(
                    "시간 중첩: 빨간 자막끼리 시작/끝 시간이 겹칩니다."
                    + details
                )
                self.subtitle_validation_label.configure(foreground="#b00020")
            else:
                self.subtitle_validation_var.set("검사 통과" + details)
                self.subtitle_validation_label.configure(foreground="#087f23")
        except Exception as exc:
            self.subtitle_validation_var.set("오류: " + str(exc))
            self.subtitle_validation_label.configure(foreground="#b00020")

    def _refresh_subtitle_overlap_tags(self) -> None:
        overlap_ids = subtitle_overlap_ids(self.subtitle_rows(validate=False))
        for cue_id in self.subtitle_tree.get_children():
            self.subtitle_tree.item(
                cue_id,
                tags=(("subtitle_overlap",) if cue_id in overlap_ids else ()),
            )

    def _subtitle_changed(self, _event=None) -> None:
        if self._subtitle_loading or not self.current_subtitle_id:
            return
        before = self._subtitle_checkpoint or self._subtitle_snapshot()
        self._update_subtitle_validation()
        if self.current_subtitle_id and self.subtitle_tree.exists(
            self.current_subtitle_id
        ):
            try:
                row = self._subtitle_row(self.current_subtitle_id)
                state = " +" if row.added else (
                    " *" if row.id in self.subtitle_edits else ""
                )
                self.subtitle_tree.item(
                    row.id,
                    values=(
                        f"{row.start:7.3f}–{row.end:7.3f}{state}",
                        " / ".join(row.ko),
                    ),
                )
            except Exception:
                pass
        self._refresh_subtitle_overlap_tags()
        after = self._subtitle_snapshot()
        self.subtitle_history.record(before, after,
            merge_key=(self.current_subtitle_id, str(self.focus_get())))
        self._subtitle_checkpoint = after

    def _subtitle_time_changed(self, *_args):
        self._subtitle_changed()

    def _subtitle_text_modified(self, _event=None):
        if self.subtitle_editor.edit_modified():
            self.subtitle_editor.edit_modified(False)
            self._subtitle_changed()

    def _subtitle_snapshot(self):
        return dict(edits=deepcopy(self.subtitle_edits), selected=self.current_subtitle_id,
                    movie=self.subtitle_movie_var.get(), start=self.subtitle_start_var.get(),
                    end=self.subtitle_end_var.get(), text=self.subtitle_editor.get("1.0", "end-1c"))

    def _finish_subtitle_action(self, before, selected):
        self.current_subtitle_id = None
        self.refresh_subtitle_list(commit=False)
        if selected and self.subtitle_tree.exists(selected):
            self.subtitle_tree.selection_set(selected)
            self.subtitle_tree.focus(selected)
            self.subtitle_tree.see(selected)
            self._select_subtitle()
        self.subtitle_tree.focus_set()
        after = self._subtitle_snapshot()
        self.subtitle_history.record(before, after)
        self._subtitle_checkpoint = after
        self._update_subtitle_actions()

    def _update_subtitle_actions(self):
        selected = self.current_subtitle_id
        rows = self.subtitle_tree.get_children()
        valid = bool(selected and selected in rows)
        movable = valid and self._subtitle_row(selected).added
        index = rows.index(selected) if valid else -1
        self.subtitle_delete_button.configure(state="normal" if valid else "disabled")
        self.subtitle_up_button.configure(state="normal" if movable and index > 0 else "disabled")
        self.subtitle_down_button.configure(state="normal" if movable and index < len(rows)-1 else "disabled")

    def delete_subtitle(self, _event=None):
        if not self.current_subtitle_id:
            return "break"
        self._subtitle_changed()
        before = self._subtitle_snapshot()
        selected = self.current_subtitle_id
        rows = list(self.subtitle_tree.get_children())
        index = rows.index(selected)
        self.subtitle_edits = delete_subtitle_edit(self.subtitle_base, self.subtitle_edits, selected)
        rows.remove(selected)
        next_id = rows[min(index, len(rows)-1)] if rows else None
        self._finish_subtitle_action(before, next_id)
        self.status_var.set("선택한 자막 삭제 · Ctrl+Z로 되돌릴 수 있습니다.")
        return "break"

    def move_subtitle(self, direction):
        if not self.current_subtitle_id or not self._subtitle_row(self.current_subtitle_id).added:
            return "break"
        self._subtitle_changed()
        if not self._commit_subtitle_editor():
            return "break"
        before = self._subtitle_snapshot()
        selected = self.current_subtitle_id
        changed = move_subtitle_edit(self.subtitle_base, self.subtitle_edits, selected, direction)
        if changed != self.subtitle_edits:
            self.subtitle_edits = changed
            self._finish_subtitle_action(before, selected)
            self.status_var.set("자막 목록 순서 이동 · 시작/종료 시간은 유지됩니다.")
        return "break"

    def _restore_subtitle_snapshot(self, snapshot):
        self._subtitle_loading = True
        self.subtitle_edits = deepcopy(snapshot["edits"])
        self.current_subtitle_id = None
        self.subtitle_movie_var.set(snapshot["movie"])
        self.refresh_subtitle_list(commit=False)
        selected = snapshot["selected"]
        if selected and self.subtitle_tree.exists(selected):
            self.subtitle_tree.selection_set(selected)
            self.subtitle_tree.focus(selected)
            self.subtitle_tree.see(selected)
            self._select_subtitle()
            self._subtitle_loading = True
            self.subtitle_start_var.set(snapshot["start"])
            self.subtitle_end_var.set(snapshot["end"])
            self.subtitle_editor.delete("1.0", "end")
            self.subtitle_editor.insert("1.0", snapshot["text"])
            self.subtitle_editor.edit_modified(False)
        self._subtitle_loading = False
        self._update_subtitle_validation()
        self._subtitle_checkpoint = self._subtitle_snapshot()
        self._update_subtitle_actions()

    def undo_subtitle(self, _event=None):
        self._subtitle_changed()
        snapshot = self.subtitle_history.undo()
        if snapshot is not None:
            self._restore_subtitle_snapshot(snapshot)
            self.status_var.set("자막 편집 되돌림 · Ctrl+Y로 다시 실행할 수 있습니다.")
        return "break"

    def redo_subtitle(self, _event=None):
        self._subtitle_changed()
        snapshot = self.subtitle_history.redo()
        if snapshot is not None:
            self._restore_subtitle_snapshot(snapshot)
            self.status_var.set("자막 편집 다시 실행")
        return "break"

    def add_subtitle(self) -> None:
        self._subtitle_changed()
        if not self._commit_subtitle_editor():
            return
        movie_id = self._selected_subtitle_movie()
        if movie_id is None:
            return
        rows = [row for row in self.subtitle_rows(validate=False)
                if row.movie_id == movie_id]
        if not rows:
            rows = [row for row in self.subtitle_base if row.movie_id == movie_id]
            if not rows:
                messagebox.showinfo("대사 없는 영상", "이 영상은 원본 대사가 없는 감상·대조용 영상입니다.", parent=self)
                return
        playhead = self.movie_preview.current_subtitle_time(movie_id)
        if playhead is None:
            messagebox.showinfo(
                "재생 위치 없음",
                "영상을 먼저 연 뒤 원하는 위치에서 정지하고 자막을 추가하세요.",
                parent=self,
            )
            return
        before = self._subtitle_snapshot()
        reference = rows[0]
        start = round(playhead, 3)
        end = round(start + 2.0, 3)
        cue_id = next_custom_id(self.subtitle_rows(validate=False), movie_id)
        added = SubtitleCue(
            id=cue_id,
            movie_id=movie_id,
            movie_title=reference.movie_title,
            source_index=None,
            start=start,
            end=end,
            ja="",
            ko=("새 자막",),
            speaker="",
            added=True,
            list_order=max((row.list_order for row in rows if row.list_order is not None), default=len(rows)-1)+1,
        )
        self.subtitle_edits = insert_subtitle_edit(
            self.subtitle_base, self.subtitle_edits, added, self.current_subtitle_id)
        self._finish_subtitle_action(before, cue_id)
        self.status_var.set(
            f"현재 영상 위치 {start:.3f}초에 자막 추가 · "
            "중첩 시 목록에 빨간색으로 표시됩니다."
        )

    def select_playing_subtitle(self, cue_id: str) -> None:
        if self.subtitle_tree.exists(cue_id):
            self.subtitle_tree.selection_set(cue_id)
            self.subtitle_tree.see(cue_id)
            self._select_subtitle()

    def extract_movies(self) -> None:
        from movie_extraction_ui import start_extraction
        start_extraction(self, self.movie_preview)

    def _tab_changed(self, _event=None) -> None:
        preview = getattr(self, "movie_preview", None)
        if preview and preview.player and self.notebook.index("current") != 1:
            preview.player.set_pause(True)

    def restore_subtitle(self) -> None:
        if not self.current_subtitle_id:
            return
        cue_id = self.current_subtitle_id
        self._subtitle_changed()
        before = self._subtitle_snapshot()
        self.subtitle_edits.pop(cue_id, None)
        self._finish_subtitle_action(before, cue_id)

    def narration_text_for(self, record: NarrationRecord) -> str:
        return self.narration_edits.get(record.id, record.base_text)

    def _refresh_narration_filters(self) -> None:
        values = narration_filter_values(self.narration_base)
        self.narration_filter_combo.configure(values=values)
        if self.narration_filter_var.get() not in values:
            self.narration_filter_var.set("전체")

    def refresh_narration_list(self, *, commit: bool = True) -> None:
        if commit:
            self._commit_narration_editor()
        selected = self.current_narration_id
        selected_label = self.narration_filter_var.get()
        self.narration_tree.delete(*self.narration_tree.get_children())
        for row in self.narration_base:
            if selected_label != "전체" and row.label != selected_label:
                continue
            text = self.narration_text_for(row)
            self.narration_tree.insert(
                "", "end", iid=row.id,
                values=(
                    row.label,
                    row.ordinal,
                    "수정" if row.id in self.narration_edits else "기본",
                    text.replace("\n", " / ")[:100],
                ),
            )
        if selected and self.narration_tree.exists(selected):
            self.narration_tree.selection_set(selected)
            self.narration_tree.see(selected)

    def _select_narration(self, _event=None) -> None:
        selection = self.narration_tree.selection()
        if not selection:
            return
        new_id = selection[0]
        if new_id == self.current_narration_id:
            return
        self._commit_narration_editor()
        self.current_narration_id = new_id
        row = self.narration_by_id[new_id]
        self.narration_id_var.set(
            f"{row.id}  ({row.label} · 프레임 {row.frame_index} · 장면 {row.ordinal})"
        )
        self.narration_source.configure(state="normal")
        self.narration_source.delete("1.0", "end")
        self.narration_source.insert("1.0", row.source_text)
        self.narration_source.configure(state="disabled")
        self.narration_editor.delete("1.0", "end")
        self.narration_editor.insert("1.0", self.narration_text_for(row))
        self.narration_editor.edit_reset()
        self._update_narration_validation()

    def _commit_narration_editor(self) -> None:
        if not self.current_narration_id:
            return
        row = self.narration_by_id[self.current_narration_id]
        value = self.narration_editor.get("1.0", "end-1c")
        if value == row.base_text:
            self.narration_edits.pop(row.id, None)
        else:
            self.narration_edits[row.id] = value

    def _update_narration_validation(self) -> None:
        if not self.current_narration_id:
            return
        self._commit_narration_editor()
        row = self.narration_by_id[self.current_narration_id]
        try:
            text = self.narration_text_for(row)
            encoded = validate_narration_text(row, text)
            maximum_width = max(narration_line_widths(text), default=0)
            self.narration_validation_var.set(
                "검사 통과"
                + (" · 수정됨" if row.id in self.narration_edits else "")
                + f" · 본문 {len(encoded)}바이트"
                + f" · 최대 줄 폭 {maximum_width}/{NARRATION_SAFE_WIDTH_PX}px"
                + f" · 화면당 최대 {NARRATION_MAX_LINES}줄"
            )
            self.narration_validation_label.configure(foreground="#087f23")
        except Exception as exc:
            self.narration_validation_var.set("오류: " + str(exc))
            self.narration_validation_label.configure(foreground="#b00020")

    def _narration_changed(self, _event=None) -> None:
        self._update_narration_validation()
        if self.current_narration_id and self.narration_tree.exists(
            self.current_narration_id
        ):
            row = self.narration_by_id[self.current_narration_id]
            text = self.narration_text_for(row)
            self.narration_tree.item(
                row.id,
                values=(
                    row.label,
                    row.ordinal,
                    "수정" if row.id in self.narration_edits else "기본",
                    text.replace("\n", " / ")[:100],
                ),
            )

    def restore_narration(self) -> None:
        if not self.current_narration_id:
            return
        row = self.narration_by_id[self.current_narration_id]
        self.narration_edits.pop(row.id, None)
        self.narration_editor.delete("1.0", "end")
        self.narration_editor.insert("1.0", row.base_text)
        self._narration_changed()

    def condition_text_for(self, record: ConditionRecord) -> str:
        return self.condition_edits.get(record.id, record.base_text)

    def _refresh_condition_filters(self) -> None:
        labels: list[str] = []
        seen: set[str] = set()
        for row in self.condition_base:
            if row.label not in seen:
                seen.add(row.label)
                labels.append(row.label)
        values = ["전체"] + labels
        self.condition_filter_combo.configure(values=values)
        if self.condition_filter_var.get() not in values:
            self.condition_filter_var.set("전체")

    def refresh_condition_list(self, *, commit: bool = True) -> None:
        if commit:
            self._commit_condition_editor()
        selected = self.current_condition_id
        selected_label = self.condition_filter_var.get()
        self.condition_tree.delete(*self.condition_tree.get_children())
        for row in self.condition_base:
            if selected_label != "전체" and row.label != selected_label:
                continue
            text = self.condition_text_for(row)
            kind = (
                "승리" if row.kind == "victory-condition"
                else "패배" if row.kind == "defeat-condition"
                else "메뉴"
            )
            self.condition_tree.insert(
                "", "end", iid=row.id,
                values=(
                    row.label,
                    kind,
                    "수정" if row.id in self.condition_edits else "기본",
                    text.replace("\n", " / ")[:100],
                ),
            )
        if selected and self.condition_tree.exists(selected):
            self.condition_tree.selection_set(selected)
            self.condition_tree.see(selected)

    def _select_condition(self, _event=None) -> None:
        selection = self.condition_tree.selection()
        if not selection:
            return
        new_id = selection[0]
        if new_id == self.current_condition_id:
            return
        self._commit_condition_editor()
        self.current_condition_id = new_id
        row = self.condition_by_id[new_id]
        kind = (
            "승리조건" if row.kind == "victory-condition"
            else "패배조건" if row.kind == "defeat-condition"
            else "시스템 메뉴 조건"
        )
        self.condition_id_var.set(
            f"{row.id}  ({row.label} · {kind} · 프레임 {row.frame_index})"
        )
        self.condition_source.configure(state="normal")
        self.condition_source.delete("1.0", "end")
        self.condition_source.insert("1.0", row.source_text)
        self.condition_source.configure(state="disabled")
        self.condition_editor.delete("1.0", "end")
        self.condition_editor.insert("1.0", self.condition_text_for(row))
        self.condition_editor.edit_reset()
        self._update_condition_validation()

    def _commit_condition_editor(self) -> None:
        if not self.current_condition_id:
            return
        row = self.condition_by_id[self.current_condition_id]
        value = self.condition_editor.get("1.0", "end-1c")
        if value == row.base_text:
            self.condition_edits.pop(row.id, None)
        else:
            self.condition_edits[row.id] = value

    def _update_condition_validation(self) -> None:
        if not self.current_condition_id:
            return
        self._commit_condition_editor()
        row = self.condition_by_id[self.current_condition_id]
        try:
            encoded = validate_condition_text(row, self.condition_text_for(row))
            widths = condition_display_line_widths(self.condition_text_for(row), row.storage)
            maximum_width = max(widths, default=0)
            context = "3~12화 전용" if row.scenario and 3 <= row.scenario <= 12 else "전역 조건"
            self.condition_validation_var.set(
                "검사 통과"
                + (" · 수정됨" if row.id in self.condition_edits else "")
                + f" · 본문 {len(encoded)}바이트 · {context} 글리프 단독 소유"
                + f" · 최대 줄 폭 {maximum_width}/{CONDITION_MAX_WIDTH_PX}px"
                + (" · 항목 자동 정렬 · 반각 공백 4px" if row.storage == "menu"
                   else " · 항목 자동 정렬 · 좁은 공백 4px")
                + (" · 최대 1줄" if row.storage == "menu" else " · 최대 4줄")
            )
            self.condition_validation_label.configure(foreground="#087f23")
        except Exception as exc:
            self.condition_validation_var.set("오류: " + str(exc))
            self.condition_validation_label.configure(foreground="#b00020")

    def _condition_changed(self, _event=None) -> None:
        self._update_condition_validation()
        if self.current_condition_id and self.condition_tree.exists(
            self.current_condition_id
        ):
            row = self.condition_by_id[self.current_condition_id]
            text = self.condition_text_for(row)
            kind = (
                "승리" if row.kind == "victory-condition"
                else "패배" if row.kind == "defeat-condition"
                else "메뉴"
            )
            self.condition_tree.item(
                row.id,
                values=(
                    row.label,
                    kind,
                    "수정" if row.id in self.condition_edits else "기본",
                    text.replace("\n", " / ")[:100],
                ),
            )

    def restore_condition(self) -> None:
        if not self.current_condition_id:
            return
        row = self.condition_by_id[self.current_condition_id]
        self.condition_edits.pop(row.id, None)
        self.condition_editor.delete("1.0", "end")
        self.condition_editor.insert("1.0", row.base_text)
        self._condition_changed()

    def refresh_aftermath_list(self, *, commit: bool = True) -> None:
        if commit:
            self._commit_aftermath_editor()
        selected = self.current_aftermath_id
        self.aftermath_tree.delete(*self.aftermath_tree.get_children())
        for row in self.epilogue_base:
            text = self.epilogue_edits.get(row.id, row.base_text)
            self.aftermath_tree.insert(
                "", "end", iid=row.id,
                values=(
                    row.ordinal + 1,
                    "수정" if row.id in self.epilogue_edits else "기본",
                    text.replace("\n", " / ").replace("{page}", " // ")[:100],
                ),
            )
        if selected and self.aftermath_tree.exists(selected):
            self.aftermath_tree.selection_set(selected)
            self.aftermath_tree.see(selected)

    def _select_aftermath(self, _event=None) -> None:
        selection = self.aftermath_tree.selection()
        if not selection:
            return
        new_id = selection[0]
        if new_id == self.current_aftermath_id:
            return
        self._commit_aftermath_editor()
        self.current_aftermath_id = new_id
        row = self.epilogue_by_id[new_id]
        self.aftermath_id_var.set(
            f"{row.id}  (실제 엔딩 후일담 {row.ordinal + 1}/134 · 다섯 엔딩 공통)"
        )
        self.aftermath_source.configure(state="normal")
        self.aftermath_source.delete("1.0", "end")
        self.aftermath_source.insert("1.0", row.source_text)
        self.aftermath_source.configure(state="disabled")
        self.aftermath_editor.delete("1.0", "end")
        self.aftermath_editor.insert(
            "1.0", self.epilogue_edits.get(row.id, row.base_text)
        )
        self.aftermath_editor.edit_reset()
        self._update_aftermath_validation()

    def _commit_aftermath_editor(self) -> None:
        if not self.current_aftermath_id:
            return
        row = self.epilogue_by_id[self.current_aftermath_id]
        value = self.aftermath_editor.get("1.0", "end-1c")
        if value == row.base_text:
            self.epilogue_edits.pop(row.id, None)
        else:
            self.epilogue_edits[row.id] = value

    def _update_aftermath_validation(self) -> None:
        if not self.current_aftermath_id:
            return
        self._commit_aftermath_editor()
        row = self.epilogue_by_id[self.current_aftermath_id]
        text = self.epilogue_edits.get(row.id, row.base_text)
        try:
            encoded = validate_epilogue_text(row, text)
            self.aftermath_validation_var.set(
                "검사 통과"
                + (" · 수정됨" if row.id in self.epilogue_edits else "")
                + f" · 본문 {len(encoded)}/{row.allocation - 1}바이트"
                + " · 화면당 4줄/204px · 다섯 엔딩 복제본 동일 반영"
            )
            self.aftermath_validation_label.configure(foreground="#087f23")
        except Exception as exc:
            self.aftermath_validation_var.set(
                "오류: " + str(exc)
            )
            self.aftermath_validation_label.configure(foreground="#b00020")

    def _aftermath_changed(self, _event=None) -> None:
        self._update_aftermath_validation()
        if self.current_aftermath_id and self.aftermath_tree.exists(
            self.current_aftermath_id
        ):
            row = self.epilogue_by_id[self.current_aftermath_id]
            text = self.epilogue_edits.get(row.id, row.base_text)
            self.aftermath_tree.item(
                row.id,
                values=(
                    row.ordinal + 1,
                    "수정" if row.id in self.epilogue_edits else "기본",
                    text.replace("\n", " / ").replace("{page}", " // ")[:100],
                ),
            )

    def restore_aftermath(self) -> None:
        if not self.current_aftermath_id:
            return
        row = self.epilogue_by_id[self.current_aftermath_id]
        self.epilogue_edits.pop(row.id, None)
        self.aftermath_editor.delete("1.0", "end")
        self.aftermath_editor.insert("1.0", row.base_text)
        self._aftermath_changed()

    def choose_base(self) -> None:
        path = filedialog.askdirectory(title="successor190 기준 이미지 폴더", initialdir=self.base_var.get())
        if path:
            self.base_var.set(path)
            self._cached_base_folder = None
            self._cached_base_image = None
            try:
                verify_base_folder(Path(path))
                self.status_var.set("기준 이미지 해시 확인 완료")
            except Exception as exc:
                messagebox.showerror("기준 이미지 오류", str(exc), parent=self)

    def open_project(self) -> None:
        self._commit_editor()
        if not self._commit_subtitle_editor():
            messagebox.showerror(
                "열기 실패", "현재 자막 시작/끝 시간을 확인하세요.", parent=self
            )
            return
        self._commit_narration_editor()
        self._commit_condition_editor()
        self._commit_aftermath_editor()
        path = filedialog.askopenfilename(title="번역 편집 파일 열기", filetypes=[("JSON", "*.json"), ("모든 파일", "*.*")])
        if not path:
            return
        try:
            self.project_path = Path(path)
            project = load_translation_project(self.project_path, self.records)
            self.texts = project.dialogue_edits
            self.subtitle_edits = project.subtitle_edits
            self.narration_edits = project.narration_edits
            self.condition_edits = project.condition_edits
            self.epilogue_edits = project.epilogue_edits
            self.current_id = None
            self.current_subtitle_id = None
            self.current_narration_id = None
            self.current_condition_id = None
            self.current_aftermath_id = None
            self.editor.delete("1.0", "end")
            self.subtitle_editor.delete("1.0", "end")
            self.narration_editor.delete("1.0", "end")
            self.condition_editor.delete("1.0", "end")
            self.aftermath_editor.delete("1.0", "end")
            self.refresh_list()
            self._refresh_subtitle_movies()
            self.refresh_subtitle_list(commit=False)
            self.subtitle_history.reset()
            self._subtitle_checkpoint = self._subtitle_snapshot()
            self._refresh_narration_filters()
            self.refresh_narration_list(commit=False)
            self._refresh_condition_filters()
            self.refresh_condition_list(commit=False)
            self.refresh_aftermath_list(commit=False)
            self.title(f"랑그릿사 FX 한글 번역 편집기 - {self.project_path.name}")
            self.status_var.set(
                f"편집 파일 열기 완료 · 대사 수정 {len(self.texts)}개 · "
                f"자막 수정 {len(self.subtitle_edits)}개 · "
                f"나레이션 수정 {len(self.narration_edits)}개 · "
                f"승패조건 수정 {len(self.condition_edits)}개 · "
                f"엔딩 후일담 수정 {len(self.epilogue_edits)}개"
            )
        except Exception as exc:
            messagebox.showerror("열기 실패", str(exc), parent=self)

    def save_project(self) -> bool:
        self._commit_editor()
        self._commit_aftermath_editor()
        if not self._commit_subtitle_editor():
            messagebox.showerror(
                "저장 실패", "자막 시작/끝 시간을 확인하세요.", parent=self
            )
            return False
        self._commit_narration_editor()
        self._commit_condition_editor()
        try:
            save_translation_project(
                self.project_path,
                self.records,
                self.texts,
                self.subtitle_edits,
                self.narration_edits,
                self.condition_edits,
                self.epilogue_edits,
            )
            self.status_var.set(f"저장 완료: {self.project_path}")
            return True
        except Exception as exc:
            messagebox.showerror("저장 실패", str(exc), parent=self)
            return False

    def save_project_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title="번역 편집 파일 저장",
            defaultextension=".json",
            initialfile=self.project_path.name,
            filetypes=[("JSON", "*.json")],
        )
        if path:
            self.project_path = Path(path)
            if self.save_project():
                self.title(f"랑그릿사 FX 한글 번역 편집기 - {self.project_path.name}")

    def _start_worker(self, target, *args) -> None:
        if self.busy:
            return
        self.busy = True
        thread = threading.Thread(target=self._worker, args=(target, args), daemon=True)
        thread.start()

    def _worker(self, target, args) -> None:
        try:
            result = target(*args, progress=lambda value: self.events.put(("status", value)))
            self.events.put(("done", result))
        except Exception as exc:
            self.events.put(("error", exc))

    def _poll_events(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "status":
                    self.status_var.set(str(value))
                elif kind == "done":
                    self.busy = False
                    if isinstance(value, Path):
                        messagebox.showinfo("빌드 완료", f"새 CUE를 만들었습니다.\n\n{value}\n\n에뮬레이터에서 반드시 확인하세요.", parent=self)
                    else:
                        messagebox.showinfo(
                            "검사 완료",
                            "대사·영상 자막·전체 나레이션·승리·패배조건·실제 엔딩 후일담이 글자 소유·용량·토큰·줄 폭 검사를 통과했습니다.",
                            parent=self,
                        )
                elif kind == "error":
                    self.busy = False
                    messagebox.showerror("작업 실패", str(value), parent=self)
                    self.status_var.set("작업 실패")
        except queue.Empty:
            pass
        self.after(80, self._poll_events)

    def run_validation(self) -> None:
        if not self.save_project():
            return
        self._start_worker(
            validate_translation_project,
            self.records,
            dict(self.texts),
            dict(self.subtitle_edits),
            dict(self.narration_edits),
            dict(self.condition_edits),
            dict(self.epilogue_edits),
            Path(self.base_var.get()),
        )

    def run_build(self) -> None:
        if not self.save_project():
            return
        suggested = suggested_output_folder()
        parent = filedialog.askdirectory(title="새 빌드가 들어갈 상위 폴더", initialdir=str(suggested.parent))
        if not parent:
            return
        output = Path(parent) / suggested.name
        self._start_worker(
            build_translation_disc,
            self.records,
            dict(self.texts),
            dict(self.subtitle_edits),
            dict(self.narration_edits),
            dict(self.condition_edits),
            dict(self.epilogue_edits),
            Path(self.base_var.get()),
            output,
        )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--movie", type=int, choices=range(30), help="영상 대조 탭으로 열기")
    args = parser.parse_args()
    app = DialogueEditor()
    if args.movie is not None:
        def show_movie():
            if not app.subtitle_base:
                app.after(250, show_movie)
                return
            app.notebook.select(1)
            app.subtitle_movie_var.set(app.subtitle_movie_labels[args.movie])
            app.refresh_subtitle_list()
            entries = app.subtitle_tree.get_children()
            if entries:
                app.subtitle_tree.selection_set(entries[0])
                app._select_subtitle()
        app.after(500, show_movie)
    app.mainloop()
