<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { ECharts } from "echarts/core";
import { useTheme } from "@/composables/useTheme";

export type TokenUsageChartItem = {
  label: string;
  detail?: string;
  tokens: number;
};

const props = defineProps<{ items: TokenUsageChartItem[] }>();
const { isDark } = useTheme();
const chartElement = ref<HTMLDivElement | null>(null);
const chartHeight = computed(() => `${Math.max(240, props.items.length * 46)}px`);
let chart: ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;
let chartLoader: Promise<typeof import("echarts/core")> | null = null;
let renderVersion = 0;

function loadChartLibrary() {
  chartLoader ??= Promise.all([
    import("echarts/core"),
    import("echarts/charts"),
    import("echarts/components"),
    import("echarts/renderers"),
  ]).then(([echarts, charts, components, renderers]) => {
    echarts.use([
      charts.BarChart,
      components.GridComponent,
      components.TooltipComponent,
      renderers.CanvasRenderer,
    ]);
    return echarts;
  });
  return chartLoader;
}

async function renderChart() {
  const version = ++renderVersion;
  const echarts = await loadChartLibrary();
  if (!chartElement.value || version !== renderVersion) return;
  chart ??= echarts.init(chartElement.value);
  const styles = getComputedStyle(chartElement.value);
  const axisColor = styles.getPropertyValue("--workspace-chart-axis").trim() || "#89979e";
  const gridColor = styles.getPropertyValue("--workspace-chart-grid").trim() || "#edf1f1";
  const textColor = styles.getPropertyValue("--workspace-text").trim() || "#27383d";
  const surfaceColor = styles.getPropertyValue("--surface").trim() || "#ffffff";
  const items = [...props.items].reverse();
  chart.setOption({
    animationDuration: 350,
    grid: { top: 8, right: 18, bottom: 24, left: 112 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      backgroundColor: "rgba(20, 35, 41, 0.94)",
      borderWidth: 0,
      textStyle: { color: "#ffffff", fontSize: 12 },
      formatter: (params: Array<{ name: string; value: number }>) => {
        const point = params[0];
        const source = [...props.items].find((item) => item.label === point?.name);
        return `${point?.name || ""}<br/>${source?.detail ? `${source.detail}<br/>` : ""}${Number(point?.value || 0).toLocaleString("zh-CN")} tokens`;
      },
    },
    xAxis: {
      type: "value",
      min: 0,
      axisLine: { lineStyle: { color: gridColor } },
      axisTick: { show: false },
      axisLabel: { color: axisColor, fontSize: 12 },
      splitLine: { lineStyle: { color: gridColor, type: "dashed" } },
    },
    yAxis: {
      type: "category",
      data: items.map((item) => item.label),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: textColor, fontSize: 12, width: 96, overflow: "truncate" },
    },
    series: [{
      type: "bar",
      data: items.map((item) => item.tokens),
      barMaxWidth: 18,
      itemStyle: { color: "#10b99a", borderRadius: [0, 5, 5, 0], borderColor: surfaceColor, borderWidth: 0 },
    }],
  });
}

onMounted(() => {
  void renderChart();
  if (chartElement.value) {
    resizeObserver = new ResizeObserver(() => chart?.resize());
    resizeObserver.observe(chartElement.value);
  }
});

watch([() => props.items, isDark], () => void renderChart(), { deep: true });

onBeforeUnmount(() => {
  renderVersion += 1;
  resizeObserver?.disconnect();
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <div
    ref="chartElement"
    class="token-usage-chart"
    :style="{ height: chartHeight }"
    role="img"
    aria-label="按项目、用户和模型统计的 Token 使用柱状图"
  />
</template>
