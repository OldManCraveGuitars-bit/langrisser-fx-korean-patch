"""Read-only hover help for the game's installed 09 xx name table."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys
import tkinter as tk

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from native_name_widths import installed_names


NAME_TOKEN = re.compile(r"\{name:([0-9A-Fa-f]{2})\}")


@dataclass(frozen=True)
class NameToken:
    start: int
    end: int
    token: str
    name_id: int

    @property
    def help_text(self) -> str:
        try:
            names = installed_names()
        except (OSError, ValueError) as exc:
            return f"{self.token} — 이름 표 확인 실패: {exc}"
        if self.name_id >= len(names):
            return f"{self.token} — 등록되지 않은 이름 번호"
        return f"{self.token} → {names[self.name_id][0]}"


def name_token_at(text: str, offset: int) -> NameToken | None:
    """Offsets are Python string positions, not Tk's UTF-16 indices."""
    for match in NAME_TOKEN.finditer(text):
        if match.start() <= offset < match.end():
            return NameToken(match.start(), match.end(), match.group(),
                             int(match[1], 16))
    return None


def name_token_under_pointer(widget: tk.Text, x: int, y: int) -> NameToken | None:
    index = widget.index(f"@{x},{y}")
    bbox = widget.bbox(index)
    # Text.index returns the NEAREST character, even over padding/empty space.
    if bbox is None:
        return None
    left, top, width, height = bbox
    if not (left <= x < left + width and top <= y < top + height):
        return None
    if widget.get(index, f"{index}+1c") in ("", "\n"):
        return None
    offset = len(widget.get("1.0", index))
    return name_token_at(widget.get("1.0", "end-1c"), offset)


class TextNameTooltip:
    """Additive bindings: never replace editing, selection or undo handlers."""

    def __init__(self, widget: tk.Text, delay_ms: int = 300) -> None:
        self.widget = widget
        self.delay_ms = delay_ms
        self.popup: tk.Toplevel | None = None
        self.label: tk.Label | None = None
        self.pending: str | None = None
        self.active: NameToken | None = None
        self.position = (0, 0)
        widget.bind("<Motion>", self._motion, add="+")
        for event in ("<Leave>", "<KeyPress>", "<ButtonPress>", "<MouseWheel>",
                      "<FocusOut>", "<Unmap>", "<Configure>", "<Destroy>"):
            widget.bind(event, self.hide, add="+")

    def hide(self, _event=None) -> None:
        if self.pending is not None:
            try:
                self.widget.after_cancel(self.pending)
            except tk.TclError:
                pass
            self.pending = None
        if self.popup is not None:
            self.popup.destroy()
            self.popup = None
            self.label = None
        self.active = None

    def _motion(self, event) -> None:
        self.position = (event.x, event.y)
        token = name_token_under_pointer(self.widget, *self.position)
        if token == self.active:
            return
        self.hide()
        if token is not None:
            self.active = token
            self.pending = self.widget.after(self.delay_ms, self._show)

    def _current(self) -> bool:
        return bool(self.widget.winfo_ismapped() and self.active is not None
                    and name_token_under_pointer(self.widget, *self.position)
                    == self.active)

    def _show(self) -> None:
        self.pending = None
        if not self._current():
            self.hide()
            return
        popup = tk.Toplevel(self.widget, takefocus=False)
        popup.withdraw()
        popup.overrideredirect(True)
        self.popup = popup
        self.label = tk.Label(popup, text=self.active.help_text,
                              bg="#fffbd6", fg="#202020", relief="solid",
                              borderwidth=1, padx=7, pady=4, wraplength=420)
        self.label.pack()
        popup.update_idletasks()
        x = self.widget.winfo_rootx() + self.position[0] + 14
        y = self.widget.winfo_rooty() + self.position[1] + 22
        x = max(0, min(x, popup.winfo_screenwidth() - popup.winfo_reqwidth()))
        y = max(0, min(y, popup.winfo_screenheight() - popup.winfo_reqheight()))
        popup.geometry(f"+{x}+{y}")
        popup.deiconify()
        self.pending = self.widget.after(150, self._check)

    def _check(self) -> None:
        # Also dismiss after programmatic record replacement or scrolling.
        self.pending = None
        if not self._current():
            self.hide()
        else:
            self.pending = self.widget.after(150, self._check)
