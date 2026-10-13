# 远帆 · 本地外贸 CRM

Python Flask + SQLAlchemy + SQLite 的本地应用，沿用已确认的远帆 CRM 界面。默认使用 Waitress 监听 `127.0.0.1:5001`，只有本机可以访问，不需要云端数据库或外部账号。浏览器关闭不影响数据保存。

## 当前电脑直接启动

双击 **start.command**，然后打开：

http://127.0.0.1:5001

或在项目目录运行：

```sh
.venv/bin/python run.py serve
```

默认管理员账号为 `admin`，初始密码由初始化命令随机生成，不写入源码或本文档。登录后在「设置 → 修改我的密码」中修改。

忘记密码可在本机终端执行（按提示输入新密码，不会回显）：

```sh
.venv/bin/python run.py reset-password admin
```

停止服务：在启动终端按 `Ctrl+C`。请勿在运行过程中移动、删除或替换数据库文件。

## 在另一台电脑安装

需要 Python 3.10 或更高版本，建议 Python 3.11。复制源码，保留 `instance` 可迁移现有数据；不复制 `instance` 则初始化为全新系统。

macOS 可双击 **install.command**，或执行：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python run.py init --name 管理员
.venv/bin/python run.py serve
```

`init` 会升级数据库并创建管理员。密码至少 10 位，留空自动生成；已存在的账号不会被覆盖。生产使用无需安装 Playwright。

Windows 对应使用：

```bat
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.lock.txt
.venv\Scripts\python run.py init --name 管理员
.venv\Scripts\python run.py serve
```

如端口被占用：

```sh
.venv/bin/python run.py serve --port 5002
```

使用地址 `http://127.0.0.1:5002`。当前应用刻意仅监听本机，不直接开放局域网或公网。

## 功能

- 工作台：个人待办、逾期提醒、真实业务漏斗、订单和分币种应收汇总。
- 客户：查询、创建、编辑、归档、多个联系人、负责人分配、跟进记录、CSV 导入导出。
- 商机：阶段看板、下一步行动、预计金额、预计成交日、赢单与丢单原因、关联报价。
- 产品：SKU、规格、单位、成本币种、自产/外采/混合方式、多个供货来源、供应商及图片/资料附件。
- 报价：多产品明细、商务条款、草稿编辑、独立版本、状态管理、中文 PDF、转订单。
- 订单：产品价格与商务条款快照、交期、自产和外采数量拆分、供货进度和质检。
- 财务：分次收款、应收余额、收款作废原因及原记录保留、收款凭证附件。
- 出货：按订单产品记录分批数量、提单/运单、目的地及出货附件。
- 报表：按实际数据汇总，币种独立统计，不自动混算汇率。
- 管理：团队账号、启用/停用、密码重置、角色限制、最近 100 条操作日志。

样例业务数据可选添加：

```sh
.venv/bin/python run.py seed
```

样例客户来源标为「示例数据」，只用于体验，初始化时不会自动添加。建议在开始录入真实业务前决定是否使用。`seed` 不覆盖已有数据，但会新增示例业务；同一批示例客户存在时不会再次添加。

## 建议使用顺序

1. 管理员在设置中创建员工账号。
2. 建立客户及联系人，指定负责人。
3. 在客户详情记录跟进；填写下一步与日期可同时创建待办。
4. 新建商机、产品和供应商。
5. 创建多产品报价，可编辑草稿；对已发送报价的修改应复制为新版本。
6. 确认报价并转为订单，填写约定交期。
7. 在订单详情分配供货任务；一条产品明细可按数量拆给自产和外采。
8. 采购生产人员或管理员更新任务进度与质检。
9. 财务登记到账，业务员登记每批实际出货数量。
10. 订单负责人按实际履约情况确认业务状态。

订单的业务状态由负责人确认；供货完成度、已收款、剩余应收和已出货数量由实际记录计算。当前支持 USD、EUR、CNY、GBP。单价与金额最多两位小数，数据库使用最小货币单位整数保存；第一版产品数量为整数。供货任务的成本使用订单币种，产品参考成本使用产品自身币种。

## 权限

| 角色 | 数据与操作范围 |
| --- | --- |
| 管理员 | 全部业务、员工账号、客户转交、成本与操作日志 |
| 业务员 | 本人负责的客户、商机、报价和订单；分配供货和登记出货；不可查看供货成本或登记收款 |
| 采购/生产 | 产品和供应商；只查看分配给自己的订单产品与任务，更新自身进度；不返回订单销售价格和收款资料 |
| 财务 | 订单及收款资料、登记/作废收款、上传凭证、财务报表 |

权限在后端执行，隐藏按钮不是唯一保护。客户转交时，未完成的关联跟进待办也会转给新负责人。停用账号后，其后续请求会失效。

订单附件仅管理员、负责业务员与财务可访问，采购生产人员不开放订单附件，以避免其中的销售或财务资料泄露。产品公共资料可由采购生产人员查看。

## 数据与备份

