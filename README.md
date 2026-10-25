<p align="center"><img src="assets/hero.png" alt="云间Bot · 万象 Cloudmere" width="100%"></p>

<h1 align="center">云间Bot · 万象 Cloudmere</h1>

<p align="center"><b>一元复始，万象更新。</b><br>起元教 AI 做事，万象替你把自己的事讲出去。第一位手艺人执笔，把你亲手做过的事落笔成文：口播一开口就留得住人，长文读着像你本人在讲；丹青作画、掠影成片，随后就到。你只管开口。</p>

<p align="center">执笔 Pen · cloudmere · Grok Bot 口播稿、长文、仿写、去 AI 味、多平台改写助手 · 仓库 <a href="https://github.com/yunjian-ai/yunjian-zimeiti">github.com/yunjian-ai/yunjian-zimeiti</a></p>

<p align="center">
  <a href="CHANGELOG.md"><img alt="执笔" src="https://img.shields.io/badge/执笔-v0.3.1-c0392b"></a>
  <a href="LICENSE"><img alt="license" src="https://img.shields.io/badge/license-CC%20BY%204.0%20%2B%20MIT-555555"></a>
  <a href="https://github.com/yunjian-ai/yunjian-zimeiti/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/yunjian-ai/yunjian-zimeiti/actions/workflows/ci.yml/badge.svg"></a>
</p>

<p align="center"><a href="#english">English</a> · <a href="#执笔--pen">执笔</a> · <a href="#安装">安装</a> · <a href="#路线图">路线图</a> · <a href="#常见问题">常见问题</a></p>

---

## 云间Bot · 万象系列是什么

云间Bot · 万象系列是云间工作室开发的第二个组合 Skill 工具，也可以直接装进 Grok Bot 调用。

名字取自「一元复始，万象更新」：起元是开端，万象是开端之后的万千气象。这一系列给你的是做自媒体的本事——写稿、作画、成片，一门手艺一位，每位单装就能从头干到尾。

现在有一位：管写稿的 **执笔**。管作画的丹青、管成片的掠影在后面。

## 执笔 · Pen

> 你讲一段亲身经历，或者丢一篇好文章，它问清一句就交排好版、配好图的成品：开口就抓人的口播、值得收藏的长文；你没说过的事，一个字不编。

**十三个技能，各干一步**

| # | 技能 | 做什么 |
|---|---|---|
| 1 | 第一次见面 | 像采访一样一次问一件，建好作者档案；支持「演练」模式，只打印不存 |
| 2 | 学口吻 | 读你 3～10 段平时说的、写的，学会你怎么说话，试写一段请你打分 |
| 3 | 参考进来 | 你丢来的视频、录音、文章、截图先变成文字，整理成素材 |
| 4 | 选题与标题 | 从你的真事里挑写哪件，出 5 个标题推荐 1 个，标题里的数字都是你说过的 |
| 5 | 骨架与开头 | 照爆款的节奏搭好骨架，出 3～5 个能留住人的开头让你挑 |
| 6 | 出稿 | 写成整条口播或整篇长文，一口气改好、配好图交成品；每句出处和检查记录放在自查记录里，想看再看 |
| 7 | 改稿 | 轻改、深改两档，改到像你本人说的、闻不到 AI 味，不添一件事 |
| 8 | 照参考仿写 | 学人家的骨架，料换成新的：你的真事，或它上网找来、打开核对过、带链接的真实案例，再跟爆款库比、取更强的打法 |
| 9 | 多平台改写 | 按平台重写标题、开头、篇幅、福利交付，清掉导流词 |
| 10 | 配图和画面 | 封面方向、封面文字（数字和正文一字不差）、口播画面表、提示词或制作单 |
| 11 | 发前自检 | 平台规则、AI 味、排版结构、缺什么，四问逐项给结论 |
| 12 | 丢链接就抓 | 抖音、视频号、公众号、X 等 18 个平台，免费办法优先，外文附中文译文 |
| 13 | 库管家 | 把爆款收进你的库、拆成能照着学的卡，每周整理一次，越用越懂你的平台 |

