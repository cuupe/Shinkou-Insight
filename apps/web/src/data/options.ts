export type AssetStatus = "indexed" | "indexing" | "failed";

export const assetTabs = ["全部", "已索引", "处理中", "失败"] as const;

export const assetDetailCopy = {
  subtitle: "查看索引详情、切片信息和引用状态。",
  summaryTitle: "索引摘要",
  summaryDescription: "当前资料可被 Agent 检索和引用。",
  chunksLabel: "切片数量",
  progressLabel: "索引进度",
  updatedLabel: "最后更新",
  securityNote: "项目内资料，仅对工作区成员可见。",
};

export const timezoneOptions = [
  { value: "Asia/Shanghai", label: "中国标准时间（UTC+8）" },
  { value: "America/New_York", label: "美国东部时间（UTC-5）" },
  { value: "UTC", label: "协调世界时（UTC）" },
];
