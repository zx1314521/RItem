<template>
  <section class="view chat-page">
    <div class="chat-workspace">
      <aside class="conversation-pane">
        <div class="conversation-header">
          <strong>对话</strong>
          <button class="btn secondary compact" @click="createConversation">新建</button>
        </div>
        <div class="conversation-list">
          <button
            v-for="thread in threads"
            :key="thread.thread_id"
            class="conversation-item"
            :class="{ active: thread.thread_id === activeThreadId }"
            @click="selectThread(thread.thread_id)"
          >
            <span>{{ thread.title }}</span>
            <small>{{ formatTime(thread.updated_at) }}</small>
          </button>
          <div v-if="!threads.length" class="conversation-empty">还没有对话</div>
        </div>
      </aside>

      <div class="chat-view">
        <div class="toolbar">
          <div class="hint">{{ activeThreadTitle }}</div>
          <div class="actions">
            <button class="btn ghost" :disabled="!chatMessages.length" @click="clearChat">清空</button>
            <button class="btn ghost" :disabled="!activeThreadId" @click="deleteConversation">删除对话</button>
          </div>
        </div>

        <div ref="messagesBox" class="messages">
          <div v-if="!chatMessages.length" class="empty">
            <div>
              <strong>可以直接问 AI，也可以让 AI 帮你新增、查询、修改物品。</strong><br />
              例如：帮我记住蓝牙耳机在书桌第二层抽屉。
            </div>
          </div>
          <div
            v-for="(message, index) in chatMessages"
            :key="index"
            class="message"
            :class="message.role"
          >
            <div
              v-if="message.role === 'assistant'"
              class="bubble markdown-body"
              v-html="renderMarkdown(message.content)"
            />
            <div v-else class="bubble">{{ message.content }}</div>
          </div>
        </div>

        <div class="chat-input">
          <img v-if="chatImagePreview" class="preview-img" :src="chatImagePreview" alt="待发送图片" />
          <div class="chat-row">
            <label class="btn secondary">
              上传图片
              <input type="file" accept="image/*" hidden @change="pickChatImage" />
            </label>
            <textarea
              v-model="chatInput"
              class="textarea"
              placeholder="输入对话内容，回车发送，Ctrl+回车换行"
              @keydown.enter.exact.prevent="sendChat"
            />
            <button class="btn" :disabled="!chatInput.trim() && !chatImageUrl" @click="sendChat">发送</button>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from "vue";
import { chatApi, uploadImage } from "../api";
import { renderMarkdown } from "../utils/markdown";

const props = defineProps({
  token: {
    type: String,
    required: true,
  },
});
const emit = defineEmits(["toast"]);

const threads = ref([]);
const activeThreadId = ref("");
const chatMessages = ref([]);
const chatInput = ref("");
const chatImageUrl = ref("");
const chatImagePreview = ref("");
const messagesBox = ref(null);

const activeThreadTitle = computed(() => {
  const active = threads.value.find((thread) => thread.thread_id === activeThreadId.value);
  return active?.title || "新对话";
});

onMounted(async () => {
  await loadThreads();
  if (!activeThreadId.value) {
    await createConversation();
  }
});

async function loadThreads() {
  try {
    threads.value = await chatApi.listThreads(props.token);
    if (threads.value.length && !threads.value.some((thread) => thread.thread_id === activeThreadId.value)) {
      await selectThread(threads.value[0].thread_id);
    }
  } catch (error) {
    emit("toast", error.message, "error");
  }
}

async function createConversation() {
  try {
    const thread = await chatApi.createThread("新对话", props.token);
    threads.value = [thread, ...threads.value.filter((item) => item.thread_id !== thread.thread_id)];
    await selectThread(thread.thread_id);
  } catch (error) {
    emit("toast", error.message, "error");
  }
}

async function selectThread(threadId) {
  activeThreadId.value = threadId;
  await loadMessages();
}

async function loadMessages() {
  if (!activeThreadId.value) return;
  try {
    const data = await chatApi.getMessages(activeThreadId.value, props.token);
    chatMessages.value = data.messages || [];
    await scrollMessages();
  } catch (error) {
    emit("toast", error.message, "error");
  }
}

async function clearChat() {
  if (!activeThreadId.value) return;
  await chatApi.clearMessages(activeThreadId.value, props.token);
  chatMessages.value = [];
  emit("toast", "对话已清空");
}

async function deleteConversation() {
  if (!activeThreadId.value) return;
  if (!window.confirm(`确定删除「${activeThreadTitle.value}」吗？`)) return;

  try {
    await chatApi.deleteThread(activeThreadId.value, props.token);
    threads.value = threads.value.filter((thread) => thread.thread_id !== activeThreadId.value);
    chatMessages.value = [];
    activeThreadId.value = "";
    if (threads.value.length) {
      await selectThread(threads.value[0].thread_id);
    } else {
      await createConversation();
    }
    emit("toast", "对话已删除");
  } catch (error) {
    emit("toast", error.message, "error");
  }
}

async function sendChat() {
  const text = chatInput.value.trim();
  if (!text && !chatImageUrl.value) return;
  if (!activeThreadId.value) {
    await createConversation();
  }

  chatMessages.value.push({
    role: "user",
    content: chatImageUrl.value ? `${text}\n[图片] ${chatImageUrl.value}` : text,
  });

  chatInput.value = "";
  const imageUrl = chatImageUrl.value;
  chatImageUrl.value = "";
  chatImagePreview.value = "";
  chatMessages.value.push({ role: "assistant", content: "" });
  await scrollMessages();

  try {
    const response = await fetch("/api/v1/chat/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${props.token}`,
      },
      body: JSON.stringify({
        message: text || "请根据这张图片帮我记录或分析物品",
        image_url: imageUrl || null,
        thread_id: activeThreadId.value,
      }),
    });
    if (!response.ok || !response.body) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || "对话请求失败");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    const last = chatMessages.value[chatMessages.value.length - 1];
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      last.content += decoder.decode(value, { stream: true });
      await scrollMessages();
    }
    if (!last.content.trim()) last.content = "我没有收到可显示的回复。";
    await loadThreads();
  } catch (error) {
    chatMessages.value[chatMessages.value.length - 1].content = error.message;
  }
}

async function pickChatImage(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  chatImagePreview.value = URL.createObjectURL(file);
  try {
    chatImageUrl.value = await uploadImage(file, props.token);
    emit("toast", "图片已上传");
  } catch (error) {
    chatImagePreview.value = "";
    emit("toast", error.message, "error");
  }
}

async function scrollMessages() {
  await nextTick();
  if (messagesBox.value) messagesBox.value.scrollTop = messagesBox.value.scrollHeight;
}

function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
</script>
