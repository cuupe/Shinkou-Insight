"""Output channel isolation and bounded generation, shared by provider streams."""
from __future__ import annotations

import re


class GenerationAborted(RuntimeError):
    pass


class GenerationGuard:
    def __init__(self, max_chars: int = 64000):
        self.max_chars = max_chars
        self.text = ""
        self._checked = 0

    def feed(self, text: str) -> None:
        self.text += text
        if len(self.text) > self.max_chars:
            raise GenerationAborted("生成超过长度上限，已停止本次输出")
        if len(self.text) - self._checked < 64:
            return
        self._checked = len(self.text)
        tail = re.sub(r"\s+", "", self.text[-12000:])
        if re.search(r"(.)\1{79,}", tail):
            raise GenerationAborted("检测到异常字符重复，已停止本次输出")
        # Four repeated blocks, even with a short transition between paragraphs.
        for width in (32, 64, 128, 256):
            if len(tail) >= width * 4 and tail.count(tail[-width:]) >= 4:
                raise GenerationAborted("检测到重复生成，已停止本次输出")


class FinalChannelFilter:
    """Drop explicit reasoning blocks even when a provider puts them in content.

    Preserve partial delimiters across chunks so no prefix leaks to the UI.
    Unlabelled prose cannot be reliably classified as private reasoning.
    """
    _tags = ("think", "thinking", "analysis", "reasoning", "scratchpad", "planner")
    _tag = re.compile(r"</?(?:think|thinking|analysis|reasoning|scratchpad|planner)\s*>", re.I)

    def __init__(self):
        self.pending = ""
        self.depth = 0

    def feed(self, value: str, *, final: bool = False) -> str:
        self.pending += value
        output = []
        while self.pending:
            match = self._tag.search(self.pending)
            if match:
                if not self.depth:
                    output.append(self.pending[:match.start()])
                self.depth = max(0, self.depth - 1) if match[0].startswith("</") else self.depth + 1
                self.pending = self.pending[match.end():]
                continue
            keep = 0
            if not final:
                for length in range(1, min(16, len(self.pending)) + 1):
                    suffix = self.pending[-length:].lower()
                    if any(tag.startswith(suffix) for name in self._tags for tag in (f"<{name}>", f"</{name}>")):
                        keep = length
            visible = self.pending[:-keep] if keep else self.pending
            if not self.depth:
                output.append(visible)
            self.pending = self.pending[-keep:] if keep else ""
            break
        return "".join(output)


def final_content(value: str) -> str:
    return FinalChannelFilter().feed(value, final=True)
