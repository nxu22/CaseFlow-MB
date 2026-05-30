import { redirect } from "next/navigation";

// 根路径直接跳登录页。已登录的话，登录页会再把你弹去 /cases。
export default function Home() {
  redirect("/login");
}
