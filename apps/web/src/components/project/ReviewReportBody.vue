<script setup lang="ts">
import { computed } from "vue";
import MarkdownIt from "markdown-it";
import DOMPurify from "dompurify";

const props = defineProps<{ content: string }>();
const markdown = new MarkdownIt({ html: false, linkify: false });
markdown.disable("image");
markdown.renderer.rules.link_open = (tokens, index, options, _env, renderer) => {
  if (!String(tokens[index]!.attrGet("href") || "").startsWith("#")) {
    tokens[index]!.attrSet("target", "_blank");
    tokens[index]!.attrSet("rel", "noopener noreferrer");
  }
  return renderer.renderToken(tokens, index, options);
};
const rendered = computed(() => DOMPurify.sanitize(markdown.render(props.content), { ADD_ATTR: ["target"] }));
</script>

<template>
  <article v-if="content.trim()" class="review-document" v-html="rendered" />
  <p v-else class="review-document-empty">正文为空，请先在报告页补充内容。</p>
</template>

<style scoped>
.review-document { color: var(--workspace-text); font-size: .875rem; line-height: 1.9; overflow-wrap: anywhere; min-width: 0; }
.review-document :deep(h1) { font-size: 1.4rem; line-height: 1.6; margin: 0 0 1.5rem; font-weight: 650; }
.review-document :deep(h2) { font-size: 1.1rem; line-height: 1.6; margin: 1.75rem 0 .85rem; font-weight: 650; }
.review-document :deep(h3) { font-size: .95rem; margin: 1.5rem 0 .75rem; font-weight: 600; }
.review-document :deep(p) { margin: .75rem 0; }
.review-document :deep(ul), .review-document :deep(ol) { padding-left: 1.5rem; margin: .75rem 0; }
.review-document :deep(ul) { list-style-type: disc; }
.review-document :deep(ol) { list-style-type: decimal; }
.review-document :deep(a) { color: var(--teal-dark); text-decoration: underline; text-underline-offset: .2em; }
.review-document :deep(table) { display: block; width: 100%; overflow-x: auto; border-collapse: collapse; margin: 1rem 0; }
.review-document :deep(th), .review-document :deep(td) { padding: .65rem .85rem; border: 1px solid var(--workspace-border); min-width: 5rem; text-align: left; }
.review-document :deep(th) { background: var(--surface-soft); font-weight: 600; }
.review-document :deep(blockquote) { border-left: 3px solid var(--workspace-border); padding-left: 1rem; color: var(--workspace-muted); margin: 1rem 0; }
.review-document :deep(pre) { max-width: 100%; overflow-x: auto; padding: 1rem; background: var(--surface-soft); border-radius: .5rem; }
.review-document :deep(code) { font-size: .8rem; }
.review-document :deep(hr) { margin: 1.5rem 0; border: 0; border-top: 1px solid var(--workspace-border); }
.review-document-empty { color: var(--workspace-muted); font-size: .85rem; padding: 2rem 0; }
@media(max-width:47.5rem) { .review-document { font-size: .8125rem; } .review-document :deep(h1) { font-size: 1.15rem; } }
</style>