另有两个后台技能：`pen-install` 负责安装（顺带装好爆款库和抓取工具），`pen-update` 负责更新。

## 安装

1. 在 Grok Bot 里点开执笔的分享链接，把它请进来：

   | 成员 | 分享链接 |
   |---|---|
   | 执笔 Pen | https://x.ai/bot/NJcMysJV_8mT5AjEJWziD |

2. 第一次对话时它会问能不能从本仓库装齐技能，说可以，一分钟装好，不装插件、不要密钥。

**手动安装**（能跑 shell 的 Bot；Claude Code 等在 `bash` 前加技能目录，如 `PEN_SKILL_DIR=~/.claude/skills bash`）：

```bash
curl -fsSL https://raw.githubusercontent.com/yunjian-ai/yunjian-zimeiti/pen-v0.3.1/members/pen/dist/install.sh | bash
```

**更新、修复、反馈**，都是一句话：
- **更新**：装好后选「自动」（每周一 9 点查新版，你点头才装）或「一句话」（说「更新执笔」）。你的档案和你自己的库都不动。
- **修复**：说「修一下执笔」，它先体检、你同意才恢复；你改过的先备份到 `~/yunjian-backup/`。
- **反馈**：说「我要反馈」，它整理成去掉隐私的反馈单，由你自己提交到[反馈表单](https://www.feishu.cn/share/base/form/shrcnFyVGCVJkpcH7lfjOD8Ec6b)或 [Issues](https://github.com/yunjian-ai/yunjian-zimeiti/issues)。

## 示例和考题

`members/pen/examples/` 里有一位虚构主人从头用到尾的全过程；`members/pen/tests/考题v0.2.md` 是发版前用全新 AI 考的题和合格标准。

## 路线图

| 系列 | 成员 | 职能 | 状态 |
|---|---|---|---|
| 万象 | 执笔 Pen | 写稿：口播、长文、仿写、多平台 | ✅ v0.3.1 |
| 万象 | 丹青 | 做图 | 规划中 |
| 万象 | 掠影 | 做视频 | 规划中 |

起元系列（提示词、Skill、蒸馏、本体、验证、统筹）在 [yunjian-ai/yunjian](https://github.com/yunjian-ai/yunjian)。

## 加微信交流

<img src="assets/wechat-qr.jpg" alt="微信二维码" width="240">

## 常见问题

**要装插件或给密钥吗？** 写稿不用。抓取的付费兜底要你自己的密钥，存在你自己电脑上，用之前先问你。

**会替我发布吗？** 不会。执笔交排好版的稿子和图，发布由你来点。

**它会编故事吗？** 不会。你的经历只用你说过的，缺了就删掉写通顺、告诉你可以补哪几句；别人的案例都带出处链接；每句都有出处，检查脚本把料外的数字、说满的结果、改掉的完成状态当硬错拦。

**抓取要不要花钱？** 免费办法优先：抖音、X 能免费拿到正文和互动数，视频号能免费拿到数据。要视频、逐字稿、公众号阅读数时才用付费接口，先问你、你同意才用，密钥只放在你自己电脑上，不进聊天。

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

**Cloudmere (云间Bot · 万象)** is the content-creation series of Cloudmere, a set of members built for bots such as Grok Bot. Its first member, **Pen (执笔)**, turns things you actually did into short-video scripts and long-form posts that sound like you, then adapts them for each platform (Douyin, WeChat Channels, WeChat Official Accounts, X). It asks one question, then hands back a finished, laid-out piece with images. When remaking an article, it keeps the structure and swaps in fresh, verified real-world cases with source links. Every fact is traced to your own words or a cited source; a bundled checker blocks invented facts, overstated results and changed completion states. It never publishes for you.
