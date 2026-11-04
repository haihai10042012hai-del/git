# 亚马逊财务 PDF 识别与命名规则

## 证据优先级

按下列优先级综合判断，并在 `evidence` 中保留最关键的原文线索：

1. 强证据：文档标题、明确的 Marketplace/站点字段、Amazon 域名、Invoice Date、Statement Period、费用行项目。
2. 中证据：Amazon 开票主体、税务国家、VAT/GST 注册地、账单地址、付款账户所属站点。
3. 弱证据：币种、语言、原文件名中的缩写。弱证据不得单独决定站点。

出现冲突时优先使用更高等级证据；同等级冲突无法排除时填待确认。`Amazon EU S.à r.l.`、EUR 或欧盟 VAT 格式不能单独区分德国、法国、意大利、西班牙等站点。

## 三类文件

### 销售汇总报表

识别销售额、退款、订单、结算或期间汇总，常见线索包括 `Sales Summary`、`Sales Report`、`Statement`、`Settlement Summary`、`Order Sales`、销售、退款、订单及报告期间。优先使用明确的报告期间确定月份；跨月报告使用报告截止日所在月，并在依据中说明。

文件名：`YY.M公司站点销售报告.pdf`。

### 广告发票

优先识别 `Amazon Ads`、`Advertising Invoice`、`Cost of Advertising`、Sponsored Products/Brands/Display 及广告活动账单。`Cost of Advertising` 出现在发票标题或广告费用项目中时属于广告发票，不归入普通费用发票。

优先使用 `Invoice Date`，不得用到期日替代；完整日期无法确认时保留 `日待确认`。

文件名：`YY.M.D公司站点广告发票.pdf`。

### 费用发票

识别 Amazon 卖家费用或服务费发票。根据行项目选择中文费用类型：

| 英文线索 | 中文费用类型 |
| --- | --- |
| Referral Fee, Selling Fee, Subscription Fee, Commission | 平台费用 |
| FBA Fee, Fulfillment Fee, Shipping Fee, Transportation Fee | FBA运费 |
| Storage Fee, Monthly Storage, Long-term Storage | 仓储费 |
| Removal Fee, Disposal Fee | 移除销毁费 |
| Return Processing Fee, Returns Processing | 退货处理费 |
| Service Fee, Administration Fee | 服务费 |
| 多类费用且无明确主项 | 综合费用 |

金额最大的费用行可作为主费用类型；若无法可靠比较金额且存在多种实质费用，使用 `综合费用`，不要武断选择其中一种。

文件名：`YY.M公司站点费用类型发票.pdf`。

## 站点规则

仅把明确站点字段、Amazon 域名或足够一致的国家证据映射为中文站点：

| 明确线索 | 中文站点 |
| --- | --- |
| amazon.com / United States marketplace | 美国 |
| amazon.ca / Canada marketplace | 加拿大 |
| amazon.com.mx / Mexico marketplace | 墨西哥 |
| amazon.co.uk / United Kingdom marketplace | 英国 |
| amazon.de / Germany marketplace | 德国 |
| amazon.fr / France marketplace | 法国 |
| amazon.it / Italy marketplace | 意大利 |
| amazon.es / Spain marketplace | 西班牙 |
| amazon.nl / Netherlands marketplace | 荷兰 |
| amazon.se / Sweden marketplace | 瑞典 |
| amazon.pl / Poland marketplace | 波兰 |
| amazon.com.be / Belgium marketplace | 比利时 |
| amazon.co.jp / Japan marketplace | 日本 |
| amazon.com.au / Australia marketplace | 澳大利亚 |
| amazon.sg / Singapore marketplace | 新加坡 |
| amazon.ae / United Arab Emirates marketplace | 阿联酋 |
| amazon.sa / Saudi Arabia marketplace | 沙特阿拉伯 |
| amazon.in / India marketplace | 印度 |
| amazon.com.br / Brazil marketplace | 巴西 |
| amazon.com.tr / Türkiye marketplace | 土耳其 |

币种只能用于交叉验证。例如 CAD 强烈支持加拿大但不能替代明确站点证据；EUR 不能区分欧元区站点。VAT 前缀可能属于开票主体、卖家或交易税务国家，必须结合字段语义，不得看到前缀就直接定站点。

## 主体与公司简称

优先使用用户提供的“法定主体 → 中文简称”映射。没有映射时，只采用文档中明确出现的中文主体简称；不得自行翻译、音译或把 Amazon 开票主体误当作用户公司。若只有英文卖家公司名，填 `主体待确认`，并在依据中记录原始主体。

## 日期和置信度

- 销售汇总报表：报告月份，格式 `YY.M`。
- 广告发票：发票日期，格式 `YY.M.D`。
- 费用发票：发票月份，格式 `YY.M`。
- 两位年份取四位年份后两位；月、日不补零。

置信度建议：

- 高（90%–100%）：类别、站点、日期和主体都有明确且一致的强证据。
- 中（70%–89%）：核心类别明确，但某字段主要来自一致的中证据。
- 低（0%–69%）：文本缺失、证据冲突或有命名字段待确认。低置信度项必须显式使用待确认标记。

## 待确认

无法可靠归入三类时将 `category` 设为 `待确认`。不要为了满足三类表面完整性而错误分类。无法确定站点时使用 `站点待确认`；无法确定中文公司简称时使用 `主体待确认`。这类文件仍需进入 ZIP 和 Excel，确保不漏文件。
