from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "ppt_assets" / "diagrams"
OUT.mkdir(parents=True, exist_ok=True)


def font(size=28, bold=False):
    candidates = [
        Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for item in candidates:
        if item.exists():
            return ImageFont.truetype(str(item), size)
    return ImageFont.load_default()


F_TITLE = font(42, True)
F_H = font(27, True)
F = font(22)
F_S = font(18)


def wrap(text, width):
    lines, line = [], ""
    for ch in text:
        if len(line) >= width and ch in " /->，。；、":
            lines.append(line.strip())
            line = ""
        line += ch
    if line:
        lines.append(line.strip())
    return lines


def box(draw, xy, title, body, fill, outline="#CBD5E1"):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=18, fill=fill, outline=outline, width=2)
    draw.text((x1 + 22, y1 + 18), title, fill="#0F172A", font=F_H)
    y = y1 + 58
    for line in wrap(body, 21):
        draw.text((x1 + 22, y), line, fill="#334155", font=F_S)
        y += 25


def arrow(draw, start, end, color="#2563EB"):
    draw.line([start, end], fill=color, width=5)
    ex, ey = end
    sx, sy = start
    if ex >= sx:
        pts = [(ex, ey), (ex - 16, ey - 9), (ex - 16, ey + 9)]
    else:
        pts = [(ex, ey), (ex + 16, ey - 9), (ex + 16, ey + 9)]
    draw.polygon(pts, fill=color)


def canvas(title):
    img = Image.new("RGB", (1600, 900), "#F8FAFC")
    d = ImageDraw.Draw(img)
    d.text((70, 48), title, fill="#0F172A", font=F_TITLE)
    d.line([(70, 110), (1530, 110)], fill="#CBD5E1", width=2)
    return img, d


def architecture():
    img, d = canvas("E-Review Agent 总体架构")
    box(d, (80, 170, 420, 330), "H5 用户端", "浏览商品 / 演示支付 / 确认收货 / 发布图文评价", "#DBEAFE")
    box(d, (80, 410, 420, 570), "后台管理端", "AI 工作台 / 风险中心 / 运营处理 / Agent 观测", "#E0E7FF")
    box(d, (520, 170, 860, 330), "Spring Boot API", "wx-api + admin-api 复用原商城与 AI 治理接口", "#DCFCE7")
    box(d, (520, 410, 860, 570), "FastAPI AI Service", "规则/Mock 分析、Agentic RAG 兼容封装、健康检查", "#FEF3C7")
    box(d, (980, 170, 1320, 330), "MySQL", "商品、订单、评论、AI 分析、风险任务、Agent 轨迹", "#FCE7F3")
    box(d, (980, 410, 1320, 570), "测试与交付", "Smoke、客户闭环、质量评估、最终验收脚本", "#E2E8F0")
    for s, e in [((420, 250), (520, 250)), ((420, 490), (520, 490)), ((860, 250), (980, 250)), ((860, 490), (980, 490)), ((690, 330), (690, 410)), ((1150, 330), (1150, 410))]:
        arrow(d, s, e)
    img.save(OUT / "architecture_overview.png")


def loop():
    img, d = canvas("用户评价到 Agent 治理闭环")
    steps = [
        ("浏览商品", "H5 商品详情"),
        ("提交订单", "不接真实支付"),
        ("演示支付/发货", "安全推进状态"),
        ("确认收货", "进入可评价"),
        ("发布评价", "写入 litemall_comment"),
        ("Agent 巡检", "扫描未分析真实评价"),
        ("风险任务", "高风险进入处理"),
        ("运营闭环", "采纳建议并反馈"),
    ]
    x, y = 70, 210
    for i, (t, b) in enumerate(steps):
        box(d, (x, y, x + 300, y + 135), f"{i+1}. {t}", b, "#FFFFFF")
        if i < len(steps) - 1:
            arrow(d, (x + 300, y + 68), (x + 355, y + 68))
        x += 370
        if x > 1250:
            x, y = 70, 500
    img.save(OUT / "customer_agent_loop.png")


def rag():
    img, d = canvas("Agentic RAG 工作流")
    items = [
        ((90, 190, 410, 350), "Review Analyst", "解析文本、评分、图片 URL 与上下文"),
        ((500, 190, 820, 350), "Case Retriever", "本地案例知识检索，返回相似处置经验"),
        ((910, 190, 1230, 350), "Risk Decision", "规则 + 案例证据生成风险等级"),
        ((500, 500, 820, 660), "Human Feedback", "运营处理反馈进入案例沉淀"),
    ]
    for xy, t, b in items:
        box(d, xy, t, b, "#EEF2FF")
    arrow(d, (410, 270), (500, 270))
    arrow(d, (820, 270), (910, 270))
    arrow(d, (1070, 350), (660, 500))
    arrow(d, (500, 580), (250, 350))
    img.save(OUT / "agentic_rag_workflow.png")


