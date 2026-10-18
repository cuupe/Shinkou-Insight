"""Trusted, timezone-aware time shared by prompts and retrieval policies."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone, tzinfo
from typing import Any, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

TIME_CONTEXT_VERSION = "1"
_TIME_CONTEXT = re.compile(r"<runtime_time\b[^>]*>.*?</runtime_time>\s*", re.DOTALL)


def resolve_timezone(name: str) -> tzinfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        # Windows may not have an IANA database until tzdata is installed.
        # These two configured defaults have fixed offsets for present dates.
        if name == "Asia/Shanghai":
            return timezone(timedelta(hours=8), name)
        if name in {"UTC", "Etc/UTC"}:
            return timezone.utc
        raise ValueError(f"Unknown runtime timezone: {name}") from None


def timezone_name() -> str:
    from config import get_settings

    return get_settings().app_timezone


def current_time() -> datetime:
    return datetime.now(timezone.utc).astimezone(resolve_timezone(timezone_name()))


def current_date() -> date:
    return current_time().date()


def time_context(now: datetime | None = None) -> str:
    now = (now or current_time()).astimezone(resolve_timezone(timezone_name()))
    return (
        '<runtime_time trust="server">\n'
        f"当前日期：{now:%Y-%m-%d}；当前时间：{now.isoformat(timespec='seconds')}；时区：{timezone_name()}。\n"
        "这是服务端本轮提供的真实时间，训练知识截止日期和历史会话日期不是当前日期。"
        "今天、今年、现在、现任等相对时间以此为准；用户明确指定的历史日期或时间范围应保留。"
        "搜索当前事实不得猜测旧年份。现任职务、最新状态等易变化事实必须核对本轮有效网页原文，"
        "不能凭模型记忆推断仍然有效。搜索失败、为空或只有旧资料时，明确说明截至当前日期无法核验，"
        "不得先断言现任人物或具体日期再用免责声明补救。网页发布日期、事件发生日和本次读取时间是不同概念。\n"
        "</runtime_time>"
    )


def with_time_context(
    messages: Sequence[dict[str, Any]], now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Refresh the clock on every model request, without mutating callers."""
    result = [dict(message) for message in messages]
    for message in result:
        if message.get("role") == "system" and isinstance(message.get("content"), str):
            message["content"] = _TIME_CONTEXT.sub("", message["content"]).strip()
    first = next((message for message in result if message.get("role") == "system"
                  and isinstance(message.get("content"), str)), None)
    context = time_context(now)
    if first is None:
        result.insert(0, {"role": "system", "content": context})
    else:
        first["content"] = context + "\n\n" + first["content"]
    return result
