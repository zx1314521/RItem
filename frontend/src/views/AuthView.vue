<template>
  <div class="auth-shell">
    <section class="auth-visual">
      <div class="brand">
        <div class="brand-mark">
          <BoxIcon />
        </div>
        <span>RememberItem</span>
      </div>
      <div class="auth-copy">
        <h1>把物品记住，把查找交给 AI。</h1>
        <p>通过文字、图片和对话管理你的物品。网页端先跑通后端能力，后续安卓和鸿蒙 App 可以复用同一套接口。</p>
      </div>
    </section>

    <section class="auth-panel">
      <div class="auth-box">
        <div class="auth-tabs">
          <button :class="{ active: authMode === 'login' }" @click="authMode = 'login'">登录</button>
          <button :class="{ active: authMode === 'register' }" @click="authMode = 'register'">注册</button>
        </div>

        <form v-if="authMode === 'login'" @submit.prevent="login">
          <div class="field">
            <label>账号或手机号</label>
            <input v-model.trim="loginForm.account" class="input" autocomplete="username" required />
          </div>
          <div class="field">
            <label>密码</label>
            <input v-model="loginForm.password" class="input" type="password" autocomplete="current-password" required />
          </div>
          <button class="btn wide" :disabled="loading">{{ loading ? "处理中" : "登录" }}</button>
        </form>

        <form v-else @submit.prevent="register">
          <div class="field">
            <label>用户名</label>
            <input v-model.trim="registerForm.username" class="input" autocomplete="username" required />
          </div>
          <div class="field">
            <label>手机号</label>
            <input v-model.trim="registerForm.phone" class="input" inputmode="tel" />
          </div>
          <div class="field">
            <label>密码</label>
            <input v-model="registerForm.password" class="input" type="password" autocomplete="new-password" required />
          </div>
          <button class="btn wide" :disabled="loading">{{ loading ? "处理中" : "注册并登录" }}</button>
        </form>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { authApi } from "../api";
import { BoxIcon } from "../components/icons";

const emit = defineEmits(["authenticated", "toast"]);

const authMode = ref("login");
const loading = ref(false);
const loginForm = ref({ account: "", password: "" });
const registerForm = ref({ username: "", phone: "", password: "" });

async function login() {
  loading.value = true;
  try {
    const data = await authApi.login(loginForm.value);
    emit("authenticated", data);
    emit("toast", "登录成功");
  } catch (error) {
    emit("toast", error.message, "error");
  } finally {
    loading.value = false;
  }
}

async function register() {
  loading.value = true;
  try {
    await authApi.register({
      username: registerForm.value.username,
      password: registerForm.value.password,
      phone: registerForm.value.phone || null,
    });
    loginForm.value.account = registerForm.value.username;
    loginForm.value.password = registerForm.value.password;
    await login();
  } catch (error) {
    emit("toast", error.message, "error");
  } finally {
    loading.value = false;
  }
}
</script>
