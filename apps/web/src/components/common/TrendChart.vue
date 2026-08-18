<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { ECharts } from "echarts/core";

type TrendSeries = {
  name: string;
  data: number[];
  color: string;
};

const props = defineProps<{
  labels: string[];
  series: TrendSeries[];
}>();

const chartElement = ref<HTMLDivElement | null>(null);
let chart: ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;
let chartLoader: Promise<typeof import("echarts/core")> | null = null;

function loadChartLibrary() {
  chartLoader ??= Promise.all([
    import("echarts/core"),
    import("echarts/charts"),
    import("echarts/components"),
    import("echarts/renderers"),
  ]).then(([echarts, charts, components, renderers]) => {
    echarts.use([
      charts.LineChart,
      components.GridComponent,
      components.TooltipComponent,
      renderers.CanvasRenderer,
    ]);
    return echarts;
  });
  return chartLoader;
}

async function renderChart() {
  const echarts = await loadChartLibrary();
  if (!chartElement.value) return;
  chart ??= echarts.init(chartElement.value);
  const styles = getComputedStyle(chartElement.value);
  const axisColor = styles.getPropertyValue("--workspace-chart-axis").trim() || "#89979e";
  const gridColor = styles.getPropertyValue("--workspace-chart-grid").trim() || "#edf1f1";
  const surfaceColor = styles.getPropertyValue("--surface").trim() || "#ffffff";
  chart.setOption({
    animationDuration: 450,
    color: props.series.map((item) => item.color),
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(20, 35, 41, 0.94)",
      borderWidth: 0,
      textStyle: { color: "#ffffff", fontSize: 11 },
    },
    grid: { top: 14, right: 14, bottom: 28, left: 36 },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: props.labels,
      axisLine: { lineStyle: { color: gridColor } },
      axisTick: { show: false },
      axisLabel: { color: axisColor, fontSize: 10 },
    },
    yAxis: {
      type: "value",
      min: 0,
      splitNumber: 4,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: axisColor, fontSize: 10 },
      splitLine: { lineStyle: { color: gridColor, type: "dashed" } },
    },
    series: props.series.map((item, index) => ({
      name: item.name,
      type: "line",
      smooth: true,
      symbol: "circle",
      symbolSize: index === 0 ? 6 : 5,
      data: item.data,
      lineStyle: { width: 2, color: item.color },
      itemStyle: { color: item.color, borderWidth: 2, borderColor: surfaceColor },
      areaStyle: index === 0 ? { color: item.color, opacity: 0.12 } : undefined,
    })),
  });
}

onMounted(() => {
  renderChart();
  if (chartElement.value) {
    resizeObserver = new ResizeObserver(() => chart?.resize());
    resizeObserver.observe(chartElement.value);
  }
});

watch(() => [props.labels, props.series], renderChart, { deep: true });

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <div ref="chartElement" class="trend-chart" role="img" aria-label="运行趋势图" />
</template>