```text
instance/
├── crm.sqlite3        数据库（账号、客户、业务、操作日志）
├── crm.sqlite3-wal    运行时 SQLite 日志，可能出现
├── crm.sqlite3-shm    运行时 SQLite 共享内存，可能出现
├── secret.key        本机会话签名密钥
└── uploads/          附件文件
```

**不要只复制运行中的 crm.sqlite3 来代替备份。** 使用备份命令会调用 SQLite 在线备份接口，并按数据库快照复制已登记的附件。

```sh
.venv/bin/python run.py backup
```

也可双击 **backup.command**。结果保存在 `backups/crm-日期时间.zip`，包含数据库、附件及清单，不包含会话密钥。备份包含完整客户资料及账号密码哈希，请妥善保存。附件采用不可变存储名，第一版不提供物理删除附件功能。

恢复前先停止本地服务：

```sh
.venv/bin/python run.py restore "backups/crm-日期时间.zip"
```

按提示输入 `RESTORE`。程序会校验备份，保留恢复前的 `instance` 副本，再恢复数据库和附件并更换会话密钥，旧登录会话失效。恢复后启动程序并重新登录。

备份按需手动执行，未安装定时任务。建议每天结束工作后备份，并将备份复制到另一块磁盘。

## CSV 与附件

客户导入使用 UTF-8 CSV，建议先导出获取模板。表头：

```csv
公司名称,国家,联系人,邮箱,客户类型,来源,关注产品
示例客户有限公司,德国,Anna,anna@example.com,潜在客户,展会,户外家具
```

公司名称必填，客户类型可为「潜在客户 / 正式客户 / 重点客户」。每次最多 2000 行；公司名称大小写不敏感查重；重复行跳过；格式错误整批撤销。导入客户默认归当前操作人负责，管理员可以再分配。

附件支持 PDF、PNG、JPG、JPEG、WebP、CSV、XLSX、DOCX、TXT，单次请求不超过 10 MB（包括表单开销）。附件存于本机磁盘，下载需要登录并校验业务权限。产品图片以附件方式保存，第一张图片会显示在产品卡片上，第一版不做图库裁剪。

## 程序结构

```text
app/
├── __init__.py           应用工厂、CSRF、事务、安全响应与错误处理
├── extensions.py         SQLAlchemy 会话与 SQLite 外键/WAL/忙等待
├── models/               19 张业务表的模型
├── modules/
│   ├── auth.py           登录、退出、修改密码
│   ├── dashboard.py      工作台数据、待办、真实报表
│   ├── customers.py      客户、联系人、跟进、CSV
│   ├── products.py       产品、供应商、供货来源
│   ├── quotations.py     报价版本、草稿、转订单
│   ├── orders.py         订单、供货分配及进度
│   ├── finance.py        收款、更正、分批出货
│   ├── settings.py       用户、操作记录
│   ├── files.py          附件及报价 PDF
│   ├── common.py         权限范围查询辅助
│   └── business.py       注册业务模块
├── services/
│   ├── access.py         角色与记录级权限
│   ├── quotation.py      报价计算、版本复制、原子转单
│   ├── serialization.py  数据输出与敏感字段过滤
│   └── audit.py          操作日志
├── utils/                日期、整数金额、参数校验
├── templates/index.html  页面入口
└── static/               原型样式与真实接口交互
migrations/               Alembic 数据库迁移
run.py                    初始化、启动、升级、备份、恢复
requirements.lock.txt     当前验证过的依赖版本
requirements-dev.txt      可选浏览器测试依赖
start.command             macOS 启动入口
install.command           macOS 首次安装入口
backup.command            macOS 备份入口
tests/                    独立数据库业务测试与可选浏览器测试
screenshots/              浏览器验证截图，使用独立临时样例数据
crm-prototype/            之前确认的静态原型，保留用于参考
```

## 升级与验证

修改模型后生成新的迁移，不应直接修改已应用的 `0001`。先备份，再执行：

```sh
.venv/bin/python -m alembic revision --autogenerate -m "describe change"
# 人工检查生成的迁移
.venv/bin/python run.py upgrade
```

核心业务测试只使用临时数据库，不修改正式数据：

```sh
.venv/bin/python -m pytest -q
```

可选浏览器测试使用已有 Chrome，安装额外开发依赖后运行：

```sh
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python tests/browser_smoke.py
```

macOS 自动使用 `/Applications/Google Chrome.app`；其他环境需自行安装 Playwright Chromium：` .venv/bin/python -m playwright install chromium`。测试使用本机 5012 端口、临时数据库和独立测试账号，结束后关闭测试服务。生产端口为 5001。

目前不含邮箱/WhatsApp 自动同步、完整库存、生产排程和自动汇率折算。SQLite 适合当前本地小团队规模，文件不要放在同步盘或网络共享磁盘中让多个应用同时写入。

## HTML 使用指南

双击项目根目录的 [远帆CRM-使用指南.html](远帆CRM-使用指南.html) 可离线查看。服务启动后也可访问 http://127.0.0.1:5001/static/guide.html 。支持目录搜索和打印，包含各模块操作、角色权限、备份恢复及常见问题。
