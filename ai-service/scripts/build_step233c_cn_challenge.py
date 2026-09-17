from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.policy_rag.index_store import load_policy_chunks
from scripts.run_step233a_qwen_embedding_ab import content_root_hash


DATASET_VERSION = "step23.3c-cn-ranking-challenge-v1"
DEFAULT_OUTPUT = ROOT / "data" / "benchmarks" / "step233c_cn_ranking_challenge_v1.jsonl"
DEFAULT_MANIFEST = ROOT / "data" / "benchmarks" / "step233c_cn_ranking_challenge_v1.manifest.json"
DEFAULT_CHUNKS = ROOT / "data" / "policy_rag_real" / "index" / "policy_chunks.jsonl"
OLD_FROZEN_GOLD = ROOT / "data" / "benchmarks" / "review_governance_gold_v1.jsonl"


RISK_TAGS: dict[str, list[str]] = {
    "fake_review": ["fake_engagement", "fake_review"],
    "rating_manipulation": ["incentivized_review", "rating_manipulation"],
    "review_suppression": ["review_suppression"],
    "privacy_risk": ["privacy"],
    "after_sales_risk": ["after_sales", "after_sales_risk"],
    "safety_or_fraud_risk": ["safety_or_fraud", "safety_or_fraud_risk"],
    "harassment_or_abuse": ["harassment_or_abuse"],
    "normal_review": [],
}


# These qrels are policy-clause judgments made before running any retrieval
# candidate. Relevance 3 is a direct primary-policy match, 2 supports a
# secondary risk or is another direct authority, and 1 is useful context.
POLICY_PROFILES: dict[str, list[dict[str, Any]]] = {
    "fake_fabricated": [
        {"chunkId": "9c3dc9939e5eb8879caf3c5c", "relevance": 3, "supports": ["fake_review"]},
        {"chunkId": "b9a74381a55c2e2a5d531eee", "relevance": 3, "supports": ["fake_review"]},
        {"chunkId": "ff0598d26200a4e201663451", "relevance": 2, "supports": ["fake_review"]},
    ],
    "rating_incentive": [
        {"chunkId": "193384aae5a85267bb71d5a2", "relevance": 3, "supports": ["rating_manipulation"]},
        {"chunkId": "d75980ec05a8bcb347f5bf52", "relevance": 3, "supports": ["rating_manipulation"]},
        {"chunkId": "74340d2418d9fcfa599e41da", "relevance": 2, "supports": ["rating_manipulation", "fake_review"]},
    ],
    "suppression_delete": [
        {"chunkId": "2bee6c98575e591210bf2067", "relevance": 3, "supports": ["review_suppression"]},
        {"chunkId": "ce069bb67cc3b294d6e7cf93", "relevance": 2, "supports": ["review_suppression"]},
        {"chunkId": "1b44f5da1082d2e258a9b675", "relevance": 1, "supports": ["review_suppression", "harassment_or_abuse"]},
    ],
    "suppression_threat": [
        {"chunkId": "1b44f5da1082d2e258a9b675", "relevance": 3, "supports": ["review_suppression", "harassment_or_abuse"]},
        {"chunkId": "2bee6c98575e591210bf2067", "relevance": 2, "supports": ["review_suppression"]},
        {"chunkId": "ce069bb67cc3b294d6e7cf93", "relevance": 1, "supports": ["review_suppression"]},
    ],
    "privacy_personal": [
        {"chunkId": "e66578cf821a0e47b9e962ca", "relevance": 3, "supports": ["privacy_risk"]},
        {"chunkId": "f7c63a5ca6444c3d8bf2766b", "relevance": 2, "supports": ["privacy_risk", "review_suppression"]},
        {"chunkId": "f9d2febf1911851cc59297b2", "relevance": 1, "supports": ["privacy_risk"]},
    ],
    "after_sales_records": [
        {"chunkId": "31b38d83c374476950d9bf66", "relevance": 3, "supports": ["after_sales_risk"]},
        {"chunkId": "a5d7486b9d28abc732aa76d1", "relevance": 2, "supports": ["after_sales_risk"]},
        {"chunkId": "93326e9355a42652819655e3", "relevance": 2, "supports": ["after_sales_risk"]},
    ],
    "safety_product": [
        {"chunkId": "eeecfa148cfe1159d4a3498f", "relevance": 3, "supports": ["safety_or_fraud_risk"]},
        {"chunkId": "80f9b79fe54394c78c211e9c", "relevance": 3, "supports": ["safety_or_fraud_risk"]},
        {"chunkId": "25b39504f13e488f3e5ae074", "relevance": 2, "supports": ["safety_or_fraud_risk"]},
    ],
    "harassment_general": [
        {"chunkId": "a120af91026adec4e2a4e419", "relevance": 3, "supports": ["harassment_or_abuse"]},
        {"chunkId": "707d8b182fcab0cc98e0d706", "relevance": 2, "supports": ["harassment_or_abuse", "safety_or_fraud_risk"]},
    ],
    "harassment_threat": [
        {"chunkId": "707d8b182fcab0cc98e0d706", "relevance": 3, "supports": ["harassment_or_abuse", "safety_or_fraud_risk"]},
        {"chunkId": "1b44f5da1082d2e258a9b675", "relevance": 2, "supports": ["harassment_or_abuse", "review_suppression"]},
        {"chunkId": "a120af91026adec4e2a4e419", "relevance": 2, "supports": ["harassment_or_abuse"]},
    ],
}


