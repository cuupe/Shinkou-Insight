import { onUnmounted, ref } from "vue";
import { api, getApiErrorMessage } from "@/api";

export const CAPTCHA_EXPIRE_SECONDS = 120;

export function useCaptcha() {
  const imageUrl = ref("");
  const captchaId = ref("");
  const loading = ref(false);
  const error = ref("");
  const expiresIn = ref(0);
  const expired = ref(false);
  let timer: number | undefined;

  function stopTimer() {
    window.clearInterval(timer);
    timer = undefined;
  }

  function startTimer() {
    stopTimer();
    expiresIn.value = CAPTCHA_EXPIRE_SECONDS;
    expired.value = false;
    timer = window.setInterval(() => {
      expiresIn.value -= 1;
      if (expiresIn.value <= 0) {
        expiresIn.value = 0;
        captchaId.value = "";
        expired.value = true;
        stopTimer();
      }
    }, 1000);
  }

  async function refresh() {
    stopTimer();
    loading.value = true;
    error.value = "";
    expired.value = false;
    expiresIn.value = 0;
    try {
      const captcha = await api.auth.captcha();
      imageUrl.value = captcha.imgUrl;
      captchaId.value = captcha.captchaId;
      startTimer();
    } catch (caughtError) {
      imageUrl.value = "";
      captchaId.value = "";
      error.value = getApiErrorMessage(caughtError, "验证码加载失败");
    } finally {
      loading.value = false;
    }
  }

  onUnmounted(stopTimer);

  return {
    imageUrl,
    captchaId,
    loading,
    error,
    expiresIn,
    expired,
    refresh,
  };
}
