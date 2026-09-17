from __future__ import annotations

"""Build the deterministic Step 21.2.2A candidate and boundary datasets."""

import csv
import hashlib
import heapq
import json
import re
import sys
import zipfile
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.contracts.review_semantics import RISK_TYPE_REGISTRY
from app.risk_calibration.severity import RiskSeverityEvaluator


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "evaluation_demo"
RAW = ROOT / "data" / "external_raw"
FROZEN = ROOT / "data" / "benchmarks" / "review_governance_gold_v1.jsonl"
DOWNLOAD_MANIFEST = ROOT / "artifacts" / "step2122a" / "source_download_manifest.json"
SEED = "step21.2.2a-demo-v1-fixed-seed-2122"
FROZEN_SHA = "9B9D596D88E28EE93327CC95E6F4B18DB0B2A939B70BE8F5CBF10C1E226CAB54"
APPROVED_SOURCE_IDS = {
    "asap_chinese_reviews", "figshare_chinese_negative_reviews",
    "hf_fake_reviews_apache", "e_review_expert_designed",
}

HF_TRANSLATIONS = {
    "5581": "和宣传完全一致。我把它们当作儿子建筑主题聚会的装饰，也可以用于运动训练，做得很结实。",
    "33082": "很棒的乐高套装，儿子非常喜欢，还想要其他同系列套装。",
    "24564": "作者很会吸引读者，这个爱情故事很抓人，让我一直想翻页看后续。",
    "25266": "很高兴结局圆满。读完这本书后，我更能理解知足的重要性。",
    "38581": "唯一的不满是尺码似乎偏大，尤其裤长比预期长了几厘米。",
    "37343": "很喜欢这件商品，如果能配裤子或围裙会更好，不过现在也不错。",
    "9424": "它正好满足我的需求，使用简单。希望能多配几把钥匙，但总体仍然满意。",
    "13678": "我从小就看这部电影，非常喜欢。表演很出色，故事也讲得很好，只是对演技的称赞重复了好几遍。",
    "34509": "这辆玩具卡车很受欢迎，不过女儿发现它只能是卡车造型时有些失望，原文到这里突然中断。",
    "34679": "买来送给一岁多的女孩，她很喜欢。后面又说这是给儿子的圣诞礼物，前后对象并不一致。",
    "9229": "东西在慢慢散架，处理起来并不容易，但我会继续观察。总体又说它和宣传一致。",
    "45": "这个价格还算可以，但产品质量让我有些失望。",
    "24148": "这位作者写的故事和角色都很好，我肯定会继续读下一本。",
    "21948": "看起来质量不错，但底部和侧面的塑料件很难安装。后面又说已经使用一年而且一直很好用。",
    "30299": "我读过这位作者的所有书。角色很真实，但发生了太多糟糕的事情，结局也很悲伤。",
    "25514": "这是一部令人愉快的小说，我还会读这位作者的作品。故事和角色都很好，人物塑造也不错。",
    "38808": "我给女儿买了这些，她很喜欢，以后还会再买。后面突然出现与商品无关的尺码描述。",
    "21714": "三只猫都很喜欢这种食物，我会继续喂。随后又说猫会吃但味道不好，并突然提到已经使用产品一年。",
    "29049": "这本书值得了解，作者很懂得如何阅读，也很会解释事情。",
    "13219": "这个系列令人印象深刻，让我一直关注其中的历史内容，整体完成得很好。",
    "24610": "当过去变成现在时，你需要面对过去，并找到另外两个人。",
    "24605": "读起来很愉快，人物有趣，故事线也不错。我喜欢这本书，但原文最后突然中断。",
    "5775": "我已经用了两年，材料质量不错。只给四星是因为我不想必须穿戴它，但原文没有说完。",
    "9305": "在 Windows 10 上识别硬盘时遇到一点问题，联系商家后很快收到说明。它有些吵，但能用，二十美元很划算。",
    "12962": "我喜欢他在其他影片里的表演，不过这一部可能是我的最爱，他在这里很有男子气概。",
}