def _spec(
    text: str,
    primary: str,
    secondary: tuple[str, ...] = (),
    profile: str = "",
    rating: int | None = None,
) -> tuple[str, str, tuple[str, ...], str, int | None]:
    return text, primary, secondary, profile, rating


MULTI_RISK = [
    _spec("群里接单的人没买过商品，按商家给的模板晒五星截图就能领三十元。", "fake_review", ("rating_manipulation",), "fake_fabricated", 5),
    _spec("我根本没有下单，客服却让我复制这段好评并打满分，完成后给话费。", "fake_review", ("rating_manipulation",), "fake_fabricated", 5),
    _spec("商家组织员工冒充顾客发布体验，还要求统一给五星提高店铺分数。", "fake_review", ("rating_manipulation",), "fake_fabricated", 5),
    _spec("所谓试用员连货都没收到，只要照着文案评价并提交满星截图就结算。", "fake_review", ("rating_manipulation",), "fake_fabricated", 5),
    _spec("工作室批量养号写购买心得，店铺按每条五星评价支付报酬。", "fake_review", ("rating_manipulation",), "fake_fabricated", 5),
    _spec("空包签收后让我假装使用一个月再写好评，五星另加十元。", "fake_review", ("rating_manipulation",), "fake_fabricated", 5),
    _spec("客服让我借家人的账号写不存在的购买经历，还指定必须全部满分。", "fake_review", ("rating_manipulation",), "fake_fabricated", 5),
    _spec("商家发来十个账号和统一话术，要我们伪装成不同买家集中打五星。", "fake_review", ("rating_manipulation",), "fake_fabricated", 5),
    _spec("东西确实买了，但客服说只有改成五星并截图才能拿到返现。", "rating_manipulation", ("fake_review",), "rating_incentive", 5),
    _spec("包裹里塞卡片，要求先给满分再扫码领红包，低于五星没有奖励。", "rating_manipulation", ("fake_review",), "rating_incentive", 5),
    _spec("售后答应补发，条件是把两星改成五星并发截图证明。", "rating_manipulation", ("fake_review",), "rating_incentive", 5),
    _spec("商家说评价内容随便写，但星级必须点满才返还运费。", "rating_manipulation", ("fake_review",), "rating_incentive", 5),
    _spec("真实买过也不能这样吧，客服用赠品换指定五星和夸奖文案。", "rating_manipulation", ("fake_review",), "rating_incentive", 5),
    _spec("退款本来就该处理，却被要求先撤掉差评再重新打五颗星。", "rating_manipulation", ("fake_review", "review_suppression"), "rating_incentive", 5),
    _spec("群公告写着每晒一张五星图返二十元，还让大家不要提奖励。", "rating_manipulation", ("fake_review",), "rating_incentive", 5),
    _spec("客服说我不删评价就天天打电话骚扰，还要到单位找我。", "harassment_or_abuse", ("review_suppression",), "harassment_threat", 2),
    _spec("商家威胁不撤差评就公开骂我，并发动员工轮番发消息。", "harassment_or_abuse", ("review_suppression",), "harassment_threat", 1),
    _spec("我拒绝改评价后，对方说会堵在家门口，直到我把内容删掉。", "harassment_or_abuse", ("review_suppression",), "harassment_threat", 1),
    _spec("店员连续辱骂我，还说不把一星改掉就让我以后别想安生。", "harassment_or_abuse", ("review_suppression",), "harassment_threat", 1),
    _spec("因为没同意撤评，客服发来人身威胁并煽动群友围攻我。", "harassment_or_abuse", ("review_suppression",), "harassment_threat", 1),
    _spec("平台直接隐藏我的真实差评，商家随后还发消息嘲讽我不识相。", "review_suppression", ("harassment_or_abuse",), "suppression_delete", 1),
    _spec("评价刚发布就被删除，客服还辱骂我故意找事。", "review_suppression", ("harassment_or_abuse",), "suppression_delete", 1),
    _spec("商家反复举报让差评消失，同时用难听的话逼我闭嘴。", "review_suppression", ("harassment_or_abuse",), "suppression_delete", 1),
    _spec("只展示好评并屏蔽低分，店员还在私信里攻击给差评的人。", "review_suppression", ("harassment_or_abuse",), "suppression_delete", 1),
    _spec("商家说不删差评就把我的手机号和地址发到群里。", "privacy_risk", ("review_suppression", "harassment_or_abuse"), "privacy_personal", 1),
    _spec("我不肯撤评后，客服把订单姓名、电话截图公开在评论区。", "privacy_risk", ("review_suppression",), "privacy_personal", 1),
    _spec("店铺用曝光家庭住址威胁我修改评价，这已经不是正常协商。", "privacy_risk", ("review_suppression", "harassment_or_abuse"), "privacy_personal", 1),
    _spec("充电器冒烟差点起火，商家却拒绝退货并让我继续使用。", "safety_or_fraud_risk", ("after_sales_risk",), "safety_product", 1),
    _spec("收到疑似假药后身体不适，平台不核验资质也不给退款。", "safety_or_fraud_risk", ("after_sales_risk",), "safety_product", 1),
    _spec("儿童玩具掉出尖锐零件，售后只肯补券不肯召回或退货。", "safety_or_fraud_risk", ("after_sales_risk",), "safety_product", 1),
    _spec("燃气配件漏气，店铺明知有问题仍拒绝退换并继续销售。", "safety_or_fraud_risk", ("after_sales_risk",), "safety_product", 1),
    _spec("破损商品申请退货一直被拖延，后来我的售后评价也被商家删了。", "after_sales_risk", ("review_suppression",), "after_sales_records", 2),
    _spec("退款记录莫名消失，写出的售后差评也一直无法展示。", "after_sales_risk", ("review_suppression",), "after_sales_records", 2),
    _spec("店铺盗用我的头像和姓名编造购买好评，还暴露了账号信息。", "fake_review", ("privacy_risk",), "fake_fabricated", 5),
    _spec("我没买过这件商品，商家却拿我的资料注册账号发布五星评价。", "fake_review", ("privacy_risk", "rating_manipulation"), "fake_fabricated", 5),
]


