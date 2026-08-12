import Axios from "axios";

// 不携带 cookie
export const axios = Axios.create({
  baseURL: "/api",
  withCredentials: false,
});

// 携带 cookie
export const anet = Axios.create({
  baseURL: "/api",
  withCredentials: true,
});
