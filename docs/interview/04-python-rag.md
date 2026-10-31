# 04. Python 服务、文档处理与混合 RAG

源码重点：apps/ai-service/api/application.py、core/container.py、documents/parser.py、documents/chunker.py、embeddings、rag/milvus_store.py、rag/keyword.py、rag/hybrid.py、rag/reranker.py、rag/cached.py。

## 1. FastAPI 不只是「写几个接口」

### 1.1 入口与生命周期

Docker 通过 uvicorn main:app 启动 ASGI 服务。main.py 为兼容导出 app，并处理 Windows 下 psycopg 异步池的事件循环策略。api/application.py 的 lifespan 构建 ServiceContainer、初始化任务队列并启动 Worker；关闭时释放队列、模型 HTTP 客户端、连接池、MCP、图存储和缓存。

为什么不每次请求建连接？HTTP、数据库和向量客户端通常需要连接复用，反复创建增加握手和资源成本。为什么必须关闭？否则可能留下连接、后台协程、文件句柄和未完成任务。

### 1.2 Pydantic 与依赖注入

Pydantic 校验请求结构、类型、范围和模型输出 Schema。FastAPI dependencies 可以统一验证内部 API Key、从 app.state 取容器，并将模型异常映射成 HTTP 状态。

类型正确不等于业务正确：一个合法的 projectId 可能属于其他工作区；一个合法 Evidence ID 可能不属于本次运行；一个 JSON 格式正确的答案仍可能与证据相反。这些要由作用域校验和语义/规则检查处理。

### 1.3 服务容器的意义

ServiceContainer 根据配置装配 ModelGateway、EmbeddingProvider、Parser、Indexer、Retriever、Storage、GraphStore、ToolRegistry、Repository 和 Runtime。协议/接口隔离使测试可以替换 mock 或内存实现，也让外部 Provider 故障不必改业务调用点。

依赖可替换不代表行为完全相同：内存检索、PostgreSQL 关键词和真实 ANN 的结果、延迟与持久化保证不同，因此需要各自集成验证。

## 2. asyncio、阻塞与并发

### 2.1 async 的真实含义

await 在可等待的 I/O 上让出控制，事件循环才能调度其他协程。同步 Milvus SDK、Office 转换、PDF 解析或同步 Redis 读取如果直接在事件循环执行，可能让全服务响应停顿。

代码使用 asyncio.to_thread 包装多个同步 SDK 操作；它把阻塞工作放到线程，适合 I/O 或释放 GIL 的 native 操作。纯 Python CPU 密集任务仍可能受 GIL 限制，适合进程或独立工作服务。

### 2.2 并发不是越大越好

队列默认 8 个工作协程、工具自身还有 semaphore，Java/AI 数据库各有池。并发预算要覆盖模型限流、HTTP 连接池、内存、CPU 和解析进程。一个任务可能同时做文档解析和模型调用，单纯按「8 个 Worker」估计压力会偏低。

超时取消外层协程不一定停止底层线程、外部转换进程或 Provider 计费。应分别管理任务取消、子进程 timeout、HTTP 关闭和结果提交的终态保护。

### 2.3 当前值得优化的点

DurableRunRepository 写快照通过 to_thread 卸载，但 get 在本地未命中时做同步 Redis get。它是值得检查的潜在事件循环阻塞点，是否成为瓶颈需要压测；不能只因为类名有 Durable 就认定所有路径异步且高性能。

## 3. 文档入库全链路

~~~text
浏览器上传
→ Java 检查身份、工作区/项目、文件大小和类型、配额
→ 业务 MinIO 保存原文件
→ PostgreSQL 保存资产、标记解析/索引状态
→ 事务提交后派发 Python
→ Parser 抽取内容与来源元数据
→ Chunker 切片并计算 checksum
→ Embedding Provider 批量向量化
→ PostgreSQL 写 Chunk / Milvus 写向量
→ 项目检索缓存版本更新
→ Java 标记成功，前端可检索
~~~

每一段都应能回答输入、输出、状态、超时、可重试性和数据位置。入库成功不能只看文件出现在列表里，要看解析结果、Chunk 数、索引状态与可解释检索结果。

