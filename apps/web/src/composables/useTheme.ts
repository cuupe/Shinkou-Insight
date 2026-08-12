import { onMounted, ref } from "vue";

type ThemeMode = "light" | "dark";

const storageKey = "shinkou-theme";
const isDark = ref(false);
let initialized = false;

function applyTheme(mode: ThemeMode) {
  isDark.value = mode === "dark";
  document.documentElement.classList.toggle("dark", isDark.value);
  document.documentElement.style.colorScheme = mode;
}

function initializeTheme() {
  if (initialized) return;
  initialized = true;

  const stored = localStorage.getItem(storageKey) as ThemeMode | null;
  const systemPrefersDark = window.matchMedia?.(
    "(prefers-color-scheme: dark)",
  ).matches;
  applyTheme(stored === "dark" || (!stored && systemPrefersDark) ? "dark" : "light");
}

function toggleTheme() {
  const nextMode: ThemeMode = isDark.value ? "light" : "dark";
  localStorage.setItem(storageKey, nextMode);
  applyTheme(nextMode);
}

export function useTheme() {
  onMounted(initializeTheme);

  return {
    isDark,
    toggleTheme,
  };
}
