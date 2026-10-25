"""执笔交稿前的机械检查。只用标准库，只报不改。
用法：python3 check_pen.py 稿子.txt [--material 料.txt …] [--form 口播|长文] [--seconds 60] [--platform 抖音] [--ad] [--source 原稿.txt --tier 1|2|3] [--json]
稿子写 - 表示从标准输入读，不用建文件。标题写成「标题：…」一行会单独查长度，「约 N 字」「出处」这类交稿说明行自动跳过。
两级：❌ 硬错（字数、长句、口播结尾没有收尾引导、料外数字、带货稿的极限词、功效承诺、导流、量产腔、翻案腔、名词化、黑话、标题超长），有一处退出码就是 1；
⚠️ 提醒（待问残留、料外概括、路标词、非带货稿的极限词、句长太齐、连词太密、「的」字长句、同头排比、比喻换场），要回原文判断，不算失败。
查到的是线索；查不出不等于没问题（比如汉字写的数字「十个里有七个」不查数字出处）。"""
import argparse
import json
import re
import statistics
import sys
from pathlib import Path

RATE = (220, 260)  # 每分钟字数，形式卡第一节；这个范围本身就是上下限，不再放宽
LONG = 25  # 口播一句不超过 25 字
CARD = Path(__file__).resolve().parent / "平台卡.md"  # 标题上限、导流禁用词都从平台卡读，平台改了只改那一处
ALIAS = {"微信公众号": "公众号", "知乎专栏": "知乎", "微博头条文章": "微博", "X Article": "X"}
EXTREME = ["全网最", "史上最", "最好用", "最好的", "最佳", "最低价", "最便宜", "第一名", "销量第一", "排名第一", "顶级", "国家级", "最高级", "首选", "100%有效", "绝对有效"]
HEALTH = ["治好", "根治", "治愈", "疗效", "药到病除", "包治", "稳赚", "保本", "保证收益", "零风险", "再也不乱",
          "一周变现", "保证通过", "包过", "稳过", "百分百有效", "月入过万", "躺赚", "绝对正品", "亏本清仓", "跳楼价", "全网最低",
          "买到顶", "毕业款", "扣1领", "扣 1 领", "转发朋友圈领"]  # 带货卖课.md 第三节（库）；虚假稀缺另查
FAKE_SCARCE = [r"最后\s*[一二两三四五\d]+\s*(?:单|件|个|份|名)", r"(?:最后|仅剩|只剩)\s*[一二两三四五\d]+\s*分钟", r"原价\s*\d+[^。！？\n]{0,8}今天\s*\d+"]
LEAD_DEFAULT = ["微信", "vx", "V信", "加V", "加我", "二维码", "扫码", "私信", "公众号", "主页", "链接", "网址", "http", "www", ".com", ".cn"]
LEAD_OK = {"公众号", "X"}  # 这些平台允许引导或放链接
# 去AI味卡 B5、E 组「必改」：量产腔、起跑铺垫、客服腔、说教
STOCK = ["家人们", "宝子们", "亲们", "点赞收藏关注", "点赞关注", "我们下期见", "今天跟大家聊聊", "让我们来看看", "接下来让我们", "以下是你需要知道的",
         "你要明白", "在当今", "希望对你有帮助", "好问题"]
# C1 路标词「看情况」：真人也会说，只提醒
ROAD = ["综上所述", "总而言之", "值得注意的是", "需要指出的是", "不难发现", "说白了", "说穿了", "本质上", "换句话说", "不可否认", "这意味着"]
JARGON = ["赋能", "抓手", "底层逻辑", "顶层设计", "商业闭环", "价值闭环", "降本增效", "认知升级", "认知跃迁", "全链路", "组合拳", "价值释放",
          "彰显", "标志着", "开启了新篇章", "焕然一新"]
# 去AI味卡 A1：先立误解再推翻。按动作列常见外衣，换字面照样算
PIVOT = [r"(?:并)?不是[^。！？\n，,]{1,30}[，,]\s*(?:而)?是", r"不是[^。！？\n]{1,30}[。！]\s*而是", r"并非[^。！？\n]{1,30}而是",
         r"不在于[^。！？\n]{1,30}而在于", r"问题不在[^。！？\n，,]{1,20}[，,]\s*(?:而)?(?:在|是)", r"与其说[^。！？\n]{1,30}(?:不如|倒不如|毋宁)",
         r"以为[^。！？\n]{1,40}(?:其实|结果|才发现|后来才)", r"回头(?:看|一看)?才(?:发现|明白|知道)", r"看似[^。！？\n]{0,40}(?:其实|实则|实际)",
         r"表面(?:上)?[^。！？\n]{0,40}(?:其实|实则|实际)", r"[^，。！？\n]{1,12}不重要[，,]\s*(?:重要|要紧)的是", r"从来(?:都)?不是",
         r"不只是?[^。！？\n，,]{1,30}[，,]\s*(?:更|还)?是", r"恰恰相反", r"说到底"]
