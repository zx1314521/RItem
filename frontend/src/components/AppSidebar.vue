<template>
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-mark">
        <BoxIcon />
      </div>
      <span>RememberItem</span>
    </div>

    <nav class="menu">
      <button
        v-for="item in menuItems"
        :key="item.view"
        :class="{ active: currentView === item.view }"
        @click="$emit('change-view', item.view)"
      >
        <component :is="item.icon" />
        <span>{{ item.label }}</span>
      </button>
    </nav>

    <div class="sidebar-bottom">
      <div>{{ user.username }}</div>
      <button class="btn ghost" @click="$emit('logout')">退出登录</button>
    </div>
  </aside>
</template>

<script setup>
import { BoxIcon, ChatIcon, SettingsIcon } from "./icons";

defineProps({
  currentView: {
    type: String,
    required: true,
  },
  user: {
    type: Object,
    required: true,
  },
});

defineEmits(["change-view", "logout"]);

const menuItems = [
  { view: "chat", label: "AI 对话", icon: ChatIcon },
  { view: "items", label: "Item", icon: BoxIcon },
  { view: "settings", label: "设置", icon: SettingsIcon },
];
</script>
