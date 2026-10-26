# 丹青公共库

> 随丹青安装到 `~/.yunjian/paint/库/`，每次更新整份换新，只读不改。主人自己的东西在 `~/.yunjian/paint/我的库/`，更新永不覆盖；计数记在 `我的库/统计.json`。

| 放什么 | 在哪 | 谁用 |
|---|---|---|
| 平台官方规格（给人看） | `平台规格.md` | paint-brief 第 4 问、paint-make |
| 平台规格（机读，两份一起改） | `规格表.json` | paint-check 的 `check_paint.py` |
| 场景模板：白底、棚拍、生活场景 | `场景/` | 需求单第 5 问「景」 |
| 品牌元素：logo 位、宣传语条、角标、价格条、字体 | `品牌元素/` | 需求单第 6 问 |
| 参考方向卡＋好图标准 | `参考/` | 需求单第 7 问、paint-check |

卡的格式和检查：`python3 <技能目录>/paint-brief/check_brief.py --library ~/.yunjian/paint/库`。
