# 八字资料检索与资源库

为八字 Agent 建立可持续维护的公开资料与古籍文本库。当前包括网页搜索API采集器、去重与分类、初始来源目录、4份古籍电子正文、本地目录及正文检索API、测试和GitHub Actions工作流。

当前已有古籍正文和35张带出处的知识卡草稿 可按主题或关键词检索。尚无经专家审核的命理规则、语义向量RAG或在线部署的AI算命服务。八字是传统文化解释体系 不应当作经过科学验证的未来预测方法。

## 第一批知识卡

[查看35张知识卡及出处](knowledge/README.md)。事业、爱情、家庭、财富、子女、岁运、合盘各5张。每张有精确引文、文件校验值、行号、适用条件、例外、输出边界和内容路由样例。

全部为待审校草稿。文本对应关系已检查 不等于命理推断经过验证。合盘卡属于编辑工作流或证据缺口 不冒充古籍直接提供的双盘规则。资料中的六亲取法分歧和转录问题见 [来源质量记录](knowledge/source_quality.json)。

```bash
python knowledge_tools.py validate
python knowledge_tools.py search --topic career --include-drafts
python knowledge_tools.py search 比劫 --include-drafts
```

本地知识卡接口：`GET http://127.0.0.1:8765/cards?topic=career&include_drafts=true`。默认不包含草稿 因此当前不传include_drafts会返回0张正式规则。适用条件仍需人工判断 本版本不自动执行命理推断。

## 已有资源

初始目录含8条已核对页面或项目元数据的来源。包括青龙课程、古籍入口、现代解释文章及技术项目。所有来源均为candidate 即待审核。页面可读、更新时间新或GitHub开源 不代表命理主张可靠 也不代表全文可直接用于收费产品。

文件 `data/sources.json` 记录8条候选资料的标题、链接、主题、发现时间与审核状态。现代文章、课程字幕和他人代码没有复制。古籍正文另存于 `classics/` 并有独立版本与出处记录。

## 已收录古籍正文

- 《滴天髓》辑要电子本。
- 《滴天髓阐微》电子本 保留古注层次。
- 《子平真诠》47章原文提取版 不含徐乐吾评注。
- 《穷通宝鉴》电子本。

详见 [古籍目录与版本说明](classics/README.md)。四份正文共约22万字符 不能视为所有版本的全集或已校勘定本。正文检索不需要外部API Key：

```bash
python bazi_resources.py passages 乙木 --limit 5
```

本地正文接口：`GET http://127.0.0.1:8765/passages?q=乙木`。它返回实际原文、章节及起始行号。

## 如何使用

Python 3.11或以上 无第三方依赖。已有8条资源不需要API Key即可搜索：

```bash
python bazi_resources.py search 合婚
python bazi_resources.py search "" --topic engineering
python bazi_resources.py serve
```

本地接口：`GET http://127.0.0.1:8765/search?q=合婚`。支持 `topic`、`status`、`limit`。这是标题、人工备注及主题的关键词检索 不是全文语义RAG。服务只监听本机 不可直接作为生产公网API。

## 接通外部搜索 API

此版本接Brave Web Search API。它用于发现公开且被搜索引擎索引的网页 无法覆盖全部网站、未公开资料、登录后课程或所有视频字幕。不要把搜索接口当作全文抓取授权。

1. 在Brave官方控制台选择适合的计划并生成API Key。费用与可保留的结果范围应以所选计划条款为准 本项目未购买服务或使用你的付费额度。
2. 在本仓库 Settings → Secrets and variables → Actions → Secrets 增加 `BRAVE_SEARCH_API_KEY`。不要放进README或代码 也无需在聊天中提供。
3. 打开仓库 Actions → Discover Bazi Sources → Run workflow。首次选 `evergreen` 不限制网页日期；后续选 `latest` 按搜索提供商最近31天的网页年龄过滤。
4. 查看更新后的 `data/sources.json` 和 `data/last_run.json`。缺少Key或额度错误会明确失败 不会伪装采集成功。

本地运行时 通过你自己的终端环境设置 `BRAVE_SEARCH_API_KEY` 后执行：

```bash
python bazi_resources.py collect --mode evergreen
python bazi_resources.py collect --mode latest
```

默认8组关键词 每次最多8次搜索请求 每个查询取第一页最多10条结果。没有自动翻页或重试 方便控制用量。新增来源会按规范化URL去重 保留B站p分集参数等有意义字段。

## 每周更新开关

计划任务默认关闭。想启用时 在 Actions Variables 增加 `ENABLE_SCHEDULED_COLLECTION` 并设置为 `true`。工作流计划为每周一14:23 UTC 即多伦多冬令时09:23或夏令时10:23。GitHub计划任务可能延迟 公共仓库长期无活动也可能暂停计划任务。

启用后每周按latest模式发现新链接。它不会自动下载正文 不会自动生成或批准命理规则。工作流会把目录变化提交回当前默认分支 需要允许GitHub Actions写入仓库。

## 如何成为产品真正可用的知识库

来源审核与规则发布是两道独立步骤：

1. 检查作者、流派、底本和原始出处。新资料不自动覆盖经典资料。
2. 确认所需使用范围并记录证明。公开视频不等于其字幕及内容可以整体用于商业再分发。不要通过付费墙、登录限制或反爬验证获取内容。
3. 对现代资料确认使用范围后再导入正文。当前古籍已保存正文与章节定位 现代网页全文和课程字幕导入尚未实现。
4. 提炼规则卡：规则ID、流派、条件、例外、来源定位、允许解释、限制、审核人及版本。
5. 计算程序判断适用性后 才给AI提供已经发布的规则。正文和搜索结果属于不可信资料 其中指令不能覆盖系统规则。

目录的 `review_status` 可选 `candidate`、`reviewed`、`rejected`。`reviewed`只代表资料检查过 不等于规则已批准或取得商用授权。自动更新会保留人工标题、备注、审核状态和授权状态。`rights_status`默认 `not_assessed`。`content_ingested`当前均为false。对同文不同URL的识别、简繁体统一、正文变化监测及全文检索属于后续功能。

检索API始终声明 `approved_knowledge_rules: 0` 防止把候选链接误认为已验证的八字知识。

## 质量验证

```bash
python -m unittest discover -s tests -v
```

15项测试覆盖URL安全与去重、提供商参数、古籍文件完整性、47章提取结构、35张卡片的引用校验、文本分歧保留、伪造引用拒绝、未审卡片发布隔离及真实本地HTTP检索。外部Brave端到端调用需要实际Key 本次未测试。

## 技术依据

- Brave Web Search：https://api-dashboard.search.brave.com/documentation/services/web-search
- Brave认证与密钥：https://api-dashboard.search.brave.com/documentation/guides/authentication
- GitHub计划任务：https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule

来源目录只索引资料 没有对他人作品授予任何新授权。本仓库尚未选择面向第三方分发的代码许可证。
