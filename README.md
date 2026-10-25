<p align="center"><img src="assets/hero.png" alt="云间Bot · 万象 Cloudmere" width="100%"></p>

<h1 align="center">云间Bot · 万象 Cloudmere</h1>

<p align="center"><b>一元复始，万象更新。</b><br>万象系列管自媒体的手艺。第一位是执笔：把你亲手做过的事，写成能直接念的口播、读着像人写的长文，再改成每个平台的版本。你只管开口。</p>

<p align="center">执笔 Pen · cloudmere · Grok Bot 口播稿、长文、仿写、去 AI 味、多平台改写助手 · 仓库 <a href="https://github.com/yunjian-ai/yunjian-zimeiti">github.com/yunjian-ai/yunjian-zimeiti</a></p>

<p align="center">
  <a href="CHANGELOG.md"><img alt="执笔" src="https://img.shields.io/badge/执笔-v0.2.4-c0392b"></a>
  <a href="LICENSE"><img alt="license" src="https://img.shields.io/badge/license-CC%20BY%204.0%20%2B%20MIT-555555"></a>
  <a href="https://github.com/yunjian-ai/yunjian-zimeiti/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/yunjian-ai/yunjian-zimeiti/actions/workflows/ci.yml/badge.svg"></a>
</p>

<p align="center"><a href="#english">English</a> · <a href="#执笔--pen">执笔</a> · <a href="#安装">安装</a> · <a href="#路线图">路线图</a> · <a href="#常见问题">常见问题</a></p>

---

## 云间Bot · 万象系列是什么

云间Bot 是云间工作室开发的组合 Skill 工具，也可以直接装进 Grok Bot 调用。起元系列给你造 AI 的本事；万象系列给你做自媒体的本事——写稿、做图、出视频，一门手艺一位，每位单装就能从头干到尾。

一期只有一位：管写稿的 **执笔**。做图的丹青、做视频的掠影在后面。

## 执笔 · Pen

> 你讲一段亲身经历，它写成开口就抓人的口播或值得收藏的长文；料里没有的事，一个字不编。

**它和一般写稿 AI 不一样的地方**

- **只写你的真事**：每句交稿都附出处，抄得出你原话的才写；约数照约数、打算照打算、「至少」「应该」这类留口子的话原样留着。自带检查脚本把编造、说满、改了完成状态当硬错拦。
- **三个底盘**：你的作者档案和口吻档案、平台打法库（抖音、视频号、公众号、X）、爆款库（按点赞收藏拆成卡，借位置和节奏，不搬句子和数字）。
- **形式跟着平台走**：抖音、视频号写口播，公众号写长文，X 写帖子串；一稿能改成每个平台的版本。

**十五个技能**

| # | 技能 | 做什么 |
|---|---|---|
| 1 | 第一次见面 | 像采访一样一次问一件，建好作者档案；支持「演练」模式，只打印不存 |
| 2 | 学口吻 | 从你 3～10 段样稿总结口吻档案，每项带原话证据，试写请你打分 |
| 3 | 参考进来 | 你丢来的视频、录音、文章、截图先变成文字，整理成素材 |
| 4 | 选题与标题 | 从你的真事里挑写哪件，出 5 个标题推荐 1 个，数字都有出处 |
| 5 | 骨架与开头 | 清点料、过开头关、按爆款卡的钩子链搭骨架，出 3～5 个开头 |
| 6 | 出稿 | 写成整条口播或整篇长文，逐句出处表，跑检查脚本 |
| 7 | 改稿 | 轻改、深改两档，去 AI 味，用你自己的话补进去，不添事实 |
| 8 | 照参考仿写 | 贴写、借骨、取神三档，重点不丢，人家的数不搬 |
| 9 | 多平台改写 | 按平台重写标题、开头、篇幅、福利交付，清掉导流词 |
| 10 | 配图和画面 | 封面方向、封面文字（数字和正文一字不差）、口播画面表、提示词或制作单 |
| 11 | 发前自检 | 平台规则、AI 味、排版结构、缺什么，四问逐项给结论 |
| 12 | 丢链接就抓 | 抖音、视频号、公众号、X 等 18 个平台，免费办法优先，外文附中文译文 |
| 13 | 库管家 | 爆款收进库、按格式拆卡、平台打法和表达库的整理和每周更新 |

另有两个后台技能：`pen-install` 负责安装（顺带装公共底盘的库和抓取工具），`pen-update` 负责更新。

