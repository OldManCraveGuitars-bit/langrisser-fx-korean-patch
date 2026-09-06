"""Audio-synchronised Tk movie review panel; does not alter game images."""
from __future__ import annotations

from pathlib import Path
import os
import sys
import tkinter as tk
from tkinter import ttk

from movie_media import ROOT, DEFAULT_MEDIA, load_media, cue_at, subtitle_seconds, video_seconds

_DLL_HANDLES = []


def media_player_class():
    deps = ROOT / 'work/editor-media-deps'
    if str(deps) not in sys.path:
        sys.path.insert(0, str(deps))
    if os.name == 'nt' and not _DLL_HANDLES:
        for name in ('ffmpeg', 'sdl'):
            directory = deps / 'share/ffpyplayer' / name / 'bin'
            if directory.is_dir():
                _DLL_HANDLES.append(os.add_dll_directory(str(directory)))
    from ffpyplayer.player import MediaPlayer
    return MediaPlayer


class MoviePreview(ttk.LabelFrame):
    def __init__(self, parent, get_cues, select_cue):
        super().__init__(parent, text='원본 영상·일본어·한글 대조')
        self.get_cues = get_cues
        self.select_cue = select_cue
        self.player = None
        self.movie_id = None
        self.position = 0.0
        self.duration = 0.0
        self.clock_offset = 0.0
        self.selected_cue = None
        self.pending_seek = None
        self.media = {}
        self.photo = None
        self._after_id = None
        self.loop = tk.BooleanVar(value=False)
        self.mute = tk.BooleanVar(value=False)
        self.overlay = tk.BooleanVar(value=True)
        self.canvas = tk.Canvas(self, width=384, height=260, bg='#05080d', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True, padx=4, pady=4)
        self.image_item = self.canvas.create_image(0, 0, anchor='nw')
        self.caption_background = self.canvas.create_rectangle(0, 220, 384, 260, fill='black', outline='', state='hidden')
        self.caption_item = self.canvas.create_text(192, 238, text='', fill='white',
                                                   justify='center', font=('맑은 고딕', 11))
        self.ja = tk.StringVar(value='영상 선택 후 재생하세요. 원본 음성을 함께 들을 수 있습니다.')
        ttk.Label(self, textvariable=self.ja, wraplength=430, justify='left').pack(fill='x', padx=5)
        self.ko = tk.StringVar()
        ttk.Label(self, textvariable=self.ko, wraplength=430, foreground='#165c95').pack(fill='x', padx=5)
        self.scale = ttk.Scale(self, from_=0, to=1)
        self.scale.pack(fill='x', padx=5)
        self.scale.bind('<ButtonRelease-1>', lambda _e: self.seek(self.scale.get()))
        self.dragging = False
        self.scale.bind('<ButtonPress-1>', lambda _e: setattr(self, 'dragging', True))
        bar = ttk.Frame(self)
        bar.pack(fill='x', padx=4)
        self.play_button = ttk.Button(bar, text='재생 / 정지', command=self.toggle)
        self.play_button.pack(side='left')
        ttk.Button(bar, text='◀ 1초', command=lambda: self.seek(self.position - 1)).pack(side='left')
        ttk.Button(bar, text='1초 ▶', command=lambda: self.seek(self.position + 1)).pack(side='left')
        ttk.Checkbutton(bar, text='음소거', variable=self.mute, command=self.set_mute).pack(side='left')
        controls = ttk.Frame(self)
        controls.pack(fill='x', padx=4, pady=4)
        ttk.Button(controls, text='선택 자막부터', command=self.play_cue).pack(side='left')
        ttk.Checkbutton(controls, text='선택 구간 반복', variable=self.loop).pack(side='left')
        ttk.Button(controls, text='재생 중 자막 선택', command=self.follow_cue).pack(side='left')
        ttk.Checkbutton(self, text='한글 겹쳐보기 (검토용 표시)', variable=self.overlay).pack(anchor='w', padx=5)
        self.status = tk.StringVar()
        ttk.Label(self, textvariable=self.status, wraplength=430).pack(fill='x', padx=5, pady=3)
        self.bind('<Destroy>', self._destroy, add='+')
        self.reload()

    def reload(self, directory=DEFAULT_MEDIA):
        try:
            self.media = load_media(Path(directory))
            self.status.set(f'원본 영상 {len(self.media)}/30개 · 자막은 검토용으로 별도 표시')
        except Exception as exc:
            self.media = {}
            self.status.set(str(exc))

    def close(self):
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        if self.player is not None:
            self.player.close_player()
            self.player = None

    def _destroy(self, event):
        if event.widget is self:
            self.close()

    def open_movie(self, movie_id):
        if movie_id == self.movie_id and self.player is not None:
            return
        self.close()
        self.movie_id = movie_id
        self.selected_cue = None
        self.position = 0.0
        self.pending_seek = None
        self.photo = None
        self.canvas.itemconfigure(self.image_item, image='')
        self.canvas.itemconfigure(self.caption_item, text='')
        self.canvas.itemconfigure(self.caption_background, state='hidden')
        self.ja.set('')
        self.ko.set('')
        self.reload()
        if movie_id not in self.media:
            self.status.set(f'영상 {movie_id:03d} 미추출 · 전체 영상 추출 후 다시 선택하세요.')
            return
        try:
            MediaPlayer = media_player_class()
            self.duration = float(self.media[movie_id]['duration_seconds'])
            self.clock_offset = float(self.media[movie_id].get('subtitle_clock_offset_seconds', 0))
            self.scale.configure(to=self.duration)
            self.player = MediaPlayer(str(self.media[movie_id]['path']),
                                      ff_opts={'paused': True, 'out_fmt': 'rgb24',
                                               'volume': 1.0})
            self.player.set_mute(self.mute.get())
            self._after_id = self.after(15, self.tick)
        except Exception as exc:
            self.status.set('영상 재생 준비 실패: ' + str(exc))

    def set_cue(self, cue):
        self.open_movie(cue.movie_id)
        self.selected_cue = cue

    def current_subtitle_time(self, movie_id=None):
        """Return the playhead in the game's subtitle clock, if available."""
        if movie_id is None:
            movie_id = self.movie_id
        if (self.player is None or movie_id != self.movie_id
                or movie_id not in self.media):
            return None
        return max(0.0, subtitle_seconds(self.media[movie_id], self.position))

    def toggle(self):
        if self.player:
            if self.position >= self.duration - .05:
                self.seek(0)
                self.pending_seek = (0.0, False)
                return
            self.player.toggle_pause()

    def set_mute(self):
        if self.player:
            self.player.set_mute(self.mute.get())

    def seek(self, seconds):
        self.dragging = False
        if self.player is None:
            return
        seconds = max(0.0, min(float(seconds), self.duration - .02))
        paused = self.player.get_pause()
        self.player.set_pause(False)
        self.player.seek(seconds, relative=False, accurate=True)
        self.pending_seek = (seconds, paused)
        self.position = seconds

    def play_cue(self):
        if self.selected_cue and self.player:
            # Read the current edit, not the row snapshot at selection time.
            cue = next((r for r in self.get_cues() if r.id == self.selected_cue.id), self.selected_cue)
            self.selected_cue = cue
            target = video_seconds(self.media[self.movie_id], cue.start)
            self.seek(target)
            self.pending_seek = (target, False)

    def follow_cue(self):
        if self.movie_id not in self.media:
            return
        cue = cue_at(self.get_cues(), self.movie_id, subtitle_seconds(self.media[self.movie_id], self.position))
        if cue:
            self.select_cue(cue.id)

    def tick(self):
        self._after_id = None
        if self.player is None:
            return
        try:
            frame, value = self.player.get_frame()
            if frame is not None:
                from PIL import Image, ImageTk
                data, pts = frame
                if self.pending_seek and abs(pts - self.pending_seek[0]) < .12:
                    pause = self.pending_seek[1]
                    self.pending_seek = None
                    self.player.set_pause(pause)
                self.position = float(pts)
                w, h = data.get_size()
                picture = Image.frombytes('RGB', (w, h), data.to_bytearray()[0])
                cw, ch = max(256, self.canvas.winfo_width()), max(200, self.canvas.winfo_height())
                ratio = min(cw / w, ch / h)
                size = (round(w * ratio), round(h * ratio))
                self.photo = ImageTk.PhotoImage(picture.resize(size, Image.Resampling.NEAREST))
                self.canvas.coords(self.image_item, (cw - size[0]) // 2, (ch - size[1]) // 2)
                self.canvas.itemconfigure(self.image_item, image=self.photo)
                self.canvas.coords(self.caption_item, cw / 2, ch - 29)
                self.canvas.coords(self.caption_background, 0, ch - 57, cw, ch)
                self.canvas.itemconfigure(self.caption_item, width=cw - 16)
            if value == 'eof':
                self.player.set_pause(True)
            rows = self.get_cues()
            game_time = subtitle_seconds(self.media[self.movie_id], self.position)
            cue = cue_at(rows, self.movie_id, game_time)
            self.ja.set(('일본어: ' + cue.ja) if cue else '일본어: (등록 자막 없음)')
            self.ko.set(('한글: ' + ' / '.join(cue.ko)) if cue else '')
            self.canvas.itemconfigure(self.caption_item, text='\n'.join(cue.ko) if cue and self.overlay.get() else '')
            self.canvas.itemconfigure(self.caption_background, state='normal' if cue and self.overlay.get() else 'hidden')
            if self.selected_cue:
                self.selected_cue = next((r for r in rows if r.id == self.selected_cue.id), None)
            if (self.loop.get() and self.selected_cue and not self.player.get_pause()
                    and self.pending_seek is None and game_time >= self.selected_cue.end):
                self.play_cue()
            if not self.dragging:
                self.scale.set(self.position)
            self.status.set(f'영상 {self.position:.3f} / {self.duration:.3f}초 · 자막 시계 {game_time:.3f}초')
        except Exception as exc:
            self.close()
            self.status.set('재생 오류: ' + str(exc))
            return
        self._after_id = self.after(15, self.tick)
