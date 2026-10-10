# Cubase 12 表情映射自动生成工具

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

从 CSV 或复制文本一键生成 Cubase 12 的 `.expressionmap`。
格式结论来自 **25 个真实 `.expressionmap`、326 个技法槽**的字节级逆向比对，不是猜的。

- **纯本地运行**，不联网、不上传任何数据；Python 3.9+ 即可，无第三方依赖。
- **两种用法**：网页编辑器（推荐）/ 命令行；也能打包成一个 exe 发给不懂 Python 的人。
- **MIT 协议**，随便用、随便改、可以商用，只需保留版权声明。

---

## 快速开始

> **想发给别人用 / 不想装 Python** → 看 **`免安装版说明.md`** 和 **`分享给朋友.md`**。
> 想改代码就往下看，改完 `python build.py` 重新打包。
> **每一版改了什么** → 看 [`CHANGELOG.md`](CHANGELOG.md)。

```bash
git clone https://github.com/<你的用户名>/CubaseEM.git
cd CubaseEM
python em.py doctor                                   # 环境自检（先跑这个）

python em.py web                                      # 网页编辑器（技法清单 + 触发方式 + 窗口总在最前）
python em.py doctor                                   # 环境自检

# 从 CSV 生成
python em.py build --in data/demo.csv --brand kontakt --out 演示库

# 从音源界面 / 说明书复制的文本生成
python em.py build --paste data/pasted.txt --out 演示库 --name "我的弦乐"

# 把现成的 .expressionmap 反转成可编辑 CSV
python em.py dump --dir "E:\Cubase project\模板文件\技法" --csv-dir out/csv_ref
```

网页编辑器打开后若看不懂某个词，右上角「使用说明」里有一张 **名词对照表（本工具 ↔ Cubase）**。

