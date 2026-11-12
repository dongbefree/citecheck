# citecheck · 引用一致性审计

一个只查**文本自身矛盾**的引用审计工具，面向人文社科写作者。输入 Word 稿，输出带**原生批注**的副本，批注落在出问题的那条注或那段正文上。

它不联网判断"你的引用对不对"，因为那件事做不到（见下文）。它做的是：找出那些**你的稿子在自相矛盾**的地方。

```
python3 scripts/docx_audit.py 稿件.docx
# → 稿件.audit.docx，用 Word 打开，批注已在对应位置
```

## 它做什么

| 层级 | 做什么 | 结论强度 |
|---|---|---|
| A 层 | 内部一致性：孤儿注、缺注、首次引用未给全称、出版项前后矛盾、期刊文章缺卷期页码 | **可判定**，每条都是文本里能指出来的矛盾 |
| B 层 | 外部检索：Crossref / Open Library 存在性核对 | **只出线索**，附检索链接，不写"错误" |

## 为什么它不"查证引用真伪"

这是我最初的想法，实测后放弃了。对 14 种真实文献做 Crossref + Open Library 核对，系统报出 7 条"记录存在但字段不符"，逐条人工复核后——**7 条全是假警报，真实错误 0 条**：

| 引用（已脱敏） | 系统报的不符 | 实情 |
|---|---|---|
| 一部 2012 年英国大学出版社的政治哲学专著 | 记录为 2020 年另一出版社版本 | 2012 年版真实存在，只是另一个条目 |
| 一部 1997 年的哲学专著 | 记录为 2018 年另一本同名词专著 | 同名不同书，题名相似度 0.88 越过阈值 |
| 一部 1987 年法国出版的法文专著 | 记录为 1989 年另一出版社 | 命中的是这本书的**书评** |
| 一部 1981 年美国大学出版社的心灵哲学专著 | 记录为 2021 年另一大学出版社 | 命中的是 2021 年**重印本** |
| 一部 1992 年的合著 | 记录为 JSTOR 1994 | 命中的又是**书评** |

> 表格按引用类型脱敏。测试语料是作者本人未发表稿件里的 14 条引用，具体书名不在公开范围内——但上表每一行都是实际发生的误判，没有一条是编出来的例子。

三个结构性原因，不是调参能解决的：

1. **书评陷阱**。评价某本书的文章，标题里天然包含那本书的题名，题名相似度永远无法区分它和原著。
2. **DOI 注册库对人文社科覆盖差**。大量 2000 年前的哲学论文只存在于 JSTOR；中译本几乎没有记录。
3. **"查不到"会被误读成"引错了"**。纠正一条正确脚注的代价，远高于漏检一条错误脚注。一个靠假警报工作的检查器，三天就会被弃用。

所以 B 层被降级为"书签"：它输出候选记录和检索链接，由人点开确认。**任何时候都不把检索无果写成"引用有误"。**

## 安装

`SKILL.md` 遵循 Agent Skills 开放标准，因此同一份目录可以丢进任何认这个标准的工具。区别只在放到哪儿。

```bash
git clone https://github.com/dongbefree/citecheck.git
```

| 运行时 | 安装位置 | 命令 |
|---|---|---|
| WorkBuddy | `~/.workbuddy/skills/` | `cp -r citecheck ~/.workbuddy/skills/citecheck` |
| Claude Code（个人级） | `~/.claude/skills/` | `cp -r citecheck ~/.claude/skills/citecheck` |
| Claude Code（项目级） | 仓库内 `.claude/skills/` | `mkdir -p .claude/skills && cp -r citecheck .claude/skills/` |

目录名与 `SKILL.md` 里的 `name` 字段都保持 `citecheck`。在 Claude Code 里，这个目录名就是你敲的 `/citecheck`。

装好后在会话里说"查一下这份 Word 的脚注"，或直接 `/citecheck`。

frontmatter 里的 `display_name`、`tags`、`category` 是 WorkBuddy 用的，其他工具不读也不受影响；`description` 是唯一所有工具都依赖的字段，改动它之前先想清楚触发语会不会变。

### 直接当脚本用

不装 skill 也能跑。只依赖 `python-docx`（需 1.2.0 以上，批注 API 才有）：

```bash
pip install -r requirements.txt
python3 scripts/docx_audit.py 稿件.docx -o 输出.docx
```

