---
name: amazon-pdf-finance-renamer
description: 解压并处理用户上传的亚马逊财务 PDF 或 ZIP 压缩包，综合原文件名、PDF 正文、Amazon 主体、VAT、日期、币种及发票明细，识别销售汇总报表、Amazon Ads 广告发票和 Amazon 费用发票，生成中文规范文件名及重命名 PDF ZIP。用于亚马逊财务文件批量分类、中文重命名、站点识别、广告/平台/FBA/仓储等费用识别，以及用户要求输出按“YY.M公司名”命名的 ZIP 时。
---

# 亚马逊 PDF 财务文件智能重命名助手

## 目标

处理全部 PDF，不凭单一关键词草率判断，不猜测无法可靠确认的站点、主体或日期。最终只交付一个 ZIP：

- `YY.M公司名.zip`，例如 `26.7灵屿.zip`

不生成、不交付识别结果 Excel。

## 工作流程

### 1. 准备文件

先定位用户上传的 ZIP、PDF 或目录，再创建独立工作目录。运行：

```text
python scripts/amazon_pdf_renamer.py prepare <输入路径> --work-dir <工作目录>
```

该命令安全解压 ZIP（含不超过三层的嵌套 ZIP）、枚举 PDF、抽取可搜索文本，并生成：

- `<工作目录>/manifest.json`
- `<工作目录>/texts/*.txt`

不得在原压缩包或原 PDF 上直接改名或覆盖。

### 2. 逐份分析

分类前读取 [references/classification-rules.md](references/classification-rules.md)。对每个 `source_id` 同时检查：

- 原文件名；
- PDF 文本或页面图像；
- Amazon 开票/报告主体与卖家主体；
- VAT/GST/税号及税务国家；
- 报告期间、发票日期与到期日期；
- Currency/币种；
- Invoice 标题、描述和费用行项目。

不得只看原文件名或只看币种。若抽取文本很短、乱码、关键字段缺失或疑似扫描件，渲染相关 PDF 页面并进行视觉/OCR 检查；至少查看首页和包含日期、VAT、金额或费用明细的页面。

### 3. 建立决策文件

为 `manifest.json` 中每一份 PDF 写一条记录到 UTF-8 JSON。允许顶层为数组或 `{"decisions": [...]}`。格式：

```json
{
  "decisions": [
    {
      "source_id": "pdf-001",
      "company": "诺威",
      "site": "加拿大",
      "category": "广告发票",
      "fee_type": "",
      "date": "2026-07-31",
      "currency": "CAD",
      "invoice_summary": "Amazon Ads 7月广告投放费用",
      "evidence": "标题为Advertising Invoice；Marketplace为Amazon.ca；Invoice Date为2026-07-31；币种CAD",
      "confidence": 96
    }
  ]
}
```

约束：

- `category` 只能填 `销售汇总报表`、`广告发票`、`费用发票` 或 `待确认`。
- `site` 必须使用中文站点名；证据不足时填 `站点待确认`，不得猜测。
- `company` 使用文件中明确出现或用户提供映射的中文简称；没有可靠中文名称时填 `主体待确认`。
- `date` 优先填 ISO 日期；销售汇总报表使用报告所属月份，费用发票使用发票月份，广告发票使用完整发票日期。
- `fee_type` 仅用于费用发票，并使用规则表中的中文费用名称。
- `evidence` 写明类别、站点、日期和主体的关键证据；同时记录冲突或缺失。
- `confidence` 使用 0–100 整数。任何进入文件名的字段待确认时，总置信度不得标为“高”。

### 4. 生成 ZIP

运行：

```text
python scripts/amazon_pdf_renamer.py finalize --manifest <工作目录>/manifest.json --decisions <决策JSON> --output-dir <输出目录>
```

脚本依据结构化决策统一生成文件名，处理重名冲突，并创建 ZIP。ZIP 使用决策记录中出现次数最多的年月和公司简称命名为 `YY.M公司名.zip`；若最高频值并列或缺失，对应部分使用 `日期待确认` 或 `主体待确认`，不得猜测。命名规则为：

- 销售汇总报表：`YY.M公司站点销售报告.pdf`
- 广告发票：`YY.M.D公司站点广告发票.pdf`
- 费用发票：`YY.M公司站点费用类型发票.pdf`

月份和日期不补零。示例：

- `26.7诺威美国销售报告.pdf`
- `26.7.31诺威加拿大广告发票.pdf`
- `26.7诺威德国FBA运费发票.pdf`
- `26.7诺威加拿大平台费用发票.pdf`

若字段无法确认，使用 `日期待确认`、`主体待确认`、`站点待确认` 或 `类别待确认`，绝不补猜测值。除用户示例明确保留的 `FBA` 外，站点与描述均使用中文。

### 5. 验证交付物

交付前完成以下检查：

1. `manifest.json` 的 PDF 数量、决策记录数和 ZIP 内 PDF 数量一致。
2. ZIP 文件名严格符合 `YY.M公司名.zip`；月份不补零。
3. ZIP 内 PDF 文件名均由决策记录生成，且无重名遗漏。
4. 所有站点均为中文或 `站点待确认`，无英文站点名称。
5. 检查 ZIP 完整性并随机打开至少一份其中的 PDF；有待确认项时在交付说明中列出数量。

只向用户提供最终 ZIP 的下载链接，以及极简的待确认项说明。不要生成或提供识别结果 Excel。工作目录、抽取文本和决策 JSON 均作为中间文件保留在 `work/`，不要当作交付物。