产物都在 `out\`：
| 文件 | 用途 |
|---|---|
| `xxx.expressionmap` | 拖进 Cubase 的表情映射 |
| `xxx.html` | 技法对照表，浏览器直接看 |
| `xxx.csv` | 中间层导出，可再编辑再生成 |
| `xxx.log` | 自动补全记录 + 冲突报告 |

放到 Cubase 目录即可加载：
`C:\Users\Administrator\Documents\Steinberg\Cubase\Expression Maps`

---

## CSV 表头

只写你关心的列，其余留空自动处理。**列名中英文均可**。

```csv
map_name,name,switch,note,note2,channel,cc_num,cc_val,color,length,description,order
我的弦乐,长音,ks,24,,,,,,1,Sustain,1
我的弦乐,拨弦,ks+ch,27,,2,,,,1,Pizzicato,2
我的弦乐,颤音,ch,,,3,,,,1,Tremolo,3
```

| 列 | 说明 |
|---|---|
| `name` | 技法显示名（**必填**） |
| `switch` | 触发方式，写法与网页下拉里的中文名对应：<br>`ks` 按键切换 / `ks2` 双键齐按 / `ch` 按通道切换 / `ks+ch` 通道＋按键 / `cc` CC 控制器 / `none` 常驻，不切换 |
| `note` | keyswitch 音符，可写音名 `C1` 或数字 `24` |
| `note2` | 第二个 keyswitch（`ks2` 用） |
| `channel` | 通道 **1–16**（界面视角，程序内部转 0-based） |
| `cc_num` / `cc_val` | CC 号与值 |
| `length` | 音符长度缩放，跳弓这类短音填 `0.2` |
| `color` | 显示色，填 Cubase 色号 1–16；留空**跟随上一行**（首行 1），不自动换色 |
| `description` | 描述，留空则用技法名 |
| `order` | 排列顺序 |
| `conditions` | 组合技法，写法见下方「多条件」小节 |

下面这些平时不用写，只在**要跟原文件逐字一致**时才由 `dump` 导出、`build` 读回：

| 列 | 说明 |
|---|---|
| `symbol` | 乐谱符号索引，**无法从数据推导**，只能原样带回；也可以直接填文字（那就不是索引了，见下） |
| `text` | 界面覆盖文字，写了就显示它而不是技法名 |
| `display` | 显示方式 `text` / `symbol` / `auto`，**无法推导**，同样原样带回 |
| `min_velocity` / `max_velocity` | 力度窗口，默认 `0` / `127`；Shreddage 这类用力度分层的音源会写别的值 |
| `articulationtype` | Cubase 的内部类型标记（0/1），同样无法推导，原样带回 |

**未填的音符/通道补不补，由「自动补触发键」开关决定 —— 网页界面上默认不打开**：
打开后 keyswitch 从 C1(24) 开始顺序分配、通道从 1 开始，自动跳过已占用的；
关着就**留空**（`key=-1`，靠通道 / CC 触发，不多一个要按的键）。
命令行默认仍会补（保持老行为与逐字节回归），加 `--no-autofill` 关掉。
颜色这类渲染必需的默认值两种情况下都会补。

---

## 复制文本能识别的写法

```
C1 Legato          C#1 Staccato       D1 - Spiccato
27 Tremolo         ch2 Pizzicato      ch3 C2 泛音
顿弓                                    ← 没写音符？自动补键
```
音名、裸数字、`chN`、`通道N` 都能认。认不出来的行不会丢，会写进日志让你人工校正。

---

## 网页界面里的「触发方式」在 Cubase 里怎么落地

界面上的六种叫法，对应 CSV 里的 `switch` 和 XML 里的写法：

| 界面叫法 | `switch` | XML 表达 |
|---|---|---|
| 按键切换 | `ks` | `key=音符` + 一条 NoteOn 输出事件 |
| 双键齐按 | `ks2` | `key`/`key2` 两个音符 + 两条 NoteOn |
| 按通道切换 | `ch` | `action.channel` 与 `noteChanger.channel` 设同值，**不发任何输出事件** |
| 通道＋按键 | `ks+ch` | 两者同时生效 |
| CC 控制器 | `cc` | `controller1num/value` + 一条 CC(176) 事件 |
| 常驻，不切换 | `none` | 不写触发条件，只登记技法名 |

---

## 多条件（Art.1–Art.4）

Cubase 的 `USlotVisuals.group` 0/1/2/3 就是界面里的 Art.1/2/3/4，它们是**条件维度**不是动作位：
- 只有 Art.1 能带触发键，Art.2–4 只是辅助条件（`description` 是它的标识）
- 同层互斥（同时只能一个生效），不同层可并存
- 某个条件写了就一直延续，直到被改写

组合槽位 = 一个槽的 `sv` 里塞多个不同 `group` 的 visual，输出 = 各层键位一起发出
（`key=24, key2=6` + 两条 NoteOn）。模型里的 `Cond` 就是它的载体，
`Art.conditions` / `SlotSpec.conditions` 是唯一真相，`group` / `description` 自动镜像第一条。

`conditions` 列写法：`层:描述[:键位]`，多条用 `;` 隔开。

```csv
name,conditions
长音连奏,0:长音;1:连奏
长音颤音,0:长音~73~1;1:颤音~210~1
```

第二行里 `~` 后面跟的是**符号索引**和**类型标记**——这两个值 Cubase 才会写，
工具推导不出来，只有在做原文件逐字还原时才需要带上。不带 `~` 的旧格式照样能读、
生成结果也完全等价，只是 `slotvisuals` 区那段跟原文件不会逐字一致。

> 实测：样本里**每一个**组合都包含 Art.1（70 个 `(0,1)`、4 个 `(0,2)`，0 个不含 Art.1）。
> 所以网页的「组合技法」面板里，缺 Art.1 键位的技法会被标红提示，生成时也只会组合带键的那层。

样本规模：Evolution 53 槽（11 单 + 7 单 + 35 组合）、Shreddage 36 槽、Modo Bass 14 槽（用到了 Art.3）。

---

## 网页编辑器

`em/webapp.py`：Python 标准库 `http.server`，不装任何第三方包；前端是单个
`em/web/index.html`，无 CDN 依赖，断网可用。端口 8777。

| 模块 | 职责 |
|---|---|
| `em/library.py` | 技法清单两层（本音源 + 共享）、查重、空闲键建议、库体检、写盘备份 |
| `em/presets.py` | 组合模板（可存多个） |
| `em/palette.py` | 16 个显示色的名字与近似 RGB，存在 `config/palette.json` |
| `em/wintop.py` | 「窗口总在最前」：ctypes `SetWindowPos` + `HWND_TOPMOST`，回读真实状态 + 看门狗 |
| `em/renderer.py` | XML 写出，字节级对齐 Cubase（浮点格式、元素顺序、显示池顺序、力度裁剪） |
| `em/reader.py` | 反向解析；返回的 `MapDoc` 额外带回原文件的显示池顺序 |
| `em/web/index.html` | 网页界面（技法清单 + 技法表 + 组合技法三步面板） |

### 这一版新增的六件事

① **界面缩放**：顶栏 `A− / A+`，六档 80 / 90 / 100 / 110 / 125 / 150%，
存在 `config/settings.json` 的 `zoom` 里，下次打开还是那个比例。
快捷键 `Ctrl+↑` / `Ctrl+↓`。小屏就往小调，不用横向拖表格。

② **批量改**：表格最左边多了勾选框。勾上若干行之后，主行上四个常用动作：

| 按钮 | 作用 |
|---|---|
| 改名字… | 全改成同一个名字，或按序号命名（`{n}` = 行号，例如 `连奏 {n}`） |
| **颜色…** | 打开颜色模块，六种改法（见下面「③ 颜色」） |
| 更多批量操作 ▾ | 展开不常用的：条件层 / 触发方式 / 高级参数… / 补齐推算出来的值 |
| 删掉这些行 | 批量删除 |
| 取消勾选 | 清空勾选 |

改完**勾选会保留**，方便连着改第二项；只有增删行才清空（下标会错位）。

③ **颜色**：

> 原则：**同一样东西用同一个颜色**。所以「+ 加一行」的新行**跟随上一行的颜色**，
> 绝不自动变色 —— 一水的蓝才是对的，杂色只会让人分不清哪些是一组。

需要配色时点批量栏的**「颜色…」**，六种改法任选，改之前有实时预览：

| 改法 | 说明 |
|---|---|
| 全部设成同一个颜色 | 最常用 |
| **按「组合路径」自动配色** | 组合技法按 `Art.1+Art.2` / `Art.1+Art.3` 这类**合成路径**分类，每类一个色；普通行按条件层分 |
| 按顺序循环取色 | 从色板里轮着来 |
| 颜色号递增 / 递减 | 以**第一行**的颜色为基准往后排，到 16 绕回 1 |
| 指定一个颜色号 | 直接给号 |

> ⚠️ `wrapColor(c)` 吃的是**颜色号本身**（1 起），内部才做 `-1/+1` 换算。
> 外面别再手动减一次，否则整体偏 1。

④ **默认技法名 + 触发信息自动递推**：

- 更多设置里的**默认技法名**，支持 `{n}` 编号。点了「+ 加一行」，新行直接用它当名字，
  并从上一行继承触发方式与条件层。
- 空着的格子会用**暗色斜体**提示下一个该填什么，点一下就采用；
  也可以点标题栏的**补齐推算出来的值**一次填完。
  这些都是**你点了才生效**；生成时要不要**再自动补一遍**，见下面的
  「自动补触发键」开关。
- 推算规则就是手点习惯：**只看离得最近的上一个 / 下一个已填的值**。
  `24 · 空 · 空 · 27` → 中间是 `25, 26`；反过来 `27 … 24` → `26, 25`。
  中间隔着好几个按键区也能各自成立。
- **每个字段各自成串**（`SERIES` 表 + `fieldPool()`）：
  触发键只跟按键类的行排、通道只跟通道行排、`cc_num`/`cc_val` 只跟 CC 行排；
  细则参数（长度 / 转调 / 力度系数 / 力度窗口 / 音高窗口）也各自成串，
  所以**改哪个框就提示哪个框**，改了长度不会跑来催你填触发键。
- ⚠️ **触发不是只有按键**：Cubase 里通道、CC 号 / CC 值同样能触发一条技法。
  所以生成前的检查按「这一行实际带了哪些触发部件」判定（`rowParts()` / `rowTriggers()`），
  而不是照着类型栏的字面要求挑刺：
  - 填了通道 → 算触发，**不会再被骂「缺键」**（这就是「导出审核只认快捷键」那个 bug 的修法）；
  - 填了 CC 号 → 算触发；缺 CC 值才单独提示会发 `CCn=0`；
  - 类型「常驻，不切换」→ 不需要任何触发部件；
  - 键盘 / 通道 / CC 一个都没填 → 才拦下来，并写明缺的是哪一个。
- ⚠️ **类型栏跟实际填的不一致**：能生成但产物会不一样，只做提示不拦。
  典型是「类型是按键切换、键位空、只填通道」—— 这时候产物取决于 **「自动补触发键」开关**
  （`autofill(..., fill_triggers=)`，界面默认关）：
  打开 → `autofill` 从起始键补一个键位，出来是「键位＋通道」（多按一个键）；
  关着 → 不补，就是纯通道触发（`key=-1` + 通道、不发 NoteOn）。
  表格里挂蓝标 `通道 N`，**点一下**把类型改成「按通道切换」，类型栏就跟实际对上了。
  这套不一致的提示收在 `triggerNotes()` 里。
- ⚠️ **组合行不参与**（它的输出是多键拼合，不是序列里的一个值）。
- ⚠️ 通道只给「通道切换 / 键+通道」这两种行填；给纯按键行写通道，
  会把输出固定在那个通道上。
  （细则面板里的「通道」对纯按键行来说是**输出通道**，不属于触发序列，所以不给它提示。
  但它同样成串：给一串行都填了输出通道，后面的空框会接着推。）
- ⚠️ 「整串都一样」时**只有重复有意义的字段**会继承（`cc_num`、长度、转调…，见 `SERIES[fld].same`）；
  触发键 / 第二键 / 通道 / CC 值重复会打架，不继承。
- **触发器那一格按触发方式换成对应的专用输入框**（`keyCellHTML()`）：
  `ks`→音名框；`ks2`→键1+键2；`ch`→通道号框（1–16）；`ks+ch`→键位+通道；
  `cc`→`CC[号]=[值]` 两个框。落值规则在 `applyKeyField()` 里，一字段一分支：
  CC 号 / 值只收 0–127（粘 `CC7=8` 会拆成两格）、通道夹 1–16、
  音名不是音名会明确提示而不是静默丢掉。
  ⚠️ **别再退回「一个文本框 + 正则猜」**：以前 CC 行要在触发键框里打 `CC4=100`，
  正则不匹配（少个 `=`、只写 `CC64`）就**静默丢弃**，界面上看就是「写不上 CC 控制器」。
- ⚠️ **重画表格时要还焦点**（`restoreWantFocus()`）：`change` 是失焦那一刻发的，
  用户点下一格的 mousedown 已经发生 —— 同步重画会把「刚点的那一格」一起销毁，
  接着打的字就没了（CC 号填完去点 CC 值那格最容易撞上）。所以 mousedown 先记住
  点的是哪行哪个字段（`[data-f]`），重画完再 focus 回去。
- **列宽可拖 + 每列最低宽度**（`COL_DEF` / `COL_MIN` / `applyColw()` / `initColGrips()`）：
  拖表头右边缘改宽度、双击恢复单列、标题栏「列宽复位」全部还原；
  列宽存 `settings.colw`（后端 `norm_colw()` 清洗成 10 个 20–900 的整数）。
  表格用 `table-layout:fixed` + `<colgroup>`，总宽超过表格框就横向滚动 ——
  以前那种「蓝标把输入框盖住、看不见填了什么」不会再出现。
  `.predwrap` / `.kwrap` 都必须 `flex-wrap`，窄格子时标签换行而不是挤掉输入框。

⑤ **补齐 Cubase 设置框里的其余参数**（收在表格下方的「更多细则」，点行尾的 `⋯` 展开）：
通道 / 长度 / 转调 / 力度系数 / 最小力度 / 最大力度 / 最小音高 / 最大音高 /
显示方式 / 记谱符号 / 短标签 / 远程触发键。填好后可以「套用到勾选的行」。
其中力度窗口会**把发出去的 NoteOn 力度夹进区间**（ vel­ocity 120 + 窗口 40–90 → 实际发 90）。

> **这块面板和表格共用「当前行」**（`markCurRow()` 同时维护 `S.actIdx` / `S.advIdx`）：
> 表格里换行 → 面板跟着换；面板里 **↑↓** 换行（焦点留在同一个框）、
> **Tab** 换到下一行同一个框并整段选中（进编辑模式），换行前会先 `advCommit()` 把没失焦的改动落实。
> 以前两边各记一个行号，表格跳到第 5 行后面板还停在第 2 行，改着改着就改错行了。

⑥ **发音法的「类型」**（= XML 里的 `articulationtype`）：表格里新增「类型」列，
两项 —— **属性（0）** / **奏法指示（1）**，就是 Cubase「发音法」表格里那个下拉。
这个值推不出来，必须原样带回（详见下面「验证结论」）。

⑦ **输出位置**：更多设置里的**导出到**，留空 = 默认的 `out` 文件夹，旁边三个按钮：
**打开这个文件夹**（打开框里当下填的那个）、**设为默认**（存成以后的默认值）、
**用回默认**（清回 `out\`）。回车即保存。生成完成后弹窗也会显示实际写到了哪里并给个打开按钮。

> ⚠️ **踩过的坑（务必别再犯）**：生成完成弹窗里的按钮**一度写成**
> `onclick="openFolderNow('${esc(res.out_dir)}')"`。`esc()` 只转 `& < > "`，
> **不转反斜杠**；而属性文本要先经 HTML 解码、再当 **JS 源码**解析，
> 于是 `D:\缓存\workbuddy\CubaseEM\out` 里的 `\缓` `\w` `\C` `\o`
> 被当成 JS 转义序列吃掉 → 路径变成 `D:缓存workbuddyCubaseEMout`，
> 资源管理器跳到一个刚建出来的空文件夹。
> **规矩：路径、id、任何用户可输入的字符串，一律不许拼进 `onclick` 属性。**
> 要么从 `S.xxx`/`dataset` 现取（`openFolderNow()` 不带参数），
> 要么只传**数组下标**（技法清单窗体就是这么改的）。
> `case_export.js` 里已加断言：弹窗按钮传出的路径必须与生成的目录**逐字符相同**。