Markdown / 纯文本稿走另一个入口，输出 Markdown 报告：

```bash
python3 scripts/audit.py 稿件.md
python3 scripts/audit.py 稿件.md --json    # 机器可读
```

## 输入要求

正文脚注标记为**上标数字**，文末是**连续编号的注释段落**（每段以 `1`、`2`… 开头）。

这是 Word 里手工维护脚注的常见写法，也是本项目唯一支持的结构。Word 内置脚注域（`word/footnotes.xml`，即"插入 → 脚注"生成的）**不支持**，遇到会明确报错而不是静默给出空结果。

## 检查项

| 检查 | 级别 | 判据 |
|---|---|---|
| 孤儿注释 | ERROR | 脚注已给出，正文从未引用该编号 |
| 缺注释 | ERROR | 正文引用了编号，脚注区无条目 |
| 全称位置错位 | ERROR | 首次引用用简称，全称却在一条未被引用的注里 |
| 转义残留 | ERROR | 正文出现 `\[3\]` 这类字面量，导出后不成上标 |
| 年份 / 出版项不一致 | ERROR | 同一文献在不同注里的年份或出版社互相矛盾 |
| 编号顺序 | WARNING | 首次出现顺序与编号不一致 |
| 文章信息不全 | WARNING | 期刊文章缺卷期或页码 |
| 未给全称 | WARNING | 文献全程只有简称，从未给出出版地 / 出版社 |
| 重复全称 | WARNING | 后续注重复给出完整出版信息 |
| 连接号 / ibid | INFO | 页码范围用连字符；使用了 ibid. |

## 批注落点

| 发现类型 | 批注位置 |
|---|---|
| 关于某条注 | 该注的文字上 |
| 关于正文 | 该段正文上 |
| 同一段多条发现 | 合并为一条，避免页边被切碎 |

源文件只读，输出永远是副本。

## 一个必须知道的实现细节

Word 用**斜体运行属性**表示书名，而不是文字里的星号。早期版本直接读 `paragraph.text`，斜体信息全部丢失，导致所有题名对解析器不可见、所有检查**静默通过**——在一份真实定稿上因此报出"0 个问题"。

`docx_audit.flavored()` 就是为修复这个缺陷存在的：它把斜体 run 还原成 `*Title*`，再交给审计核心。**这个函数不能删，也不能绕过**。那次教训是整个项目里最有价值的一条：最危险的不是报错，是报"一切正常"。

## 自检

```bash
python3 tests/test_smoke.py
```

用仓库里的 `samples/fixture.docx`（一份带已知缺陷的构造稿）断言必须报出 2 条：孤儿注 5、注 4 缺出版项。改动脚本后先跑这个。

样本本身由 `tests/make_fixture.py` 生成，里面的文献全部是编造的，不含任何人的真实书目。要改样本结构，改那个脚本再重跑，不要手改 docx——手改会丢掉斜体运行属性，测试就测不到 `flavored()` 那条路径了。

## 已知限制

- 只支持手动脚注结构，不支持 Word 脚注域。
- 中文文献不覆盖（GB/T 7714 体例与中文出版信息不在范围内）。
- 只以 `"Title", 2007` 形式出现、且无斜体的文献可能漏采。
- 不做页码越界检查（需要文献总页数，属 B 层能力）。
- **不做引文与原文的比对**。核对"这段引文是否真在第 145 页"需要全文，本项目不碰。

## License

MIT

---

## English

**citecheck** audits a Word manuscript's footnotes for internal inconsistency — orphan notes, missing notes, short forms with no prior full form, conflicting years or publishers, journal articles missing volume/issue — and writes findings back as **native Word comments** anchored at the offending note.

It deliberately does not adjudicate whether a citation is "correct". A measured attempt at Crossref/Open Library cross-checking produced 7 flagged mismatches on 14 real references, **all 7 false positives**: book reviews that carry the reviewed title, reprints, and same-title different books. External lookup can tell you a book probably exists; it cannot tell you your entry is wrong. Layer B therefore only emits candidates and search links.

Requires Python 3.9+ and `python-docx>=1.2.0`. Manual footnotes only (superscript numbers in body, numbered paragraphs at the end); real Word footnote fields are unsupported and raise an error rather than returning an empty result.
