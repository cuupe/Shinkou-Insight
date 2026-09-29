# 06. RAG 设计

## 1. 目标

RAG 的任务不是替代模型，而是为模型提供可验证的项目资料。

```text
问题
→ 检索真实文档片段
→ 组织上下文
→ LLM 基于证据回答
→ 返回可点击引用
```

## 2. 不使用 RAG 的场景

- 登录和权限。
- 普通项目 CRUD。
- 精确状态查询。
- 报告分页。
- 金额、计数等严格数据库计算。

## 3. 入库流水线

```text
原始文件
→ 类型检测
→ 文本解析
→ 清洗和结构识别
→ Chunk 切分
→ Chunk 元数据
→ Embedding
→ PostgreSQL Chunk 元数据 + Milvus 向量索引
→ 索引状态更新
```

### 3.1 Parser

MVP：

- PDF：保留页码，优先文本型 PDF。
- Markdown：保留标题层级和代码块边界。
- TXT：按段落处理。

后续：DOCX、HTML、OCR PDF。

OCR 不进入首版，避免质量和依赖复杂度。

### 3.2 清洗

- 统一换行和空白。
- 删除重复页眉页脚。
- 保留标题、列表和表格文本。
- 不删除可能影响语义的数字、单位和否定词。
- 为每次清洗策略记录 `parser_version`。

### 3.3 Chunk 策略

MVP 建议：

```text
目标 500～800 Tokens
重叠 80～120 Tokens
优先按标题、段落和句子边界切分
超长表格或代码块单独处理
```

Chunk 元数据：

```text
asset_id
chunk_index
page_number
section_title
start_offset / end_offset
parser_version
chunking_version
checksum
```

不同文档类型可使用不同 Chunker，但统一输出 Schema。

## 4. Embedding

`EmbeddingProvider` 接口：

```python
class EmbeddingProvider(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, text: str) -> list[float]: ...
```

要求：

- 记录模型名称和维度。
- 维度变更必须新建列、表或重建索引，不能混存。
- 批量调用需要限流、重试和断点进度。
- 文档未变化不重复 Embedding。

## 5. 检索策略

### 5.1 Vector Search

使用余弦距离或与模型推荐一致的度量。Milvus filter 必须包含：

```sql
workspace_id == :workspaceId and project_id == :projectId
```

Milvus 只返回 `chunk_id` 和相似度；AI 服务使用 `chunk_id` 回查 PostgreSQL，补齐原文、文件名、页码和标题。这样向量库不会成为引用事实源。

### 5.2 Keyword Search

使用 PostgreSQL Full Text Search 或简化关键词搜索，补偿：

- 型号、接口名、缩写。
- 数字和精确术语。
- 向量模型不敏感的专有名词。

PostgreSQL 关键词通道先按工作区、项目、资产和成功索引状态过滤，再对每个片段做一次小写归一化，使用字面子串匹配中文 2/3-gram 和英文术语。按命中词长度加权覆盖率与全文检索分数排序后再截取候选，避免所有中文命中统一记为 `0.1`，使弱相关片段挤掉目标原文。无需重新索引或变更数据库结构。

### 5.3 Hybrid Fusion

建议首版使用 Reciprocal Rank Fusion：

```text
vector candidates
+ keyword candidates
→ 去重
→ RRF 融合
→ Top N
```

不要依赖未经归一化的分数直接相加。

向量与关键词通道并发执行，各自使用知识库工具总超时的 65% 作为检索预算（默认约 3.9 秒），其余时间留给缓存与融合。一条通道失败或超时时，保留另一条通道已有的结果；失败且无可用结果时返回错误，不把故障缓存成“资料不存在”。显式向量模式仍报告向量错误，关键词模式不依赖 Embedding 服务或维度。

聊天中的事实查询先检查项目资料。启用联网搜索后，同时查询可核验的网页，并在回答中区分项目资料和外部来源；网页只接受通过主题匹配、正文和时间校验的页面，不把搜索摘要当作证据。联网未启用时只报告项目资料的检索结果，资料或网页没有命中不构成相关人物、事件或奖项不存在的证明。检索失败、没有结果与资料互相矛盾时分别报告实际状态。

### 5.4 Reranker

流程：

```text
召回 20～30 条
→ Reranker
→ 取 5～8 条进入 LLM
```

