"""Bounded, deep-copy undo for subtitle drafts and structural edits."""
from copy import deepcopy
from time import monotonic


class SubtitleHistory:
    def __init__(self, limit=200):
        self.limit = limit
        self.reset()

    def reset(self):
        self.undo_stack = []
        self.redo_stack = []
        self.break_group()

    def break_group(self):
        self.merge_key = None
        self.last_time = 0.0

    def record(self, before, after, *, merge_key=None):
        if before == after:
            return
        now = monotonic()
        if (merge_key is not None and merge_key == self.merge_key
                and now - self.last_time <= 0.8 and self.undo_stack
                and self.undo_stack[-1][1] == before):
            self.undo_stack[-1] = (self.undo_stack[-1][0], deepcopy(after))
        else:
            self.undo_stack.append((deepcopy(before), deepcopy(after)))
            del self.undo_stack[:-self.limit]
        self.redo_stack.clear()
        self.merge_key, self.last_time = merge_key, now

    def undo(self):
        self.break_group()
        if not self.undo_stack:
            return None
        command = self.undo_stack.pop()
        self.redo_stack.append(command)
        return deepcopy(command[0])

    def redo(self):
        self.break_group()
        if not self.redo_stack:
            return None
        command = self.redo_stack.pop()
        self.undo_stack.append(command)
        return deepcopy(command[1])