## 4. 解析器按格式拆解

| 类型 | 当前工具/路径 | 易被追问的问题 |
| --- | --- | --- |
| TXT / Markdown / 日志 | 解码与文本清理 | 编码检测、换行、控制字符、标题层级 |
| PDF | pypdf 文本提取；无文本页可 Poppler 渲染 + Tesseract | 扫描 PDF 与文本 PDF 区别、多栏顺序、页码、表格损失 |
| DOCX | python-docx 处理段落/表格等 | 列表语义、标题、内嵌图片和布局不等于纯文本 |
| 旧 Office | LibreOffice 转换后解析 | 转换超时、并发用户目录、临时文件与安全隔离 |
| XLSX | openpyxl | 工作表名、行列定位、公式与缓存值、合并单元格 |
| PPTX | python-pptx，图片可 OCR | 幻灯片编号、文本框顺序、图表文本缺失 |
| CSV / JSON | 结构读取与文本化 | 分隔符、嵌套、字段名、超大行、内容展开上限 |
| HTML | BeautifulSoup 等抽取 | 导航噪音、脚本、链接、网页正文边界 |
| 图片 | Pillow / Tesseract | 旋转、分辨率、语言包、空白图与 OCR 误差 |
| 音频 | FFmpeg 预处理 + faster-whisper | 采样、语言、分段、时间位置和模型下载 |
| 视频 | FFprobe/FFmpeg、抽帧 OCR、语音转写 | 抽帧遗漏、长视频成本、音画证据定位 |

当前默认 OCR 语言 chi_sim+eng、PDF 180 DPI、最多 OCR 100 页、视频最多 8 帧、Whisper base/cpu/int8。默认值是成本边界，不表示所有格式都能无损理解。

### 4.1 解析质量如何验证

准备有数字、日期、表格、标题、脚注、扫描页和乱码的固定文件。检查抽取文本是否保持语义及来源页码；OCR 把 0 识别成 O、把小数点漏掉会直接污染后续数字审查。警告应向用户可见，不能用「解析成功」掩盖半数页面为空。

### 4.2 文件处理资源边界

压缩后的 Office 文件可能很小但解压很大，PDF 页数、图像像素、音视频时长与文件字节数并不成正比。除了上传大小，还需要转换时限、页数/帧数/输出字符上限，以及子进程资源隔离。镜像含依赖只说明可用，不证明模型权重已下载或真实转写已通过。

## 5. Chunk：为什么这样切

### 5.1 当前配置

DocumentChunker 默认 chunk_size=1200、overlap=180、strategy=natural、preserve_sections=true；支持 natural、paragraph、fixed。natural 按段落、换行、中文标点、英文句号和空格逐级切分，Markdown 标题可先保留章节边界。

这个 size 当前按字符长度的 splitter 语义理解，不能说是固定 1200 Token。中文、英文和代码的字符/Token 比例不同，最终模型上下文仍要按 Token 预算控制。

### 5.2 长短与 overlap 的取舍

- 太短：上下文丢失，定义、约束和结论分离，结果重复且数量多。
- 太长：检索包含噪音，模型输入昂贵，细粒度事实难定位。
- overlap 保留边界附近信息，但增加向量数、存储和重复召回。
- 标题/页码/表名应随 Chunk 保存，用于检索提示和引用展示。

估算：长度 L 的长文在固定窗口近似下，Chunk 数约为 max(1,ceil((L−overlap)/(size−overlap)))；真实 natural 分割受章节与空白影响，不能把公式当精确计数。

### 5.3 元数据与版本

Chunk 包含正文、序号、页码、章节、起止位置、checksum、parser_version、chunking_version、embedding_model。它们让重建和引用变得可解释。

当前起止位置通过原文 find(content) 得到，重复文本会命中第一次出现，因此精确位置存在边界。这是静态代码可推导的限制；面试可提出保留 splitter 位置或解析结构路径的改进，但不能声称已精确到所有原始格式坐标。

## 6. Embedding：模型、维度与缓存

### 6.1 语义向量是什么