NOMINAL = [r"进行(?:了|一次)?[一-鿿]{0,6}(?:调整|优化|升级|分析|讨论|沟通|梳理|复盘|探索|尝试|整理|规划)",
           r"实现了?[一-鿿]{0,8}(?:提升|增长|突破|转变|跃升)", r"完成了?对[^。，！？\n]{1,16}的", r"起到了?[^。，！？\n]{0,12}作用",
           r"具有[^。，！？\n]{0,10}(?:意义|价值)"]
# 写法卡第三节：替主人下的概括、听来的话、比较；料里原样有这句就放过
GENERALIZE = [r"多半", r"大多(?:数)?", r"大部分人", r"很多人", r"不少人", r"绝大多数", r"往往", r"普遍", r"有人问我", r"客户都说", r"大家都(?:说|知道|觉得)",
              r"粉丝(?:问|留言)", r"效果一样", r"十个[^，。！？\n]{0,4}有[一二三四五六七八九]个",
              r"想不到", r"没想到", r"难得", r"常见的原因"]  # 后四个：为了衔接顺手带进的想法、频率、原因（第 4 轮判分 A）
SCOPE = ["剩下的", "全都", "没人", "从来", "一直", "惦记", "动过", "当着", "第一件事", "每次都", "总是",  # 范围、动作细节（第 5 轮判分 A）
         "天天", "每天都在", "只留", "只剩", "只挂", "没动别的",  # 频率升级、结果说满（第 7 轮判分 H）
         "空了", "清空", "再也不用", "彻底",  # 结果说满（第 8 轮判分 I：「能看到底」写成「空了」）
         "没让", "一件都不用",  # 否定句加事实（第 10 轮判分 M：「我没让她扔一件」）
         "开心", "高兴", "感动", "心疼", "焦虑", "崩溃", "松了口气", "踏实", "委屈", "犯愁"]  # 人的感受（料里没有就是编）
SCOPE_RE = [re.compile(r"困(?![难惑扰境局])")]  # 「困」是状态，「困难」不算
SELF_LABEL = re.compile(r"(我的概括|我的判断|我对.{0,8}的概括|判断|推断|补的说明)")  # 出处表里自己标的加话（第 9 轮判分 K）
HEDGE = ["至少", "应该", "大概", "差不多", "好像", "基本上", "估计"]  # 人家话里留口子的词（第 8 轮判分 I：「至少不用每箱都打开」写成「不用开箱」）
PLAN = re.compile(r"(?:要|打算|准备|计划|想)([\u4e00-\u9fff]{2})")  # 料里的打算：稿里写成「动作了」「已经动作」就是改了完成状态
SOURCE_TALK = ["真实发生", "真实的结果", "的说法", "口径", "都是这次", "这次整理里的", "都是同一个", "别处领", "不用再去别处", "是真的", "没有编", "不是编的", "这条料", "这份料", "这份材料", "材料里", "料里写", "这里不猜", "不替她猜", "这里认的是", "别拼成", "的做法里没有", "不能据此", "不能直接推出", "推不出"]  # 正文对观众自证出处（全量回归根子 X）、讲范围（第 3 次根子 EE）
COPY_RUN = 15  # 仿写原创度：和原稿连续相同多少字算照搬（pen-remake，二三档不许）
CONJ = ["因为", "所以", "但是", "然而", "同时", "此外", "而且", "并且", "因此", "不仅"]
METAPHOR = {"仓储": ("仓库", "库存", "入库"), "赛道": ("赛道", "跑道", "终点线", "弯道超车"), "海洋": ("浪潮", "潮水", "蓝海", "灯塔", "彼岸"),
            "建筑": ("地基", "坍塌", "支柱", "基石", "底座"), "温度": ("降温", "升温", "余温"), "机器": ("引擎", "齿轮", "血管", "骨架")}
