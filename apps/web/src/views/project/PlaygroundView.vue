<script setup lang="ts">
import { ArrowRight, Check, Search, SlidersHorizontal } from "@lucide/vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useWorkspace } from "@/composables/useWorkspace";
const {
  playgroundQuery,
  retrievalMode,
  topK,
  rerank,
  retrievalResults,
  notify,
} = useWorkspace();
</script>

<template>
  <PageHeader
    eyebrow="PROJECT / RETRIEVAL"
    title="检索 Playground"
    subtitle="快速验证知识库召回质量与证据覆盖"
    ><template #action
      ><button
        class="button button-secondary"
        type="button"
        @click="notify('检索参数接口待接入')"
      >
        <SlidersHorizontal :size="16" />参数设置
      </button></template
    ></PageHeader
  >
  <div class="playground-layout">
    <section class="panel playground-query">
      <div class="panel-heading">
        <div>
          <h2>输入问题</h2>
          <p>使用真实业务问题检查检索结果。</p>
        </div>
      </div>
      <textarea v-model="playgroundQuery" rows="5" />
      <div class="playground-controls">
        <label
          >模式<select v-model="retrievalMode">
            <option>Hybrid</option>
            <option>Vector</option>
            <option>Keyword</option>
          </select></label
        ><label
          >Top K<input
            v-model.number="topK"
            type="number"
            min="1"
            max="20" /></label
        ><label class="toggle-label"
          ><input v-model="rerank" type="checkbox" />启用 Rerank</label
        >
      </div>
      <button
        class="button button-primary"
        type="button"
        @click="notify('检索接口待接入')"
      >
        <Search :size="16" />运行检索
      </button>
    </section>
    <section class="panel retrieval-results">
      <div class="panel-heading">
        <div>
          <h2>召回结果</h2>
          <p>{{ retrievalResults.length }} 条结果 · {{ retrievalMode }}</p>
        </div>
      </div>
      <article
        v-for="result in retrievalResults"
        :key="result.rank"
        class="retrieval-card"
      >
        <div class="retrieval-card-top">
          <span class="rank-number">0{{ result.rank }}</span
          ><span class="status-badge status-indexed"
            ><i />{{ result.score }}</span
          >
        </div>
        <h3>{{ result.title }}</h3>
        <small>{{ result.source }}</small>
        <p>{{ result.text }}</p>
        <button
          class="text-button"
          type="button"
          @click="notify('证据详情接口待接入')"
        >
          查看证据 <ArrowRight :size="14" />
        </button>
      </article>
    </section>
  </div>
</template>