Embedding 将文本映射到向量空间，检索依赖相近语义在该空间内距离较近。常用余弦相似度：cos(q,d)=q·d/(||q||·||d||)。它表示当前模型空间中的接近程度，不是事实正确概率。

文档与查询应使用兼容的模型/版本、归一化和维度。两个模型都输出 1536 维，不意味着可以混在同一个语义空间。

### 6.2 当前默认 hash 的真实行为

HashEmbeddingProvider 用相邻字符片段做确定性哈希并归一化，不是训练过的语义模型。ServiceContainer 基础 Provider 固定使用 hash，只有经过运行配置选择外部 Embedding 时才创建对应 Provider。

MilvusKnowledgeStore 检测模型名以 hash-embedding 开头后，把 VECTOR/HYBRID 的有效模式降为 KEYWORD，避免随机邻居挤掉真实字面证据。面试必须解释这一点，否则演示默认配置时会被误以为实际展示了语义召回质量。

### 6.3 维度与重建

Collection schema 维度固定，启动和请求都会检查配置维度。改变模型、维度或切片方式，需要计划重新生成向量并切换索引；仅改环境变量不会让旧数据自动变成新模型向量。

稳妥扩展是版本化 Collection：新集合后台全量构建、质量验证，再切别名/配置，保留回滚窗口。当前适配器主要是直接重建资产，不应说已实现零停机蓝绿索引。

### 6.4 缓存

CachedEmbeddingProvider 用 model、dimension、文本 SHA-256 做键，查询和文档分开 scope。优点是内容重复时节省外部调用；边界是未显式包含 Provider endpoint/模型修订/租户身份，同名模型在不同服务或版本下不一定输出兼容向量，生产可扩充指纹并评估跨租户缓存政策。

## 7. Milvus 数据结构和查询安全

Collection 主要包含 chunk_id 主键、workspace_id、project_id、asset_id 和 FLOAT_VECTOR。正文不放在返回向量字段中，而是回 PostgreSQL 根据 Chunk ID 读取。

当前 index_type=AUTOINDEX、metric_type=COSINE、consistency_level=Bounded。不能把 HNSW 的 M/efConstruction 或 IVF 的 nlist/nprobe 描述为当前已经手工配置的参数。

查询先用 workspace/project/asset 标量表达式限制 ANN，再在 PostgreSQL 回表时 JOIN 项目并校验范围和资产状态。双层过滤使残留或错误的向量 ID 不直接暴露其他租户正文；它仍需要跨租户负例测试证明每条路径都使用正确范围。

## 8. 关键词通道与中文检索

生产 fetch_keyword_rows：

1. 规范化问题并生成少量查询变体。
2. 提取英文实体词及中文 2/3-gram，限制词数。
3. 先按 workspace/project、索引成功状态、可选 assetIds 缩小 Chunk。
4. 结合 ts_rank_cd 与子串命中长度计算得分。
5. 对用户明确提到的文件名给予定位，并在结果侧进一步约束。
6. 先按相关性排序再 LIMIT，避免较旧但相关的片段被新文件挤掉。

simple 全文配置不是高质量中文分词器；n-gram 提高字面召回但也会引入噪音和扫描成本。当前使用 strpos 对归一化正文检查，使百分号、下划线等按字面处理，也减少多次复杂匹配。

hybrid.py 中的 BM25 用于本地/回退检索，不等同于 PostgreSQL ts_rank_cd。BM25 的核心思想是词频饱和、逆文档频率和长度归一；如果面试要推公式，应先明确是在解释算法还是生产 SQL。

## 9. 混合检索、RRF、重排与多样性

### 9.1 为什么不直接加原始分数

余弦、全文排名和字面匹配的尺度不同，直接相加会让某通道天然占优。当前支持 RRF、加权 RRF、归一化 LINEAR。

加权 RRF 可写为 S(d)=Σ w_i/(k+rank_i(d))。当前默认 rank_constant=60、vector_weight=0.55、keyword_weight=0.45；每通道先去重，保留 channel score/rank。RRF 主要依赖顺序，降低分数尺度不一致的影响，但会损失原始分差。

