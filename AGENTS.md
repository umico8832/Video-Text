# 开发环境

- 本项目开发环境使用 PowerShell。执行命令时必须使用 PowerShell 支持的语法，不要使用当前环境不支持的 Bash/CMD 专用写法，例如 `&&` 链式命令。
- PowerShell 会话默认使用 UTF-8 输入/输出，不要依赖 GBK/CP936 编码行为。

# Git 提交规范

当用户要求提交 git commit 时，必须使用以下提交信息规范。

格式：

```text
<type>(<可选作用域>): <中文简短描述>

<可选: 详细说明>
<可选: Closes #42>
```

大多数提交一句话搞定。一行不够时，空一行再补充。

type 只能使用：

- `feat`：新功能
- `fix`：修 bug
- `docs`：文档
- `style`：代码格式，不影响逻辑
- `refactor`：重构
- `perf`：性能优化
- `test`：测试
- `chore`：构建、工具、依赖
- `ci`：CI/CD
- `security`：安全

要求：

- 提交信息必须使用中文描述。
- 一次提交只描述一件事。
- 修改涉及特定模块时优先添加作用域，例如 `refactor(settings): 抽取 settings 管理逻辑`。
- 禁止使用模糊信息，如 `fix bug`、`wip`、`修改了一些文件`。
- 禁止写成 `feat: 添加A顺便修了B` 这类混合事项描述。