界面上的名词都对齐了功能，避免「名字看不懂」：

| 旧叫法 | 现在的叫法 | 它到底是干什么的 |
|---|---|---|
| 技法库 | **技法清单** | 列出已有的技法，可搜名字也可搜键位（例如 `连奏` / `sus` / `C1`） |
| 方式 | **触发方式** | 怎么触发这个技法，六个选项都有悬浮解释，旁边还有一张常开的对照表 |
| 色 | **显示色** | 点色块选颜色，写进 Cubase 的是色号 1–16 |
| 层 | **条件层** | 对应 Cubase 设置框里的 Art.1–Art.4 四行 |
| 组合配合 | **组合技法** | 勾选哪几层搭配，下方会直接预览「哪键 ＋ 哪键」 |
| 置顶 | **窗口总在最前** | 真的能关掉，状态来自系统回读不是本地记的 |
| 导入音源 | **打开已有表情映射** | 三种用途：打开单个文件改 / 多选文件收集进清单 / 扫预设目录 |
| 品牌 | 收进**更多设置 ▾** 里的**输出写法（各家的写法差异）** | 决定 XML 细节按哪家的习惯写。目前只内置了 Kontakt / NI 一套，所以这里不显示下拉、只显示一句话；以后加了别家的才会出现选项 |