例：A 向量第 1、关键词第 4，B 两路均第 2，可代入相同参数比较。只在一个通道出现的候选仍有贡献；如果某通道不可用，是否重新归一化权重必须以实现与评估为准。

### 9.2 candidate_k 与 top_k

candidate_k 是候选池，top_k 是最终供给模型或 UI 的数量；当前适配器按 top_k 放大候选并设上限。候选太少，后续重排无法挽回没召回的证据；候选太多，数据库、重排与网络成本增加。

HYBRID 当前并行调用两个通道，各自有超时，以 return_exceptions 收集失败。一条通道失败、另一条确实有结果时可继续；存在失败且两路都没有结果时抛异常，避免把 Provider 故障缓存为「成功但无证据」。显式 VECTOR 模式不能据此承诺自动切关键词，hash 的特殊降级另算。

### 9.3 轻量多样性

diversify_candidates 使用词集合重叠的 MMR 风格选择，降低相邻 Chunk 重复占据结果。相关性先归一化，避免 RRF 的小分值被 0—1 的重复惩罚压倒。

它不是用神经语义向量做标准 MMR 的完整实现。多样性过强可能把最相关的同文档证据挤掉，lambda 应在固定评估集上调。

### 9.4 当前词法 Reranker

LexicalReranker 计算问题词项命中、短语奖励与融合分数；retain_relevant_items 有最低词法相关阈值，并保留明确文件约束的特殊处理。

优势是便宜、确定性、好测试；局限是同义表达和跨语言语义可能被误删。Cross Encoder 可以提高语义判断能力，但增加推理延迟、部署资源和上下文上限，属于适配器扩展。

## 10. 检索缓存与失效

CachedRetriever 键包含工作区、项目、检索 revision、问题、topK、过滤条件、模式、重排、融合参数和 Embedding 信息，并读取项目级版本。索引变化时 bump version，旧键自然不再被命中，TTL 最终回收旧数据。

缓存正确性要问：权限变化是否失效？外部 Provider 指纹是否完整？query_variants 等输入是否都纳入？同一问题但不同用户数据范围是否一定相同？不能只说「用了 Redis 所以性能高」。

版本化减少按通配扫描删除缓存的成本，但版本号丢失、回退到本地缓存及多进程更新仍要验证一致性。缓存降级不应扩大权限或把未知数据当成已验证证据。

## 11. 引用与事实校验

### 11.1 至少拆成四层

1. 引用 ID 是否存在。
2. 引用是否属于本工作区、项目、本次可用证据集合。
3. Quote 是否真实出现在对应 Chunk 中。
4. 这段 Quote 是否真的支持该断言，时间、主体、单位和条件是否匹配。

rag/citation.py 只负责一种引用 ID 存在性检查；不能凭它声称四层全完成。DecisionEngine、Reviewer 与业务审查在不同路径有额外检查，面试要指出具体入口。

### 11.2 模型复核与确定性门禁

apply_review_guards 在模型审查后检查无效引用、缺引用、低词法支撑、证据中没有出现的数字和外部来源标注，并可阻断发布。

这些规则是有用的下限，但词重叠不等于语义蕴含，数字出现在证据集合中不等于属于同一事实。日期、编号可能被误当成数字事实，允许的计算结果也需要计算收据而非简单集合包含。应通过标注样本评估误报、漏报。

## 12. 重建与一致性窗口

当前 Milvus index 顺序大致是：生成全部向量 → 删除资产旧向量 → 在 PostgreSQL 删除旧 Chunk 并写新 Chunk 后提交 → 插入 Milvus 新向量 → 必要时 flush。

它便于失败后重新执行，但存在旧结果不可用窗口；PG 提交而向量失败时不是原子回滚。新 Chunk ID 还可能影响旧引用，所以历史报告若需要稳定回看，应保留证据快照或版本化 Chunk。

改进方案：引入 asset_version/index_version；先写新版本 Chunk/向量，验证后在业务库切 active version，再异步清旧版本。查询与缓存都携带版本。需要同时考虑删除和索引任务并发，防止已删除资产被迟到任务重新写回。

