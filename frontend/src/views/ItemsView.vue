<template>
  <section class="view">
    <div class="grid">
      <form class="section" @submit.prevent="saveItem">
        <h3>{{ itemForm.id ? "修改物品" : "添加物品" }}</h3>
        <div class="field">
          <label>名称</label>
          <input v-model.trim="itemForm.name" class="input" required />
        </div>
        <div class="field">
          <label>描述</label>
          <textarea v-model="itemForm.description" class="textarea" />
        </div>
        <div class="field">
          <label>图片</label>
          <input v-model.trim="itemForm.image_url" class="input" placeholder="图片 URL，可选" />
          <label class="btn secondary wide">
            上传图片
            <input type="file" accept="image/*" hidden @change="pickItemImage" />
          </label>
        </div>
        <div class="actions">
          <button type="button" class="btn secondary" @click="resetItemForm">重置</button>
          <button class="btn">{{ itemForm.id ? "保存修改" : "添加" }}</button>
        </div>
      </form>

      <div>
        <div class="section search-section">
          <div class="search-row">
            <input v-model.trim="itemSearch" class="input" placeholder="按名称查找" @keyup.enter="loadItems" />
            <button class="btn secondary" @click="loadItems">查找</button>
          </div>
        </div>
        <div class="item-list">
          <article v-for="item in items" :key="item.id" class="item-card">
            <img v-if="item.image_url" class="item-img" :src="item.image_url" alt="物品图片" />
            <div v-else class="item-img" />
            <div>
              <div class="item-title">{{ item.name }}</div>
              <div class="item-desc">{{ item.description || "暂无描述" }}</div>
            </div>
            <div class="actions">
              <button class="btn secondary" @click="editItem(item)">修改</button>
              <button class="btn danger" @click="deleteItem(item)">删除</button>
            </div>
          </article>
          <div v-if="!items.length" class="section empty item-empty">还没有物品。</div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { itemApi, uploadImage } from "../api";

const props = defineProps({
  token: {
    type: String,
    required: true,
  },
});
const emit = defineEmits(["toast"]);

const itemSearch = ref("");
const itemForm = ref({ id: null, name: "", description: "", image_url: "" });
const items = ref([]);

onMounted(loadItems);

async function loadItems() {
  try {
    items.value = await itemApi.list(itemSearch.value, props.token);
  } catch (error) {
    emit("toast", error.message, "error");
  }
}

async function saveItem() {
  try {
    const payload = {
      name: itemForm.value.name,
      description: itemForm.value.description || null,
      image_url: itemForm.value.image_url || null,
    };
    if (itemForm.value.id) {
      await itemApi.update(itemForm.value.id, payload, props.token);
      emit("toast", "物品已更新");
    } else {
      await itemApi.create(payload, props.token);
      emit("toast", "物品已添加");
    }
    resetItemForm();
    await loadItems();
  } catch (error) {
    emit("toast", error.message, "error");
  }
}

function editItem(item) {
  itemForm.value = {
    id: item.id,
    name: item.name,
    description: item.description || "",
    image_url: item.image_url || "",
  };
}

function resetItemForm() {
  itemForm.value = { id: null, name: "", description: "", image_url: "" };
}

async function deleteItem(item) {
  if (!window.confirm(`确定删除「${item.name}」吗？`)) return;
  await itemApi.delete(item.id, props.token);
  emit("toast", "物品已删除");
  await loadItems();
}

async function pickItemImage(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  try {
    itemForm.value.image_url = await uploadImage(file, props.token);
    emit("toast", "图片已上传");
  } catch (error) {
    emit("toast", error.message, "error");
  }
}
</script>
