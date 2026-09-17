# 09 Split与数据泄漏政策

## 1. 数据角色

- DEVELOPMENT：用于修改系统；
- REGRESSION：用于防止历史能力退化；
- PILOT：用于修改数据协议，不用于最终指标；
- HELD_OUT：最终封存评测；
- RESERVE：替换不合格Held-out，不用于调参。

## 2. Group-level Split

禁止逐行随机切分同一事件或模板家族。

切分优先级：

1. sourceEventId；
2. scenarioGroupId；
3. generationParentId；
4. templateFamilyId；
5. sourceRecord family。

## 3. seenDuringDevelopment

只要样本被用于以下任一活动，即必须移出严格Held-out：

- 修改Prompt；
- 修改知识库；
- 调整Chunk；
- 调TopK或RRF；
- 选择Reranker；
- 调风险阈值；
- 修规则；
- 修标签映射；
- 根据模型错误定向改写样本。

记录：

- seenDuringDevelopment；
- developmentUseReason；
- developmentUseDate；
- developmentChangeType；
- migratedToRole。

## 4. Gold隔离

正式评测输入文件只包含：

- sampleId；
- text；
- 非Gold运行元数据。

Gold文件单独保存并在预测完成后加载。

建议：

```text
heldout_500_v1.inputs.jsonl
heldout_500_v1.gold.jsonl
```

如条件允许，Gold文件使用访问权限或加密隔离。

## 5. 历史数据

历史预期132条已用于路线选择或报告，应归为Development/Regression，不能直接进入Strict Held-out。

## 6. 污染审计

正式封存前检查：

- 精确Hash；
- 词面近重复；
- BGE-M3语义近重复；
- 同事件；
- 同模板；
- 同生成父样本；
- 是否曾出现在Issue、报告、Prompt、单元测试；
- 是否被用于模型选择。

## 7. 评测期间禁止

- 删除模型答错样本；
- 修改Gold而不留历史；
- 只报告有利子集；
- 跑到中途修改索引或Prompt；
- 用测试集选择阈值；
- 将失败样本移到Reserve后不披露。

任何配置变化必须创建新的Evaluation Manifest和实验版本。
