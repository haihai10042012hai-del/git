#!/usr/bin/env python3
"""Prepare Amazon finance PDFs for review and build a renamed ZIP output."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any


MAX_ZIP_DEPTH = 3
MAX_ZIP_FILES = 5000
MAX_MEMBER_BYTES = 500 * 1024 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024

CATEGORIES = {"销售汇总报表", "广告发票", "费用发票", "待确认"}
SITES = {
    "美国", "加拿大", "墨西哥", "英国", "德国", "法国", "意大利", "西班牙",
    "荷兰", "瑞典", "波兰", "比利时", "日本", "澳大利亚", "新加坡",
    "阿联酋", "沙特阿拉伯", "印度", "巴西", "土耳其", "站点待确认",
}
FEE_TYPES = {
    "平台费用", "FBA运费", "仓储费", "移除销毁费", "退货处理费", "服务费",
    "综合费用", "费用待确认",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unique_path(parent: Path, name: str) -> Path:
    candidate = parent / name
    stem, suffix = candidate.stem, candidate.suffix
    number = 2
    while candidate.exists():
        candidate = parent / f"{stem}（{number}）{suffix}"
        number += 1
    return candidate


def safe_extract_zip(zip_path: Path, destination: Path, depth: int = 0) -> None:
    if depth > MAX_ZIP_DEPTH:
        raise RuntimeError(f"嵌套 ZIP 超过 {MAX_ZIP_DEPTH} 层：{zip_path}")
    destination.mkdir(parents=True, exist_ok=True)
    extracted_zips: list[Path] = []
    total_bytes = 0

    with zipfile.ZipFile(zip_path) as archive:
        members = [m for m in archive.infolist() if not m.is_dir()]
        if len(members) > MAX_ZIP_FILES:
            raise RuntimeError(f"ZIP 文件数超过安全上限：{zip_path}")

        for member in members:
            member_path = PurePosixPath(member.filename.replace("\\", "/"))
            if member_path.is_absolute() or ".." in member_path.parts or ":" in member.filename:
                raise RuntimeError(f"ZIP 含不安全路径：{member.filename}")
            if member.file_size > MAX_MEMBER_BYTES:
                raise RuntimeError(f"ZIP 单个文件过大：{member.filename}")
            total_bytes += member.file_size
            if total_bytes > MAX_TOTAL_BYTES:
                raise RuntimeError(f"ZIP 解压总量超过安全上限：{zip_path}")

            suffix = member_path.suffix.lower()
            if suffix not in {".pdf", ".zip"}:
                continue
            target = destination.joinpath(*member_path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target = unique_path(target.parent, target.name)
            with archive.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            if suffix == ".zip":
                extracted_zips.append(target)

    for nested_zip in extracted_zips:
        nested_destination = unique_path(nested_zip.parent, f"{nested_zip.stem}_已解压")
        safe_extract_zip(nested_zip, nested_destination, depth + 1)


def copy_pdf(source: Path, destination_dir: Path) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    target = unique_path(destination_dir, source.name)
    shutil.copy2(source, target)
    return target


def stage_input(input_path: Path, work_dir: Path) -> list[Path]:
    staged = work_dir / "source-pdfs"
    extracted = work_dir / "extracted"
    staged.mkdir(parents=True, exist_ok=True)
    sources: list[Path] = []

    if input_path.is_file() and input_path.suffix.lower() == ".pdf":
        sources.append(copy_pdf(input_path, staged))
    elif input_path.is_file() and input_path.suffix.lower() == ".zip":
        safe_extract_zip(input_path, extracted / input_path.stem)
        for pdf in sorted(extracted.rglob("*.pdf"), key=lambda p: str(p).lower()):
            sources.append(copy_pdf(pdf, staged))
    elif input_path.is_dir():
        candidates = list(input_path.rglob("*"))
        for candidate in sorted(candidates, key=lambda p: str(p).lower()):
            if not candidate.is_file():
                continue
            if candidate.suffix.lower() == ".pdf":
                sources.append(copy_pdf(candidate, staged))
            elif candidate.suffix.lower() == ".zip":
                zip_destination = unique_path(extracted, candidate.stem)
                safe_extract_zip(candidate, zip_destination)
        for pdf in sorted(extracted.rglob("*.pdf"), key=lambda p: str(p).lower()):
            sources.append(copy_pdf(pdf, staged))
    else:
        raise ValueError("输入必须是 PDF、ZIP 或目录。")

    if not sources:
        raise RuntimeError("输入中没有找到 PDF。")
    return sources


def extract_with_pypdf(pdf_path: Path) -> tuple[str, int, str]:
    errors: list[str] = []
    for module_name in ("pypdf", "PyPDF2"):
        try:
            module = __import__(module_name)
            reader = module.PdfReader(str(pdf_path))
            if getattr(reader, "is_encrypted", False):
                try:
                    reader.decrypt("")
                except Exception:
                    pass
            texts = []
            for page in reader.pages:
                try:
                    texts.append(page.extract_text() or "")
                except Exception as exc:
                    texts.append("")
                    errors.append(str(exc))
            return "\n\n".join(texts), len(reader.pages), "; ".join(errors)
        except Exception as exc:
            errors.append(f"{module_name}: {exc}")

    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.stdout, 0, "; ".join(errors)
    except Exception as exc:
        errors.append(f"pdftotext: {exc}")
    return "", 0, "; ".join(errors)


def command_prepare(args: argparse.Namespace) -> None:
    input_path = Path(args.input).expanduser().resolve()
    work_dir = Path(args.work_dir).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"输入不存在：{input_path}")
    if work_dir.exists() and any(work_dir.iterdir()):
        raise FileExistsError(f"工作目录不是空目录：{work_dir}")
    work_dir.mkdir(parents=True, exist_ok=True)

    pdfs = stage_input(input_path, work_dir)
    text_dir = work_dir / "texts"
    text_dir.mkdir(parents=True, exist_ok=True)
    manifest_items = []

    for index, pdf_path in enumerate(pdfs, start=1):
        source_id = f"pdf-{index:03d}"
        text, page_count, extraction_error = extract_with_pypdf(pdf_path)
        text_path = text_dir / f"{source_id}.txt"
        text_path.write_text(text, encoding="utf-8")
        manifest_items.append(
            {
                "source_id": source_id,
                "original_name": pdf_path.name,
                "pdf_path": str(pdf_path),
                "text_path": str(text_path),
                "page_count": page_count,
                "text_characters": len(text.strip()),
                "text_status": "可分析" if len(text.strip()) >= 80 else "需视觉/OCR检查",
                "extraction_error": extraction_error,
                "sha256": sha256_file(pdf_path),
            }
        )

    manifest = {
        "schema_version": 1,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "input_path": str(input_path),
        "pdf_count": len(manifest_items),
        "items": manifest_items,
    }
    manifest_path = work_dir / "manifest.json"
    write_json(manifest_path, manifest)
    print(f"已准备 {len(manifest_items)} 份 PDF")
    print(f"清单：{manifest_path}")


def clean_component(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "", text)
    text = re.sub(r"\s+", "", text)
    return text or fallback


def normalize_company(value: Any) -> str:
    company = clean_component(value, "主体待确认")
    if re.search(r"[A-Za-z]", company):
        return "主体待确认"
    return company


def normalize_site(value: Any) -> str:
    site = clean_component(value, "站点待确认")
    return site if site in SITES else "站点待确认"


def normalize_date(value: Any) -> tuple[int | None, int | None, int | None]:
    text = str(value or "").strip()
    match = re.search(
        r"(?P<y>20\d{2}|19\d{2})\D+(?P<m>1[0-2]|0?[1-9])"
        r"(?:\D+(?P<d>3[01]|[12]\d|0?[1-9]))?",
        text,
    )
    if not match:
        return None, None, None
    year = int(match.group("y"))
    month = int(match.group("m"))
    day = int(match.group("d")) if match.group("d") else None
    return year, month, day


def date_prefix(category: str, value: Any) -> str:
    year, month, day = normalize_date(value)
    if year is None or month is None:
        return "日期待确认"
    prefix = f"{year % 100}.{month}"
    if category == "广告发票":
        prefix += f".{day}" if day is not None else ".日待确认"
    return prefix


def build_filename(decision: dict[str, Any]) -> tuple[str, bool]:
    category = clean_component(decision.get("category"), "待确认")
    if category not in CATEGORIES:
        category = "待确认"
    company = normalize_company(decision.get("company"))
    site = normalize_site(decision.get("site"))
    prefix = date_prefix(category, decision.get("date"))

    if category == "销售汇总报表":
        name = f"{prefix}{company}{site}销售报告.pdf"
    elif category == "广告发票":
        name = f"{prefix}{company}{site}广告发票.pdf"
    elif category == "费用发票":
        fee_type = clean_component(decision.get("fee_type"), "费用待确认")
        if fee_type not in FEE_TYPES:
            fee_type = "费用待确认"
        name = f"{prefix}{company}{site}{fee_type}发票.pdf"
    else:
        name = f"{prefix}{company}{site}类别待确认.pdf"

    pending = "待确认" in name
    return name, pending


def load_decisions(path: Path) -> list[dict[str, Any]]:
    payload = read_json(path)
    decisions = payload.get("decisions") if isinstance(payload, dict) else payload
    if not isinstance(decisions, list) or not all(isinstance(item, dict) for item in decisions):
        raise ValueError("决策 JSON 必须是对象数组，或包含 decisions 对象数组。")
    return decisions


def dominant_value(values: list[Any], fallback: Any) -> Any:
    """Return the sole most-common value, or a safe fallback on missing/tied data."""
    if not values:
        return fallback
    counts = Counter(values)
    highest = max(counts.values())
    winners = [value for value, count in counts.items() if count == highest]
    return winners[0] if len(winners) == 1 else fallback


def build_archive_filename(decisions: list[dict[str, Any]]) -> str:
    months: list[tuple[int, int]] = []
    companies: list[str] = []
    for decision in decisions:
        year, month, _ = normalize_date(decision.get("date"))
        if year is not None and month is not None:
            months.append((year, month))
        companies.append(normalize_company(decision.get("company")))

    dominant_month = dominant_value(months, None)
    prefix = (
        f"{dominant_month[0] % 100}.{dominant_month[1]}"
        if dominant_month is not None
        else "日期待确认"
    )
    company = dominant_value(companies, "主体待确认")
    return f"{prefix}{company}.zip"


def command_finalize(args: argparse.Namespace) -> None:
    manifest_path = Path(args.manifest).expanduser().resolve()
    decisions_path = Path(args.decisions).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    manifest = read_json(manifest_path)
    items = manifest.get("items") if isinstance(manifest, dict) else None
    if not isinstance(items, list):
        raise ValueError("manifest.json 缺少 items 数组。")

    decisions = load_decisions(decisions_path)
    by_id: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        source_id = str(decision.get("source_id") or "")
        if not source_id or source_id in by_id:
            raise ValueError(f"决策中 source_id 缺失或重复：{source_id!r}")
        by_id[source_id] = decision

    expected_ids = {str(item.get("source_id")) for item in items}
    if set(by_id) != expected_ids:
        missing = sorted(expected_ids - set(by_id))
        extra = sorted(set(by_id) - expected_ids)
        raise ValueError(f"决策与清单不一致；缺少={missing}，多余={extra}")

    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / build_archive_filename(decisions)
    if zip_path.exists():
        raise FileExistsError(f"输出目录中已有同名结果：{zip_path.name}")

    used_names: set[str] = set()
    archive_entries: list[tuple[Path, str]] = []
    for item in items:
        source_id = str(item["source_id"])
        decision = by_id[source_id]
        base_name, _ = build_filename(decision)
        new_name = base_name
        number = 2
        while new_name.casefold() in used_names:
            new_name = f"{Path(base_name).stem}（{number}）.pdf"
            number += 1
        used_names.add(new_name.casefold())

        source_pdf = Path(item["pdf_path"])
        if not source_pdf.is_file():
            raise FileNotFoundError(f"PDF 不存在：{source_pdf}")
        archive_entries.append((source_pdf, new_name))

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source_pdf, new_name in sorted(archive_entries, key=lambda item: item[1].casefold()):
            archive.write(source_pdf, arcname=new_name)

    with zipfile.ZipFile(zip_path) as archive:
        zip_names = [Path(name).name for name in archive.namelist() if name.lower().endswith(".pdf")]
        damaged_member = archive.testzip()
    expected_names = [new_name for _, new_name in archive_entries]
    if set(zip_names) != set(expected_names) or len(zip_names) != len(items):
        raise RuntimeError("输出自检失败：ZIP 与清单数量或文件名不一致。")
    if damaged_member is not None:
        raise RuntimeError(f"输出自检失败：ZIP 成员损坏：{damaged_member}")

    print(f"已生成 {len(archive_entries)} 份重命名 PDF")
    print(f"ZIP：{zip_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="亚马逊财务 PDF 准备与 ZIP 重命名工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="解压并抽取 PDF 文本")
    prepare.add_argument("input", help="PDF、ZIP 或目录路径")
    prepare.add_argument("--work-dir", required=True, help="空的工作目录")
    prepare.set_defaults(handler=command_prepare)

    finalize = subparsers.add_parser("finalize", help="依据人工/模型决策生成重命名 ZIP")
    finalize.add_argument("--manifest", required=True, help="prepare 生成的 manifest.json")
    finalize.add_argument("--decisions", required=True, help="UTF-8 决策 JSON")
    finalize.add_argument("--output-dir", required=True, help="新的输出目录")
    finalize.set_defaults(handler=command_finalize)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.handler(args)
        return 0
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