CAL_EXPERT = [
    ("paid-01", "商家说明只要提交真实使用评价，就会发放十元体验补贴，星级不限。", ["paid_review"], "explicit", "medium"),
    ("paid-02", "发布晒单后可领取赠品，活动页面没有要求必须好评。", ["paid_review"], "explicit", "medium"),
    ("paid-03", "每完成一条商品体验评论，推广方都会结算固定佣金。", ["paid_review"], "explicit", "easy"),
    ("paid-04", "客服邀请我评价后领取红包，但没有说明评价内容必须正面。", ["paid_review"], "explicit", "medium"),
    ("paid-05", "试用活动会向参与评价的用户提供购物券。", ["paid_review"], "explicit", "easy"),
    ("paid-06", "品牌方按已发布的测评数量支付稿费。", ["paid_review"], "explicit", "easy"),
    ("rating-01", "客服说必须给五颗星并发送截图，才能领取优惠券。", ["rating_manipulation"], "explicit", "easy"),
    ("rating-02", "商家要求把四星修改成五星后才补差价。", ["rating_manipulation"], "explicit", "easy"),
    ("rating-03", "群里通知大家今晚集中给店铺打满分冲排名。", ["rating_manipulation"], "explicit", "medium"),
    ("rating-04", "只有评分达到五分的买家才能参加返利活动。", ["rating_manipulation"], "explicit", "easy"),
    ("rating-05", "客服逐个联系低分用户，要求全部改成满分。", ["rating_manipulation"], "explicit", "medium"),
    ("rating-06", "补偿金额与最终星级挂钩，分数越高返得越多。", ["rating_manipulation"], "mixed", "hard"),
    ("suppress-01", "售后说先删除差评，系统里才会开放退款入口。", ["review_suppression"], "explicit", "easy"),
    ("suppress-02", "商家反复要求撤下低分评价，否则不再处理工单。", ["review_suppression"], "explicit", "medium"),
    ("suppress-03", "客服提出补偿的条件是隐藏之前发布的负面内容。", ["review_suppression"], "mixed", "hard"),
    ("suppress-04", "对方威胁说不删评论就公开我的投诉记录。", ["review_suppression", "harassment_or_abuse"], "explicit", "hard"),
    ("suppress-05", "页面只保留好评，近期出现的低分内容都被批量屏蔽。", ["review_suppression"], "explicit", "medium"),
    ("after-01", "退货已经签收一周，退款仍未到账，客服让我继续等待。", ["after_sales_risk"], "explicit", "medium"),
    ("after-02", "商品开箱就是坏的，售后拒绝换货也不说明原因。", ["after_sales_risk"], "explicit", "easy"),
    ("after-03", "少发了配件，补发工单多次被关闭。", ["after_sales_risk"], "explicit", "medium"),
    ("after-04", "退货运费由谁承担一直没有明确答复。", ["after_sales_risk"], "implicit", "hard"),
    ("after-05", "维修后的商品再次故障，平台和商家互相推诿。", ["after_sales_risk"], "implicit", "hard"),
    ("multi-01", "五星截图可以返现，但必须同时删除之前的差评。", ["paid_review", "rating_manipulation", "review_suppression"], "mixed", "hard"),
    ("multi-02", "商家组织员工刷单冲分，并让客服屏蔽真实投诉。", ["fake_review", "rating_manipulation", "review_suppression"], "mixed", "hard"),
    ("multi-03", "给好评就发红包，给差评则威胁停止售后。", ["paid_review", "rating_manipulation", "harassment_or_abuse"], "mixed", "hard"),
    ("multi-04", "没有购买过的人统一发布五星内容，完成后按条结算。", ["fake_review", "paid_review", "rating_manipulation"], "mixed", "hard"),
    ("multi-05", "退款被绑定到改五星和撤掉负面评价两个条件。", ["rating_manipulation", "review_suppression"], "mixed", "hard"),
    ("hardneg-01", "客服已经正常退款，我收到钱后主动更新评价，没有任何附加条件。", ["normal_review"], "mixed", "hard"),
    ("hardneg-02", "我删除旧评价是因为问题已经解决，并不是商家的要求。", ["normal_review"], "mixed", "hard"),
    ("hardneg-03", "赠品随订单直接附送，与是否评价以及评价星级都无关。", ["normal_review"], "mixed", "hard"),
]


