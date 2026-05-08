<template>
  <div v-if="toast" class="toast" :class="toast.type">{{ toast.message }}</div>
</template>

<script setup>
defineProps({
  toast: {
    type: Object,
    default: null,
  },
});
</script>