LABELS = re.compile(r"【(前 ?3 ?秒|正文|结尾)】")
SEG = re.compile(r"^\s*(?:[🟥🟧🟨🟩🟦🟪⬛⬜]\s*)?[①-⑳]\s*[^\s〔0-9]+")  # 口播分段段头（形式卡第一节）：「🟥 ① 钩子 0～3″〔提示〕」
MARK = re.compile(r"【[^】]*】")
HARD = {"ENDING_NO_GUIDE", "QUESTION_PILE", "SOURCE_TALK", "REPEAT_PAD", "SELF_LABEL", "HEDGE_DROPPED", "SCOPE_WORD", "FAKE_QUOTE", "STATE_CHANGED", "COPY_RUN", "FAKE_SCARCE", "APPROX_CHANGED", "LENGTH_OFF", "LONG_SENTENCE", "INVENTED_NUMBER", "EXTREME_WORD", "HEALTH_CLAIM", "LEAD_WORD", "AI_STOCK", "PIVOT", "NOMINAL", "JARGON", "TITLE_LONG"}


def read_card(path=CARD):
    """从平台卡读各平台标题上限和导流禁用词；读不到就用保守的默认值。"""
    titles, lead = {"小红书": 20, "公众号": 64}, list(LEAD_DEFAULT)
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return titles, lead
    for sec in re.split(r"\n### ", text)[1:]:
        name = re.split(r"[（(\n]", sec, maxsplit=1)[0].strip()
        m = re.search(r"标题(?:上限：)?\s*(\d+)\s*字", sec)
        if m:
            titles[ALIAS.get(name, name)] = int(m.group(1))
    m = re.search(r"## 三、导流禁用词[^\n]*\n([^\n]+)", text)
    if m:
        lead = [w.strip("「」。 ") for w in m.group(1).split("、") if w.strip("「」。 ") and "某某" not in w]
    return titles, lead


TITLE_MAX, LEAD = read_card()
CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def approx_numbers(text):
    """料里的约数（四十多、七八个、八万多、十来个）→ 它容易被写成的精确数。"""
    out = {}
    for m in re.finditer(r"([一二两三四五六七八九])?十([一二三四五六七八九])?(多|来)", text):
        base = (CN_NUM.get(m.group(1), 1)) * 10 + CN_NUM.get(m.group(2), 0)
        out[m.group()] = {str(base)}
    for m in re.finditer(r"([一二两三四五六七八九])([一二三四五六七八九])(?=[个件块元天次年家人位张条本])", text):
        out[m.group()] = {str(CN_NUM[m.group(1)]), str(CN_NUM[m.group(2)])}
    for m in re.finditer(r"([一二两三四五六七八九])万多", text):
        out[m.group()] = {f"{CN_NUM[m.group(1)]}万", str(CN_NUM[m.group(1)] * 10000)}
    return out


def cn_numbers(text):
    """料里汉字写的数（两天、十二分钟、一千八百台）→ 阿拉伯数字，稿子写成「2 天」「12 分钟」不算编（示例重走 v0.2.1 三组反馈）。只认后面跟量词的。"""
    out = set()
    for m in re.finditer(r"[零一二两三四五六七八九十百千]+(?=[个件块元天次年家人位张条本台分秒小时月周倍岁期斤米升瓦成])", text):
        s, total, cur = m.group(), 0, 0
        for ch in s:
            if ch in CN_NUM:
                cur = CN_NUM[ch]
            elif ch in "十百千":
                total += (cur or 1) * {"十": 10, "百": 100, "千": 1000}[ch]
                cur = 0
        out.add(str(total + cur))
    return out


def xhs_len(text):
    """小红书标题：中文和标点算 1，英文和数字算 0.5（平台卡第四节）。"""
    return sum(0.5 if re.match(r"[A-Za-z0-9]", ch) else 1 for ch in text if not ch.isspace())


def han(text):
    return len(re.findall(r"[一-鿿]", text))


META = re.compile(r"^\**(约 ?\d+ ?(?:字|秒|分钟)|目录[：:]|要准备|引导|出处|待问|推算|稿型|句长|机械检查|钩子链|钩子骨架|重点|参照|借用单|推进节点|材料清单|观众带走|开头候选|标题候选|母版|平台和形式|档位|原创度|换掉的事实|重点不丢|收藏件[｜|：:]|福利|搜索词|清扫|两版差别)[\**：:（(｜|]?")


