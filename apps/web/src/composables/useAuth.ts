export function useAuth() {
  function isPhone(value: string) { return /^1\d{10}$/.test(value); }
  function isCode(value: string) { return /^\d{6}$/.test(value); }
  function isCaptcha(value: string) { return value.trim().length > 0; }
  return { isPhone, isCode, isCaptcha };
}
