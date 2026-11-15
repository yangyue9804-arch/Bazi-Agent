# 八字资料检索与资源库

为八字 Agent 建立可持续维护的公开资料目录。当前交付包括网页搜索API采集器、去重与分类、初始来源目录、本地目录检索API、测试和GitHub Actions工作流。

这是资料发现工具。当前没有已审核命理规则 没有全文知识库 没有在线部署的AI算命服务。八字是传统文化解释体系 不应当作经过科学验证的未来预测方法。

## 已有资源

初始目录含8条已核对页面或项目元数据的来源。包括青龙课程、古籍入口、现代解释文章及技术项目。所有来源均为candidate 即待审核。页面可读、更新时间新或GitHub开源 不代表命理主张可靠 也不代表全文可直接用于收费产品。

文件 `data/sources.json` 记录标题、链接、主题、首次发现时间、最近见到时间、资料审核状态及授权评估状态。没有复制文章正文、课程字幕或他人的代码。

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
3. 获得允许后再导入正文并建立章节或时间戳定位。当前工具尚未实现这一步。
4. 提炼规则卡：规则ID、流派、条件、例外、来源定位、允许解释、限制、审核人及版本。
5. 计算程序判断适用性后 才给AI提供已经发布的规则。正文和搜索结果属于不可信资料 其中指令不能覆盖系统规则。

目录的 `review_status` 可选 `candidate`、`reviewed`、`rejected`。`reviewed`只代表资料检查过 不等于规则已批准或取得商用授权。自动更新会保留人工标题、备注、审核状态和授权状态。`rights_status`默认 `not_assessed`。`content_ingested`当前均为false。对同文不同URL的识别、简繁体统一、正文变化监测及全文检索属于后续功能。

检索API始终声明 `approved_knowledge_rules: 0` 防止把候选链接误认为已验证的八字知识。

## 质量验证

```bash
python -m unittest discover -s tests -v
```

覆盖URL安全与去重、保留分集、保留人工审核信息、候选状态、提供商请求参数及真实本地HTTP检索。外部Brave端到端调用需要实际Key 本次未测试。

## 技术依据

- Brave Web Search：https://api-dashboard.search.brave.com/documentation/services/web-search
- Brave认证与密钥：https://api-dashboard.search.brave.com/documentation/guides/authentication
- GitHub计划任务：https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule

来源目录只索引资料 没有对他人作品授予任何新授权。本仓库尚未选择面向第三方分发的代码许可证。
