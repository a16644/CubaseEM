# Cubase 12 Expression Map 自动生成工具 — 施工规格 v1

> 状态：**方案已确认，等黄金样本到位后开工**
> 在拿到 `GOLDEN.expressionmap` 之前，不编写任何生成器代码（避免凭猜测手写私有 XML）。

---

## 1. 目标

读取技法清单（手写 CSV / 从音源界面或说明书复制的文本），自动生成 Cubase 12 能直接打开的 `.expressionmap` 文件。

---

## 2. 已确认决策

| 项 | 决策 |
|---|---|
| Cubase 版本 | **12**（旧版扁平格式：Sound Slot + Output Mapping） |
| 输出粒度 | **一个音源整包 = 一个 `.expressionmap` 文件** |
| 模块切分 | **按音源/品牌**；首批只做 **Kontakt（NI 系）** 模块 |
| 触发方式 | keyswitch / 纯通道 / 通道+keyswitch（CC、ProgramChange 预留接口） |
| 乐谱符号层 | **不生成**，只管发声切换 |
| 输入源 | ① 手写 CSV/Excel　② 从音源界面或 PDF 说明书复制的文本 |
| 交付形态 | **Python 命令行脚本** |
| 副产物 | ① HTML 可视化对照表　② CSV 反向导出　③ 生成日志 + 冲突报告 |
| 落位 | 输出到 `out/`；**不自动同步** Cubase 目录，仅在日志末尾打印候选路径供手动拖入 |
| 架构 | 「分品牌模块 + 总控调度」；品牌模块只写规则层，底层共享事件构造器 |

---

## 3. 目录结构

```
D:\缓存\workbuddy\CubaseEM\
├─ em\
│  ├─ core\
│  │  ├─ model.py       # 统一中间层 Articulation / ExpressionMap（模块间唯一契约）
│  │  ├─ registry.py    # 模块自动发现注册（新增品牌只丢文件，不改主程序）
│  │  ├─ validator.py   # 冲突校验：音符/通道/CC 撞车、重名
│  │  ├─ renderer.py    # 黄金样本骨架 + 数据 → .expressionmap
│  │  ├─ events.py      # 共享事件构造器（make_keyswitch / make_channel / make_cc / make_progchange）
│  │  └─ locator.py     # 探测 Cubase 12 的 Expression Maps 候选路径（仅打印，不写入）
│  ├─ parsers\          # 输入解析（可插拔，与品牌模块正交组合）
│  │  ├─ csv_parser.py
│  │  └─ clipboard_parser.py   # 音源界面/PDF 复制的乱文本
│  ├─ methods\          # 品牌模块（总控调度）
│  │  └─ kontakt.py     # 首批
│  └─ report\
│     ├─ html_report.py # 可视化对照表
│     └─ csv_export.py  # CSV 反向导出
├─ templates\
│  ├─ GOLDEN.expressionmap      # ← 待提供（4 slot）
│  └─ GOLDEN_MIN.expressionmap  # ← 待提供（1 slot，用于 diff）
├─ data\     # 输入
├─ out\      # 产出
└─ em.py     # 总控 CLI
```

---

## 4. 中间层字段（Articulation，模块间唯一契约）

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | str | Slot 显示名，如 `Legato` |
| `group` | str? | 仅备注（C12 无分组，为将来 C15 留口子） |
| `switch` | enum | `ks` / `ch` / `ks+ch` / `cc` / `pc` |
| `note` | int? | keyswitch 音符 MIDI 号；填了才生成音符事件 |
| `channel` | int? | 1–16；填了才生成通道事件 |
| `cc_no` / `cc_val` | int? | 预留 |
| `program` / `bank` | int? | 预留 |
| `color` | int? | 未指定则**跟随上一行**（首行 1），不自动递增/随机 |
| `order` | int | Slot 排列顺序 |

> 规则：**填哪个字段就生成哪个输出事件**，不填不生成。
> 因此「纯通道」= 只填 `channel`；「通道+keyswitch」= `channel` 与 `note` 都填。

---

## 5. 模块接口

```python
class BrandModule:
    id = "kontakt"                    # CLI: --brand kontakt
    display = "Kontakt / NI"
    # 规则层：该品牌的默认行为，可被 CSV 显式值覆写
    defaults = {"keyswitch_base": 24, "start_channel": 1}
    capabilities = ["ks", "ch", "ks+ch"]

    def normalize(self, raw_rows, cfg) -> list[Articulation]:
        """原始行 → 统一中间层（应用品牌规则）"""

    def build(self, arts: list[Articulation], cfg) -> list[SoundSlot]:
        """中间层 → Cubase Slot（调用 core/events.py 构造器）"""
```

新增品牌 = 在 `methods/` 丢一个实现该接口的 `.py`，`registry.py` 自动发现，主程序零改动。