BOUNDARY_EXPERT = [
    ("implicit-01", "评价那边处理妥当后把页面截一下，这边会给你安排一点心意。", ["paid_review", "rating_manipulation"], "implicit_or_paraphrase", "implicit"),
    ("implicit-02", "结果改得更漂亮一些，之前说好的补贴就能走流程。", ["rating_manipulation"], "implicit_or_paraphrase", "implicit"),
    ("implicit-03", "公开内容清理完成后，我们再继续处理你的售后申请。", ["review_suppression"], "implicit_or_paraphrase", "implicit"),
    ("implicit-04", "找些没下过单的账号把店铺口碑做起来。", ["fake_review"], "implicit_or_paraphrase", "implicit"),
    ("implicit-05", "满意度达到最高档，补偿就按约定发放。", ["rating_manipulation"], "implicit_or_paraphrase", "implicit"),
    ("lexical-01", "客服让我把那颗没点亮的星补上，才肯继续谈补偿。", ["rating_manipulation"], "lexical_mismatch", "implicit"),
    ("lexical-02", "他们希望把页面上不好听的声音先处理掉。", ["review_suppression"], "lexical_mismatch", "implicit"),
    ("lexical-03", "有人负责下单，有人负责写统一口径的体验。", ["fake_review"], "lexical_mismatch", "implicit"),
    ("lexical-04", "完成公开反馈任务后，会收到一笔辛苦费。", ["paid_review"], "lexical_mismatch", "implicit"),
    ("lexical-05", "店铺需要一批满格反馈把平均分托上去。", ["rating_manipulation"], "lexical_mismatch", "implicit"),
    ("multi-01", "没买过也能接单写满分评价，发完截图按条返钱。", ["fake_review", "paid_review", "rating_manipulation"], "multi_risk_or_conflict", "mixed"),
    ("multi-02", "删掉低分并改成五星，客服才同意退回货款。", ["rating_manipulation", "review_suppression"], "multi_risk_or_conflict", "mixed"),
    ("multi-03", "商家雇人集中打高分，同时批量投诉真实差评。", ["fake_review", "paid_review", "rating_manipulation", "review_suppression"], "multi_risk_or_conflict", "mixed"),
    ("multi-04", "客服公开我的号码，还威胁我撤掉那条一星评价。", ["privacy_risk", "harassment_or_abuse", "review_suppression"], "multi_risk_or_conflict", "mixed"),
    ("multi-05", "收到假货后申请退款，对方要求先给满分并删除投诉。", ["safety_or_fraud_risk", "rating_manipulation", "review_suppression"], "multi_risk_or_conflict", "mixed"),
    ("multi-06", "返红包换五星，随后又让参与者举报其他低分评论。", ["paid_review", "rating_manipulation", "review_suppression"], "multi_risk_or_conflict", "mixed"),
    ("multi-07", "统一模板由未购买账号发布，完成后领取购物卡。", ["fake_review", "paid_review"], "multi_risk_or_conflict", "mixed"),
    ("multi-08", "不撤差评就曝光地址，也不会再受理退货。", ["privacy_risk", "harassment_or_abuse", "review_suppression"], "multi_risk_or_conflict", "mixed"),
    ("multi-09", "五星任务按截图结算，低分内容则由专人设法隐藏。", ["paid_review", "rating_manipulation", "review_suppression"], "multi_risk_or_conflict", "mixed"),
    ("multi-10", "商家安排亲友假装买家夸商品，还要求真正买家撤回批评。", ["fake_review", "review_suppression"], "multi_risk_or_conflict", "mixed"),
    ("noise-01", "5⭐截T后返2O，低分先别留。", ["paid_review", "rating_manipulation"], "noisy_or_adversarial", "mixed"),
    ("noise-02", "shan图给客fu，wu星到位就发h包。", ["paid_review", "rating_manipulation"], "noisy_or_adversarial", "mixed"),
    ("noise-03", "差P删了→退k，懂的都懂。", ["review_suppression"], "noisy_or_adversarial", "implicit"),
    ("noise-04", "评 价 弄 成 满 格，再给你 bu 偿。", ["rating_manipulation"], "noisy_or_adversarial", "implicit"),
    ("noise-05", "没mai也可写，统1话术，jie算看截图。", ["fake_review", "paid_review"], "noisy_or_adversarial", "mixed"),
]


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize(text: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", text.lower())


def redact(text: str) -> str:
    text = re.sub(r"(?i)[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "[EMAIL]", text)
    text = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[PHONE]", text)
    text = re.sub(r"(?<!\d)\d{17}[0-9Xx](?!\d)", "[ID]", text)
    text = re.sub(r"(?i)https?://\S+", "[URL]", text)
    return re.sub(r"\s+", " ", text).strip()


def case(
    source: str, row_id: str, text: str, risks: list[str], *, selected_for: str,
    original_label: Any, expression: str, difficulty: str, boundary: str | None = None,
    translated: bool = False, label_source: str = "external_dataset_label",
) -> dict[str, Any]:
    text = redact(text)
    severity = RiskSeverityEvaluator().evaluate(risks, review_text=text).severity
    prefix = "cal" if selected_for == "calibration" else "boundary"
    public_row_id = str(row_id) if source == "e_review_expert_designed" else "sha256:" + sha(f"{source}|{row_id}")[:24]
    return {
        "caseId": f"{prefix}-{source}-{sha(str(row_id))[:14]}",
        "textZh": text,
        "sourceDataset": source,
        "sourceRowId": public_row_id,
        "sourceLanguage": "en" if translated else "zh",
        "translationStatus": "translated" if translated else "native",
        "adaptationStatus": "none",
        "riskTypes": sorted(set(risks)),
        "severity": severity,
        "expressionType": expression,
        "difficulty": difficulty,
        "multiRisk": len(set(risks)) > 1,
        "ambiguity": boundary == "ambiguous_context",
        "boundaryType": boundary,
        "labelSource": label_source,
        "sourceTier": "project_expert" if source == "e_review_expert_designed" else "public_open",
        "externalLabel": original_label,
        "calibrationStatus": "CANDIDATE_ONLY" if selected_for == "calibration" else None,
        "contentHash": sha(text),
        "templateFamily": "family-" + sha(re.sub(r"\d+", "<n>", normalize(text)))[:16],
    }


def ranked(rows: Iterable[dict[str, Any]], namespace: str) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: sha(f"{SEED}|{namespace}|{row['id']}"))


def load_asap() -> list[dict[str, Any]]:
    frame = pd.read_csv(RAW / "asap" / "train.csv", encoding="utf-8-sig")
    rows = []
    for _, row in frame.iterrows():
        text = redact(str(row["review"]))
        if 8 <= len(text) <= 220 and len(re.findall(r"[\u4e00-\u9fff]", text)) >= 6:
            rows.append({"id": str(row["id"]), "text": text, "star": int(float(row["star"]))})
    return rows


def load_figshare_reservoir(limit_per_label: int = 80) -> dict[int, list[dict[str, Any]]]:
    heaps: dict[int, list[tuple[int, str, dict[str, Any]]]] = {value: [] for value in range(4)}
    with zipfile.ZipFile(RAW / "figshare_chinese_negative" / "openData.zip") as bundle:
        for member in (item for item in bundle.infolist() if not item.is_dir()):
            with bundle.open(member) as handle:
                for raw_line in handle:
                    try:
                        source = json.loads(raw_line)
                        label = int(source["label"])
                        text = redact(str(source["content"]))
                    except (ValueError, KeyError, TypeError):
                        continue
                    if not 8 <= len(text) <= 180 or len(re.findall(r"[\u4e00-\u9fff]", text)) < 6:
                        continue
                    row_id = str(source["id"])
                    score = int(sha(f"{SEED}|figshare|{row_id}"), 16)
                    item = (-score, row_id, {"id": row_id, "text": text, "label": label})
                    if len(heaps[label]) < limit_per_label:
                        heapq.heappush(heaps[label], item)
                    elif item > heaps[label][0]:
                        heapq.heapreplace(heaps[label], item)
    return {label: [item[2] for item in sorted(values, key=lambda item: -item[0])] for label, values in heaps.items()}


def build_public_cases() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    calibration, boundary = [], []
    used: set[tuple[str, str]] = set()
    asap = load_asap()

    def take_asap(predicate, count: int, namespace: str) -> list[dict[str, Any]]:
        selected = []
        for row in ranked((row for row in asap if predicate(row)), namespace):
            key = ("asap_chinese_reviews", row["id"])
            if key not in used:
                used.add(key)
                selected.append(row)
            if len(selected) == count:
                break
        if len(selected) != count:
            raise RuntimeError(f"ASAP_SELECTION_SHORTFALL {namespace}={len(selected)}/{count}")
        return selected

    for row in take_asap(lambda item: item["star"] >= 4, 30, "cal-normal"):
        calibration.append(case("asap_chinese_reviews", row["id"], row["text"], ["normal_review"], selected_for="calibration", original_label=f"star={row['star']}", expression="implicit", difficulty="easy"))
    for row in take_asap(lambda item: item["star"] <= 2, 20, "cal-negative"):
        calibration.append(case("asap_chinese_reviews", row["id"], row["text"], ["negative_review"], selected_for="calibration", original_label=f"star={row['star']}", expression="implicit", difficulty="medium"))
    for row in take_asap(lambda item: item["star"] <= 2, 10, "boundary-hard-negative"):
        boundary.append(case("asap_chinese_reviews", row["id"], row["text"], ["negative_review"], selected_for="boundary", original_label=f"star={row['star']}", expression="implicit", difficulty="hard", boundary="hard_negative"))
    for row in take_asap(lambda item: item["star"] == 3, 5, "boundary-ambiguous"):
        risks = ["normal_review"]
        boundary.append(case("asap_chinese_reviews", row["id"], row["text"], risks, selected_for="boundary", original_label=f"star={row['star']}", expression="implicit", difficulty="hard", boundary="ambiguous_context"))

    fig = load_figshare_reservoir()

    def take_fig(labels: list[int], count: int, namespace: str) -> list[dict[str, Any]]:
        pool = ranked((row for label in labels for row in fig[label] if ("figshare_chinese_negative_reviews", row["id"]) not in used), namespace)
        selected = pool[:count]
        for row in selected:
            used.add(("figshare_chinese_negative_reviews", row["id"]))
        if len(selected) != count:
            raise RuntimeError(f"FIGSHARE_SELECTION_SHORTFALL {namespace}={len(selected)}/{count}")
        return selected

    for row in take_fig([2], 15, "cal-after-sales"):
        calibration.append(case("figshare_chinese_negative_reviews", row["id"], row["text"], ["after_sales_risk"], selected_for="calibration", original_label="2:consumer_service", expression="explicit", difficulty="medium", label_source="external_mapped_candidate"))
    for row in take_fig([0, 1], 5, "cal-legitimate-negative"):
        calibration.append(case("figshare_chinese_negative_reviews", row["id"], row["text"], ["negative_review"], selected_for="calibration", original_label=f"{row['label']}:logistics_or_product_function", expression="explicit", difficulty="medium", label_source="external_mapped_candidate"))
    for row in take_fig([3], 5, "cal-false-marketing"):
        calibration.append(case("figshare_chinese_negative_reviews", row["id"], row["text"], ["safety_or_fraud_risk"], selected_for="calibration", original_label="3:false_marketing", expression="implicit", difficulty="hard", label_source="external_mapped_candidate"))
    for row in take_fig([3], 5, "boundary-implicit"):
        boundary.append(case("figshare_chinese_negative_reviews", row["id"], row["text"], ["safety_or_fraud_risk"], selected_for="boundary", original_label="3:false_marketing", expression="implicit", difficulty="hard", boundary="implicit_or_paraphrase", label_source="external_mapped_candidate"))
    for row in take_fig([0, 1, 2], 5, "boundary-hard-negative"):
        boundary.append(case("figshare_chinese_negative_reviews", row["id"], row["text"], ["negative_review"], selected_for="boundary", original_label=f"{row['label']}:legitimate_complaint", expression="explicit", difficulty="hard", boundary="hard_negative", label_source="external_mapped_candidate"))

    fake_frame = pd.read_parquet(RAW / "hf_fake_reviews" / "train.parquet")
    hf_plan = [("cal-real", 0, 7), ("cal-fake", 1, 8), ("boundary-implicit", 1, 5), ("boundary-lexical-fake", 1, 3), ("boundary-lexical-real", 0, 2)]
    used_hf: set[str] = set()
    for purpose, label, count in hf_plan:
        candidates = []
        for index, row in fake_frame[fake_frame.label == label].iterrows():
            text = re.sub(r"\s+", " ", str(row.text)).strip()
            if str(index) in HF_TRANSLATIONS and str(index) not in used_hf and 35 <= len(text) <= 220:
                candidates.append({"id": str(index), "text": text, "label": int(label)})
        selected = ranked(candidates, purpose)[:count]
        if len(selected) != count:
            raise RuntimeError(f"HF_TRANSLATION_CACHE_SHORTFALL {purpose}={len(selected)}/{count}")
        for row in selected:
            used_hf.add(row["id"])
            text_zh = HF_TRANSLATIONS[row["id"]]
            risks = ["fake_review"] if label == 1 else ["normal_review"]
            if purpose.startswith("cal"):
                calibration.append(case("hf_fake_reviews_apache", row["id"], text_zh, risks, selected_for="calibration", original_label=f"label={label}", expression="implicit", difficulty="hard" if label else "medium", translated=True, label_source="external_mapped_candidate"))
            else:
                boundary_type = "implicit_or_paraphrase" if "implicit" in purpose else "lexical_mismatch"
                boundary.append(case("hf_fake_reviews_apache", row["id"], text_zh, risks, selected_for="boundary", original_label=f"label={label}", expression="implicit", difficulty="hard", boundary=boundary_type, translated=True, label_source="external_mapped_candidate"))
    return calibration, boundary


def build_expert_cases() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    calibration = [case("e_review_expert_designed", row_id, text, risks, selected_for="calibration", original_label=None, expression=expression, difficulty=difficulty, label_source="expert_designed") for row_id, text, risks, expression, difficulty in CAL_EXPERT]
    boundary = [case("e_review_expert_designed", row_id, text, risks, selected_for="boundary", original_label=None, expression=expression, difficulty="hard", boundary=boundary_type, label_source="expert_designed") for row_id, text, risks, boundary_type, expression in BOUNDARY_EXPERT]
    return calibration, boundary


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8", newline="\n")


def near(left: str, right: str) -> bool:
    return SequenceMatcher(None, normalize(left), normalize(right)).ratio() >= 0.9


def distributions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "sourceDistribution": dict(Counter(row["sourceDataset"] for row in rows)),
        "riskDistribution": dict(Counter(risk for row in rows for risk in row["riskTypes"])),
        "severityDistribution": dict(Counter(row["severity"] for row in rows)),
        "expressionDistribution": dict(Counter(row["expressionType"] for row in rows)),
        "difficultyDistribution": dict(Counter(row["difficulty"] for row in rows)),
        "boundaryDistribution": dict(Counter(row["boundaryType"] for row in rows if row["boundaryType"])),
        "multiRiskCount": sum(row["multiRisk"] for row in rows),
        "ambiguityCount": sum(row["ambiguity"] for row in rows),
        "nativeChineseCount": sum(row["translationStatus"] == "native" for row in rows),
        "translatedCount": sum(row["translationStatus"] == "translated" for row in rows),
        "businessAdaptedCount": sum(row["adaptationStatus"] == "business_adapted" for row in rows),
        "templateFamilyCount": len({row["templateFamily"] for row in rows}),
    }


