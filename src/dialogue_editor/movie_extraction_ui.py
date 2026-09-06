"""Non-blocking extraction launcher; retains verified completed clips on cancel."""
from __future__ import annotations

import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from movie_media import ROOT, DEFAULT_MEDIA


def start_extraction(parent, preview):
    existing = getattr(parent, '_movie_extraction_window', None)
    if existing is not None and existing.winfo_exists():
        existing.lift()
        return
    core = ROOT / 'work/movie-extract-tools/mednafen_pcfx_libretro.dll'
    if not core.is_file():
        messagebox.showerror('영상 추출 도구', '영상 추출용 PC-FX 코어가 없습니다. 편집기 안내의 설치 절차를 먼저 실행하세요.', parent=parent)
        return
    cue = filedialog.askopenfilename(parent=parent, title='일본판 원본 CUE 선택 (한글판 아님)',
                                    filetypes=[('PC-FX 원본 디스크', '*.cue')])
    if not cue:
        return
    bios = filedialog.askopenfilename(parent=parent, title='PC-FX BIOS pcfx.rom 선택',
                                     filetypes=[('PC-FX BIOS', '*.rom')])
    if not bios:
        return
    # A copy is read into the private core only; no file is written back.
    save = filedialog.askopenfilename(parent=parent, title='LOAD 메뉴 진입용 세이브 선택 (원본 수정 없음)',
                                     filetypes=[('PC-FX 저장 파일', '*.sav *.srm')])
    if not save:
        return
    window = tk.Toplevel(parent)
    parent._movie_extraction_window = window
    window.title('원본 영상 30개 추출')
    window.geometry('650x260')
    status = tk.StringVar(value='원본 확인 중… 완료된 영상은 재사용합니다.')
    ttk.Label(window, textvariable=status, wraplength=610, padding=15).pack(fill='both', expand=True)
    messages = queue.Queue()
    process = subprocess.Popen([
        sys.executable, '-X', 'utf8', '-u', str(ROOT / 'tools/extract_editor_movies.py'),
        '--cue', cue, '--bios', bios, '--save', save, '--core', str(core),
        '--output', str(DEFAULT_MEDIA)], cwd=ROOT, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

    def reader():
        for line in process.stdout:
            messages.put(line.strip())
        process.wait()
        messages.put(('exit', process.returncode))

    def cancel():
        if process.poll() is None:
            process.terminate()
            status.set('중단했습니다. 완료된 영상은 보존되며 다음 추출에서 이어집니다.')
        else:
            window.destroy()

    ttk.Button(window, text='중단 / 닫기', command=cancel).pack(pady=12)
    window.protocol('WM_DELETE_WINDOW', cancel)
    def destroyed(event):
        if event.widget is window and process.poll() is None:
            process.terminate()
    window.bind('<Destroy>', destroyed, add='+')

    def poll():
        while not messages.empty():
            message = messages.get_nowait()
            if isinstance(message, tuple):
                preview.reload()
                status.set('30개 영상 추출 완료. 영상 탭에서 선택해 재생하세요.' if message[1] == 0
                           else status.get() + '\n추출이 중단되었거나 오류가 발생했습니다. 완료된 파일은 보존됩니다.')
                return
            status.set(message)
        if window.winfo_exists():
            window.after(200, poll)

    threading.Thread(target=reader, daemon=True).start()
    poll()