## 安装

1. 在 Grok Bot 里点开执笔的分享链接，把它请进来：

   | 成员 | 分享链接 |
   |---|---|
   | 执笔 Pen | https://x.ai/bot/NJcMysJV_8mT5AjEJWziD |

2. 第一次对话时它会问能不能从本仓库装齐技能，说可以，一分钟装好，不装插件、不要密钥。

**手动安装**（能跑 shell 的 Bot；Claude Code 等在 `bash` 前加技能目录，如 `PEN_SKILL_DIR=~/.claude/skills bash`）：

```bash
curl -fsSL https://raw.githubusercontent.com/yunjian-ai/yunjian-zimeiti/pen-v0.2.4/members/pen/dist/install.sh | bash
```

**更新、修复、反馈**，都是一句话：
- **更新**：装好后选「自动」（每周一 9 点查新版，你点头才装）或「一句话」（说「更新执笔」）。你的档案和你自己的库都不动。
- **修复**：说「修一下执笔」，它先体检、你同意才恢复；你改过的先备份到 `~/yunjian-backup/`。
- **反馈**：说「我要反馈」，它整理成去掉隐私的反馈单，由你自己提交到[反馈表单](https://www.feishu.cn/share/base/form/shrcnFyVGCVJkpcH7lfjOD8Ec6b)或 [Issues](https://github.com/yunjian-ai/yunjian-zimeiti/issues)。

**抓取要不要花钱？** 免费办法优先：抖音、X 能免费拿到正文和互动数，视频号能免费拿到数据。视频、逐字稿、公众号阅读数这类要付费接口的，会先问你、你同意才用，密钥只放你自己电脑的环境变量，不进聊天。

## 示例和考题

`members/pen/examples/` 里有虚构主人从头用到尾的全过程；`members/pen/tests/考题v0.2.md` 是发版前用全新 AI 考的题和合格标准。

## 路线图

| 系列 | 成员 | 职能 | 状态 |
|---|---|---|---|
| 万象 | 执笔 Pen | 写稿：口播、长文、仿写、多平台 | ✅ v0.2.0 |
| 万象 | 丹青 | 做图 | 规划中 |
| 万象 | 掠影 | 做视频 | 规划中 |

起元系列（提示词、Skill、蒸馏、本体、验证、统筹）在 [yunjian-ai/yunjian](https://github.com/yunjian-ai/yunjian)。

## 加微信交流

<img src="assets/wechat-qr.jpg" alt="微信二维码" width="240">

## 常见问题

**要装插件或给密钥吗？** 写稿不用。抓取的付费兜底要你自己的密钥，存在你自己电脑上，用之前先问你。

**会替我发布吗？** 不会。执笔只交文字和方案，发布由你来点。

**它会编故事吗？** 不会。料不够它先问你；每句交稿都附出处，检查脚本把料外的数字、说满的结果、改掉的完成状态当硬错拦。

**一定要装起元吗？** 不用，执笔单装就能用。

## 参与开发

`python3 tools/validate.py` 查格式和禁用词，`python3 tools/pack.py` 打包，`python3 members/pen/tests/run_tests.py` 跑测试；只依赖 Python 3 自带的库（抓取工具另有 `members/pen/抓取/requirements.txt`）。怎么参与见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可

© 2026 GangGe。内容和代码分开授权，全文在 [LICENSE](LICENSE)：

- **文字类**（技能、卡片、库、示例、考题，shared/ 里的规范，以及各种说明文档）用 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.zh-hans)：可以转载、改编，注明「云间Bot Cloudmere · GangGe」并附上仓库地址即可。
- **工具代码**（tools/、tests/ 里的脚本、.github/、安装脚本、检查脚本）：MIT。
- **第三方**：`members/pen/抓取/` 改自 [BeatAPI/omniscraper](https://github.com/BeatAPI/omniscraper)（MIT，原许可证保留在该目录）；中文套话清单参考了 Humanizer-zh（MIT）。

---

## English

**Cloudmere (云间Bot · 万象)** is the content-creation series of Cloudmere, a set of members built for bots such as Grok Bot. Its first member, **Pen (执笔)**, turns things you actually did into short-video scripts and long-form posts that sound like you, then adapts them for each platform (Douyin, WeChat Channels, WeChat Official Accounts, X). Every sentence it delivers cites your own words; a bundled checker blocks invented facts, overstated results and changed completion states. It never publishes for you.
