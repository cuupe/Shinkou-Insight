# 01. 前端、浏览器与实时交互

本章围绕「用户在页面上发起一次研究，到看到可追溯结果」拆解。源码基准：apps/web/package.json、src/main.ts、src/router/index.ts、src/api、src/composables、src/utils/request.ts、src/utils/agentStream.ts、nginx.conf。

## 1. 技术栈与职责

| 技术 | 在本项目的作用 | 必须理解的原理 |
| --- | --- | --- |
| Vue 3 | 页面、组件和响应式更新 | 依赖收集、触发更新、组件生命周期 |
| TypeScript | API 类型、事件联合类型、组件约束 | 编译期检查与运行时校验的区别 |
| Vite | 本地开发、模块转换、生产构建 | 开发服务与静态部署的区别 |
| Vue Router | 工作区、项目和页面导航 | History 模式、嵌套路由、守卫 |
| Axios | JSON/上传请求、Cookie、CSRF 和错误处理 | 拦截器、超时、取消与业务错误 |
| Composition API | 业务状态和可复用逻辑 | ref、computed、watch、作用域和清理 |
| Tailwind / shadcn-vue / Reka UI | 样式与可访问交互组件 | 语义结构、键盘焦点、组件状态 |
| Markdown-it / KaTeX / Shiki / DOMPurify | 文本、公式、代码和 HTML 清洗 | 不可信内容的渲染边界与性能 |
| ECharts | 统计图表 | 实例生命周期、resize、dispose |

package 声明 Vue ^3.5.40、TypeScript ~6.0.0、Vite ^8.1.5、Router ^5.2.0；这些是声明范围，精确安装结果要看 lockfile。不要只凭习惯把 Router 说成 v4。当前 main.ts 只安装 router，业务没有体现全面使用 Pinia，也没有 TanStack Query。

## 2. 浏览器访问系统经过什么

### 2.1 从输入地址到首页

1. 浏览器解析 URL；远程域名需要 DNS，localhost 主要走本机解析。
2. 建立 TCP；HTTPS 还需要 TLS 协商和证书校验。当前 Compose Nginx 仅监听 HTTP 80，TLS 终止是上线扩展方案。
3. Nginx 返回 index.html，浏览器加载 JS、CSS、字体等资源。
4. HTML 形成 DOM，CSS 形成样式规则；脚本执行创建 Vue 应用并挂载。
5. Vue Router 根据地址匹配页面，组合函数加载项目和用户数据。
6. 浏览器进行布局、绘制、合成。网络完成不等于页面可交互，要考虑脚本执行和渲染时间。

静态资源缓存可用内容哈希提高命中率，但 index.html 应便于及时更新，否则用户拿到旧页面引用已删除的脚本。仓库 Nginx 没有显式实现完整的静态缓存策略，面试时作为优化方案说明。

### 2.2 为什么 /api 代理

浏览器请求 /api/auth/me。开发时 Vite 去掉 /api，转给 localhost:8080/auth/me；容器部署由 Nginx 以带尾斜杠的 proxy_pass 完成同样改写。

同源取决于协议、主机、端口。浏览器看到同源 /api，通常不需要因 Java 的容器地址而跨域；代理在服务端连接 backend:8080。直接从浏览器访问另一个端口则是跨源，CORS 和 Cookie 条件要重新分析。

追问：changeOrigin 是什么？它调整代理发往目标的 Host 行为，不会让浏览器放弃同源策略，更不构成后端权限控制。

## 3. JavaScript / TypeScript 基础如何落到项目

### 3.1 事件循环与异步

网络请求等待期间，主线程可以处理输入和渲染；Promise 后续逻辑在微任务中执行，定时器回调属于后续任务。async/await 改变代码组织，不会把 CPU 密集工作自动放到另一线程。

与项目有关的例子：大段 Markdown 解析、代码高亮和图表初始化仍可能阻塞主线程；把它们包进 async 函数并不能解决卡顿。可选方案是减少计算、缓存结果、增量渲染，或把适合的纯计算转到 Web Worker。

### 3.2 Promise 并发与顺序

