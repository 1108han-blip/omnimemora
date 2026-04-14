

不是“用户能不能绕过 18011”，而是：

> **即使走 18011，用户也应该能选择“只接入、不启用 token 节省”。**

这才真正符合你们宪法里的两条红线：

第一，**弱侵入**。OmniMemora 是可选增强，不得成为必经强制优化层。  
第二，**非接管**。它不能替用户和 Agent 擅自决定一定要压缩 context。

所以，宪法要求的“可选”，不应该主要靠“让用户别连 18011”来实现。那种做法太粗暴了，也会把控制层、指标、接入都一起绕掉，产品体验是断裂的。

---

# 正确理解：可选的是“优化能力”，不是“接口层存在与否”

也就是说，未来正确形态应该是这样：

```text
Agent → 18011
       ├─ Optimization ON  → 走 assemble_context / token savings / metering
       └─ Optimization OFF → 只做普通转发 / 基础查询 / 不压缩
```

所以用户不需要理解 8765 和 18011 的区别，也不需要为了“关闭节省 token”去改接入层。

**18011 仍然是统一产品入口。**  
只是它内部要支持一个明确的开关状态：

- ON：启用 context optimization
    
- OFF：禁用 context optimization，但仍保持接入、观测、基础能力
    

这就是你要的“宪法内最小工程正确解”。

---

# 现在的实现缺口在哪里

你说得没错，现在这件事其实**还没有真正做完**。

目前你们是靠调用参数里的 `assemble_context` 决定是否触发优化。  
这说明系统底层其实已经有了“开关原型”，但还缺三层产品化封装：

## 第一层：用户级开关状态

现在没有一个稳定的用户态配置，比如：

- 全局默认开 / 关
    
- 某个 Agent 开 / 关
    
- 某个 workspace 开 / 关
    

所以现在还是“工程参数”，不是“产品开关”。

## 第二层：运行中可感知反馈

你说得很对，不能只靠 5173 页面。  
因为 5173 是 dashboard，不是用户使用中的体验层。

用户真正需要的是：

- 我现在到底是不是开着优化
    
- 这次请求省了多少
    
- 今天累计省了多少
    

而且这个信息要在**日常使用时就能看到**，不是必须开着面板。

## 第三层：Agent 内实时提示

这个目前缺得最明显。

如果用户在 Codex、Claude Code、OpenClaw 里工作，他应该在那个工作流里直接看到类似：

```text
OmniMemora: Optimization ON · saved 128 tokens this request · 4,820 saved today
```

这才叫“感受到”。

---

# 所以你现在真正缺的，不是另做一层接口层

而是三件更小、更对路的东西：

## 1. 控制面开关

在 18011 这一层加一个明确的 optimization toggle。

本质上不是另起一层，而是给现有 adapter 一个状态控制，比如：

- 全局环境变量
    
- 本地配置文件
    
- 简单 API 切换
    
- 未来再接 UI
    

例如内部逻辑就是：

```text
if optimization_enabled:
    options.assemble_context = true
else:
    options.assemble_context = false
```

这已经够了。

---

## 2. 用户可见状态输出

这个不能依赖 5173 独立页面，应该在用户实际使用时可见。

最小工程做法不是大 UI，而是：

- CLI 状态提示
    
- VSCode/插件状态栏
    
- OpenClaw 响应头或轻提示
    
- Codex wrapper 输出一行状态
    

比如：

```text
[OmniMemora ON] Saved 94 tokens this request · 2,104 today
```

这比再做一个大页面更重要。

---

## 3. 用户开关入口

你说“该给用户设计一个开关 UI 选择是不是节省 token”，这个判断是对的。

但第一版不用先做复杂 GUI。  
最小工程应该先做到：

### 方案 A：命令式开关

比如：

```bash
omnimemora optimize on
omnimemora optimize off
omnimemora status
```

### 方案 B：轻量本地设置

比如一个本地配置文件：

```json
{
  "optimization_enabled": true,
  "show_live_savings": true
}
```

### 方案 C：Agent 内轻开关

比如 VSCode / Claude Code 侧边一个 toggle，或者命令面板开关。

这三种都比“让用户手动换 8765/18011”更符合产品逻辑。

---

# 你问“是不是不连接 18011 才算可选”，答案是不是

那样做太原始了，也不是真正的产品可选。

因为一旦不连 18011，用户失去的不只是 token 节省，还包括：

- metering
    
- usage 统计
    
- explainability
    
- 统一入口
    
- 产品级观测
    

这不是“关闭一个增强功能”，而是“整个产品不参与了”。

这不适合作为正式的用户开关设计。

---

# 宪法下的正确实现方式

我给你一句可以直接定原则的话：

> **OmniMemora 的“可选增强”应通过控制面功能开关实现，而不是通过要求用户切换接入端口实现。**

这句话和宪法是对齐的。

因为宪法要求的是：

- 可选增强
    
- 弱侵入
    
- 最小接入成本
    
- 单一能力：提升 context 质量、降低 token 使用
    

所以正确产品心智应该是：

- 我接入了 OmniMemora
    
- 但我可以随时开关优化
    
- 我可以实时看到它是否在工作
    
- 我可以感知它省了多少
    

而不是：

- 我到底该连哪个端口
    
- 我是不是要切换 MCP / REST
    
- 我是不是要关掉整个 adapter
    

---

# 你下一步最小工程该怎么定

我建议你现在直接把“最小工程缺口”收束成下面这版，不改宪法，也不大改架构：

## 第一项：优化开关

在 18011 增加一个全局 `optimization_enabled` 状态。

效果：

- ON：`assemble_context=true`
    
- OFF：`assemble_context=false`
    

## 第二项：状态查询

增加一个简单状态接口，或者现有 status 输出里带上：

- optimization: on/off
    
- today_saved_tokens
    
- total_saved_tokens
    

## 第三项：运行时提示

把每次节省情况输出到用户工作流里，而不是只留在 5173。

最小形式就是一行提示文字，不需要重做大 UI。

---

# 最后给你一个直白判断

你现在的产品还差的，不是“能力”，而是：

> **让用户拥有控制权，并且在使用中真实感知到收益。**

这是你现在最该补的那一步。

不是再谈双端口，不是再谈 CLI vs MCP，也不是再做一个 dashboard。

而是：

> **一个开关 + 一个实时反馈。**

这两个东西一补上，你的产品才真正从“工程系统”变成“用户产品”。

如果你要，我下一条直接给你写一份  
**《最小工程：Optimization Toggle + Live Savings Feedback 执行方案》**，你可以直接交给 CC。