## 13. RAG 质量排查顺序

1. 原文是否正确解析，目标页是否漏 OCR？
2. 关键事实是否被切断，标题是否丢失？
3. 资产是否成功索引、模型是否仍为 hash？
4. 查询范围和文件约束是否过窄或错误？
5. 关键词与向量各自能否召回？
6. 融合、重排、阈值和多样性在哪一步丢掉证据？
7. 上下文预算是否截掉关键证据？
8. 模型是否忽略条件、捏造引用或数字？

把检索错误、解析错误和生成错误分开统计；不能用「换个大模型」回答所有失败。

## 14. FastAPI 官方补充：同步辅助函数不会自动卸载

FastAPI 调用普通 def 路由或依赖时可在线程池执行；但从 async 路由里直接调用自己的 def 辅助函数，仍按普通 Python 调用运行，不会自动变成线程池任务。见 [FastAPI 异步技术细节](https://fastapi.tiangolo.com/async/#other-utility-functions)。

所以 parser.parse_bytes、同步 Milvus SDK、文件转换都要沿调用点检查，而不是只看函数有没有 async。当前 index_bytes 对解析和切片使用 to_thread，Milvus 也显式卸载多个 SDK 调用；下一步应测实际事件循环延迟，确认其他同步路径是否造成阻塞。

Python 3.11 的 TaskGroup 倾向于在子任务失败后取消其他任务，而 gather(return_exceptions=True) 允许收集独立结果；CancelledError 应清理后通常继续传播。两路检索允许部分成功，因而不能机械替换并发原语。依据 [Python 3.11 协程与任务](https://docs.python.org/3.11/library/asyncio-task.html)。

## 15. Schema、连接上下文与后台任务的边界

### 15.1 Pydantic 默认可能做类型转换

「模型有 int 字段」不一定等于「字符串数字被拒绝」；需要按字段、调用或模型选择 strict 行为，且 JSON 输入与 Python 对象校验仍有差异。参考 [Pydantic Strict Mode](https://pydantic.dev/docs/validation/latest/concepts/strict_mode/)。

项目练习：对 Run ID、topK、布尔开关输入字符串、空值、超范围数和额外字段，分别记录接受、转换和拒绝；再检查应用是否依赖了这种转换。严格化是协议变更，不能一键开启后默认所有客户端兼容。

### 15.2 拿到池连接不意味着没有事务

psycopg 的 pool.connection 上下文在正常结束时提交、异常时回滚已有事务并归还连接。若把模型等待放在上下文里，就可能长时间占连接/事务；应把查询结果物化后及时退出。依据 [psycopg 连接池](https://www.psycopg.org/psycopg3/docs/advanced/pool.html)。当前网页包含后续开发版本内容，实际可用参数仍须以已安装 psycopg/psycopg_pool 版本核对。

### 15.3 BackgroundTasks 不等于持久任务队列

FastAPI BackgroundTasks 适合响应后的同进程工作；重任务、跨进程与恢复需求要另外组织队列和 Worker，见 [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)。当前项目采用 Redis Streams 处理研究任务，但仍需核对认领、幂等和保留策略，不能由「使用队列」推导出完整恢复保证。

## 16. 从论文到项目：不照搬结论

RRF 原论文基于排名的倒数求和，并在其实验中选择 k=60；这是默认参数的研究背景，不是所有中文企业语料的最优保证。项目的通道权重、候选上限和词法重排属于进一步工程选择，需要单独评估。见 [Cormack 等：RRF，SIGIR 2009](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf)。

原始 RAG 研究把参数化生成与外部检索记忆结合；本项目使用的是文档处理、检索、模型与引用校验组成的工程链，不能说已复现原论文训练方法，也不能把其基准收益写到本项目简历。见 [Lewis 等：RAG，2020](https://arxiv.org/abs/2005.11401)。

建议做一次消融实验：固定语料/问题/模型/预算，依次跑关键词、向量、融合、融合+重排；分别记录 Recall、引用支持、无答案误答、延迟和成本。这样能指出哪一个模块确实有贡献，哪一个只是增加复杂度。
