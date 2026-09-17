# v1.6 Hybrid RAG 系统设计

## 1. 目标

v1.6 将 TF-IDF、BAAI/bge-m3、FAISS IndexFlatIP 和可回退 reranker 组合为可评估的 Hybrid RAG。检索指标与 Qwen3 下游生成指标分开计算，不把检索命中率写成风险识别准确率。

## 2. 模块结构

`ai-service/app/rag_v2` 按职责拆分：配置、Schema、语料加载、TF-IDF、Dense Encoder、FAISS、reranker、融合检索、评估器和服务层。FastAPI 提供 status、index/build、search、evaluate 和 report 五个接口。

TF-IDF 使用中文字符 1-3 gram 与 cosine similarity。bge-m3 使用 Transformers `AutoTokenizer/AutoModel` 真实编码 CLS dense embedding，并执行 L2 归一化。FAISS 使用 IndexFlatIP，归一化后 inner product 等价 cosine similarity。

## 3. 融合与重排

候选集默认取 20 条，各路分数先按候选集 min-max 归一化，再按 `0.30 lexical + 0.40 dense + 0.20 rerank + 0.10 metadata` 融合。支持 tfidf、dense、hybrid 和 hybrid_rerank 四种策略。

RuleReranker 综合风险类型、风险等级、证据关键词、商品类目、字符/词元重叠和困难负样本惩罚。NeuralReranker 使用本地开源交叉编码模型；模型不可用时明确显示 `rule_fallback`，不会把规则重排冒充神经重排。

## 4. 资源与失败边界

bge-m3、reranker 与 Qwen3 权重均位于 Git 仓库外。索引阶段允许 bge-m3 使用 CUDA，编码完案例后主动卸载；Qwen 下游评估时 Embedding 和 reranker 可切换 CPU，避免 8GB GPU 同时常驻三套模型。

模型、依赖或索引缺失分别输出 `BGE_M3_NOT_AVAILABLE`、`FAISS_NOT_AVAILABLE` 或 `FAISS_INDEX_NOT_AVAILABLE`。Dense 失败不会被写成真实 Dense 命中；服务启动不依赖模型权重。

## 5. 安全边界

历史案例只用于风险判断与运营建议，不能成为当前评论的事实证据。RAG 不自动执行退款、赔付、封禁等最终动作，完整评论不会写入 Tool Log；日志只保存截断摘要、策略、数量、分数和案例 ID。

## 6. 本机复现环境

本机使用独立 Conda `torchtest` 环境：PyTorch 2.5.1+cu121、Transformers 5.3.0、NumPy 1.26.4、FAISS CPU 1.8.0.post1 和 scikit-learn。NumPy 固定在 2.0 以下是因为当前 Windows FAISS wheel 使用 NumPy 1.x ABI。

可选依赖清单位于 `ai-service/requirements-rag.txt`。模型目录通过环境变量传入，不写入 `.env.example` 的实际值；FAISS 二进制索引通过脚本重建且默认不提交 Git，元数据 JSON 保留模型、维度、案例数、设备、构建时间和编码耗时。
