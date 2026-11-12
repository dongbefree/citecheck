---
name: citecheck
display_name: "引用一致性审计"
display_name_en: "Citation Audit"
title: "引用一致性审计 / Citation Audit"
tags: ["脚注", "参考文献", "引用核对", "citation", "footnote", "bibliography"]
description: >-
  Audit footnotes, endnotes and bibliographies for internal inconsistency:
  orphan notes, missing notes, short forms without a prior full form, and
  incomplete publication data. Reads .docx directly and writes findings back
  as native Word comments at the offending note. Use when a manuscript needs
  its citations checked before submission. 凡涉及脚注、尾注、参考文献的核对与审计任务都用它：
  检查孤儿注释、编号错位、首次引用未给全称、出版项缺失、同一文献前后不一致。
  触发词：查脚注、核对参考文献、引用检查、citation check、bibliography audit、脚注对不对
category: writing
version: "0.4.0"
disable-model-invocation: false
user-invocable: true
agent_created: true
---

# 引用一致性审计

面向人文社科写作者的引用核查工具。当前版本只做 **A 层**：内部一致性。

## 两条铁律

1. **A 层出结论，B 层只出线索。** A 层的每一条发现都是文本自身矛盾，可以直接改。
   B 层（外部数据库核验）在实测中不可靠，见下方证据，因此**不得**把 B 层结果写成"错误"。
2. **"查不到"不等于"引错了"。** 任何时候都不得把检索无果表述为引用有误。

## B 层为什么不能给结论（实测证据）

对 14 种真实文献做 Crossref + Open Library 存在性核验，得到 7 条"存在但字段不符"，
逐条人工复核后 **7 条全部是假警报**，真实错误 0 条：

| 引用 | 系统报的不符 | 实情 |
|---|---|---|
| Hobbes, *Leviathan*, Clarendon 2012 | 记录为 Bloomsbury 2020 | 另有 2020 年版本，2012 年版真实存在 |
| James, *Passion and Action* 1997 | 记录为 *Hume, Passion, and Action* 2018 | 同名不同书，相似度 0.88 越过阈值 |
| Zarka 1987, Vrin | 记录为 Informa 1989 | 命中该书的一篇**书评** |
| Dretske 1981, MIT Press | 记录为 UChicago 2021 | 命中 2021 年**重印本** |
| Fodor & Lepore 1992, Blackwell | 记录为 JSTOR 1994 | 命中该书的一篇**书评** |

结论：外部检索只能回答"这本书大概存在"，不能回答"你的著录对不对"。
因此 B 层输出一律标注为**候选线索**，并附检索链接，由人点开确认。

## 工作流

1. 取得稿件。**`.docx` 为第一入口**，输出批注直接落在原文对应位置。
2. 运行：

   ```bash
   python3 scripts/docx_audit.py 稿件.docx            # 生成 稿件.audit.docx
   python3 scripts/docx_audit.py 稿件.docx -o 出.docx  # 指定输出
   python3 scripts/audit.py 稿件.md                   # markdown/纯文本版，出报告
   ```

   源文件只读，输出另存为副本。
3. 用 Word 打开输出文件，批注已在脚注与正文的对应位置。
4. 逐条处理：ERROR 直接改，WARNING 结合体例判断。
5. 如需外部核验，另跑 `scripts/b_layer.py`，**只把它当书签用**。

## 批注落点规则

| 发现类型 | 批注位置 |
|---|---|
| 关于某条注 | 该注的文字上（文末注释块内） |
| 关于正文 | 该段正文上 |
| 同一段多条发现 | 合并为一条批注，避免页边被切碎 |

## 稿件结构要求（当前版本）

正文脚注标记为**上标数字**，文末为**连续编号的注释段落**（每段以 `1`、`2`… 开头）。

Word 内置脚注域（`word/footnotes.xml`，即"插入→脚注"生成的）**不在本版本范围内**。
这是刻意的取舍：本 skill 的使用者一律采用手动脚注写法，统一结构比支持两套提取逻辑更可靠。
若遇到脚注域，脚本会明确报错，不会静默给出空结果。

## 自检

改动脚本后先跑样本，应报 2 条（孤儿注 5、注 4 缺出版项）：

```bash
python3 scripts/docx_audit.py samples/fixture.docx -o /tmp/fixture.check.docx
```

## 实现要点（改动前必读）

- **斜体必须还原成 `*Title*`**。Word 用运行属性标记书名，审计核心读的是 `*Title*`。
  早期版本直接读 `paragraph.text`，斜体信息全丢，导致所有题名不可见、所有检查静默通过——
  在真实定稿上因此错报"0 问题"。`docx_audit.flavored()` 就是为修复这个缺陷而存在，不可删除。
- **不得用 `paragraph.text` 做任何脚注判断**，一律走 `flavored()`。
- 批注 id 与 `commentRangeStart/End`、`commentReference` 三处必须一致，缺一则 Word 报错修复。

## 检查项

| 检查 | 级别 | 判据 |
|---|---|---|
| 孤儿注释 | ERROR | 脚注已给出，正文从未引用该编号 |
| 缺注释 | ERROR | 正文引用了编号，脚注区无条目 |
| 全称位置错位 | ERROR | 首次引用用简称，全称却在一条未被引用的注里 |
| 转义残留 | ERROR | 正文出现 `\[3\]` 这类字面量，导出后不成上标 |
| 年份/出版项不一致 | ERROR | 同一文献在不同注里的年份或出版社互相矛盾 |
| 编号顺序 | WARNING | 首次出现顺序与编号不一致 |
| 文章信息不全 | WARNING | 期刊文章缺卷期或页码 |
| 未给全称 | WARNING | 文献全程只有简称，从未给出出版地/出版社 |
| 重复全称 | WARNING | 后续注重复给出完整出版信息 |
| 连接号 / ibid | INFO | 页码范围用连字符；使用了 ibid. |

## 局限（必须在交付时说明）

- **只支持"手动脚注"结构**（正文上标数字 + 文末编号段落）。Word 内置脚注域未支持。
- **中文文献不覆盖**。GB/T 7714 体例与中文出版信息不在本版本范围内。
- **纯引号题名可能漏采**。只以 `"Title", 2007` 出现且无斜体的文献可能未被识别。
- **不做页码越界检查**。需要文献总页数，属 B 层能力。
- **不做引文与原文的比对**。核对"这段引文是否真在第 145 页"需要全文，本工具不碰。
- **不判断副标题省略是否合规**。若作者一贯省略副标题，这属于体例选择而非错误。

## 报告措辞规范

- 说"文本内部矛盾"，不说"引用错误"。
- 说"未给全称"，不说"格式不规范"——后者需先确认体例。
- 无法判断时明说"无法核实"，并说明缺什么证据。