数据落点：
```
config/techniques.json        共享技法
config/libs/<音源>.json       本音源技法
config/combo_presets.json     组合模板
config/palette.json           显示色（只存改过的）
config/settings.json          起始键等偏好
config/*.bak                  每次写盘前的上一版
```

一条技法的主键 = `name + group + switch + 键位标识`。
单个音源库内部撞键**硬拦**：`/api/save` 回 `{status:'conflict', conflict, free_key}`。
⚠️ **前端只报不填** —— `handleSaveResult()` 撞键时弹窗列出双方键位与占用者，
`free_key` 只当提示（`目前空着的：C#0 / 25`），**绝不自动改写行里的键位**（旧版会，已删）。
共享库允许不同音源共用键位（这是常态），所以批量导入走 `allow_conflict=True`。

### 窗口总在最前的三个坑

> ⚠️ `ctypes` 在 64 位下**必须**显式声明 `argtypes`：HWND 是指针宽度，
> 不声明就只填低 32 位，`HWND_TOPMOST(-1)` 会传错，置顶静默失效。

> ⚠️ 设完要**回读**才算数。用 `GetWindowLongW(hwnd, GWL_EXSTYLE=-20)` 看
> `WS_EX_TOPMOST(0x8)` 位在不在，不能靠自己记的状态字——否则「关了又像是开着的」。
> 另外要先 `GetAncestor(hwnd, GA_ROOT=2)` 走到根窗口，改子窗口没用。