def split_draft(text):
    """拆出标题和正文：去掉交稿说明行、段落标签，正文只留要念 / 要读的。
    口播稿有【前 3 秒】标签时只取【前 3 秒】到【结尾】那一段（结尾后遇空行停）；长文遇到单独一行 --- 停（后面是出处表、钩子链）。
    交稿头「母版｜口播 60 秒」、借用单、推进节点这些说明行不算正文，不数字数、不查数字（全量回归根子 Q）。"""
    title, out = "", []
    if any(SEG.match(l.strip()) for l in text.splitlines()):  # 分段格式：只取段头下面的台词，一段并成一行（行间用 / 断开，不算字）
        cur = None
        for line in text.splitlines():
            s = line.strip()
            m = re.match(r"^\**标题\**[：:]\s*(.+)", s)
            if m and not out and cur is None:
                title = title or re.sub(r"[（(].*$", "", m.group(1)).strip().strip("*")
                continue
            if SEG.match(s):
                cur = []
                out.append(cur)
                continue
            if cur is None or not s:
                continue
            if META.match(s) or s == "---":
                break
            cur.append(s.replace("==", ""))
        return title, ["/".join(x) for x in out if x]
    labeled = any(re.search(r"【前 ?3 ?秒】", l) for l in text.splitlines())
    started, ending = not labeled, False
    for line in text.splitlines():
        s = line.strip()
        m = re.match(r"^\**标题\**[：:]\s*(.+)", s)
        if m:
            title = title or re.sub(r"[（(].*$", "", m.group(1)).strip().strip("*")
            continue
        if labeled and not started:
            if not re.search(r"【前 ?3 ?秒】", s):
                continue
            started = True
        if ending and not s:
            break
        if out and s == "---":
            break
        if not s or META.match(s) or "原话「" in s or re.match(r"^第 ?\d+ ?句 ?→", s):
            continue
        if re.search(r"【结尾】", s):
            ending = True
        out.append(LABELS.sub("", s))
    return title, out


def body_lines(text):
    return split_draft(text)[1]


def count_chars(text):
    """汉字、字母、数字各算一个字；标点、停顿 /、加粗 ** 不算。"""
    return len(re.findall(r"[一-鿿A-Za-z0-9]", MARK.sub("", text)))


def numbers(text):
    text = re.sub(r"\d+(?:\.\d+)?%?\s*[一-鿿]{0,2}\s*【推算[^】]*】", "", text)  # 数字后面（隔一两个字，如「32 个」）跟着【推算：算式】的不算编
    text = MARK.sub("", text)  # 【问】【推算】里面的数也不算
    text = re.sub(r"(?m)^\s*\d+[.、）)]", "", text)  # 列表序号
    text = re.sub(r"(?m)^\s*#{1,6}\s*(?:[一二三四五六七八九十]+、)?\s*\d+(?:\.\d+)*", "", text)  # 长文小节编号「### 1.1」
    text = re.sub(r"(?m)^\s*\**\s*\d+\s*/\s*\d+\s*\**", "", text)  # 帖子串编号「1/6」
    return set(re.findall(r"\d+(?:\.\d+)?%?", text))


def sentences(body):
    """按句号、问号、换行切句；「1. 2. 3.」开头的编号清单行、# 开头的小标题不算（天然一样长或本来就短，去AI味卡第三节放过；第 11 轮考生反馈）。"""
    body = re.sub(r"(?m)^\s*(?:\d+[.、）)]|[-•]|#{1,6}\s)\s*.*$", "", MARK.sub("", body))  # 小标题（# 开头）也不算：它们本来就短
    return [s for s in re.split(r"[。！？!?\n]", body.replace("*", "")) if han(s) >= 4]


