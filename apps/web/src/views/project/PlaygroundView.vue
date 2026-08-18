<script setup lang="ts">
import { ArrowRight, Check, Search, SlidersHorizontal } from "@lucide/vue";
import { ref } from "vue";
import PageHeader from "@/components/common/PageHeader.vue";
import { useWorkspace } from "@/composables/useWorkspace";
import { retrievalModes } from "@/data/mock";
const {
  playgroundQuery,
  retrievalMode,
  topK,
  rerank,
  retrievalResults,
  notify,
} = useWorkspace();
const isSearching = ref(false);
const selectedRank = ref<number | null>(null);

function runSearch() {
  if (!playgroundQuery.value.trim() || isSearching.value) return;
  isSearching.value = true;
  selectedRank.value = null;
  window.setTimeout(() => {
    isSearching.value = false;
    notify(`检索完成，返回 ${retrievalResults.length} 条结果`);
  }, 700);
}

function openParameters() {
  const currentIndex = retrievalModes.indexOf(retrievalMode.value);
  retrievalMode.value = retrievalModes[(currentIndex + 1) % retrievalModes.length]!;
  topK.value = Math.min(20, Math.max(3, topK.value));
  notify(`已切换为 ${retrievalMode.value} 检索`);
}
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
        @click="openParameters"
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
            <option v-for="mode in retrievalModes" :key="mode">{{ mode }}</option>
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
        @click="runSearch"
      >
        <Search :size="16" />{{ isSearching ? "检索中..." : "运行检索" }}
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
        :class="{ selected: selectedRank === result.rank }"
        @click="selectedRank = result.rank"
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
          @click.stop="selectedRank = result.rank"
        >
          查看证据 <ArrowRight :size="14" />
        </button>
      </article>
    </section>
  </div>
</template>