def quality_report(calibration: list[dict[str, Any]], boundary: list[dict[str, Any]], frozen: list[dict[str, Any]]) -> dict[str, Any]:
    rows = calibration + boundary
    required = {"caseId", "textZh", "sourceDataset", "sourceRowId", "sourceLanguage", "translationStatus", "adaptationStatus", "riskTypes", "severity", "expressionType", "difficulty", "multiRisk", "ambiguity", "boundaryType", "labelSource", "sourceTier", "contentHash"}
    schema_errors = [row["caseId"] for row in rows if not required.issubset(row)]
    risk_errors = [row["caseId"] for row in rows if not set(row["riskTypes"]).issubset(RISK_TYPE_REGISTRY)]
    severity_errors = [row["caseId"] for row in rows if row["severity"] not in {"low", "medium", "high", "critical"}]
    texts = [row["textZh"] for row in rows]
    normalized = [normalize(text) for text in texts]
    exact_duplicates = len(texts) - len(set(texts))
    normalized_duplicates = len(normalized) - len(set(normalized))
    frozen_texts = [row["reviewText"] for row in frozen]
    frozen_normalized = {normalize(text) for text in frozen_texts}
    frozen_exact = sum(value in frozen_normalized for value in normalized)
    frozen_near = sum(any(near(row["textZh"], text) for text in frozen_texts) for row in rows)
    frozen_templates = {"family-" + sha(re.sub(r"\d+", "<n>", normalize(text)))[:16] for text in frozen_texts}
    frozen_template = sum(row["templateFamily"] in frozen_templates for row in rows)
    chinese = sum(len(re.findall(r"[\u4e00-\u9fff]", row["textZh"])) >= 4 for row in rows)
    boundary_expected = {"implicit_or_paraphrase": 15, "lexical_mismatch": 10, "hard_negative": 15, "multi_risk_or_conflict": 10, "ambiguous_context": 5, "noisy_or_adversarial": 5}
    boundary_actual = Counter(row["boundaryType"] for row in boundary)
    core_risks = {"normal_review", "negative_review", "after_sales_risk", "fake_review", "paid_review", "rating_manipulation", "review_suppression"}
    seen_risks = {risk for row in rows for risk in row["riskTypes"]}
    score_parts = {
        "riskTypeCoverage": round(15 * len(core_risks & seen_risks) / len(core_risks)),
        "severityCoverage": 10 if {"low", "medium", "high", "critical"}.issubset({row["severity"] for row in rows}) else 7,
        "explicitImplicit": 10 if {"explicit", "implicit", "mixed"}.issubset({row["expressionType"] for row in rows}) else 5,
        "hardNegativeCoverage": 10 if boundary_actual["hard_negative"] >= 15 else 5,
        "multiRiskCoverage": 5 if sum(row["multiRisk"] for row in rows) >= 10 else 3,
        "sourceDiversity": 10 if len({row["sourceDataset"] for row in rows}) >= 4 else 8,
        "templateDiversity": 5 if len(set(normalized)) / len(rows) >= 0.95 else 3,
        "frozenIsolation": 5 if frozen_exact == 0 and frozen_near == 0 else 0,
    }
    coverage_gaps = []
    if len({row["sourceDataset"] for row in rows}) < 4:
        coverage_gaps.append("Only three selected source families; broader external robustness is deferred.")
    if distributions(calibration)["riskDistribution"].get("paid_review", 0) < 15:
        coverage_gaps.append("Paid-review coverage is below the suggested 15 because no public Chinese incentive-labelled source was approved.")
    text_payload = "\n".join(row["textZh"] for row in rows)
    field_payload = " ".join(sorted({key for row in rows for key in row}))
    security_violations = []
    if re.search(r"(?i)(api[_-]?key|authorization|chain.of.thought|reviewer(identity|id|name))", field_payload):
        security_violations.append("forbidden_field")
    for pattern, name in (
        (r"(?i)[A-Z]:\\", "private_absolute_path"),
        (r"(?<!\d)1[3-9]\d{9}(?!\d)", "phone_number"),
        (r"(?<!\d)\d{17}[0-9Xx](?!\d)", "identity_number"),
    ):
        if re.search(pattern, text_payload):
            security_violations.append(name)
    license_approved = {row["sourceDataset"] for row in rows}.issubset(APPROVED_SOURCE_IDS)
    report = {
        "schemaValid": not schema_errors,
        "schemaErrors": schema_errors,
        "riskTypeValid": not risk_errors,
        "riskTypeErrors": risk_errors,
        "severityValid": not severity_errors,
        "severityErrors": severity_errors,
        "sourcePresent": all(row["sourceDataset"] and row["sourceRowId"] for row in rows),
        "licenseApproved": license_approved,
        "exactDuplicateCount": exact_duplicates,
        "normalizedDuplicateCount": normalized_duplicates,
        "nearDuplicateCount": sum(near(rows[left]["textZh"], rows[right]["textZh"]) for left in range(len(rows)) for right in range(left + 1, len(rows))),
        "frozenExactOverlap": frozen_exact,
        "frozenNearOverlap": frozen_near,
        "frozenTemplateOverlap": frozen_template,
        "chineseLanguageRatio": round(chinese / len(rows), 6),
        "textLength": {"min": min(map(len, (row["textZh"] for row in rows))), "max": max(map(len, (row["textZh"] for row in rows)))},
        "boundaryExpected": boundary_expected,
        "boundaryActual": dict(boundary_actual),
        "deterministicCompletenessScore": sum(score_parts.values()),
        "scoreParts": score_parts,
        "coverageGaps": coverage_gaps,
        "securityViolations": security_violations,
    }
    report["gates"] = {
        "SOURCE_LICENSE_GATE": "PASS" if license_approved else "FAIL",
        "SCHEMA_GATE": "PASS" if report["schemaValid"] and report["riskTypeValid"] and report["severityValid"] else "FAIL",
        "RISK_COVERAGE_GATE": "PASS" if core_risks.issubset(seen_risks) else "FAIL",
        "BOUNDARY_COVERAGE_GATE": "PASS" if dict(boundary_actual) == boundary_expected else "FAIL",
        "TEMPLATE_DIVERSITY_GATE": "PASS" if normalized_duplicates == 0 and report["nearDuplicateCount"] == 0 else "FAIL",
        "FROZEN_ISOLATION_GATE": "PASS" if frozen_exact == 0 and frozen_near == 0 else "FAIL",
        "SECURITY_GATE": "PASS" if not security_violations else "FAIL",
    }
    return report


