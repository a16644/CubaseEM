# 开源到 GitHub —— 三步走

仓库已经在本机准备好了（`git init` + 两次提交已完成，82 个文件，MIT 协议）。

**当前状态**（用户名已知：`a16644`）

| 事项 | 状态 |
|---|---|
| 本地仓库 + 提交 | ✅ 已好，作者已改成 `a16644 <a16644@users.noreply.github.com>` |
| 远程地址 | ✅ 已接好 → `ssh://git@github.com/a16644/CubaseEM.git` |
| SSH 密钥 | ✅ 已生成，❌ **还没加到 GitHub**（现在测是 `Permission denied (publickey)`） |
| 网页上的仓库 | ❓ 待确认（`github.com/a16644/CubaseEM` 需要先建出来） |

所以只剩：**加公钥 → 建空仓库 → 推**。

---

## 第 1 步：把本机密钥交给 GitHub（做一次，以后永久有效）

本机已经生成好 SSH 密钥对。**复制下面这一整行**（开头 `ssh-ed25519` 到结尾 `CubaseEM`）：

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPAfPNSOun0utSEdl4UXNsZ3VcCVdpeuWLSga0RSBQsG CubaseEM
```

然后：

1. 打开 <https://github.com/settings/keys>（Settings → **SSH and GPG keys**）
2. 点 **New SSH key**
3. Title 随便写（比如 `我的台式机`），Key type 保持 `Authentication Key`
4. 把上面那行粘进 **Key** 框 → **Add SSH key**

> 这个文件也在 `C:\Users\Administrator\.ssh\id_ed25519.pub`，用记事本打开也能拿到同一串。
> 私钥 `id_ed25519`（没有 .pub）**永远不要发给任何人**，也不要提交进仓库。

---

## 第 2 步：在 GitHub 上建一个**空**仓库

打开 <https://github.com/new>：

| 字段 | 填什么 |
|---|---|
| Repository name | `CubaseEM`（想改别的也行，第 3 步里跟着填同样的名字） |
| Description | `从 CSV / 复制文本一键生成 Cubase 12 的 .expressionmap` |
| Public / Private | **Public**（= 开源） |
| **Initialize this repository with** 那一栏 | **全部不要勾**（README / .gitignore / license 都别加，本机已经有了，勾了会冲突） |

点 **Create repository**。建好后会看到一个写着 `git remote add origin ...` 的页面 —— **不用管它**，第 3 步脚本会自己做。

---

## 第 3 步：推送

回到 `D:\缓存\workbuddy\CubaseEM`，双击 **`push_github.bat`**：

1. 问 `GitHub username:` → 填 `a16644`
2. 问 `Repo name [CubaseEM]:` → 直接回车
3. 它会先自检 SSH 密钥，通过后自动推送

看到 `[OK] done -> https://github.com/a16644/CubaseEM` 就完成了。刷新网页就是你的开源项目页。

也可以直接敲两条命令，效果一样：

```bash
git -C "D:/缓存/workbuddy/CubaseEM" push -u origin main
```

> **为什么远程地址写成 `ssh://git@github.com/...` 而不是常见的 `git@github.com:...`？**
> 这台机器有一条全局 git 规则 `url.https://github.com/.insteadof=git@github.com:`，
> 会把 `git@github.com:a16644/CubaseEM.git` 悄悄改写成 https 地址（然后要求账密/token）。
> `ssh://` 这种写法不匹配那条规则，于是老老实实走密钥认证。


---

## 以后改了代码怎么同步

**推荐：双击 `更新GitHub.bat`**（一键版，三步全包）

1. 先列出这次改了哪些文件
2. 让你敲一句说明（比如「修复加一行键位推算」）；**直接回车 = 取消，什么都不推**
3. 自动 `add → commit → push`，最后打印最新 3 条提交

没改动时它会自己说「Nothing changed」然后退出，不会硬推一个空提交。

> ⚠️ 这个 bat 里的提示语**故意全是英文**：`.bat` 里写中文会被 cmd 按字节错位重读，
> 整段变成乱码命令（双击没反应就是这么来的），和 `push_github.bat` 一个规矩。

想自己敲命令也行，完全等价：

```bash
git add -A
git commit -m "改了什么"
git push origin main
```

`push_github.bat` 是**第一次**用的（配远程地址 + 自检 SSH），日常同步别用它。

---

## 出错了先看这里

| 现象 | 原因 / 怎么办 |
|---|---|
| `Permission denied (publickey)` | 第 1 步没做或公钥粘错。终端跑 `ssh -T git@github.com`，成功会是 `Hi <用户名>! You've successfully authenticated...` |
| `repository not found` | 第 2 步仓库名和 bat 里填的对不上，或者仓库还没建 |
| 提示要先 pull / `non-fast-forward` | 建仓库时不小心勾了 README。解法：`git pull --rebase origin main` 一次，或者干脆删掉网页上的仓库重建一个空的 |
| 想换许可证 | 换掉 `LICENSE` 文件内容，并把 README 顶部徽章和「开源协议」那节一起改 |

## 这次为开源做了哪些改动

- 新增 `LICENSE`（**MIT**：随便用、改、商用，只需保留版权声明）
- 新增 `config/README.md`：说明哪些 config 文件进仓库、哪些不进
- `.gitignore` 补上个人数据：技法库 `config/techniques.json`、界面偏好 `config/settings.json`、你保存的 `config/libs/` **都不上传**
- 新增 `.gitattributes`：仓库统一存 LF，Windows 上 checkout 自动转回 CRLF（`.bat` 必须是 CRLF）
- README 加了协议徽章、通用安装步骤、「开源协议 / 参与改动」两节（含回归怎么跑）
- 新增 `push_github.bat`：双击即可推送（纯 ASCII 写的，遵守项目里「bat 不能出现中文」的规矩）