MVP 可以先不启用远程 Reranker，但接口和评估要预留。

## 6. Query Rewrite

仅在以下情况启用：

- 用户问题非常宽泛。
- 需要拆成多个事实查询。
- 第一次召回质量不足。

输出必须结构化：

```json
{
  "queries": [
    {"text": "订单系统峰值消息吞吐量", "intent": "INTERNAL_FACT"}
  ]
}
```

最大查询数量由代码限制，不由 Prompt 自由决定。

## 7. 上下文组装

每个上下文块使用统一格式：

```text
[E1]
asset: 业务流量说明.pdf
page: 8
section: 峰值流量
content: ...
```

规则：

- 不将检索分数暴露为事实置信度。
- 控制总 Token 预算。
- 去除高度重复 Chunk。
- 同一文档连续 Chunk 可合并，但保留原始 ID。

## 8. 引用设计

回答结构：

```json
{
  "answer": "... [E1]",
  "claims": [
    {
      "text": "峰值 TPS 约为 3500",
      "evidenceIds": ["E1"]
    }
  ],
  "citations": []
}
```

服务端校验：

1. 引用的 Evidence ID 真实存在。
2. Evidence 属于当前 Run、Workspace 和 Project。
3. 内部 Evidence 的 quote 出现在对应 Chunk 中。
4. 报告不允许引用被删除资产。

## 9. Prompt Injection 防护

文档内容是不可信数据。检索到的文本可能包含：

```text
忽略系统指令
泄露其他项目数据
调用某个工具
输出密钥
```

防护：

- System Prompt 明确资料只是数据，不是指令。
- 工具调用权限不由文档内容决定。
- 不把敏感配置放入模型上下文。
- 检索结果和用户指令分隔标记。
- 高风险工具要求人工确认。
- 对外网页内容同样按不可信输入处理。

## 10. RAG 评估

### 10.1 检索指标

```text
Hit Rate@K
Recall@K
MRR
NDCG（可选）
目标 Chunk 排名
无关 Chunk 比例
```

### 10.2 生成指标

```text
引用正确率
引用覆盖率
无证据事实率
拒答正确率
答案关键点覆盖率
```

### 10.3 测试数据

至少 20～30 个问题：

- 精确事实。
- 多文档综合。
- 同义表达。
- 数字和时间。
- 文档中没有答案。
- 冲突资料。

## 11. MVP 验收

- 三种文档格式成功入库。
- 每个 Chunk 有来源和页码/标题信息。
- 检索 Playground 可解释向量、关键词和融合结果。
- 跨工作区 Chunk 永远不会返回。
- 普通 RAG 支持引用和资料不足提示。
- 离线评估可以一条命令重复运行。

## 12. 上传与检索故障处理

- 上传和重新索引在数据库事务提交后才派发 Python 索引请求，避免资料记录尚不可见时插入片段。
- 解析使用存储路径中的原文件名，资料显示名称可以不带扩展名。空白文件不能标记为索引成功；重新索引不会在解析前删除旧片段。
- Java 索引等待时限由 `SHINKOU_AI_INDEXING_TIMEOUT_SECONDS` 控制，默认 600 秒；普通知识库请求为 90 秒。前端上传等待 120 秒、检索等待 95 秒，上传接口返回后由资料列表轮询索引状态。
- Python 的 MinIO 连接超时为 5 秒，读取超时为 60 秒，连接失败最多重试两次。原文件缺失返回 404；存储不可用返回 503，资料列表保留可操作的错误原因。
- 检索接口统一转换检索器返回的证据类型，首次查询和缓存命中均按同一响应结构输出。Playground 区分未查询、查询无结果和请求失败，并提供失败重试。
- Windows 本地开发若 Docker 已健康但连接 `localhost` 长时间等待，可将本地 `.env` 中的 `MINIO_ENDPOINT`、`SHINKOU_MINIO_ENDPOINT`、`DATABASE_URL` 主机改为 `127.0.0.1` 后重启服务。容器内仍使用 Compose 服务名，不能改成容器自己的回环地址。

回归测试覆盖事务提交与回滚、超过 10 秒的索引响应、显示名称无扩展名、空文本、存储断开、原文件缺失、三种检索模式及缓存返回。真实基础设施联调用合成资料验证 MinIO → 解析切分 → PostgreSQL/Milvus → 检索，并在结束后清理测试数据。
