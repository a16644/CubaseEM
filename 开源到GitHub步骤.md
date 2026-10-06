# 开源到 GitHub —— 三步走

仓库已经在本机准备好了（`git init` + 首次提交已完成，80 个文件，MIT 协议）。
剩下三步在网上，做完就能公开。

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

## 第 3 步：双击 `push_github.bat`

回到 `D:\缓存\workbuddy\CubaseEM`，双击 **`push_github.bat`**：

1. 问 `GitHub username:` → 填你的用户名（页面右上角头像点开能看到，就是 `github.com/<这个>`）
2. 问 `Repo name [CubaseEM]:` → 直接回车用默认
3. 它会自动：设好提交身份（用 GitHub 的 noreply 邮箱，不泄露真实邮箱）→ 接远程 → 推送

看到 `[OK] done -> https://github.com/xxx/CubaseEM` 就完成了。刷新网页就是你的开源项目页。

---

## 以后改了代码怎么同步

```bash
git add -A
git commit -m "改了什么"
git push
```

嫌记命令麻烦就再双击一次 `push_github.bat`（它只负责接远程和推送，提交还得自己敲上面两条）。

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