IMPLICIT = [
    _spec("一屋子手机轮流下单又取消，评价区却整齐地夸同一句话。", "fake_review", profile="fake_fabricated"),
    _spec("这些买家秀连标点都一样，看着像从同一张表里复制出来的。", "fake_review", profile="fake_fabricated"),
    _spec("没见过实物也能写使用感受，照群主的话发完就领任务费。", "fake_review", profile="fake_fabricated"),
    _spec("今天刚上架，几分钟内突然冒出上百条一模一样的体验心得。", "fake_review", profile="fake_fabricated"),
    _spec("朋友让我帮店里撑场面，说不用买，写得像真的用过就行。", "fake_review", profile="fake_fabricated"),
    _spec("小卡片没明说好评，但只有点亮全部星星才能扫出红包。", "rating_manipulation", profile="rating_incentive", rating=5),
    _spec("客服问我愿不愿意把星星补齐，补齐后运费原路退回。", "rating_manipulation", profile="rating_incentive", rating=5),
    _spec("赠品写着评价达标后发放，所谓达标就是页面全部点满。", "rating_manipulation", profile="rating_incentive", rating=5),
    _spec("本来给了三星，对方暗示改到最高档就能优先处理售后。", "rating_manipulation", profile="rating_incentive", rating=3),
    _spec("钱不是白送的，要先把评分拉满并把截图交给群管理员。", "rating_manipulation", profile="rating_incentive", rating=5),
    _spec("我的低分像从来没存在过，列表里只剩一片夸赞。", "review_suppression", profile="suppression_delete", rating=1),
    _spec("每次提交不满意的内容都显示审核中，换成表扬立刻出现。", "review_suppression", profile="suppression_delete", rating=2),
    _spec("客服反复劝我把那段经历收回，否则售后就一直排队。", "review_suppression", profile="suppression_threat", rating=2),
    _spec("页面说按规则过滤，可奇怪的是消失的全是低分体验。", "review_suppression", profile="suppression_delete", rating=1),
    _spec("问题解决不了，对方只关心怎样让我的评价看不见。", "review_suppression", profile="suppression_delete", rating=1),
    _spec("刚咨询完，陌生营销电话就准确说出了我的订单和住址。", "privacy_risk", profile="privacy_personal"),
    _spec("评论回复里出现了我的完整号码，这些信息不该被公开。", "privacy_risk", profile="privacy_personal"),
    _spec("店家把我就诊时填写的资料拿来证明我说谎，还发给旁人。", "privacy_risk", profile="privacy_personal"),
    _spec("订单截图未经遮挡就被贴出来，姓名和收货地点都能看清。", "privacy_risk", profile="privacy_personal"),
    _spec("退回去半个月了，页面里找不到任何退货处理记录。", "after_sales_risk", profile="after_sales_records", rating=2),
    _spec("直播间买完才发现没有售后入口，经营主体也查不到。", "after_sales_risk", profile="after_sales_records", rating=2),
    _spec("补发、退款、签收几个状态互相矛盾，客服也不给处理凭据。", "after_sales_risk", profile="after_sales_records", rating=2),
    _spec("申请退换后一直踢皮球，连之前的沟通记录都无法查询。", "after_sales_risk", profile="after_sales_records", rating=1),
    _spec("插上电源外壳就发烫并有焦味，这东西不敢再用了。", "safety_or_fraud_risk", profile="safety_product", rating=1),
    _spec("页面宣传是正品，收到后防伪码却已被多次查询。", "safety_or_fraud_risk", profile="safety_product", rating=1),
    _spec("给孩子用后出现割伤，边缘和宣传图完全不是一回事。", "safety_or_fraud_risk", profile="safety_product", rating=1),
    _spec("付款后被引导到陌生账户再次转账，不转就不给发货。", "safety_or_fraud_risk", profile="safety_product", rating=1),
    _spec("客服从早到晚换号来骂人，我拉黑一个又来一个。", "harassment_or_abuse", profile="harassment_general", rating=1),
    _spec("只是反馈问题，对方却持续发送侮辱性语音攻击我。", "harassment_or_abuse", profile="harassment_general", rating=1),
    _spec("店员扬言会找到我当面算账，这让我担心人身安全。", "harassment_or_abuse", profile="harassment_threat", rating=1),
]