> ⚠️ 页面刷新、别的窗口抢焦点都会把「最前」状态顶掉。所以开着的时候会有一个
> 每 2 秒重新 `SetWindowPos` 的看门狗线程。

### 界面相关的四个坑（都实际踩过）

> ⚠️ **浮动提示条必须是 `fixed` + `pointer-events:none`**。
> 它曾经是 `sticky; bottom:0; z-index:60`，而「弹过一次之后就再没隐藏过」，
> 于是在窗口底部横跨一大条，z-index 又最高 —— 把表格上方的按钮全挡住，
> `elementFromPoint` 返回 `null`，表现就是**「按钮点了没反应」**。

> ⚠️ **横向溢出会被误报成「按钮失效」**。
> 三栏 `#main` 没写 `flex-wrap`，`#mid` 还写死 `min-width:560px`，
> 窗口一窄右半边整块被推出可视区 —— 按钮还「存在」（有尺寸），但根本点不到。
> 现在 `#main{flex-wrap:wrap}` + `#mid{flex:1 1 560px;min-width:0}`。

> ⚠️ **别用 `element.click()` 做回归测试**。它会绕过遮挡、绕过坐标，
> 「点得到」才是假的。要走 CDP 的 `Input.dispatchMouseEvent` 派发真实鼠标事件，
> 才能验证用户真的点得到。`tools/web_smoke/case_layout.js` 就是这么做的。

> ⚠️ **字符串不许拼进 `onclick` 属性**。属性文本会先 HTML 解码、再当 JS 源码解析，
> `esc()` 又不转反斜杠 —— Windows 路径 `D:\...\out` 里的 `\缓` `\w` `\C` `\o`
> 会被当转义序列吃掉，变成 `D:缓存workbuddyCubaseEMout`。
> 传路径/名字/id 一律走 `dataset`、`S.xxx` 现取，或只传**数组下标**（见上面 ⑦）。

自查：`python em/wintop.py status` 会按窗口打印系统回读值。

---

## 打包成 exe（发给别人用）

```bash
python build.py            # 出 dist\表情映射生成器.exe（单文件，约 8 MB）
python build.py --onedir   # 文件夹版，启动略快
python build.py --clean    # 先清 build/ dist/ 再打
```

对方**不需要装 Python**，双击就能用。打包**只读不写，源码原地不动**，
改完 bug 再跑一次 `python build.py` 就是新版。

### 三个设计决定

1. **根目录 = exe 所在目录**，不是 `%APPDATA%`。
   工具是绿色便携的：拷到 U 盘、换台机器都能直接用，卸载 = 删文件夹。
2. **`out/` `config/` 启动时自动建**，路径全在 `em/paths.py` 里算。
   真的写不进去（比如塞进了 `C:\Program Files`）会自动搬到
   `%LOCALAPPDATA%\CubaseEM` 并在界面上说明，不让程序起不来。
3. **onefile 的临时解压目录绝不写东西**。PyInstaller 单文件模式会把资源
   解压到 `%TEMP%\_MEIxxxx`，那个目录每次都不一样、退出就删 ——
   只有「读 index.html」用它，配置和产出永远落在 exe 旁边。

