"""华为产品全量参数导出工具。

直接运行即可抓取中国国内全部产品参数（华为商城 + 华为消费者官网中国站）：

    python run.py

所有可配置项都在下方 CONFIG 区域，修改后重新运行即可。
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# CONFIG：所有配置都在这里修改，改完直接 python run.py 重新运行
# ---------------------------------------------------------------------------
CONFIG = {
    # 抓取任务："vmall" = 华为商城（国内在售商品），"consumer" = 华为消费者官网
    # 默认两个都抓；只抓一个就改成 ["vmall"] 或 ["consumer"]
    "tasks": ["vmall", "consumer"],
    # consumer 官网区域：字符串抓单个国家，列表一次抓多个国家
    # 已验证可用：cn 中国大陆 / my 马来西亚 / hk 中国香港 / mx 墨西哥
    #             ru 俄罗斯 / ae 阿联酋 / id 印尼 / th 泰国
    # 示例：只抓中国 -> "cn"；抓多个国家 -> ["cn", "my", "hk"]
    "consumer_region": "cn",
    # 要抓的品类：None = 全部品类；也可以指定列表，例如 ["phones", "tablets"]
    # VMALL 品类：phones tablets wearables audio laptops routers
    #             smart_screens printers monitors cars
    # 官网品类： phones tablets wearables laptops headphones speakers
    #            routers monitors printers visions
    "categories": None,
    # 每个品类最多抓取多少个产品：None = 不限；调试时可改成 5 之类的小数字
    "limit": None,
    # 输出目录（相对项目根目录）
    "output_dir": "output",
    # 是否同时导出 Excel / CSV（JSON 始终导出）
    "export_excel": True,
    "export_csv": True,
    # 网络控制：请求间隔秒数 / 最大重试次数 / 重试退避基数
    "request_interval": 0.8,
    "max_retries": 4,
    "backoff_factor": 1.5,
    # 日志：DEBUG / INFO / WARNING / ERROR；log_file 为 None 时只输出到屏幕
    "log_level": "INFO",
    "log_file": None,
}
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from huawei_export.config import CONSUMER_CATEGORY_PRESETS, VMALL_CATEGORY_PRESETS
from huawei_export.consumer import ConsumerHuaweiExporter
from huawei_export.excel_export import write_csv, write_excel
from huawei_export.hima import HIMA_CATEGORY_KEY, HimaCarExporter
from huawei_export.http_client import ConsumerClient, VmallClient
from huawei_export.vmall import VmallExporter


def configure_logging(level_name: str, log_file: str | None) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


def export_tabular(payload: dict, output_dir: Path, config: dict) -> None:
    """按配置把品类 JSON 同步导出为 Excel / CSV。"""
    if config["export_excel"]:
        path = write_excel(payload, output_dir)
        print(f"  Excel -> {path}")
    if config["export_csv"]:
        path = write_csv(payload, output_dir)
        print(f"  CSV   -> {path}")


def run_vmall(config: dict) -> None:
    """抓取华为商城（vmall.com）全部品类。"""
    logger = logging.getLogger("run_vmall")
    output_dir = PROJECT_ROOT / config["output_dir"] / "vmall"
    diff_dir = PROJECT_ROOT / config["output_dir"] / "diff" / "vmall"

    client = VmallClient(
        min_request_interval=config["request_interval"],
        max_retries=config["max_retries"],
        backoff_factor=config["backoff_factor"],
    )
    exporter = VmallExporter(client=client)
    hima_exporter = HimaCarExporter(request_interval=config["request_interval"])

    categories = config["categories"] or list(VMALL_CATEGORY_PRESETS)
    for key in categories:
        try:
            if key == HIMA_CATEGORY_KEY:
                file_path, count = hima_exporter.export_category(
                    output_dir=output_dir,
                    diff_dir=diff_dir,
                    limit=config["limit"],
                )
                print(f"[vmall] {key}: {count} 个产品 -> {file_path}")
                payload = json.loads(Path(file_path).read_text(encoding="utf-8"))
                export_tabular(payload, output_dir, config)
                continue
            category = exporter.get_category(key)
            file_path, count, payload = exporter.export_category(
                category,
                output_dir=output_dir,
                diff_dir=diff_dir,
                limit=config["limit"],
            )
            print(f"[vmall] {key}: {count} 个产品 -> {file_path}")
            export_tabular(payload, output_dir, config)
        except Exception as exc:  # noqa: BLE001 - 单个品类失败不影响其他品类
            logger.error("品类 %s 抓取失败，已跳过: %s", key, exc)
    logger.info("VMALL export finished")


def run_consumer_one_region(config: dict, region: str) -> None:
    """抓取华为消费者官网（consumer.huawei.com）单个区域的全部品类。"""
    logger = logging.getLogger("run_consumer")
    output_dir = PROJECT_ROOT / config["output_dir"] / f"consumer_{region}"
    diff_dir = PROJECT_ROOT / config["output_dir"] / "diff" / f"consumer_{region}"

    client = ConsumerClient(
        region=region,
        min_request_interval=config["request_interval"],
        max_retries=config["max_retries"],
        backoff_factor=config["backoff_factor"],
    )
    exporter = ConsumerHuaweiExporter(client=client)

    categories = config["categories"] or list(CONSUMER_CATEGORY_PRESETS)
    for key in categories:
        if key not in CONSUMER_CATEGORY_PRESETS:
            logger.warning("官网没有该品类，已跳过: %s", key)
            continue
        try:
            category = exporter.get_category(key)
            file_path, count, payload = exporter.export_category(
                category,
                output_dir=output_dir,
                diff_dir=diff_dir,
                limit=config["limit"],
            )
            print(f"[consumer/{region}] {key}: {count} 个产品 -> {file_path}")
            export_tabular(payload, output_dir, config)
        except Exception as exc:  # noqa: BLE001 - 单个品类失败不影响其他品类
            logger.error("品类 %s 抓取失败，已跳过: %s", key, exc)
    logger.info("Consumer export finished (region=%s)", region)


def run_consumer(config: dict) -> None:
    """按配置抓取一个或多个区域的官网数据。"""
    logger = logging.getLogger("run_consumer")
    regions = config["consumer_region"]
    if isinstance(regions, str):
        regions = [regions]
    for region in regions:
        try:
            run_consumer_one_region(config, region.strip())
        except Exception as exc:  # noqa: BLE001 - 单个国家失败不影响其他国家
            logger.error("区域 %s 抓取失败，已跳过: %s", region, exc)


def main() -> int:
    config = CONFIG
    configure_logging(config["log_level"], config["log_file"])

    print("=" * 60)
    print("华为产品全量参数导出")
    print(f"任务: {', '.join(config['tasks'])}")
    print(f"品类: {config['categories'] or '全部'}")
    print(f"输出目录: {PROJECT_ROOT / config['output_dir']}")
    print("=" * 60)

    logger = logging.getLogger("main")
    if "vmall" in config["tasks"]:
        try:
            run_vmall(config)
        except Exception as exc:  # noqa: BLE001 - 任务级失败不影响其他任务
            logger.error("VMALL 任务失败: %s", exc)
    if "consumer" in config["tasks"]:
        try:
            run_consumer(config)
        except Exception as exc:  # noqa: BLE001
            logger.error("Consumer 任务失败: %s", exc)

    print("全部任务完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
