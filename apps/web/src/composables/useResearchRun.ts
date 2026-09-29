import { computed, onUnmounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { runsApi } from "@/api/runs";
import type { ResearchRun } from "@/api/types";
import { isResearchActive } from "@/utils/researchRun";

export function useResearchRun() {
  const route = useRoute();
  const run = ref<ResearchRun | null>(null);
  const loading = ref(true);
  const error = ref("");
  const lastSynced = ref(0);
  const now = ref(Date.now());
  const active = computed(() => isResearchActive(run.value));
  let timer: ReturnType<typeof setTimeout> | undefined;
  let controller: AbortController | undefined;
  let revision = 0;
  const clock = setInterval(() => { now.value = Date.now(); }, 1000);

  async function refresh() {
    clearTimeout(timer);
    controller?.abort();
    controller = new AbortController();
    const version = ++revision;
    try {
      const detail = await runsApi.detail(String(route.params.workspaceId), Number(route.params.projectId), String(route.params.runId), controller.signal);
      if (version !== revision) return;
      run.value = detail;
      error.value = "";
      lastSynced.value = Date.now();
    } catch (cause) {
      if (version !== revision || controller.signal.aborted) return;
      error.value = cause instanceof Error ? cause.message : "无法获取最新分析状态";
    } finally {
      if (version === revision) {
        loading.value = false;
        if (active.value || error.value || run.value?.runtimeAvailable === false) {
          timer = setTimeout(() => void refresh(), error.value ? 5000 : 2000);
        }
      }
    }
  }

  watch(() => [route.params.workspaceId, route.params.projectId, route.params.runId], () => {
    run.value = null;
    lastSynced.value = 0;
    loading.value = true;
    void refresh();
  }, { immediate: true });

  onUnmounted(() => {
    revision++;
    clearTimeout(timer);
    clearInterval(clock);
    controller?.abort();
  });
  return { run, active, loading, error, lastSynced, now, refresh };
}
