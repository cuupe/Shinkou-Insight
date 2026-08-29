import type { ClassValue } from "clsx";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function dateFormatWithday(zone: string, date: Date) {
  if (!date) {
    return null;
  }

  return date.toLocaleDateString("zh-CN", {
    timeZone: zone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

export function dateFormatWithseconds(zone: string, date: Date) {
  if (!date) {
    return null;
  }

  return date
    .toLocaleString("zh-CN", {
      timeZone: zone,
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