def check(doc):
    """doc：{"body": 稿子, "material": [料], "form": "口播"/"长文", "seconds": 秒数或 None, "platform": 平台或 None, "ad": 是不是带货稿}。
    返回问题列表，每项 {"code", "level": "硬"/"提醒", "text", "hint"}。"""
    title, lines = split_draft(doc.get("body", ""))
    body = "\n".join(lines)
    plain = MARK.sub("", body)
    form, sec, plat, ad = doc.get("form") or "口播", doc.get("seconds"), doc.get("platform"), doc.get("ad")
    mats = doc.get("material") or []
    matx = "\n".join(mats)
    issues = []

    def add(code, text, hint):
        hard = code in HARD and not (code == "EXTREME_WORD" and not ad) and not (code == "COPY_RUN" and doc.get("tier") == 1)
        # 极限词只在带货稿算违法，别的稿只提醒；仿写一档（贴写）照搬只提醒
        issues.append({"code": code, "level": "硬" if hard else "提醒", "text": text, "hint": hint})

    n = count_chars(body)
    pending = len(re.findall(r"【问", body))
    if form == "口播" and sec:
        lo, hi = sec * RATE[0] / 60, sec * RATE[1] / 60
        if not lo <= n <= hi:
            if ad and pending >= 3 and lo * 0.85 <= n < lo:  # 带货稿【问】占位多：差一点只提醒，差太多照样硬错（第 12 轮乙卷 73 字）
                add("LENGTH_PENDING", f"约 {n} 字（另有 {pending} 处【问】）", f"{sec} 秒应在 {round(lo)}～{round(hi)} 字，主人答完【问】再补足")
            else:
                add("LENGTH_OFF", f"约 {n} 字", f"{sec} 秒应在 {round(lo)}～{round(hi)} 字之间")
    if form == "口播":
        for piece in re.split(r"[。！？!?；;，,、…/\n：:]", plain.replace("*", "")):
            if count_chars(piece) > LONG:
                add("LONG_SENTENCE", piece.strip(), f"超过 {LONG} 字不断开")
    if title and plat in TITLE_MAX:
        n_title = xhs_len(title) if plat == "小红书" else len(re.sub(r"\s", "", title))
        if n_title > TITLE_MAX[plat]:
            add("TITLE_LONG", f"{title}（{n_title:g} 字）", f"{plat}标题不超过 {TITLE_MAX[plat]} 字")
    approx = approx_numbers(matx)
    if mats:
        have = set().union(*(numbers(m) for m in mats), *approx.values(), cn_numbers(matx))  # 约数改精确数单独报 APPROX_CHANGED
        for x in sorted(numbers(title + "\n" + body) - have):
            add("INVENTED_NUMBER", x, "料里没有的数：改、标【推算】或【问】")
    for phrase, exact in approx.items():
        if phrase not in plain and any(re.search(rf"(?<![0-9.]){re.escape(x)}(?![0-9.])", plain) for x in exact):
            add("APPROX_CHANGED", phrase, "约数改成精确数：照原话写")
    for words, code, hint in ((EXTREME, "EXTREME_WORD", "极限词（规则卡 8）：换具体好处或数字"),
                              (HEALTH, "HEALTH_CLAIM", "功效收益承诺（带货卖课.md 第三节，库）：换真实感受或结果加条件"),
                              (STOCK, "AI_STOCK", "量产腔（去AI味 B5、E）"),
                              (ROAD, "ROAD_SIGN", "路标词（C1）：删了不少意思就删"),
                              (JARGON, "JARGON", "黑话拔高（C3、C4）：换成人、动作、钱、时间")):
        for w in words:
            if w in plain:
                add(code, w, hint)
    if plat not in LEAD_OK:
        for w in LEAD:
            if w.lower() in plain.lower():
                add("LEAD_WORD", w, "导流（平台卡三）：福利写进正文")
    spans = []
    for p in PIVOT:
        for m in re.finditer(p, plain):
            if m.group() in matx:  # 主人料里原样的话是主人的说法，不算
                continue
            if not any(m.start() < e and m.end() > s for s, e in spans):  # 同一处只报一次
                spans.append(m.span())
                add("PIVOT", m.group(), "翻案腔（A1）：判断正面说")
    for p in FAKE_SCARCE:
        for m in re.finditer(p, plain):
            if m.group() not in matx:
                add("FAKE_SCARCE", m.group(), "虚假稀缺（带货卖课.md 第三节，库）")
    for p in NOMINAL:
        for m in re.finditer(p, plain):
            add("NOMINAL", m.group(), "名词化（C2）：写动作")
    for p in GENERALIZE:
        for m in re.finditer(p, plain):
            if m.group() not in matx:
                add("GENERALIZE", m.group(), "料外概括（写法卡三）：标料号或删")
    if mats:  # 出处表里「料原话「…」」要在料里原样搜得到（去掉空格标点再比）
        squash = lambda t: re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", t)
        whole = squash(matx)
        for q in re.findall(r"原话「([^」]+)」", doc.get("body", "")):
            if squash(q) and squash(q) not in whole:
                add("FAKE_QUOTE", q, "出处表引的原话料里搜不到（写法卡三）：抄料里的原句，抄不出就是编的")
    for w in SCOPE + SCOPE_RE:
        hit = (w.search(plain) and not w.search(matx)) if hasattr(w, "search") else (w in plain and w not in matx)
        if hit and mats:
            add("SCOPE_WORD", w if isinstance(w, str) else w.pattern[0], "范围、频率、结果、感受（写法卡三）：料里没有就是编，删掉或照料写")
    for line in doc.get("body", "").split("\n"):
        m = "→" in line and not META.match(line.strip()) and SELF_LABEL.search(re.sub(r"「[^」]*」", "", line.split("→", 1)[1]))  # 引号里的原话不算；钩子链、推进节点这些说明行不是出处表
        if m:
            add("SELF_LABEL", m.group(1), "出处表只许四种：料原话／连接，不带事实／处境问句／给观众的动作或问题；自己的概括、判断、补的说明整句删（写法卡三）")
    for key in {m.group(1) for h in HEDGE for m in re.finditer(h + r"([\u4e00-\u9fff]{2})", matx)}:
        for sent in re.split(r"[。！？\n]", plain):
            if key in sent and not any(h in sent for h in HEDGE):
                add("HEDGE_DROPPED", sent.strip()[:30], f"料里「{key}」前面有「至少／应该」这类留口子的词，稿里丢了（写法卡三）：原样带上，或不写这句")
    for verb in {m.group(1) for m in PLAN.finditer(matx)}:
        if verb + "了" not in matx and (verb + "了" in plain or "已经" + verb in plain):
            add("STATE_CHANGED", verb, "料里是打算，稿里写成已经（写法卡三）：照料写「要／打算」")
    for m in re.findall(r"【(?:问|推算)[^】]*】", body):
        add("PENDING", m, "交稿前请主人答")
    sents = sentences(body)
    lens = [han(s) for s in sents]
    if len(lens) >= 8:
        flat = statistics.pstdev(lens) / statistics.mean(lens) < 0.3 or max(lens) - min(lens) < 15
        run = next((i for i in range(len(lens) - 2) if max(lens[i:i + 3]) - min(lens[i:i + 3]) < 3), None)
        if flat or run is not None:
            add("RHYTHM_FLAT", "句长 " + "、".join(map(str, lens)), "句子太齐（写法卡六）")
    total = han(plain)
    conj = sum(plain.count(c) for c in CONJ)
    if total >= 100 and conj >= 4 and conj * 100 / total > 1.5:
        add("CONJ_DENSE", f"连词 {conj} 个 / {total} 字", "连词太密（写法卡五）：删一半")
    for s in sents:
        if han(s) >= 38 and s.count("的") >= 4:
            add("HEAVY_DE", s.strip(), "的字长句（写法卡五）：主干先出")
        clauses = [c for c in re.split(r"[，、；,;]", s) if han(c) >= 3]
        heads = [re.sub(r"[^\u4e00-\u9fff]", "", c)[:2] for c in clauses]  # 只比开头两个汉字，停顿 / 和空格不算
        if any(heads[i] and heads[i] == heads[i + 1] == heads[i + 2] for i in range(len(heads) - 2)):
            add("ANAPHORA", s.strip(), "同头排比（B1）")
    keep = lambda t: re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", MARK.sub("", t))  # 只比字，不比标点、空格和标记

    def copy_runs(src, why):
        a, b = keep(plain), keep(src)
        grams = {b[i:i + COPY_RUN] for i in range(len(b) - COPY_RUN + 1)}
        i = 0
        while i <= len(a) - COPY_RUN:
            if a[i:i + COPY_RUN] in grams:
                j = i + COPY_RUN
                while j < len(a) and a[i:j + 1] in b:
                    j += 1
                add("COPY_RUN", a[i:j], f"和{why}连续 {j - i} 字相同")
                i = j
            else:
                i += 1
    if doc.get("source"):
        copy_runs(doc["source"], "原稿（pen-remake：二三档要自己写）")
    for name, card in doc.get("cards") or []:  # 借用爆款卡：只借公式，卡里摘的原句不搬
        copy_runs("\n".join(re.findall(r"「([^」]+)」", card)), f"爆款卡 {name} 的原句（pen-library 第 2 节：只借公式）")
    for w in SOURCE_TALK:
        if w in plain and w not in matx:
            add("SOURCE_TALK", w, "出处和范围只写在出处表里，正文不对观众自证「是真的／是说法／都是这次的数」、不讲「这里不猜／不能据此说」（写法卡三）：删掉这句")
    first = keep(lines[0]) if lines else ""
    seen = {}
    prose = "\n".join(l for l in plain.splitlines() if not l.lstrip().startswith(("|", "#")))  # 表格（收藏件）和小标题本来就是把正文再列一遍，不算凑字
    for c in re.split(r"[，。？！；、/\n：:,?!;]", prose.replace("*", "")):
        k = keep(c)
        if han(k) >= 4:
            seen[k] = seen.get(k, 0) + 1
    reps = [k for k, v in seen.items() if v >= 2 and not (v == 2 and k in first)]  # 开头那句结尾回扣一次不算
    whole = [keep(x) for x in re.split(r"[。？！?!\n]", prose.replace("*", "")) if han(keep(x)) >= 8]
    big = lambda t: {t[i:i + 2] for i in range(len(t) - 1)}
    for i in range(len(whole)):  # 换几个字的重复（第 12 轮：「你衣柜里一年没穿的外套现在有多少件」和结尾那句）
        for j in range(i + 1, len(whole)):
            a, b = big(whole[i]), big(whole[j])
            if len(a & b) / len(a | b) >= 0.6 and whole[j] not in reps and not (i == 0 and j == len(whole) - 1):
                reps.append(whole[j])
    raw = doc.get("body", "")
    segmented = any(SEG.match(l.strip()) for l in raw.splitlines())
    end = lines[-1] if segmented and lines else next((l for l in reversed(raw.splitlines()) if re.search(r"【结尾】", l)), None)
    first = re.split(r"[。！？!?\n]", MARK.sub("", "\n".join(lines)).replace("*", "").replace("=", "").lstrip())[0] if lines else ""
    if re.match(r"^\s*(上周|这周|本周|前天|昨天|今天|上个月|这个月|前几天|那天|有一次|去年)", first) and not re.search(r"\d|[两三四五六七八九十几百千]+[个件双本箱袋样瓶层次摞]|十来|几十|半面墙", first):
        add("HOOK_SETUP", first[:20], "第一句用时间地点起头、没落下痛或反差（钩子卡第二节）：把客户的痛、反差或前后对比挪到第一句，时间地点放第二句")
    if form == "长文" and han(plain) >= 1000:
        if "👇" not in raw:
            add("MEDIA_MISSING", "全文没有 👇 图片位", "长文每个大章至少一个图片位（形式卡第二节）：写清这张图看什么、要拍什么、没有就用什么")
        if "【收藏件】" not in raw and not re.search(r"(?m)^\s*\|", raw):
            add("SAVE_MISSING", "没有收藏件", "长文至少一个能存下来反复用的东西（形式卡第二节）：清单、速查表、模板")
    if form == "口播" and segmented:
        heads = [l.strip() for l in raw.splitlines() if SEG.match(l.strip())]
        nocue = [h for h in heads if "〔" not in h]
        if nocue:
            add("CUE_MISSING", nocue[0][:20], "段头没写〔画面 · 动作 · 语气〕提示（形式卡第一节）")
        if not any("**" in l for l in raw.splitlines() if not SEG.match(l.strip())):
            add("BOLD_MISSING", "台词里没有 **重读**", "要重读的数字和词用 **…** 标出（形式卡第一节），念的人知道哪里加重")
        if "==" not in raw:
            add("HIGHLIGHT_MISSING", "全稿没有 ==重点==", "口播要用 ==…== 标出重点句和字幕词（形式卡第一节），念的人扫一眼就知道重音在哪")
        longl = [x for x in "/".join(lines).split("/") if han(x) > 18]
        if longl:
            add("LINE_LONG", longl[0][:20], "台词一行一口气，最多 15 字左右（形式卡第一节）：在逗号处换行")
    if form == "口播" and not segmented and re.search(r"(?m)^\s*【(?:前 ?3 ?秒|冲突|正文|方法|结果|结尾|戳观众|转折)】", raw):
        add("OLD_HEADER", "【前 3 秒】式段头", "口播段头换成「🟥 ① 钩子 0～3″〔画面 · 动作 · 语气〕」（形式卡第一节，10-24 起的格式）")
    if form == "口播" and end is not None and not re.search(r"评论|留言|收藏|关注|下一条|下期", end):
        add("ENDING_NO_GUIDE", MARK.sub("", end).replace("【结尾】", "")[:30], "口播收尾要给观众一个动作（钩子卡第五节）：好回答的评论问题（「评论区报个日期」），或说清理由的收藏；料里真有下一条才提关注")
    if re.search(r"我把(?:这次的)?做法整理成", plain):
        add("TEMPLATE_LINE", "我把这次的做法整理成……", "引出收藏件的套话（pen-draft 第 2 节第 6 条）：换成跟着这条话头走的说法")
    asks = len(re.findall(r"[？?]", plain))
    if form == "口播" and asks >= 4:  # 写法卡二：最多三个（开头、正文、结尾各一），四个起才报（10-24 考生反馈口径不一致）
        add("QUESTION_PILE", f"{asks} 个问句", "口播问句太多（写法卡二）：处境问句最多一句，结尾只留一个互动问题")
    for k in reps:
        add("REPEAT_PAD" if len(reps) >= 2 else "REPEAT", k, f"同一句（或只换了几个字）在正文说了 {seen.get(k, 2)} 遍（写法卡二）：用料写满，不靠重复凑字；料不够就写短并说一句")
    fields = [f for f, ws in METAPHOR.items() if any(w in plain and w not in matx for w in ws)]
    if len(fields) >= 3:
        add("METAPHOR_MIX", "、".join(fields), "比喻换场（C5）：还原本义")
    return issues


