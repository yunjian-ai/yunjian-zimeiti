---
id: brand-font-anton
类: 品牌元素
元素: 字体
名字: Anton（英文特粗窄体）
适用图: [标题, 海报, 视频封面, 分镜关键帧]
版本: 1
用过: 0
选中: 0
---
## 什么样
英文特粗、很窄的无衬线体，只有一种粗细，字母高、挤得紧，几个大写单词就能铺满画面。MV、音乐、潮牌、运动类海报和「大字压人」那种版式常用。**只有英文字母、数字和符号，没有中文**。

## 怎么做
开源字体，授权为 SIL 开源字体许可 1.1（可商用、可嵌入；Google Fonts 收录，授权原文 https://github.com/google/fonts/blob/main/ofl/anton/OFL.txt ）。用到时下载到 `~/.yunjian/paint/字体/`：`curl -fsSL -o ~/.yunjian/paint/字体/Anton-Regular.ttf https://raw.githubusercontent.com/google/fonts/main/ofl/anton/Anton-Regular.ttf`。图层里写 `"font": "Anton", "fontFile": "<字体文件路径>"`，叠图和调图网页都认，网页里能双击改字。

## 平台提醒（只提醒，主人定）
—

## 注意
- 大字要压在人后面：图层从下往上是 底（背景）→ 大字 → 抠出来的人，人那层用透明底 PNG。
- 中文标题别用它（没有中文字形，会掉成别的字体）；中英混排时中文配思源黑体 Heavy。