---

## 6. CLI 形态

```bash
python em.py build --in data/violin.csv --brand kontakt --out "Berlin Strings"
python em.py build --paste data/pasted.txt --brand kontakt --out "X"   # 复制文本
python em.py dump  --map out/X.expressionmap --csv out/X.csv           # 反向导出
python em.py doctor                                                     # 检查环境/样本
```

---

## 7. CSV 表头草案（待你确认）

```csv
map_name,slot_name,switch,channel,note,color,order
Berlin Strings,Legato,ks+ch,1,24,,1
Berlin Strings,Staccato,ks+ch,2,25,,2
Berlin Strings,Sustain,ch,3,,,3
```

- `switch`：`ks` / `ch` / `ks+ch`
- `note`：支持音名或 MIDI 号（`C0` 或 `24`）。八度编号默认按 **Cubase 官方约定**
  （中央 C = C3：`0=C-2`、`12=C-1`、`24=C0`、`36=C1`、`60=C3`、`127=G8`），
  与 Cubase 钢琴窗里看到的名字一一对应。要科学记法（中央 C = C4）用
  `--octave-offset -1`（界面上叫「音名标准」）。
- `color` 留空则跟随上一行（首行 1）；`order` 留空则按表格顺序
  （⚠️ 老版本这里会按 `(i % 16) + 1` 自动轮着给色，**已改掉** ——
   想排成彩虹色就用网页界面「颜色…」模块的「循环 / 递增」改法）

---

## 8. 样本与 schema 结论（已解除阻塞）

样本来源：`E:\Cubase project\模板文件\技法` —— 25 个真实文件 / 326 个技法槽（**只读，全程未修改**）。

### 文件骨架
```
<?xml version="1.0" encoding="utf-8"?>
<InstrumentMap>
   <string name="name" value="映射名" wide="true"/>
   <member name="slotvisuals"> ... </member>     <!-- 所有 sv 的展平去重池 -->
   <member name="slots"> ... </member>
   <member name="controller"> <int name="ownership" value="1"/> </member>  <!-- 恒为空壳 -->
</InstrumentMap>
```
- 3 空格/级缩进，CRLF，文件末尾带换行
  （例外：2 个 CH Solo Strings 文件是**老 Mac 的 CR-only** 换行，内容结构完全一样）
- ID 只需**同一文件内唯一**（25 个样本内均无重复）

### PSoundSlot（326 个样本子元素顺序 100% 一致）
`remote(PSlotThruTrigger)` → `action(PSlotMidiAction)` → `sv` → `name` → `color`

### PSoundSlot（326 个样本子元素顺序 100% 一致）
`remote(PSlotThruTrigger)` → `action(PSlotMidiAction)` → `sv` → `name` → `color`

### 六种触发方式（= `switch`，界面上的中文叫法写在括号里）
| `switch` | XML 表达 |
|---|---|
| `ks`（按键切换） | `key=音符` + midiMessages 一条 NoteOn(144, note, 力度) |
| `ks2`（双键齐按） | 两条 NoteOn，`key` + `key2` |
| `ch`（按通道切换） | `action.channel` 与 `noteChanger.channel` 设同值，**midiMessages 空**，key=-1 |
| `ks+ch`（通道＋按键） | 两者同时 |
| `cc`（CC 控制器） | `controller1num/value` + 一条 CC(176, cc号, cc值) |
| `none`（常驻，不切换） | 不写触发条件，只登记技法名 |

> NoteOn 的力度默认 120，但**会被裁进该槽的力度窗口**：
> Shreddage 有 2 个槽把 `minVelocity/maxVelocity` 设成 70/90，这两个槽实际发出的是 **90**。
> 见 `renderer.out_velocity()`。

### 关键字段
- `channel`：`-1` 不指定，否则 **0-based**（0 = 通道 1）
- `key` / `key2`：`-1` 或 0–127
- `color`：1–16 的调色板索引（不是 RGB）
- `lengthFact`：1 或 0.2（短音技法）
- `ownership`：sv 为 `2`，其余为 `1`
- 存在**不带 USlotVisuals 的空槽**（sv 只有 ownership），渲染器已支持

### Cubase「发音法」表格里那几项 ↔ XML 的对应

| Cubase 界面 | XML | 备注 |
|---|---|---|
| 类型（属性 / 奏法指示） | `articulationtype` | **0 = 属性，1 = 奏法指示**。推不出来，必须 round-trip |
| 显示方式（符号 / 文本） | `displaytype` + `text` | `displaytype=1` + 有 `text` = 文本模式（显示文字）；`displaytype=0` = 符号模式（显示 `symbol` 编号对应的小记号）。**左边「声音插槽 → 名称」是做表情的人看的代号，这里决定的是使用者看到什么** |
| 乐谱符号 | `symbol` | 数字编号 = 符号模式；**也可以直接填文字**——填了文字就等于文本模式，那段字落进 `text` |
| 文本 / 短标签 | `text` | 留空 = 显示技法名 |

