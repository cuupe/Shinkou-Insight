import { createApp } from "vue";
import App from "./App.vue";
import "./style.css";
import router from "./router";
import { setAuthFailureHandler } from "./utils/request";

setAuthFailureHandler((reason) => {
  if (router.currentRoute.value.name === "login") return;

  void router.replace({
    name: "login",
    query: { reason },
  });
});

createApp(App).use(router).mount("#app");