HARD_NEGATIVE = [
    _spec("不是返现的问题，商家真正做的是把我的手机号公开给陌生人。", "privacy_risk", profile="privacy_personal", rating=2),
    _spec("没有要求我删差评，但客服未经同意展示了完整收货地址。", "privacy_risk", profile="privacy_personal", rating=2),
    _spec("我不怀疑是假货，只是订单里的身份证照片被店铺发到了群里。", "privacy_risk", profile="privacy_personal", rating=2),
    _spec("没人逼我打五星，实际问题是退货签收后两个月还没有退款记录。", "after_sales_risk", profile="after_sales_records", rating=2),
    _spec("这不是刷单，商品破损寄回后平台一直查不到售后进度。", "after_sales_risk", profile="after_sales_records", rating=1),
    _spec("评价没有被删除，但直播店铺根本没提供可联系的售后主体。", "after_sales_risk", profile="after_sales_records", rating=2),
    _spec("不是普通差评纠纷，电池已经鼓包漏液，继续使用可能出事。", "safety_or_fraud_risk", profile="safety_product", rating=1),
    _spec("客服没有骂人，可这个插座通电就冒火花，存在明显安全问题。", "safety_or_fraud_risk", profile="safety_product", rating=1),
    _spec("并非为了退款找借口，检测报告显示商品材料含有禁用成分。", "safety_or_fraud_risk", profile="safety_product", rating=1),
    _spec("商家给了补偿，但仍把所有两星以下的真实评价从页面移除。", "review_suppression", profile="suppression_delete", rating=1),
    _spec("没人威胁我，问题是低分内容提交后始终不展示而好评立即通过。", "review_suppression", profile="suppression_delete", rating=2),
    _spec("不是售后没处理，而是处理完就要求平台把我的原评价删除。", "review_suppression", profile="suppression_delete", rating=2),
    _spec("没有现金奖励，但这些账号从未购买却同时发布相同的使用经历。", "fake_review", profile="fake_fabricated", rating=5),
    _spec("评分不全是五星，可评论者根本不存在，头像和文字都是批量生成的。", "fake_review", profile="fake_fabricated", rating=4),
    _spec("不涉及删差评，店员只是用多个空账号编造长期使用感受。", "fake_review", profile="fake_fabricated", rating=5),
    _spec("评价还在，客服却连续七天用不同号码发送侮辱和恐吓信息。", "harassment_or_abuse", profile="harassment_threat", rating=1),
    _spec("隐私没有泄露，但商家扬言要让我和家人付出代价。", "harassment_or_abuse", profile="harassment_threat", rating=1),
    _spec("商品并非假货，可包裹卡片明确写着五星截图才返十元。", "rating_manipulation", profile="rating_incentive", rating=5),
    _spec("没有删除任何评价，但客服用免单交换把两星改成满星。", "rating_manipulation", profile="rating_incentive", rating=5),
    _spec("我确实买过，不是假体验，不过店铺要求指定夸奖内容才能领赠品。", "rating_manipulation", profile="rating_incentive", rating=5),
]