### 打包后必须验证

```bash
python tools/verify_exe.py
```

它把 exe 复制到**只有 exe 的空目录**、**把 Python 从 PATH 里摘掉**，
然后跑：目录自建 → 服务起得来 → 生成文件 → **与源码版逐行比对**。
最后一条最要紧：`roundtrip` 那一套是靠字节对齐的，打包改一个换行就前功尽弃。

### 双击之后的行为也有专门测试

```bash
python tools/check_gui_exit.py
```

真启动 exe、真数窗口、真去点窗口右上角 ×，验五件事：只开**一个**窗口 →
关窗口**真的退掉**（含两层进程和端口）→ 已有实例在跑时再双击**不起第二个** →
点「退出程序」立刻干净退出 → 关掉再双击**端口照常用回来**。
进程和窗口都用 Win32 接口数（ctypes），不借 PowerShell —— 那玩意儿一次一秒多，
会把"到底几秒退的"给糊弄过去。

> ⚠️ 打包踩过的坑：
> - `pkgutil.iter_modules` 在 exe 里扫不到 `methods/*.py`（文件已编译进包内），
>   表现是「只有 kontakt能用，加的品牌全丢」→ `build.py` 把模块名写进
>   `CUBASEEM_BRANDS` 环境变量，`registry.py` 优先读它。
> - 探测端口**不能**设 `SO_REUSEADDR` —— Windows 上这选项允许绑定已被
>   LISTENING 占用的端口，探测会「通过」然后 serve 立刻失败。
> - 单文件 exe 是**两层进程**（bootloader + 子进程），`terminate()` 只杀父进程，
>   子进程会变孤儿继续占着 exe 文件。停服务要按进程树杀（`taskkill /T`）。
> - **GUI 模式没有控制台时 `sys.stdout` 是 None** —— `webapp.start()` 里的
>   `print()` 会抛 `AttributeError`，服务线程当场死掉、界面永远打不开。
>   所有输出**只能**走 `paths._say()`（内部已经判过 None）。
>   这也是"双击 exe 一片空白、命令行跑却正常"的根因。
> - **浏览器只能开一次**：`em/app.py` 已经负责开，`webapp.start(open_browser=False)`
>   必须关掉它自己那次 —— 两处都开，双击 exe 就弹出两个一模一样的窗口。
> - 双击 exe 打开的是浏览器窗口，关的是浏览器、服务收不到任何通知 →
>   端口一直被占，下次双击弹「端口被占用」。解法：页面每 8 秒报到一次
>   （`/api/ping`），超时没报服务自己退；关窗口时再补一发 `sendBeacon('/api/shutdown')`。
>   ⚠️ 超时必须**远大于**心跳间隔（默认 180 秒 vs 8 秒），否则服务会被自己误杀；
>   并且只有 exe 打开的页面（URL 带 `?ac=1`）才这套逻辑 ——
>   普通浏览器标签里跳去别的网页也会触发关窗，会把人正在用的服务退掉。
> - 已经有一个实例在跑时，新实例**直接退出并提示**（`/api/ping` 探活），
>   不再开第二个窗口、不再占第二个端口，也不再弹「端口被占用」。

详细给朋友的说明见 **`分享给朋友.md`**。

---

## 加新音源品牌

往 `em\methods\` 丢一个 `.py`，实现 `BrandModule` 接口即可，主程序零改动：

```python
from .base import BrandModule

class Spitfire(BrandModule):
    id = "spitfire"
    display = "Spitfire Audio"
    defaults = {"keyswitch_base": 24, "start_channel": 1, "ks_velocity": 120}
