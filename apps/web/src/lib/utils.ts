import type { ClassValue } from "clsx";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const legacyTimeZoneAliases: Record<string, string> = {
  // Older profile settings stored locale identifiers instead of IANA zones.
  "zh-CN": "Asia/Shanghai",
  "en-US": "America/New_York",
};

function resolveTimeZone(zone: string) {
  const candidate = legacyTimeZoneAliases[zone?.trim()] || zone?.trim();
  if (!candidate) return "Asia/Shanghai";

  try {
    // Intl throws for locale identifiers such as "zh-CN" when used as a zone.
    new Intl.DateTimeFormat("en-US", { timeZone: candidate }).format();
    return candidate;
  } catch {
    return "Asia/Shanghai";
  }
}

export function dateFormatWithday(zone: string, date: Date) {
  if (!date || Number.isNaN(date.getTime())) {
    return null;
  }

  return date
    .toLocaleDateString("zh-CN", {
      timeZone: resolveTimeZone(zone),
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    })
    .replace(/\//g, "-");
}

export function dateFormatWithseconds(zone: string, date: Date) {
  if (!date || Number.isNaN(date.getTime())) {
    return null;
  }

  return date
    .toLocaleString("zh-CN", {
      timeZone: resolveTimeZone(zone),
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    })
    .replace(/\//g, "-");
}

export type DateTimeLike = Date | string | number | null | undefined;

/** Format backend timestamps for the UI without ISO delimiters or fractions. */
export function formatDateTime(
  value: unknown,
  fallback = "—",
  zone = "Asia/Shanghai",
) {
  if (value == null || value === "") return fallback;

  if (typeof value === "string") {
    const raw = value.trim();
    if (!raw) return fallback;
    if (["—", "暂无", "等待中", "刚刚"].includes(raw)) return raw;
  }

  const date =
    value instanceof Date
      ? value
      : typeof value === "string" || typeof value === "number"
        ? new Date(value)
        : null;
  if (date && !Number.isNaN(date.getTime())) {
    return dateFormatWithseconds(zone, date) || fallback;
  }

  if (typeof value !== "string" && typeof value !== "number") return fallback;

  return (
    String(value)
      .trim()
      .replace("T", " ")
      .replace(/\.\d+(?=(Z|[+-]\d{2}:?\d{2})?$)/, "")
      .replace(/Z$/, "") || fallback
  );
}