NORMAL = [
    _spec("物流按时送达，包装完整，使用后与页面描述一致。", "normal_review", rating=5),
    _spec("尺寸正合适，颜色没有色差，日常使用很方便。", "normal_review", rating=5),
    _spec("试用了三天，功能稳定，没有遇到明显问题。", "normal_review", rating=4),
    _spec("味道偏淡但可以接受，个人口味不同，不影响正常使用。", "normal_review", rating=3),
    _spec("快递比预计晚一天，商品本身完好，客服也及时说明了。", "normal_review", rating=4),
    _spec("面料手感不错，洗过一次没有缩水，整体满意。", "normal_review", rating=5),
    _spec("安装步骤清楚，配件数量齐全，半小时就装好了。", "normal_review", rating=5),
    _spec("容量和标注相符，外观简洁，暂时没有发现异常。", "normal_review", rating=4),
    _spec("价格活动后比较合适，收到的款式也是我选择的。", "normal_review", rating=4),
    _spec("客服回答很耐心，换尺码也顺利完成，体验正常。", "normal_review", rating=4),
    _spec("声音比想象中大一点，但参数页面已经写明，可以接受。", "normal_review", rating=3),
    _spec("给家里人买的，操作简单，老人也能看懂说明。", "normal_review", rating=5),
    _spec("第二次购买，批次之间没有明显差异，质量比较稳定。", "normal_review", rating=5),
    _spec("实物颜色稍深，退换流程正常，商家当天就处理了。", "normal_review", rating=3),
    _spec("包装有轻微压痕，里面的商品没有受损，不影响使用。", "normal_review", rating=4),
]


