<template>
  <AuthView
    v-if="!isAuthed"
    @authenticated="handleAuthenticated"
    @toast="showToast"
  />

  <div v-else class="app-shell">
    <AppSidebar
      :current-view="currentView"
      :user="user"
      @change-view="currentView = $event"
      @logout="logout"
    />

    <main class="content">
      <div class="topbar">
        <h2>{{ viewTitle }}</h2>
      </div>

      <nav class="mobile-menu">
        <button class="btn secondary" :class="{ active: currentView === 'chat' }" @click="currentView = 'chat'">AI 对话</button>
        <button class="btn secondary" :class="{ active: currentView === 'items' }" @click="currentView = 'items'">Item</button>
        <button class="btn secondary" :class="{ active: currentView === 'settings' }" @click="currentView = 'settings'">设置</button>
      </nav>

      <ChatView
        v-if="currentView === 'chat'"
        :token="token"
        @toast="showToast"
      />
      <ItemsView
        v-else-if="currentView === 'items'"
        :token="token"
        @toast="showToast"
      />
      <SettingsView
        v-else
        :token="token"
        @toast="showToast"
        @logout="logout"
      />
    </main>
  </div>

  <ToastMessage :toast="toast" />
</template>

<script setup>
import { computed, ref } from "vue";
import { authApi, clearStoredAuth, getStoredAuth, storeAuth } from "./api";
import AppSidebar from "./components/AppSidebar.vue";
import ToastMessage from "./components/ToastMessage.vue";
import AuthView from "./views/AuthView.vue";
import ChatView from "./views/ChatView.vue";
import ItemsView from "./views/ItemsView.vue";
import SettingsView from "./views/SettingsView.vue";

const { token: storedToken, user: storedUser } = getStoredAuth();
const token = ref(storedToken);
const user = ref(storedUser);
const currentView = ref("chat");
const toast = ref(null);
const toastTimer = ref(null);

const isAuthed = computed(() => Boolean(token.value && user.value));
const viewTitle = computed(
  () => ({ chat: "AI 对话", items: "Item", settings: "设置" })[currentView.value],
);

function handleAuthenticated(data) {
  token.value = data.access_token;
  user.value = data.user;
  currentView.value = "chat";
  storeAuth(token.value, user.value);
}

function showToast(message, type = "success") {
  toast.value = { message, type };
  window.clearTimeout(toastTimer.value);
  toastTimer.value = window.setTimeout(() => {
    toast.value = null;
  }, 2600);
}

async function logout() {
  try {
    await authApi.logout(token.value);
  } catch (_) {
    // Local logout should still continue when the token has already expired.
  }
  token.value = "";
  user.value = null;
  currentView.value = "chat";
  clearStoredAuth();
  showToast("已退出登录");
}
</script>
