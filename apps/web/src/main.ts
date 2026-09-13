import { createApp } from "vue";
import App from "./App.vue";
import "./style.css";
import router from "./router";
import { setAuthFailureHandler } from "./utils/request";

setAuthFailureHandler((reason) => {
  // 只有后端明确返回 401 才能判定登录状态失效。
  // 502/503/网络错误由当前页面自行展示，不应把用户强制退出。
  if (reason !== "unauthorized") return;
  if (router.currentRoute.value.name === "login") return;

  void router.replace({
    name: "login",
    query: { reason },
  });
});

createApp(App).use(router).mount("#app");