LONG_NOISY = [
    _spec("先说商品本身，外盒普通，说明书也一般；重点是包裹里那张卡反复写满星、满星、满星，只有拍下五颗星页面并上传截图才能领二十五元，我问能不能如实给三星，客服说那就没有任何返还。", "rating_manipulation", profile="rating_incentive", rating=3),
    _spec("前面几次沟通都在说物流，我也等了很久，后来才发现评论区同一天出现大量相同句子，头像不同但错别字、标点、照片顺序全一样，还有人承认没收到货只是按群任务发内容。", "fake_review", profile="fake_fabricated", rating=2),
    _spec("事情有点长：商品退回、仓库签收、客服说登记、平台说等待，我把每次时间都记下来了，可一个月后退换货和沟通记录都查不到，钱也没有回来，三个客服给出三种互相矛盾的说法。", "after_sales_risk", profile="after_sales_records", rating=1),
    _spec("我原本只想提醒尺寸问题，没有要求赔偿，结果低分内容一次次卡在审核，改成夸赞马上显示，再换回真实描述又消失，页面始终只留下高分，看起来不是普通审核延迟。", "review_suppression", profile="suppression_delete", rating=2),
    _spec("收到后先充了十分钟，机身越来越烫，随后有焦味和轻微烟雾，我立即断电；店铺却让我继续充一晚试试，还拒绝登记安全问题，这种处理让我不敢再碰设备。", "safety_or_fraud_risk", profile="safety_product", rating=1),
    _spec("电话号码我只在订单里填写过，评价发布后商家为了反驳我，直接把姓名、号码、楼栋和门牌截图贴在公开回复，虽然很快删掉，但已经有人据此联系我。", "privacy_risk", profile="privacy_personal", rating=1),
    _spec("从早上到晚上，客服先是说我不懂产品，后来开始辱骂，再后来换号码发语音，说知道我在哪里上班并会来找我，我已经明确要求停止联系，对方仍持续发送。", "harassment_or_abuse", profile="harassment_threat", rating=1),
    _spec("店铺先让我撤掉两星，说撤掉就退款；我没有同意，对方又说会找平台处理，之后评价真的无法查看，同时每天发消息讽刺和施压，问题从售后变成了压制真实反馈。", "review_suppression", ("harassment_or_abuse", "after_sales_risk"), "suppression_threat", 2),
    _spec("我核对过订单，确实从未购买这款产品，可店铺页面出现一个用我头像和昵称发布的长期体验，内容还给了满星，客服承认资料来自以前的咨询记录。", "privacy_risk", ("fake_review", "rating_manipulation"), "privacy_personal", 5),
    _spec("字可能打得有点乱：充电时壳子烫、烫、还有糊味，线头也露铜，问退或换一直没人接，后来只回一句正常现象；这不只是体验不好，我担心继续用会触电。", "safety_or_fraud_risk", ("after_sales_risk",), "safety_product", 1),
]


BOUNDARY = [
    _spec("客服没直接说必须五星，只说把星星补齐会有一份小礼物。", "rating_manipulation", profile="rating_incentive", rating=4),
    _spec("朋友让我替他的店写几句体验，我没有下单，也没拿钱。", "fake_review", profile="fake_fabricated"),
    _spec("商家说评价写得太真实会影响生意，希望我先隐藏几天再谈退款。", "review_suppression", ("after_sales_risk",), "suppression_delete", 2),
    _spec("客服在公开回复里只露出了手机号后四位和小区名称，我仍担心被识别。", "privacy_risk", profile="privacy_personal", rating=2),
    _spec("插头偶尔发热但还没冒烟，商家没有提供检测说明，只让我放心使用。", "safety_or_fraud_risk", profile="safety_product", rating=2),
    _spec("对方说会让同行都知道我是麻烦顾客，没有直接说要伤害我。", "harassment_or_abuse", profile="harassment_general", rating=1),
    _spec("退货已签收，平台状态停在处理中十天，暂时没有给出原因。", "after_sales_risk", profile="after_sales_records", rating=2),
    _spec("一批评价都很相似，也可能是大家用了店铺提供的参考句子。", "fake_review", profile="fake_fabricated", rating=5),
    _spec("商家同意补差价，但建议我把原来的一星改得好看一些。", "rating_manipulation", profile="rating_incentive", rating=1),
    _spec("评价页面偶尔看不到低分，刷新后又出现，不确定是系统延迟还是被限制。", "review_suppression", profile="suppression_delete", rating=2),
]


SLICE_CASES = {
    "multi_risk_precedence": MULTI_RISK,
    "implicit_colloquial": IMPLICIT,
    "hard_negative": HARD_NEGATIVE,
    "normal_easy": NORMAL,
    "long_noisy": LONG_NOISY,
    "boundary_ambiguous": BOUNDARY,
}


