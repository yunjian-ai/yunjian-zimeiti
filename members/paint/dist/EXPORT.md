# 丹青分享卡怎么导出（照着做的操作单）· v0.2.0

在 Grok Bot 里导出。**导出功能只能导出发起导出的那个 Bot 自己**，所以分三步：
1. 新建一个 Bot，照 `dist/template.json`（由 `tools/pack.py` 按标签 paint-v0.2.0 生成）原样放进下表的名字、资料卡指令、两个技能，一个字不改（记忆在第 3 步让它自己存）；
2. **先别让它装技能**（一打开对话它就会问要不要装，先不答）；技能库是所有 Bot 共用的，先核对库里的安装、第一次见面两个技能和 template.json 一字不差，分享卡带的是库里的内容；
3. 在这个 Bot 里发一条话：先把 memory 的两条原样各存成一条记忆，再用 `CreateBotShareJson` 导出它自己（skills 只点名下表两个，memory 只放这两条）；导出后是草稿，核对卡里描述的字数和本地一致，要在卡上确认「发布」才公开。

| 参数 | 填什么 |
|---|---|
| name | `丹青 · Paint ｜ 做图`（template.json → `profile.name`） |
| description（导出工具只有这一栏，导入后它就是新 Bot 的指令，2026-10-22 实测逐字一致） | template.json → `_meta.storefront`，空一行，再接 `profile.description`（岗位说明第一句是「你是丹青（Paint），云间里管做图的那位。」）；原样、不删换行。只放简介会丢掉岗位说明 |
| visibility | `public` |
| gettingStarted | `paint-install`（不是 paint-getting-started） |
| skills | 只放两个：`paint-install`、`paint-getting-started`（template.json → `skills`） |
| memory | template.json → `memory`（kind=log，两条：「丹青安装规矩」和一行「丹青安装状态」） |

**卡里不放的：** 另外 7 个技能——第一次聊天时由 paint-install 从 paint-v0.2.0 装上；主人的视觉档案也不放。

**导完一定要试：** 新建一个干净的 Bot 导入这张卡，打个招呼。丹青应先问一句能不能从仓库安装；回答「可以」后，回复第一句是开场白「您好，欢迎来到云间。我是万象系列的手艺人·丹青，9 件工具已备好，接下来由我陪您把想要的图理清楚、做出来。」，接着是第一次见面的第 1 题。然后请它列一下技能目录，应该能看到 9 个 paint- 技能，paint-brief 里有需求单卡、推荐规则卡，paint-master 里有母版卡、写法卡、身份证模板；问一句「库在哪」应答 `~/.yunjian/paint/库/`。

**导出之前先确认三件事：** 配方是最新的（`python3 tools/pack.py --check` 通过）；仓库对外公开；卡里没有密钥、内部网址和真实客户资料。

**发布后怎么导入实测：** 卡上「复制链接」得到 `https://x.ai/bot/<编号>`；本机运行 `open "grokbot://app/v1/bot-template?id=<编号>"` 就弹出导入窗口，点「添加 Bot」。草稿不能导入，可见范围只有 public / team。