def main() -> int:
    if hashlib.sha256(FROZEN.read_bytes()).hexdigest().upper() != FROZEN_SHA:
        raise SystemExit("FROZEN_GOLD_HASH_MISMATCH")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    public_cal, public_boundary = build_public_cases()
    expert_cal, expert_boundary = build_expert_cases()
    calibration = sorted(public_cal + expert_cal, key=lambda row: row["caseId"])
    boundary = sorted(public_boundary + expert_boundary, key=lambda row: row["caseId"])
    if len(calibration) != 120 or len(boundary) != 60:
        raise SystemExit(f"DATASET_COUNT_MISMATCH calibration={len(calibration)} boundary={len(boundary)}")
    frozen = load_jsonl(FROZEN)
    quality = quality_report(calibration, boundary, frozen)
    write_jsonl(OUTPUT / "router_calibration_candidate_demo_v1.jsonl", calibration)
    write_jsonl(OUTPUT / "boundary_challenge_demo_v1.jsonl", boundary)

    downloads = {row["sourceId"]: row for row in json.loads(DOWNLOAD_MANIFEST.read_text(encoding="utf-8"))["sources"]}
    selected = Counter(row["sourceDataset"] for row in calibration + boundary)
    source_registry = {
        "registryVersion": "source-registry-demo-v1",
        "sources": [
            {"sourceId": "asap_chinese_reviews", "datasetName": "ASAP Chinese Review Dataset", "sourceUrl": "https://github.com/Meituan-Dianping/ASAP", "publisher": "Meituan-Dianping dataset authors", "language": "zh", "license": "Apache-2.0", "citation": "Bu et al., NAACL 2021, doi:10.18653/v1/2021.naacl-main.167", "downloadMethod": "pinned GitHub archive", "selectedCount": selected["asap_chinese_reviews"], "contentHash": downloads["asap_chinese_reviews"]["contentHash"], "status": "APPROVED", "notes": "Used only for genuine normal/negative expression and hard negatives; not mapped to product-governance risk."},
            {"sourceId": "figshare_chinese_negative_reviews", "datasetName": "More than one million negative reviews from a Chinese e-commerce platform", "sourceUrl": "https://figshare.com/articles/dataset/11944947", "publisher": "Jichang Zhao", "language": "zh", "license": "CC BY 4.0", "citation": "Zhao, J. (2020), Figshare dataset 11944947", "downloadMethod": "Figshare file 24701156 with size and MD5 verification", "selectedCount": selected["figshare_chinese_negative_reviews"], "contentHash": downloads["figshare_chinese_negative_reviews"]["contentHash"], "status": "APPROVED", "notes": "Original anonymous userID is discarded; only review id/hash and selected text are retained."},
            {"sourceId": "hf_fake_reviews_apache", "datasetName": "Fake-Reviews-Dataset", "sourceUrl": "https://huggingface.co/datasets/theArijitDas/Fake-Reviews-Dataset", "publisher": "theArijitDas via Hugging Face", "language": "en", "license": "Apache-2.0", "citation": "Hugging Face dataset revision cffa887a877db747e540f15eb891f0d18070b994", "downloadMethod": "pinned revision parquet", "selectedCount": selected["hf_fake_reviews_apache"], "contentHash": downloads["hf_fake_reviews_apache"]["contentHash"], "status": "APPROVED", "notes": "Label 1 is computer-generated/deceptive; mapped only to fake_review candidate, never rating manipulation or paid review."},
            {"sourceId": "e_review_expert_designed", "datasetName": "E-Review business boundary supplement", "sourceUrl": "project://step21.2.2a", "publisher": "E-Review project", "language": "zh", "license": "project-owned", "citation": "Step 21.2.2A construction report", "downloadMethod": "version-controlled expert design", "selectedCount": selected["e_review_expert_designed"], "contentHash": sha(json.dumps(CAL_EXPERT + BOUNDARY_EXPERT, ensure_ascii=False)), "status": "APPROVED", "notes": "Candidate-only business boundaries; not human gold."},
            {"sourceId": "amazon_reviews_2023", "datasetName": "Amazon Reviews 2023", "sourceUrl": "https://amazon-reviews-2023.github.io/", "publisher": "McAuley Lab / UCSD", "language": "en", "license": "unclear", "citation": "Hou et al. 2024", "downloadMethod": "not downloaded", "selectedCount": 0, "contentHash": None, "status": "SKIPPED_LICENSE_UNCLEAR", "notes": "No review body used."},
        ],
    }
    (OUTPUT / "source_registry_demo_v1.json").write_text(json.dumps(source_registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    risk_rows = {code: {"label": item.label, "description": item.description, "severity": RiskSeverityEvaluator.registry()[code], "defaultAction": item.default_action, "evidenceTags": list(item.evidence_tags)} for code, item in sorted(RISK_TYPE_REGISTRY.items())}
    risk_snapshot = {"registryVersion": "risk-registry-snapshot-demo-v1", "severityRegistryVersion": RiskSeverityEvaluator.version, "risks": risk_rows, "contentHash": sha(json.dumps(risk_rows, ensure_ascii=False, sort_keys=True))}
    (OUTPUT / "risk_registry_snapshot.json").write_text(json.dumps(risk_snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sampling = []
    for row in calibration + boundary:
        sampling.append({"caseId": row["caseId"], "sourceDataset": row["sourceDataset"], "sourceRowId": row["sourceRowId"], "sourceRowHash": sha(f"{row['sourceDataset']}|{row['sourceRowId']}"), "originalLabel": row["externalLabel"], "samplingReason": row["boundaryType"] or "risk-and-source coverage", "selectedFor": "boundary" if row["boundaryType"] else "calibration", "fixedSeed": SEED})
    write_jsonl(OUTPUT / "sampling_manifest_demo_v1.jsonl", sorted(sampling, key=lambda row: row["caseId"]))
    ai_usage = {"translationCalls": 25, "boundaryGenerationCalls": 25, "calibrationBusinessDesignCalls": 30, "cacheHits": 25, "inputTokens": None, "outputTokens": None, "notes": "Translations and project-specific cases were curated once into a deterministic cache; token counts were not available. No runtime API or LLM judge was invoked."}
    (OUTPUT / "ai_usage_report_demo.json").write_text(json.dumps(ai_usage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "datasetVersion": "evaluation-dataset-demo-v1", "fixedSeed": SEED,
        "calibrationCount": len(calibration), "boundaryCount": len(boundary), "frozenCount": len(frozen),
        "frozenGoldSha256": FROZEN_SHA,
        "calibration": distributions(calibration), "boundary": distributions(boundary), "quality": quality,
        "datasetHashes": {
            "calibration": hashlib.sha256((OUTPUT / "router_calibration_candidate_demo_v1.jsonl").read_bytes()).hexdigest().upper(),
            "boundary": hashlib.sha256((OUTPUT / "boundary_challenge_demo_v1.jsonl").read_bytes()).hexdigest().upper(),
        },
    }
    all_pass = all(value == "PASS" for value in quality["gates"].values())
    manifest["gate"] = "PASS_WITH_COVERAGE_LIMITATION" if all_pass and quality["coverageGaps"] else "PASS" if all_pass else "FAIL"
    (OUTPUT / "dataset_manifest_demo_v1.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"calibration": len(calibration), "boundary": len(boundary), "quality": quality, "gate": manifest["gate"]}, ensure_ascii=False, indent=2))
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