def trace():
    img, d = canvas("Agent Trace 与 Run Replay")
    box(d, (90, 190, 450, 360), "Run State", "记录每次 Agent 执行输入、状态、耗时、输出", "#E0F2FE")
    box(d, (610, 190, 970, 360), "Step Timeline", "按角色展示分析、检索、决策和建议步骤", "#F0FDFA")
    box(d, (1130, 190, 1490, 360), "Replay Compare", "重放同一输入，对比原始结果和新结果", "#FEF3C7")
    box(d, (610, 520, 970, 700), "Debug Evidence", "用于解释模型行为、定位失败与支撑答辩展示", "#FCE7F3")
    arrow(d, (450, 275), (610, 275))
    arrow(d, (970, 275), (1130, 275))
    arrow(d, (790, 360), (790, 520))
    img.save(OUT / "agent_trace_replay.png")


def er():
    img, d = canvas("核心数据模型")
    tables = [
        ("litemall_comment", "真实商品评价\nsource_id"),
        ("litemall_review_ai_analysis", "情感/风险/建议\nsource_type"),
        ("litemall_ai_review_risk_task", "风险任务\n处理状态"),
        ("litemall_ai_operation_log", "运营动作\n反馈记录"),
        ("litemall_ai_agent_run", "Agent Run\n执行状态"),
        ("litemall_ai_case_knowledge", "案例知识\n本地 RAG"),
    ]
    coords = [(90, 180), (500, 180), (910, 180), (910, 520), (500, 520), (90, 520)]
    for (name, body), (x, y) in zip(tables, coords):
        box(d, (x, y, x + 330, y + 150), name, body.replace("\n", " / "), "#FFFFFF")
    for s, e in [((420, 255), (500, 255)), ((830, 255), (910, 255)), ((1075, 330), (1075, 520)), ((910, 595), (830, 595)), ((500, 595), (420, 595)), ((255, 520), (255, 330))]:
        arrow(d, s, e)
    img.save(OUT / "database_er_core.png")


def test_matrix():
    img, d = canvas("测试与验收矩阵")
    rows = [
        ("Service", "8008 / 8080 / 8083 / 6255 / 9527", "PASS"),
        ("Smoke", "AI 分析、巡检、风险、Dashboard", "PASS"),
        ("Customer Loop", "购买评价到 Agent 风险任务", "PASS"),
        ("Agent Quality", "情感、风险类型、风险等级、案例检索", "PASS"),
        ("Final Acceptance", "脚本聚合验收", "PASS"),
    ]
    x0, y0 = 140, 190
    widths = [280, 700, 220]
    headers = ["测试域", "覆盖内容", "结果"]
    for i, h in enumerate(headers):
        d.rectangle((x0 + sum(widths[:i]), y0, x0 + sum(widths[:i+1]), y0 + 58), fill="#1E293B")
        d.text((x0 + sum(widths[:i]) + 18, y0 + 15), h, fill="#FFFFFF", font=F_H)
    y = y0 + 58
    for row in rows:
        for i, val in enumerate(row):
            d.rectangle((x0 + sum(widths[:i]), y, x0 + sum(widths[:i+1]), y + 72), fill="#FFFFFF", outline="#CBD5E1")
            d.text((x0 + sum(widths[:i]) + 18, y + 20), val, fill="#16A34A" if val == "PASS" else "#0F172A", font=F)
        y += 72
    img.save(OUT / "test_acceptance_matrix.png")


def benchmark():
    img, d = canvas("能力对比与创新点")
    cols = ["传统评论管理", "E-Review Agent", "答辩展示价值"]
    rows = [
        ("人工筛查", "Agent 巡检真实评价", "降低漏检风险"),
        ("只看评论列表", "风险中心 + 运营闭环", "形成治理流程"),
        ("结果不可解释", "Trace + Replay", "可观测、可复盘"),
        ("无经验沉淀", "Case Knowledge 本地 RAG", "可复用处置经验"),
    ]
    x0, y0, w = 95, 175, 450
    for i, c in enumerate(cols):
        d.rounded_rectangle((x0 + i*w, y0, x0 + i*w + 405, y0 + 70), radius=14, fill="#2563EB")
        d.text((x0 + i*w + 24, y0 + 18), c, fill="#FFFFFF", font=F_H)
    y = y0 + 100
    for r in rows:
        for i, val in enumerate(r):
            d.rounded_rectangle((x0 + i*w, y, x0 + i*w + 405, y + 80), radius=12, fill="#FFFFFF", outline="#CBD5E1")
            d.text((x0 + i*w + 22, y + 24), val, fill="#0F172A", font=F)
        y += 105
    img.save(OUT / "benchmark_matrix.png")


if __name__ == "__main__":
    architecture()
    loop()
    rag()
    trace()
    er()
    test_matrix()
    benchmark()
    print("DIAGRAM_GENERATION_PASS 7")
