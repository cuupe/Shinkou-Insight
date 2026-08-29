import { computed, ref } from "vue";

// Keep these values in sync with AuthServiceImpl on the backend.
export const SMS_CODE_EXPIRE_SECONDS = 300;
export const SMS_RESEND_COOLDOWN_SECONDS = 60;

export function useSmsCode() {
  const codeId = ref("");
  const expiresIn = ref(0);
  const resendCountdown = ref(0);
  const expired = ref(false);
  let timer: number | undefined;

  function stopTimer() {
    window.clearInterval(timer);
    timer = undefined;
  }

  function tick() {
    if (resendCountdown.value > 0) resendCountdown.value -= 1;
    if (expiresIn.value > 0) expiresIn.value -= 1;

    if (expiresIn.value <= 0 && codeId.value) {
      codeId.value = "";
      expiresIn.value = 0;
      expired.value = true;
    }

    if (resendCountdown.value <= 0 && expiresIn.value <= 0) stopTimer();
  }

  function start(nextCodeId: string) {
    stopTimer();
    codeId.value = nextCodeId;
    expiresIn.value = SMS_CODE_EXPIRE_SECONDS;
    resendCountdown.value = SMS_RESEND_COOLDOWN_SECONDS;
    expired.value = false;
    timer = window.setInterval(tick, 1000);
  }

  function markExpired() {
    codeId.value = "";
    expiresIn.value = 0;
    expired.value = true;
    if (resendCountdown.value <= 0) stopTimer();
  }

  function clear() {
    stopTimer();
    codeId.value = "";
    expiresIn.value = 0;
    resendCountdown.value = 0;
    expired.value = false;
  }

  return {
    codeId,
    expiresIn,
    resendCountdown,
    expired,
    hasValidCode: computed(() => !!codeId.value && expiresIn.value > 0),
    start,
    markExpired,
    clear,
    stopTimer,
  };
}