> **「符号可以是文本」规则**（用户从 Cubase 发音法面板补的）：
> 输入里 `symbol` 这一格既接受数字编号也接受任意文字。填文字时，
> `renderer._visual_block` 把它写进 `<string name="text">` 并置 `displaytype=1`，
> 于是宿主里使用者看到的就是这段文字，而不是 `≡ · −` 这种小记号。
> 另有一个全局开关（`display` 列 / `--display` / 界面下拉），
> `text` = 强制文本模式（短标签没填就用技法名顶上）、`symbol` = 符号模式、`auto` = 按上面判断。
| 通道 | `action.channel` + `noteChanger.channel` | 0-based，-1 = 不指定 |
| 长度 | `lengthFact` | 浮点，走 50 位写法 |
| 转调 | `transpose` | 半音，可为负 |
| 力度系数 | `velocityFact` | 1 = 原样 |
| 最小 / 最大力度 | `minVelocity` / `maxVelocity` | **会把 NoteOn 力度夹进区间** |
| 最小 / 最大音高 | `minPitch` / `maxPitch` | 0–127 |
| 远程触发键 | `remote` (`PSlotThruTrigger`) | 空 = 不写 |
| 显示色 | `color` | 1–16 调色板索引 |

> ⚠️ 通道看着人畜无害，但给**纯按键技法**写 channel 会把输出固定在那个通道上。
> 因此界面的自动递推只在「通道切换 / 键＋通道」这几种方式下才填通道。

### 界面行 → Art： Conditions 的两种来源

普通行在界面上**没有** condition 条目，后端要合成一条，此时必须把**行级**的
`symbol` / `text` / `articulationtype` 带上，否则会被静默丢掉
（`webapp.row_to_art()` 里的 `if not conds:` 分支）。
一行只有一条 condition 时（从技法清单带入的就是这种），改名/换层/换键必须同步它 ——
因为 `slotvisuals` 的 `description` 是从 `conditions[0]` 取的，不同步就会出现
「表格里叫 A，Cubase 里还是旧名」。前端用 `syncCond()` 统一处理。

---

## 9. 验证结果（已完成）

| 验证 | 结果 |
|---|---|
| 往返回归：真实文件 → 重新生成 → 回读 | **25/25 文件，326/326 槽，零字段偏差** |
| 闭环无损：原 map → CSV → 新 map | **25/25 完全无损** |
| **逐行比对（抹掉 ID）** | 源文件合计 22657 行，**差异 0 行** |
| 其中 `slots` 段（决定发声） | **25/25 逐字节相同** |
| 其中 `slotvisuals` 段（纯显示） | **25/25 逐字节相同** |

例外只有换行：2 个 CH Solo Strings 文件用的是**老 Mac 的 CR-only 换行**（只有 `\r`），
重新生成统一输出 CRLF —— 内容一字不差。

要做到 0 差异，这四个值必须**原样带回**，它们都无法从数据推导：

| 值 | 为什么推不出来 |
|---|---|
| `slotvisuals` 池的**原始顺序** | 19/25 是首次出现顺序，另 6 份是作者手点的杂乱顺序，不是拼音也不是编码序 |
| `symbol` | 同一 `(层, 描述)` 在不同文件里符号不同 |
| `articulationtype` | 1:206 / 0:33 分布，与 displaytype / group / symbol 都不相关；8 组 `(层, 描述)` 两个值都出现过 |
| 浮点字面量 | 写 50 位小数再去掉尾零（`0.2` → `0.2000000000000000111022302462515654042363166809082`），整数写整数 |

> `articulationtype` 那条是被验证过的：假设「有 `text` 就是 0」的公式，
> 实测只对了 **43.5%**，加上那 8 组反例，才确认它必须 round-trip。
> 不要凭直觉宣布某个字段可推导 —— 写个一次性脚本先量一下准确率。

### 界面自动化测试

```bash
python tools/web_smoke/run.py      # 需要网页服务已在 8777 上跑着
```

Node ≥ 22 自带 WebSocket，直接驱动无头 Edge 的 CDP，**不装 puppeteer**。
两个坑：① 无头模式下页面的 `confirm()` 会卡死 JS，驱动里必须监听
`Page.javascriptDialogOpening` 并自动确认；② 断言走 `Runtime.evaluate` 读 JS 状态变量，
不要去匹配 DOM 文本。当前用例：**51 条断言，0 失败**。

复跑：`python tools/roundtrip.py`、`python tools/closure.py`、`python tools/roundtrip_full.py`
（比对前记得先把换行归一化 —— CR-only 的文件不归一化会算成"整份都是一行"）