```

然后 `python em.py build --brand spitfire ...`。

---

## 验证结论

| 验证 | 结果 |
|---|---|
| 往返回归（真实文件 → 重新生成 → 回读，含多条件签名） | **25/25 文件、326/326 技法槽，零字段偏差** |
| 闭环无损（原 map → CSV → 新 map，含 conditions/notes + 符号/类型/力度窗口） | **25/25 完全无损** |
| 多条件渲染 | Evolution 53 槽/35 组合、Shreddage 36/15、Shreddage text 36/15、Modo Bass 14/4，槽位数·组合数·分组·visual 池大小全部与原文件一致 |
| **逐行比对**（`roundtrip_full.py`，抹掉 ID） | 源文件合计 **22657 行，差异 0 行** —— 25 份真实文件重新生成后**逐字节一致** |
| 分段：`slots`（真正决定发声的那段） | **25/25 逐字节相同** |
| 分段：`slotvisuals`（纯显示） | **25/25 逐字节相同** |

> 唯一的例外是**换行符**：2 个 CH Solo Strings 文件用的是老 Mac 的 CR（只有 `\r`），
> 重新生成统一写 CRLF。内容一字不差，只是换行写法现代化了。

做到这一步靠的是四个"推不出来、只能原样带回"的东西，缺一个都到不了 0：

| 保真项 | 说明 |
|---|---|
| `slotvisuals` 池的**原始顺序** | 25 份里 19 份是"首次出现"顺序，另 6 份是作者手点的杂乱顺序，既非拼音也非编码序。`read_map` 会把它读出来（返回值 `MapDoc.visual_pool`），`render_map(..., pool_order=...)` 照原顺序写回 |
| `symbol` 乐谱符号索引 | 同一个 `(层, 描述)` 在不同文件里符号不一样，无法推断；填文字时它就不是索引了（见下节） |
| `articulationtype` | 分布 1:206 / 0:33，与显示类型、层、符号都不相关；有 8 组 `(层, 描述)` 在两个值上都出现过 |
| 浮点写法 | Cubase 写 50 位小数再去掉尾零，`0.2` 实际是 `0.2000000000000000111022302462515654042363166809082`；整数写整数（样例中 `1.0` 写成 `"1"`） |

### 「符号可以是文本」：左边给自己看，右边给使用者看

Cubase 发音法面板里，左边「声音插槽 → 名称」是**做表情的人**认的代号；
最下面「发音法」那一列才是**用这个映射的人**看到的。后者有两种画法：

| 模式 | XML | 宿主里长什么样 |
|---|---|---|
| 符号 | `displaytype=0` + `<int name="symbol" value="73"/>` | 一个小记号 `≡` |
| 文本 | `displaytype=1` + `<string name="text" value="滑音"/>` | 直接写「滑音」三 |

所以**「符号」这一格既可以填 Cubase 的符号编号，也可以直接填文字**——填了文字就自动
走文本模式，那段字落进 `text`。嫌一行一行填麻烦，还有个全局开关：CSV 的 `display`
列、`--display text|symbol|auto`、界面上的「显示方式」下拉。`display=text` 时
短标签没填就用技法名顶上，使用者看到的就是「无尾滑音」这种能读的名字。

命令行用法：

```bash
python em.py build --in 技法.csv --display text --out 我的弦乐
```

> 默认 `auto`：只按每行 `symbol` 那格判断，原来的行为一点没变
> （回归里 27 个文件、353 个槽位逐字段一致，就是靠这个默认不动）。

另外一条实用规则：**NoteOn 的力度会被裁进力度窗口**。Shreddage 有两个槽把窗口限成 70–90，
原文发出的力度就是 90 而不是默认的 120（`out_velocity()` 里实现）；默认窗口 0–127 时裁完还是原值。

复跑验证：
```bash
python tools/roundtrip.py        # 往返回归（字段级）：25/25 文件、326/326 槽
python tools/closure.py          # CSV 闭环：25/25 无损
python tools/roundtrip_full.py   # 逐行比对 + 分段结论：差异应为 0
python tools/check_symbol_text.py # 符号可以是文本 + 显示方式（auto/text/symbol）
python em/wintop.py status       # 「窗口总在最前」的系统回读值
```

### 前端界面的自动化冒烟（无第三方依赖）

网页改动之后跑一遍，能在不用手点的情况下验证交互：

```bash
python tools/web_smoke/run.py    # 无头浏览器跑 10 个用例（需先起 em/webapp.py --port 8777 --no-open --no-pin）
python tools/web_smoke/run.py --only case_edit.js       # 单跑一个
python tools/web_smoke/debug_one.py case_cc.js          # 开发时单拉一个浏览器跑（自带页面检查）
```

十个用例：`case_ui.js` 缩放·批量·推算·高级参数、
`case_note.js` 音名换算（含 128 音全量互逆）、
`case_edit.js` 默认名与唯一化·同名文件确认·键盘导航·MIDI 录键、
`case_save.js` 保存撞键只报不填（桩掉 api，不写真库）、
`case_color_name.js` 颜色六种改法、
`case_pred_adv.js` 分字段推算（CC / 细则参数）与「更多细则」面板跟随、
`case_cc.js` CC 号 / CC 值 / 通道的专用输入框 + 列宽可拖（真实键鼠）、
`case_audit.js` 生成前审核按触发部件判定、
`case_export.js` 输出目录与 XML 字段、
`case_layout.js` 布局与按钮可点（**排最后**，它会点「退出程序」真把服务退掉）。

> ⚠️ 用 `debug_one.py` 时**配置目录必须每次唯一**（现在带 pid+时间戳）：
> 上次跑崩留下的 Edge 会占着同一个 profile，新 Edge 直接「转交给已有实例」再退出 ——
> 表现是调试端口起不来、node 端 `send` 永远不返回，看着像卡死。
> 起不来时换个 `--cdp 9345` 也能立刻验证。

> ⚠️ **生成类的用例记得带 `overwrite:true`**：否则第二次跑会被「同名文件确认」挡住，
> 断言拿到的是 `{need_confirm:true}` 而不是生成结果（覆盖流程由 `case_edit.js` 专门测）。
> 另外临时目录里会留着上一轮的文件，映射名要不就带时间戳，要不就带 overwrite。

> ⚠️ 坑 1：无头模式下页面里的 `confirm()` 会**卡死**整个 JS，之后连
> `Runtime.evaluate` 都不再响应（表现出来是「什么都取不到」）。驱动里必须在收到
> `Page.javascriptDialogOpening` 时自动 `Page.handleJavaScriptDialog`。
> ⚠️ 坑 2：断言要读 JS 变量（`S.rows` 等），别去抓 DOM 文本 —— 页面状态才是准的。
> ⚠️ 坑 3：验证「按钮能点到」必须用真实鼠标事件，见上面「界面相关的三个坑」。

---

## 注意

- **八度编号**：默认跟 Cubase 一致，`C0 = 24`（中央 C = C3 = 60，官方映射 C-2 ~ G8）。
  想要科学记法（中央 C = C4，24 叫 C1）就 `--octave-offset -1`，
  界面顶栏「音名标准」也能切。
  ⚠️ 以前默认按科学记法算 —— 「填 C0 导出成 C-1」差一个八度的 bug 就是这么来的。
- 工具**绝不会写入** `E:\Cubase project\模板文件\技法`，所有产物只落在 `D:\缓存\workbuddy\CubaseEM\out\`。
- 冲突（音符撞车、通道重复、CC 重复、越界）会**阻断生成**，加 `--force` 可强行出文件。
- 没填的触发键 / 通道：命令行**默认会补**（`--keyswitch-base` 起始键、`--start-channel` 起始通道），
  加 `--no-autofill` 就**留空不补**（`key=-1`，靠通道 / CC 触发）——
  跟网页界面上的「自动补触发键」开关是同一件事，界面上默认关。
- 没写名字的槽位一律叫 **插槽N**，且生成前会全局去重（重名加 ` (2)`）。
  Cubase 认条目全靠名字，两条重名就分不出谁是谁 —— 见 `em/model.py` 的 `make_unique_names`。
- **生成前会查同名文件**：`.expressionmap/.html/.csv/.log` 里只要有一个已存在，
  就只回报清单不写盘，等界面确认后带 `overwrite:true` 再来一次。CLI 同理（`--overwrite` 跳过询问）。

### ⚠️ .bat 文件里一个中文都不能写

`chcp 65001` + **UTF-8 无 BOM** 的 bat 是 cmd 的经典地雷：切完代码页，cmd 会按**字节偏移**
重新读文件，中文行被截断成乱码后当成命令执行，实测报错长这样：

```
'ㄦ儏鏞犲皠鐢熸垚鍣?echo' 不是内部或外部命令，也不是可运行的程序
系统找不到指定的路径。
```

表现出来就是**双击 bat 完全没反应**（Python 压根没被启动）。用户报障过一次。

`chcp 65001` 是留给 Python 打印中文用的，不能去掉 —— 所以只能让 bat 本身保持**纯 ASCII**
（连 `rem` 注释里都别写中文），要说的话全部交给 Python 去 `print`。
项目里 `启动网页工具.bat` / `_findpy.bat` / `拖文件到这里生成.bat` / `窗口总在最前.bat` 都已按这条改过。

---

## 开源协议

**MIT**（见 [`LICENSE`](LICENSE)）。可以随便用、改、二次分发、商用，
唯一要求是保留版权声明。软件按「原样」提供，作者不对使用结果负责。

一点说明：Cubase 是 Steinberg 的注册商标，本项目是**社区第三方工具**，
与 Steinberg 没有任何关系；`.expressionmap` 的文件格式结论来自对真实样本的逆向比对，
记录在 [`SPEC.md`](SPEC.md) 里，欢迎拿去核对、补充。

## 参与改动

改动前先跑一遍回归，别把格式搞坏了：

```bash
python tools/roundtrip.py        # 现有 expressionmap → CSV → 再生成，逐字节比对
python tools/closure.py          # 端到端闭环
python em/webapp.py --port 8777 --no-open --no-pin   # 另开一个终端，起服务
python tools/web_smoke/run.py    # 无头浏览器跑 10 个界面用例（约 220 条断言）
```

代码结构一图流：`em/parsers/`（读输入）× `em/methods/`（各音源品牌的规则）两层解耦，
中间靠 `em/model.py` 的 `Art` 做唯一契约 —— 加新音源只要往 `em/methods/` 丢一个 .py，主程序零改动。

提交前请顺手做两件事：

1. **别把自己 `config/` 里的个人技法库传上来**（`.gitignore` 已排除 `techniques.json` / `settings.json` / `libs/`）。
2. 改了 `em/web/index.html` 或 `em/methods/` 之后跑一次上面的界面冒烟，UI 的坑基本都在那 10 个用例里钉着。
3. **顺手更新 [`CHANGELOG.md`](CHANGELOG.md)** —— 版本号跟 `dist\` 里的 exe 文件名一致，发新版时两边一起改。
