import { ref } from "vue";
import { api } from "@/api";

export function useCaptcha() {
  const imageUrl = ref("");
  const captchaId = ref("");
  const loading = ref(false);
  const error = ref("");

  async function refresh() {
    loading.value = true;
    error.value = "";
    try {
      const captcha = await api.auth.captcha();
      imageUrl.value = captcha.imgUrl;
      captchaId.value = captcha.captchaId;
    } catch {
      imageUrl.value = "";
      captchaId.value = "";
      error.value = "验证码加载失败";
    } finally {
      loading.value = false;
    }
  }

  return { imageUrl, captchaId, loading, error, refresh };
}
