<script setup lang="ts">
import { ArrowLeft, CheckCircle2, FileText, ShieldCheck } from "@lucide/vue";
import { useRoute, useRouter } from "vue-router";
import { assets } from "@/data/mock";
const route = useRoute();
const router = useRouter();
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
    <p class="page-subtitle">查看索引详情、切片信息和引用状态。</p>
  </div>
  <div class="asset-detail-grid">
    <section class="panel">
      <div class="asset-detail-preview">
        <span class="file-type large"><FileText :size="24" /></span>
        <h2>{{ asset.name }}</h2>
        <p>{{ asset.type }} · {{ asset.size }} · {{ asset.uploader }}</p>
        <span class="status-badge status-indexed"
          ><i /><CheckCircle2 :size="13" />已索引</span
        >
      </div>
    </section>
    <section class="panel">
      <div class="panel-heading">
        <div>
          <h2>索引摘要</h2>
          <p>当前资产可被 Agent 检索和引用。</p>
        </div>
      </div>
      <div class="detail-facts">
        <div>
          <span>切片数量</span><strong>{{ asset.chunks }}</strong>
        </div>
        <div>
          <span>索引进度</span><strong>{{ asset.progress }}%</strong>
        </div>
        <div>
          <span>最后更新</span><strong>{{ asset.updated }}</strong>
        </div>
      </div>
      <div class="security-note">
        <ShieldCheck :size="17" /><span>项目内资料，仅对工作区成员可见。</span>
      </div>
    </section>
  </div>
</template>