def build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    sequence = 0
    for slice_name, specs in SLICE_CASES.items():
        for local_index, (text, primary, secondary, profile, rating) in enumerate(specs, start=1):
            sequence += 1
            risk_types = [primary, *secondary]
            qrels = build_qrels(primary, secondary, profile) if primary != "normal_review" else []
            high_risk = any(risk not in {"normal_review", "after_sales_risk"} for risk in risk_types)
            expected_decision = "auto_pass" if primary == "normal_review" else "human_review" if high_risk else "suggest_action"
            expected_tags = sorted({tag for risk in risk_types for tag in RISK_TAGS[risk]})
            cases.append(
                {
                    "caseId": f"cn-{sequence:03d}",
                    "datasetVersion": DATASET_VERSION,
                    "language": "zh",
                    "slice": slice_name,
                    "sliceIndex": local_index,
                    "reviewText": text,
                    "rating": rating,
                    "ratingSource": "USER_PROVIDED" if rating is not None else "UNKNOWN",
                    "riskTypes": risk_types,
                    "primaryRiskType": primary,
                    "secondaryRiskTypes": list(secondary),
                    "expectedRiskTypes": risk_types,
                    "expectedEvidenceTags": expected_tags,
                    "expectedRoute": "low_touch" if primary == "normal_review" else "governance_required",
                    "expectedDecision": expected_decision,
                    "expectedEvidenceStatus": "supported",
                    "requiresHumanReview": bool(primary != "normal_review" and high_risk),
                    "policyProfile": profile or None,
                    "policyRelevance": qrels,
                    "annotationBasis": "预先定义的业务主风险与真实政策条款相关性，未使用候选模型输出。",
                }
            )
    return cases


def build_qrels(primary: str, secondary: tuple[str, ...], profile: str) -> list[dict[str, Any]]:
    if profile not in POLICY_PROFILES:
        raise ValueError(f"UNKNOWN_POLICY_PROFILE:{profile}")
    merged: dict[str, dict[str, Any]] = {}
    for row in POLICY_PROFILES[profile]:
        merged[row["chunkId"]] = {**row, "judgment": "primary_policy" if row["relevance"] == 3 else "supporting_policy"}
    for risk in secondary:
        secondary_profile = default_profile(risk)
        for row in POLICY_PROFILES[secondary_profile]:
            relevance = min(2, int(row["relevance"]))
            current = merged.get(row["chunkId"])
            candidate = {
                "chunkId": row["chunkId"],
                "relevance": relevance,
                "supports": sorted(set(row["supports"]) | {risk}),
                "judgment": "secondary_policy",
            }
            if current is None:
                merged[row["chunkId"]] = candidate
            else:
                current["supports"] = sorted(set(current["supports"]) | set(candidate["supports"]))
                if candidate["relevance"] > current["relevance"]:
                    current["relevance"] = candidate["relevance"]
    return sorted(merged.values(), key=lambda item: (-item["relevance"], item["chunkId"]))


def default_profile(risk: str) -> str:
    return {
        "fake_review": "fake_fabricated",
        "rating_manipulation": "rating_incentive",
        "review_suppression": "suppression_delete",
        "privacy_risk": "privacy_personal",
        "after_sales_risk": "after_sales_records",
        "safety_or_fraud_risk": "safety_product",
        "harassment_or_abuse": "harassment_general",
    }[risk]


