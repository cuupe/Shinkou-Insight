<script setup lang="ts">
import { RouterView } from "vue-router";
import Sidebar from "@/components/navigation/Sidebar.vue";
import Topbar from "@/components/navigation/Topbar.vue";
</script>

<template>
  <div class="app-shell">
    <Sidebar />
    <section class="app-content">
      <Topbar />
      <main class="page-content"><RouterView /></main>
    </section>
  </div>
</template>