- 独立的统计和通知请求可并发；需要先创建项目再上传资料的操作必须顺序执行。
- Promise.all 任一失败会使整体拒绝，但其他请求不会自动取消。
- Promise.allSettled 适合允许部分页面模块失败的场景。
- 串行 await 会放大相互独立请求的总耗时；无界并发则会冲击后端和连接池。

### 3.3 类型不能替代数据校验

接口写成 Promise<Report> 不意味着响应一定符合 Report；类型在编译后消失。后端结构化输出由 Pydantic 校验，前端仍需处理空值、未知状态、错误事件和格式异常。

事件适合用带 type 判别字段的联合类型。例如 run.completed、run.failed、message.replace 具有不同字段，渲染层通过 type 缩小类型范围。不要到处使用 any 或强制断言来掩盖协议变化。

### 3.4 ID 精度是跨语言问题

PostgreSQL BIGINT 和 Java long 可能超过 JavaScript Number 的安全整数上限 2^53−1。工作区、项目、事件等大 ID 应作为字符串传输、保存和比较；确实要比较大小时可使用 BigInt，不能先 JSON 解析成已经损失精度的 Number 再转字符串。

agentStream.ts 用 BigInt 比较事件游标，说明团队已考虑游标精度。但仍需检查后端每种 JSON 响应的大 ID 序列化策略，不能由一个比较点推断所有接口都完全解决精度问题。

## 4. Vue 响应式与组件设计

### 4.1 ref、reactive、computed、watch

| API | 适合什么 | 常见误用 |
| --- | --- | --- |
| ref | 单值、数组、需要整体替换的状态 | 在脚本中忘记 .value |
| reactive | 一组相关的对象字段 | 解构字段后丢失响应式连接 |
| computed | 从已有状态推导过滤列表、按钮能力 | 在 getter 里请求接口或修改源状态 |
| watch | workspaceId 改变后加载数据等副作用 | 深度监听大对象，造成多余请求 |
| shallowRef | 不需要深层追踪的外部实例、大对象 | 修改内部字段却期待自动触发更新 |