def validate_cases(cases: list[dict[str, Any]], chunks_path: Path, old_gold_path: Path = OLD_FROZEN_GOLD) -> dict[str, Any]:
    if len(cases) != 120:
        raise ValueError(f"CASE_COUNT_MISMATCH:{len(cases)}")
    expected_slices = {name: len(rows) for name, rows in SLICE_CASES.items()}
    observed_slices = Counter(case["slice"] for case in cases)
    if dict(observed_slices) != expected_slices:
        raise ValueError(f"SLICE_COUNT_MISMATCH:{dict(observed_slices)}")
    ids = [case["caseId"] for case in cases]
    texts = [normalize_text(case["reviewText"]) for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("DUPLICATE_CASE_ID")
    if len(texts) != len(set(texts)):
        raise ValueError("DUPLICATE_REVIEW_TEXT")
    for case in cases:
        text = case["reviewText"]
        if not re.search(r"[\u4e00-\u9fff]", text) or re.search(r"[A-Za-z]", text):
            raise ValueError(f"NON_CHINESE_CASE:{case['caseId']}")
        if case["riskTypes"][0] != case["primaryRiskType"]:
            raise ValueError(f"PRIMARY_RISK_ORDER_INVALID:{case['caseId']}")
        if case["secondaryRiskTypes"] != case["riskTypes"][1:]:
            raise ValueError(f"SECONDARY_RISK_MISMATCH:{case['caseId']}")
        qrels = case["policyRelevance"]
        if case["primaryRiskType"] == "normal_review":
            if qrels:
                raise ValueError(f"NORMAL_CASE_HAS_QRELS:{case['caseId']}")
        elif not any(row["relevance"] == 3 and case["primaryRiskType"] in row["supports"] for row in qrels):
            raise ValueError(f"PRIMARY_QREL_MISSING:{case['caseId']}")
    old_texts = load_old_texts(old_gold_path)
    overlap = sorted(set(texts).intersection(old_texts))
    if overlap:
        raise ValueError(f"OLD_GOLD_TEXT_OVERLAP:{len(overlap)}")
    chunks = load_policy_chunks(chunks_path)
    chunk_ids = {chunk.chunkId for chunk in chunks}
    referenced = {row["chunkId"] for case in cases for row in case["policyRelevance"]}
    missing = sorted(referenced - chunk_ids)
    if missing:
        raise ValueError("QREL_CHUNK_MISSING:" + ",".join(missing))
    ranking_count = sum(bool(case["policyRelevance"]) for case in cases)
    if ranking_count != 105:
        raise ValueError(f"RANKING_CASE_COUNT_MISMATCH:{ranking_count}")
    return {
        "caseCount": len(cases),
        "rankingCaseCount": ranking_count,
        "normalCaseCount": len(cases) - ranking_count,
        "sliceCounts": dict(observed_slices),
        "uniquePolicyChunkCount": len(referenced),
        "oldGoldExactOverlapCount": 0,
        "allChinese": True,
        "contentRootHash": content_root_hash(chunks),
    }


def write_dataset(cases: list[dict[str, Any]], output: Path) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(case, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for case in cases)
    output.write_text(payload, encoding="utf-8", newline="\n")
    return sha256_file(output)


def build_manifest(dataset: Path, sha256: str, validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "step23.3c-challenge-manifest-v1",
        "datasetVersion": DATASET_VERSION,
        "status": "FROZEN",
        "datasetPath": dataset.name,
        "sha256": sha256,
        "language": "zh",
        "construction": {
            "method": "project-authored controlled Chinese challenge cases",
            "labelsAssignedBeforeCandidateExecution": True,
            "candidateOutputsUsedForLabels": False,
            "productionTraffic": False,
        },
        "validation": validation,
        "comparedVariants": {
            "v1": "active Qwen legacy embedding plus current hybrid RRF",
            "B0": "Qwen official retrieval v2 plus current hybrid RRF",
            "B2": "B0 candidates plus local BGE reranker over Top-5",
        },
        "metricDefinitions": {
            "primaryPolicyAccuracyAt1": "Top-1 chunk has graded relevance 3 for the primary risk.",
            "ndcgAt3": "Graded policy relevance 0-3 over the three citations consumed by workflow.",
            "multiRiskCoverageAt3": "For multi-risk cases, Top-3 qrels jointly support every annotated risk type.",
            "candidateRecallAt5": "At least one relevance-3 primary-policy chunk appears in Top-5.",
            "reflectionAccuracy": "Deterministic Reflection output equals expectedEvidenceStatus using annotated risks and Top-3 citations.",
            "decisionAccuracy": "Governance decision derived from annotated risk severity and Reflection equals expectedDecision.",
            "highRiskPrimaryOmissionCount": "High-risk cases without a relevance-3 primary-policy chunk in Top-3.",
        },
        "promotionGate": {
            "candidate": "B2",
            "rules": [
                "B2 primaryPolicyAccuracyAt1 >= v1",
                "B2 ndcgAt3 >= v1",
                "B2 multiRiskCoverageAt3 >= v1",
                "B2 candidateRecallAt5 >= v1",
                "B2 reflectionAccuracy >= v1",
                "B2 decisionAccuracy >= v1",
                "B2 highRiskPrimaryOmissionCount = 0",
                "B2 citationValidity = 1.0",
                "B2 multi_risk_precedence primaryPolicyAccuracyAt1 >= v1",
            ],
        },
    }


def load_old_texts(path: Path) -> set[str]:
    if not path.exists():
        return set()
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    return {normalize_text(str(row.get("reviewText") or "")) for row in rows}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text).strip()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and freeze the independent Chinese Step 23.3C ranking challenge.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--chunks", type=Path, default=DEFAULT_CHUNKS)
    args = parser.parse_args()

    cases = build_cases()
    validation = validate_cases(cases, args.chunks.resolve())
    sha256 = write_dataset(cases, args.output.resolve())
    manifest = build_manifest(args.output.resolve(), sha256, validation)
    args.manifest.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.manifest.resolve().write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"dataset": str(args.output.resolve()), "sha256": sha256, **validation}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
