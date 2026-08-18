<script setup lang="ts">
import { ArrowLeft, CheckCircle2, FileText, ShieldCheck } from "@lucide/vue";
import { useRoute, useRouter } from "vue-router";
import { assetDetailCopy, assets } from "@/data/mock";
import { useWorkspace } from "@/composables/useWorkspace";
const route = useRoute();
const router = useRouter();
const { statusClass, statusLabel } = useWorkspace();
const asset =
  assets.find((item) => item.id === String(route.params.assetId)) ?? assets[0]!;
</script>

<template>
  <button class="text-button back-button" type="button" @click="router.back()">
    <ArrowLeft :size="15" />返回知识资产
  </button>
  <div class="page-heading">
    <p class="eyebrow">KNOWLEDGE / ASSET DETAIL</p>
    <h1>{{ asset.name }}</h1>
    <p class="page-subtitle">{{ assetDetailCopy.subtitle }}</p>
  </div>
  <div class="asset-detail-grid">
    <section class="panel">
      <div class="asset-detail-preview">
        <span class="file-type large"><FileText :size="24" /></span>
        <h2>{{ asset.name }}</h2>
        <p>{{ asset.type }} · {{ asset.size }} · {{ asset.uploader }}</p>
        <span class="status-badge" :class="statusClass(asset.status)"
          ><i /><CheckCircle2 :size="13" />{{ statusLabel(asset.status) }}</span
        >
      </div>
    </section>
    <section class="panel">
      <div class="panel-heading">
        <div>
          <h2>{{ assetDetailCopy.summaryTitle }}</h2>
          <p>{{ assetDetailCopy.summaryDescription }}</p>
        </div>
      </div>
      <div class="detail-facts">
        <div>
          <span>{{ assetDetailCopy.chunksLabel }}</span><strong>{{ asset.chunks }}</strong>
        </div>
        <div>
          <span>{{ assetDetailCopy.progressLabel }}</span><strong>{{ asset.progress }}%</strong>
        </div>
        <div>
          <span>{{ assetDetailCopy.updatedLabel }}</span><strong>{{ asset.updated }}</strong>
        </div>
      </div>
      <div class="security-note">
        <ShieldCheck :size="17" /><span>{{ assetDetailCopy.securityNote }}</span>
      </div>
    </section>
  </div>
</template>
