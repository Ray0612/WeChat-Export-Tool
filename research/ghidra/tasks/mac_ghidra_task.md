# Mac Mini Ghidra 分析任务

## 任务目标

在 Weixin.dll（4.1.10.29 版本，175MB）中用 Ghidra 找到 `GetPagedMessages` 函数的地址。

## 为什么需要这个

微信从 4.1.9.56 升级到 4.1.10.29 后，核心 DLL 的函数地址变了，之前所有 Hook 分析全部失效。需要在 Ghidra 中重新找到这个函数的位置。

## 背景知识

- 在 4.1.9.56 版本中，GetPagedMessages 函数位于 **DLL 偏移 0x016ade70**，对应函数名 `FUN_1816ade70`
- 函数附近有以下字符串特征：
  - `"GetPagedMessages"`
  - `", last:"`
  - `"GetPagedMessages has messages:"`
- 函数接收 4 个参数：arg0=Manager, arg1=GlobalCtx, arg2=PagingContext, arg3=arg2+0x20
- 返回值 = arg1（在 M6 中验证）

## 环境准备

### 1. 安装 Java 21（如果还没有）

下载链接：https://adoptium.net/temurin/releases/?version=21
选 **macOS ARM64** 版本（M4 芯片）
安装后确认：

```bash
java -version
# 应该显示 21.x.x
```

### 2. 安装 Ghidra 12.1

下载链接：https://github.com/NationalSecurityAgency/ghidra/releases/tag/Ghidra_12.1_build
下载 `ghidra_12.1_PUBLIC_*.zip`
解压到任意目录，比如 `~/ghidra_12.1_PUBLIC/`

### 3. 准备 DLL 文件

将以下文件从 Windows 拷贝到 Mac：
- `D:\Program Files\Tencent\Weixin\4.1.10.29\Weixin.dll`（175MB）
- 可以用 U 盘或局域网共享

放到 Mac 上，比如 `~/Desktop/Weixin.dll`

## 分析步骤

### Step 1: 启动 Ghidra

```bash
cd ~/ghidra_12.1_PUBLIC
./ghidraRun
```

### Step 2: 创建工程

- File → New Project
- 选 **Non-Shared Project** → Next
- Project Name: `WeChat_411029`（或任意名称）
- Project Directory: 默认即可 → Finish

### Step 3: 导入 DLL

- File → Import File
- 选择 `~/Desktop/Weixin.dll`
- 弹出对话框 **直接点 OK**（所有选项默认）
- 之后会问 "Analyze?" → 点 **No**（先导入，后续再分析）

### Step 4: 打开并分析

- 在 Ghidra 左侧 **Project Window** 中展开刚刚导入的 `Weixin.dll`
- **双击** `Weixin.dll` 打开它
- 如果弹窗问 "Perform auto-analysis?" → 点 **Yes**
- 分析选项窗口弹出 → **直接点窗口右下角的 Analyze 按钮**（全部默认选项）
- 分析开始，底部状态栏会显示进度

### Step 5: 等待

**分析时间：约 1-2 小时**（M4 性能好，比 Windows 快）

可以最小化 Ghidra，做其他事情。分析完成后会有提示。

### Step 6: 搜索 GetPagedMessages 字符串

- 在 Ghidra 的代码浏览器（CodeBrowser）中，按 **`S`** 键打开字符串搜索
  - 或者菜单：Search → Program Text
- 搜索框输入：`GetPagedMessages`
- 搜索结果列表中应该会出现这个字符串（在 `.rdata` 节）
- **双击** 该字符串跳转到它的位置

### Step 7: 找到函数的 xref

- 在选中的 `GetPagedMessages` 字符串上 **右键**
- 选择 **References** → **Show References to Address**
- 会弹出一个窗口，列出引用这个字符串的所有指令地址
- 这些地址就是调用 GetPagedMessages 或者在代码中引用它的位置
- 点击 **Function column** 排序，可以看到这些 xref 属于哪些函数

### Step 8: 确认函数地址

Ghidra 中显示的地址格式是 `1816XXXXX`（基址 `180000000` + DLL 偏移）。

需要记录两个值：

```
1. xref 所在函数的起始地址（例如 FUN_1816XXXXX）
2. DLL 偏移 = Ghidra 地址 - 0x180000000
```

例如如果函数地址是 `0x1816ade70`，则 DLL 偏移是 `0x016ade70`。

### Step 9: 验证（可选）

如果有多个 xref，重点关注：
- xref 数量最多的函数
- 函数体积大（翻页函数通常比较复杂，>500 字节）
- 函数附近还有对 `", last:"` 和 `"GetPagedMessages has messages:"` 的引用

## 需要报告的内容

分析完成后，请在 Windows 端告诉我：

1. **函数地址**（Ghidra 中的地址，如 `0x1816XXXXX`）
2. **DLL 偏移**（地址 - 0x180000000）
3. **xref 数量**（有几个引用）
4. **函数首字节**（如果是 `55` 就是标准 PUSH RBP 开头）

## 注意

- 如果分析完后搜不到 `GetPagedMessages` 字符串，可以试试搜 `"has messages"` 或 `", last:"`
- 新版本 4.1.10.29 对字符串做了混淆，但之前确认该字符串在 DLL 的 `.rdata` 节偏移 `0x084f4a2f` 处仍然存在
- 如果完全搜不到字符串，则可能是运行时解密，需要告知 Claude Code