Vue 通过响应式依赖建立数据与视图的关系，DOM 更新会批量调度。修改状态后需要读取更新后的布局，可等待 nextTick。这个机制可对照 [Vue 响应式基础](https://vuejs.org/guide/essentials/reactivity-fundamentals.html)。

### 4.2 为什么 composables

useAuth 管认证交互，useWorkspace 管上下文，useAgentWorkspace 管消息和运行，useResearchRun 管研究状态，useActionWorkflow 管行动项。组合函数让模板主要负责展示，使请求、状态迁移和清理可复用。

需要继续解释状态作用域：函数内部的 ref 通常每次调用独立；模块顶层 ref 会被所有调用者共享。共享是设计选择，需要在用户登出或工作区切换时清空，防止旧用户、旧项目的内容短暂闪现。

Pinia 的适用场景是跨页面共享、需要明确 action/getter 和调试跟踪的业务状态；本项目目前不能用「用 Pinia 统一管理全部状态」来概括。

### 4.3 生命周期清理

页面离开时应清理定时器、EventSource、AbortController、DOM 监听和图表实例。关闭连接能减少资源泄漏，但如果业务要求后台继续运行，前端清理不应等同于调用后端取消任务。

useResearchRun 已使用 AbortController、定时刷新与 onUnmounted 清理。应分别验证：路由离开后不再写旧页面状态；重新进入时能从持久化快照恢复；取消操作才改变服务端运行状态。

## 5. 路由与权限交互

当前使用 createWebHistory；路由体现 /workspaces/:workspaceId/projects/:projectId 层级。刷新深层路径时，服务器需要回退到 index.html，Nginx 的 try_files 处理这一点。

beforeEach 会调用 authApi.me()，读取可访问工作区；工作区缓存无目标时强制刷新一次；没有任何工作区时尝试创建默认工作区。

要回答三个问题：

1. **路由守卫能否保障安全？** 只能改善体验。请求可以绕过前端，后端仍需校验成员关系和资源归属。
2. **为什么缓存会过期？** 邀请加入、被移除、账号切换、工作区删除都可能改变可访问范围。缓存键和失效时机需要考虑身份。
3. **静态导入页面有什么代价？** 当前 router/index.ts 大量静态 import，可能使初始包更大；可按页面用动态 import 分割，再测首屏和二次导航代价。不能说目前已经全面懒加载。

## 6. HTTP 客户端、Cookie 与 CSRF

### 6.1 当前统一客户端

request.ts 创建 anet：baseURL=/api、withCredentials=true、普通请求超时 10 秒，指定 XSRF-TOKEN Cookie 和 X-XSRF-TOKEN Header。旧 axios 导出指向同一实例，减少新模块绕开安全设置的机会。

api/core.ts 的 unwrap 校验业务 code 是否为 SUCCESS。HTTP 200 只代表 HTTP 层成功，不保证业务成功；HTTP 401、403、429、502 则需要保留传输层含义，不能全部抹成「操作失败」。

### 6.2 两种 Cookie 不同

| Cookie | 内容职责 | 为什么这样设置 |
| --- | --- | --- |
| JSESSIONID | 浏览器关联服务端登录会话 | HttpOnly，脚本无需读取登录凭据 |
| XSRF-TOKEN | 防跨站请求伪造所需 token | 前端需要读取后写入请求头，因此不是 HttpOnly |

HttpOnly 降低脚本直接窃取 Cookie 的机会，但 XSS 仍可借当前页面发请求。SameSite=Lax 有帮助，但不能据此关闭所有 CSRF 检查。Secure 仅允许 HTTPS 发送，生产配置必须与 TLS 一致。

### 6.3 CSRF 初始化为什么使用共享 Promise

首次写请求发现没有 XSRF Cookie，会先 GET /auth/csrf。多个写请求同时到达时，通过 csrfRequest 复用同一次初始化，避免并发创建多个 token 或形成请求风暴；finally 将 Promise 清空，允许失败后重试。

单独的 csrfClient 防止初始化请求再次进入相同拦截器产生递归。后端 SPA token 机制的细节应与 Spring Security 当前版本核对，见 [官方 CSRF 说明](https://docs.spring.io/spring-security/reference/servlet/exploits/csrf.html)。

### 6.4 401 与 502 不能同样处理

当前实现只有明确 401 才标记本地会话失效、清 CSRF Cookie 并跳登录；502/503/504 或无响应只提示服务不可用。这样后端短暂重启不会把仍有效的用户会话误判为失效。

并发失败使用 authFailureInProgress 合并一段时间内的处理，避免多个弹窗和重定向循环。它是前端去抖，不是认证依据；最终身份仍由服务端确认。

## 7. 请求竞态：切换项目为什么会串数据

典型顺序：请求 A 开始 → 用户切到项目 B → 请求 B 返回 → 慢请求 A 返回。若无保护，A 会覆盖当前 B 的列表。

可选处理：

1. 参数变化时用 AbortController 取消旧请求。
2. 记录递增 requestVersion，只有最新请求可以提交状态。
3. 响应写入前核对当前 workspaceId/projectId。
4. 缓存按用户、工作区、项目、过滤条件分区。

取消网络不是完整保证：响应可能已到达、底层库可能不支持取消、服务端任务可能已启动。因此页面写入状态前仍应判断上下文。面试时可用「快速切换两个项目并人为让旧请求延迟」验证。

## 8. SSE：从连接到终态

### 8.1 为什么选择 SSE

Agent 主要需要服务器向浏览器持续推送进度，用户发起、取消和修改计划仍走普通 HTTP。SSE 贴合单向事件需求，连接和代理机制相对简单。WebSocket 适合持续双向交互，但需要另外设计协议、重连、鉴权和消息确认。

SSE 消息包含 id、event、data 等字段，以空行分隔。EventSource 自动处理流和重连；不能像普通 fetch 任意增加自定义 Authorization Header，同源 Cookie 对当前会话方案较自然。

### 8.2 本项目的恢复措施

agentStream.ts 的 watchAgentStream 同时维护 SSE 与运行快照：

- 优先处理事件流；每 5 秒查询快照。
- 使用事件 ID 去重，seen 集合保留上限 4096。
- 用 BigInt 尝试推进最大游标。
- SSE 报错后马上拉快照，设置 15 秒的连接检查定时器。
- 快照返回终态时，用完整 content 修正文本，再结束等待。
- 终态或回调异常都会清理定时器并 close，避免 Promise 永久悬挂。

Java 对应 agent_run_events 落库和 SseEmitter 推送。Last-Event-ID 是重连游标的一种传输方式，快照 API 也可以显式传 afterId。要核对具体接口读取了哪个游标，不能只说「浏览器自动重连所以不会丢消息」。

### 8.3 重复、乱序、漏消息分别处理

| 问题 | 处理思路 | 仍需注意 |
| --- | --- | --- |
| 重复 | 按 eventId 去重 | 有界去重集合可能淘汰旧 ID，不是永久账本 |
| 乱序 | 文本有序归并、游标单调、终态保护 | 只更新最大游标不等于自动重排所有事件 |
| 缺片段 | 游标补拉、最终 content 覆盖 | 必须有完整终态内容和持久化来源 |
| 页面刷新 | 重新读取 thread/run 快照再订阅 | 本地内存消息不能成为唯一事实来源 |
| 浏览器断线 | 重连和快照恢复 | 不应自动取消后台研究 |

message.delta 适合增量拼接，message.replace 适合最终修正。二者混用必须定义顺序，否则完整文本后又追加旧 delta 会重复。

### 8.4 代理为什么导致「一口气出来」

Nginx 缓冲会积累上游内容再发送。当前 /api/ 配置关闭 proxy_buffering、proxy_cache，并把读写超时设为 3600 秒。仍要检查浏览器、后端 flush、压缩中间层及上游模型是否真实流式输出。长超时允许长连接，不证明一小时内任务一定正常。

## 9. Markdown、公式、代码和安全

资料和模型输出都不可信。正确心智模型是「文本 → Markdown 解析 → 公式/代码增强 → HTML 清洗 → DOM」，具体实现顺序要看渲染组件。

- 原始 HTML、链接协议、图片来源、事件处理属性都可能引入风险。
- DOMPurify 是清洗工具，不能仅凭依赖存在就证明每个 v-html 都经过清洗。
- 新窗口链接应处理 opener；生成下载链接仍需后端权限校验。
- 未闭合代码围栏是流式输出正常中间态，不能急于把其中内容解释成标题或公式。
- agentMarkdown.ts 对代码围栏和行内代码做保护，再规范标题、数学表达，避免路径和普通代码被误转为公式。
- 每个 token 都做全量高亮和 KaTeX 渲染会放大 CPU 成本。可定时批量更新，最终文本到达后做完整增强。

## 10. 列表、图表与交互性能

1. 列表 key 用稳定业务 ID，不能在排序、插入频繁时仅依赖下标。
2. 大量消息或 Chunk 先分页；虚拟列表属于后续优化，需处理动态行高、引用跳转和键盘访问。
3. 自动滚动只在用户接近底部时跟随；用户查看旧内容时应提示新消息，而非强行拉到底部。
4. ECharts 创建实例后要在容器尺寸变化时 resize，离开页面 dispose；隐藏标签页初始尺寸可能为零。
5. 大 JSON、深层响应式对象、深度 watch、大量 computed 全表过滤都可能占用主线程。
6. 分包后用构建分析确认大依赖位置；预加载、懒加载和缓存需依据访问模式决定。
7. 当前验收记录提到大于 500 kB 的构建分块提示，它是优化线索，不等于页面已经不可用。

## 11. 可访问性与错误体验

表单要有 label、错误提示和可见焦点；模态框应约束焦点并支持 Esc；消息进度不能只靠颜色表达；按钮 disabled 的原因应可理解。图表提供文字摘要，长任务展示阶段、错误原因与可操作的重试入口。

错误区分表单校验、未登录、无权限、配额不足、模型配置错误和暂时不可用。不要把网络重试绑定为无条件再次创建研究，否则可能重复计费。

## 12. 面试前的验证练习

| 场景 | 操作 | 预期 |
| --- | --- | --- |
| 首次写请求 | 清除 XSRF Cookie，连续发起写请求 | CSRF 初始化被复用，写请求带正确 Header |
| 会话过期 | 让 /auth/me 返回 401 | 合并处理并跳登录 |
| 网关故障 | 让 API 暂时返回 502 | 保留页面，不判定注销 |
| 快速切项目 | 延迟旧项目请求 | 不覆盖当前项目内容 |
| SSE 重连 | 断开网络再恢复 | 游标恢复、去重、快照补终态 |
| 刷新长任务 | 运行中刷新页面 | 从数据库记录与快照重建 |
| 长答案 | 大量文本及代码流入 | 输入仍可操作，滚动不抢焦点 |
| 深层路由 | 直接刷新项目详情 URL | Nginx 返回 SPA 首页并正确路由 |

前端命令为 npm test、npm run type-check、npm run build。当前测试基于 Node 内置 test runner；静态逻辑测试不自动覆盖真实浏览器布局、焦点、网络和 SSE 行为，这些需要单独的浏览器验收。

## 13. 官方资料补充：watch 清理必须与请求生命周期绑定

Vue 3.5 的 onWatcherCleanup 要在回调同步阶段注册，不能等 await 结束再注册；watchEffect 只自动跟踪第一次 await 之前读取的依赖。需要更新后 DOM 时使用 flush:post，同步高频数组监听则不宜用 flush:sync。这些细节见 [Vue Watchers](https://vuejs.org/guide/essentials/watchers.html)。

下面是适用于项目切换的设计示意，并非已经替换现有组合函数：

~~~typescript
watch([workspaceId, projectId], async ([workspace, project], _, onCleanup) => {
  const controller = new AbortController();
  let current = true;
  onCleanup(() => {
    current = false;
    controller.abort();
  });
  loading.value = true;
  try {
    const result = await loadAssets(workspace, project, controller.signal);
    if (current) items.value = result;
  } catch (cause) {
    if (current && !controller.signal.aborted) error.value = toMessage(cause);
  } finally {
    if (current) loading.value = false;
  }
}, { immediate: true });
~~~

current 同时保护数据、错误和 loading，避免旧请求在 finally 把新请求的加载状态关掉。测试时让 A 的成功、失败和取消分别晚于 B 返回；不仅检查列表有没有串，还要检查错误提示和按钮状态。

## 14. SSE 协议补充：游标不是业务 ACK

事件块以空行结束，多个 data 行按规则连接；event 字段指定具名事件，未指定才走默认 message。Last-Event-ID 在同一 EventSource 自动重连时报告游标，HTTP 204 可停止重连；它不表示数据库结果已被用户处理。依据 [WHATWG SSE 规范](https://html.spec.whatwg.org/multipage/server-sent-events.html)。

~~~text
id: 142
event: run.progress
data: {"runId":"run-a","progress":35}

~~~

这个示意使用具名事件，因此客户端要监听 run.progress。项目当前将业务 type 放在 JSON payload 并使用 onmessage；如果后端新增 event 字段而前端不改监听方式，会出现连接正常但业务事件不更新的情况。手动 new EventSource 也不能假设继承上一个对象的游标，要从已保存的 afterId 恢复。

HTTP/1.x 下同源多标签页的 SSE 常遇到浏览器低连接数限制；HTTP/2 可多路复用，但并发流数量仍受协商与服务器限制，不能写成无限连接。可考虑每页合并订阅或按活动页面控制连接，见 [MDN SSE 使用说明](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events)。

## 15. 官方性能建议怎样变成项目实验

Vue 官方将懒加载、大列表虚拟化、稳定 props 与浅层响应式列为不同优化手段；应按真实瓶颈选择，见 [Vue Performance](https://vuejs.org/guide/best-practices/performance.html)。本项目可分别设计实验：

| 假设 | 只改变什么 | 看什么结果 |
| --- | --- | --- |
| 静态页面导入拖大首屏 | 只改路由动态 import | 初次 JS 下载/执行与二次导航耗时 |
| 流式全文高亮阻塞输入 | 只对文本更新合批，终态完整高亮 | 长任务时长、键入延迟、结果一致性 |
| 大 Chunk 列表 DOM 太多 | 保持数据不变，分页/虚拟化对比 | 节点数、滚动稳定、引用跳转正确性 |
| 深层追踪大对象代价高 | 对确实不可变的数据用 shallowRef | 更新 CPU、内存与整体替换语义 |

优化前后使用相同数据、设备、网络和缓存条件；同时观察功能正确性。只报告 bundle 字节减少，不能证明流式消息页面交互改善。
