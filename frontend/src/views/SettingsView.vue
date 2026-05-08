<template>
  <section class="view">
    <div class="settings-layout">
      <div class="section">
        <h3>MCP 配置</h3>
        <div class="switch-row">
          <div>
            <strong>启用 MCP</strong>
            <div class="hint">允许外部 AI 按你的配置调用 RememberItem。</div>
          </div>
          <button class="switch" :class="{ on: settings.mcp_enabled }" aria-label="启用 MCP" @click="toggleSetting('mcp_enabled')" />
        </div>
        <div class="switch-row">
          <div>
            <strong>允许读取物品</strong>
            <div class="hint">外部 AI 可以查询你的物品。</div>
          </div>
          <button class="switch" :class="{ on: settings.mcp_read_enabled }" aria-label="允许读取物品" @click="toggleSetting('mcp_read_enabled')" />
        </div>
        <div class="switch-row">
          <div>
            <strong>允许写入物品</strong>
            <div class="hint">外部 AI 可以新增、修改或删除物品。</div>
          </div>
          <button class="switch" :class="{ on: settings.mcp_write_enabled }" aria-label="允许写入物品" @click="toggleSetting('mcp_write_enabled')" />
        </div>
        <div class="field config-field">
          <label>配置片段</label>
          <pre class="code">{{ mcpConfigText }}</pre>
        </div>
        <p class="hint">{{ settings.mcp_note }}</p>
        <button class="btn secondary" @click="copyMcpConfig">复制配置</button>
      </div>

      <form class="section" @submit.prevent="changePassword">
        <h3>修改密码</h3>
        <div class="field">
          <label>原密码</label>
          <input v-model="passwordForm.old_password" class="input" type="password" required />
        </div>
        <div class="field">
          <label>新密码</label>
          <input v-model="passwordForm.new_password" class="input" type="password" required />
        </div>
        <div class="actions">
          <button class="btn">保存密码</button>
          <button type="button" class="btn secondary" @click="$emit('logout')">退出登录</button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { authApi, settingsApi } from "../api";

const props = defineProps({
  token: {
    type: String,
    required: true,
  },
});
const emit = defineEmits(["toast", "logout"]);

const settings = ref({
  mcp_enabled: false,
  mcp_read_enabled: true,
  mcp_write_enabled: false,
  mcp_base_url: "",
  mcp_server_command: "",
  mcp_server_args: [],
  mcp_client_config: {},
  mcp_note: "",
  updated_at: "",
});
const passwordForm = ref({ old_password: "", new_password: "" });

const mcpConfigText = computed(() => {
  const template = settings.value.mcp_client_config?.mcpServers
    ? settings.value.mcp_client_config
    : {
        mcpServers: {
          "remember-item": {
            command: "rememberitem-mcp",
            args: [],
            env: {
              REMEMBER_ITEM_BASE_URL: settings.value.mcp_base_url || window.location.origin,
              REMEMBER_ITEM_TOKEN: "<access_token>",
            },
          },
        },
      };
  const config = JSON.parse(JSON.stringify(template));
  const rememberServer = config.mcpServers["remember-item"];
  rememberServer.env = rememberServer.env || {};
  rememberServer.env.REMEMBER_ITEM_TOKEN = props.token || "<access_token>";
  return JSON.stringify(config, null, 2);
});

onMounted(loadSettings);

async function loadSettings() {
  try {
    settings.value = await settingsApi.get(props.token);
  } catch (error) {
    emit("toast", error.message, "error");
  }
}

async function toggleSetting(key) {
  try {
    settings.value = await settingsApi.update({ [key]: !settings.value[key] }, props.token);
    emit("toast", "设置已保存");
  } catch (error) {
    emit("toast", error.message, "error");
  }
}

async function changePassword() {
  try {
    await authApi.changePassword(passwordForm.value, props.token);
    passwordForm.value = { old_password: "", new_password: "" };
    emit("toast", "密码已修改");
  } catch (error) {
    emit("toast", error.message, "error");
  }
}

async function copyMcpConfig() {
  await navigator.clipboard.writeText(mcpConfigText.value);
  emit("toast", "MCP 配置已复制");
}
</script>
