# 09. LoRA / QLoRA 微调设计（增强项）

## 1. 定位

LoRA 不是让模型记住企业文档的方式。动态知识使用 RAG；LoRA 用于优化稳定、重复、可量化的任务行为。

本模块不进入 MVP。

## 2. 推荐微调任务

首选：证据支持性判断。

输入：

```json
{
  "question": "订单系统峰值 TPS 是多少？",
  "claim": "峰值 TPS 为 3500。",
  "context": "促销期间订单服务峰值 TPS 约为 3500。"
}
```

输出：

```json
{
  "label": "SUPPORTED",
  "evidenceText": "促销期间订单服务峰值 TPS 约为 3500。"
}
```

标签：

```text
SUPPORTED
PARTIALLY_SUPPORTED
UNSUPPORTED
CONFLICTED
```

## 3. 为什么选择该任务

- 输入输出边界清楚。
- 数据可以从真实运行和人工修正中积累。
- 可以计算 Accuracy、Macro-F1、Conflict Recall。
- 直接服务于 `evaluate_evidence` 和 `review_report`。
- 不要求模型记忆不断变化的企业知识。

## 4. 不推荐的首个任务

- 通用报告生成：评价主观、长文本成本高。
- 把企业全部知识训练进模型：更新困难、不可引用。
- 工具权限决策：必须由代码控制。
- 任意通用 Agent：难以构建可靠训练标签。

## 5. 数据来源

```text
真实 Run
→ 用户接受 / 拒绝
→ 人工修正
→ 审核标签
→ 脱敏和去重
→ 数据集版本
```

正负样本必须覆盖：

```text
直接支持
部分支持
完全无关
直接冲突
数字不同
主体不同
时间范围不同
证据不足
```

## 6. 数据格式

推荐 JSONL：

```json
{"messages":[
  {"role":"system","content":"判断证据是否支持结论，并输出 JSON。"},
  {"role":"user","content":"question: ...\nclaim: ...\ncontext: ..."},
  {"role":"assistant","content":"{\"label\":\"SUPPORTED\",...}"}
]}
```

数据集划分必须按项目或文档分组，不能随机拆分相邻 Chunk，避免泄漏。

## 7. 训练技术栈

```text
Transformers
PEFT
TRL SFTTrainer
Datasets
bitsandbytes（硬件和平台支持时）
QLoRA
```

目录：

```text
training/
├─ prepare_dataset.py
├─ train_qlora.py
├─ evaluate_adapter.py
├─ configs/
├─ datasets/
└─ artifacts/adapters/
```

## 8. 配置示例

```python
LoraConfig(
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    bias="none",
    task_type="CAUSAL_LM",
)
```

目标模块必须依据所选基础模型实际结构确认，不能盲目照抄。

## 9. 对照实验

至少三组：

```text
A 基础模型 + 基础 Prompt
B 基础模型 + 优化 Prompt
C 基础模型 + LoRA Adapter
```

指标：

| 指标 | 目标 |
|---|---|
| Macro-F1 | 比 B 有稳定提升 |
| Conflict Recall | 重点关注冲突识别 |
| JSON Valid Rate | 不低于基线 |
| Citation Match | 引用文本真实存在 |
| Latency | 在可接受范围 |

只有 C 明显优于 B，才能说明微调具有价值。

## 10. 模型注册与推理

`model_versions` 保存：

```text
base_model
adapter_name
adapter_version
task_type
dataset_version
training_config
evaluation_metrics
status
artifact_path
```

Model Router：

```text
EVIDENCE_CLASSIFICATION
→ 优先已启用 LoRA Adapter
→ 加载失败回退基础模型 + Prompt
```

## 11. 安全和隐私

- 训练前删除个人信息、密钥和商业敏感字段。
- 不把未授权工作区数据合并为公共数据集。
- 保存数据来源和审核者。
- Adapter 不随仓库公开上传，除非训练数据允许。

## 12. 完成标准

LoRA 模块只有同时满足以下条件才算完成：

1. 有明确业务任务。
2. 有版本化、人工审核的数据集。
3. 有 Prompt 优化基线。
4. 有独立测试集。
5. 有可重复训练配置。
6. 有业务指标提升，而不只是 Loss 下降。