def stamp(text):
    """检查码：只由正文（【前 3 秒】到【结尾】／长文到 ---）的字算出来，交稿照抄脚本第一行，判的人重算一遍就知道真跑过、稿子没再改（全量回归第 2 次：自报 237 字、实际 203）。"""
    import hashlib
    body = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", MARK.sub("", "\n".join(body_lines(text))))
    return hashlib.sha1(body.encode("utf-8")).hexdigest()[:6]


def main(argv=None):
    ap = argparse.ArgumentParser(description="执笔交稿前的机械检查")
    ap.add_argument("draft")
    ap.add_argument("--material", action="append", default=[])
    ap.add_argument("--form", choices=["口播", "长文"], default="口播")
    ap.add_argument("--seconds", type=int)
    ap.add_argument("--platform")
    ap.add_argument("--ad", action="store_true", help="种草带货稿：极限词算硬错")
    ap.add_argument("--source", help="仿写的原稿：查和原稿连续 15 字以上相同")
    ap.add_argument("--tier", type=int, choices=[1, 2, 3], default=2, help="仿写档位：1 贴写（照搬只提醒）、2 借骨（默认）、3 取神")
    ap.add_argument("--cards", nargs="*", default=[], help="这次借用的爆款卡：查和卡里摘的原句连续 15 字以上相同")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    read = lambda p: sys.stdin.read() if p == "-" else open(p, encoding="utf-8").read()

    def card_path(c):  # --cards 可以给文件路径，也可以只给卡 id（如 dy-zs-014），去库里找（考生反馈）
        if Path(c).exists():
            return c
        here = Path(__file__).resolve()
        for lib in (Path.home() / ".yunjian" / "pen" / "库", here.parents[2] / "库"):
            hit = sorted(lib.glob(f"**/{c}-*.md")) + sorted(lib.glob(f"**/{c}.md"))
            if hit:
                return str(hit[0])
        sys.exit(f"--cards 找不到卡：{c}（给卡文件路径，或库里有的卡 id）")
    doc = {"body": read(a.draft), "material": [read(p) for p in a.material], "form": a.form, "seconds": a.seconds, "platform": a.platform, "ad": a.ad,
           "source": read(a.source) if a.source else None, "tier": a.tier,
           "cards": [(Path(card_path(p)).stem, read(card_path(p))) for p in a.cards]}
    issues = check(doc)
    hard = [i for i in issues if i["level"] == "硬"]
    if a.json:
        print(json.dumps(issues, ensure_ascii=False, indent=1))
    else:
        n = count_chars("\n".join(body_lines(doc["body"])))
        lens = [han(s) for s in sentences("\n".join(body_lines(doc["body"])))]
        head = f"约 {n} 字" + (f"，预计 {round(n / RATE[1] * 60)}～{round(n / RATE[0] * 60)} 秒" if a.form == "口播" else "") + f"｜检查码 {stamp(doc['body'])}"
        print(head + (f"｜句长 {'、'.join(map(str, lens))}" if lens else ""))
        for i in issues:
            print(f"{'❌' if i['level'] == '硬' else '⚠️'} [{i['code']}] {i['text']} → {i['hint']}")
        print(f"硬错 {len(hard)} 处、提醒 {len(issues) - len(hard)} 处" if issues else "机械检查通过（还要人判：口吻、开头、顺不顺嘴、冷读）")
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
