# 华为产品全量参数导出工具

一键抓取**中国国内**华为产品的全量规格参数，数据来源两个：

| 数据源 | 内容 | 特点 |
|---|---|---|
| 华为商城 `vmall.com` | 国内在售商品（含汽车） | 参数最细，含 SKU、型号、传播名 |
| 华为消费者官网 `consumer.huawei.com/cn` | 官网产品库 | 覆盖广，含部分历史型号 |

输出 `品类 -> 系列 -> 产品 -> 参数` 的层级 JSON，并同步导出 **Excel** 和 **CSV**。

## 快速开始（任何机器 3 步搞定）

环境要求：Python 3.9 及以上（Windows / macOS / Linux 均可）。

```bash
# 1. 安装依赖（只有 3 个）
pip install -r requirements.txt

# 2. 运行（不需要任何命令行参数）
python run.py

# 3. 查看结果
#    output/vmall/         华为商城数据
#    output/consumer_cn/   华为官网中国站数据
```

> 如果 `pip` 下载慢，使用国内镜像：
> `pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`
>
> 如果报错 `no module named 'requests'`，说明依赖没装上或装到了别的 Python，
> 用 `python -m pip install -r requirements.txt` 重新安装即可。

## 修改配置

所有配置都在 `run.py` 顶部的 `CONFIG` 区域，改完保存、重新运行即可，不需要记任何命令行参数：

```python
CONFIG = {
    "tasks": ["vmall", "consumer"],   # 抓哪些来源，可只留一个
    "consumer_region": "cn",          # 官网区域：cn 中国；多国用列表 ["cn","my"]
    "categories": None,               # None=全部品类；或 ["phones", "tablets"]
    "limit": None,                    # None=不限数量；调试时改成 5
    "export_excel": True,             # 是否导出 Excel
    "export_csv": True,               # 是否导出 CSV
    "request_interval": 0.8,          # 请求间隔（秒）
    ...
}
```

常用改法举例：

| 需求 | 改法 |
|---|---|
| 只抓手机 | `"categories": ["phones"]` |
| 只抓华为商城 | `"tasks": ["vmall"]` |
| 抓官网其他海外站 | `"consumer_region": "my"`（马来）/ `"hk"` 香港 / `"mx"` 墨西哥 / `"ru"` 俄罗斯 / `"ae"` 阿联酋 / `"id"` 印尼 / `"th"` 泰国 |
| 一次抓多个国家 | `"consumer_region": ["cn", "my", "hk"]`（列表形式） |
| 先少量测试 | `"limit": 5` |

## 品类清单

- **华为商城**：`phones` 手机、`tablets` 平板、`wearables` 手表手环、`audio` 耳机音箱、`laptops` 笔记本、`routers` 路由器、`smart_screens` 智慧屏、`printers` 打印机、`monitors` 显示器、`cars` 汽车（鸿蒙智行）
- **消费者官网**：`phones`、`tablets`、`wearables`、`laptops`、`headphones`、`speakers`、`routers`、`monitors`、`printers`、`visions`

## 输出说明

```
output/
├── vmall/                # 华为商城，每品类 3 个文件
│   ├── phones.json       #   层级 JSON（品类 -> 系列 -> 产品 -> 参数）
│   ├── phones.xlsx       #   Excel：「全部参数」汇总表 + 每系列一个 sheet
│   ├── phones.csv        #   CSV：一行一个参数
│   └── ...
├── consumer_cn/          # 华为官网中国站，结构同上
└── diff/                 # 重复运行时自动生成「新增商品」差异文件
```

JSON 中每个产品的 `specifications` 为参数列表：

```json
{
  "group_name": "主体",
  "attr_name": "型号",
  "attr_value": "HLS-AL00",
  "attr_remark": ""
}
```

Excel / CSV 为平铺结构，每行一个参数：`品类 / 系列 / 产品 / 参数分组 / 参数名 / 参数值 / 备注 / 链接`。

## 项目结构

```
huawei-spec-export/
├── run.py                  # 唯一入口（配置在文件顶部 CONFIG 区域）
├── requirements.txt        # 依赖清单（requests / beautifulsoup4 / openpyxl）
├── README.md
├── src/
│   └── huawei_export/
│       ├── config.py       # 品类与系列归类规则
│       ├── http_client.py  # HTTP 客户端（限速/重试/CSRF）
│       ├── vmall.py        # 华为商城抓取
│       ├── consumer.py     # 消费者官网抓取
│       ├── hima.py         # 鸿蒙智行汽车抓取
│       ├── json_export.py  # JSON 导出与新增商品 diff
│       └── excel_export.py # Excel / CSV 导出
└── output/                 # 运行后自动生成
```

## 常见问题

**Q: 报 `no module named 'requests'`？**
A: 依赖没安装或装错了 Python。在项目目录执行 `python -m pip install -r requirements.txt`。

**Q: 抓一半失败怎么办？**
A: 直接重新运行 `python run.py`。工具内置限速、重试与退避；重复运行会覆盖同品类结果，并在 `output/diff/` 生成新增商品差异文件。

**Q: 想定时每天抓？**
A: Windows 用「任务计划程序」、macOS/Linux 用 `cron`，命令都是 `python run.py`。

**Q: 官网有些老产品没有参数？**
A: 部分历史型号的规格页官网已下线，这类产品会保留条目但参数为空，属于官网真实情况。

## 注意事项

- 商城数据来自 VMALL 官方搜索接口与商品详情页内嵌 JSON；官网数据来自规格页的静态 HTML。
- 官网页面结构如果变化，解析逻辑可能需要调整（解析器已兼容标准手风琴、多列 `__wrap`、多变体 `multi-*` 三种结构）。
- 全量抓取约需 10–30 分钟（有限速保护），请保持网络畅通。
