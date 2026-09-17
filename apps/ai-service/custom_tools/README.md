# 自定义 Python 工具

把受信任的 Python 文件放在本目录，或通过 `CUSTOM_TOOLS_DIR` 指定一个目录。服务启动时会加载目录下的直接 `.py` 文件；修改后调用 `POST /internal/tools/custom/reload`，也可以直接重启服务。

推荐使用装饰器声明工具契约：

```python
from tools.custom import custom_tool


@custom_tool(
    "custom.weather",
    description="查询指定城市的天气",
    input_schema={
        "type": "object",
        "required": ["city"],
        "properties": {"city": {"type": "string", "maxLength": 80}},
    },
)
async def weather(*, city: str) -> dict:
    # 这里编写自己的异步 HTTP、数据库或本地计算逻辑。
    return {"city": city, "status": "replace-with-real-provider"}
```

同步函数也可以直接编写，执行器会自动放入线程池，不阻塞事件循环。写操作必须声明 `permission="WRITE"`，并同时经过 `allowWrites=true` 和 `confirmed=true`；工具链只能通过 `$from` 或 `{{steps.*}}` 引用前序结果。

自定义文件是服务进程的受信任代码，只允许从本地配置目录加载，系统不提供通过 HTTP 上传并执行源码的能力。
