# Evaluation Dataset Sources

## Scope

Step 21.2.2A uses only sources with an explicit free license for the committed demo subset. Raw downloads remain under `ai-service/data/external_raw/` and are excluded from Git. The repository retains the downloader, pinned source revision or file identifier, selected subset, hashes, and attribution metadata.

## Selected Sources

### ASAP Chinese Review Dataset

- Source: https://github.com/Meituan-Dianping/ASAP
- Publisher: Meituan-Dianping dataset authors
- License: Apache-2.0, https://github.com/Meituan-Dianping/ASAP/blob/master/LICENSE
- Citation: Bu et al., *ASAP: A Chinese Review Dataset Towards Aspect Category Sentiment Analysis and Rating Prediction*, NAACL 2021, https://doi.org/10.18653/v1/2021.naacl-main.167
- Selected: 65 native Chinese rows
- Use: genuine normal reviews, legitimate negative reviews, hard negatives, and ambiguous sentiment boundaries
- Constraint: restaurant/O2O reviews are not mapped to product-governance risks such as fake review, paid review, or rating manipulation.

### Chinese E-commerce Negative Reviews

- Source: https://figshare.com/articles/dataset/11944947
- Publisher: Jichang Zhao
- License: CC BY 4.0, https://creativecommons.org/licenses/by/4.0/
- Citation: Zhao, J. (2020), *More than one million negative reviews from a Chinese e-commerce platform*, Figshare dataset 11944947
- Selected: 35 native Chinese rows
- Use: customer-service/after-sales candidates, legitimate complaints, and false-marketing candidates
- Constraint: original user identifiers are discarded. Dataset reason labels are mapped only to candidate risk types and are not represented as human E-Review gold.

### Fake-Reviews-Dataset

- Source: https://huggingface.co/datasets/theArijitDas/Fake-Reviews-Dataset
- Publisher: theArijitDas via Hugging Face
- License declared by dataset card: Apache-2.0
- Pinned revision: `cffa887a877db747e540f15eb891f0d18070b994`
- Selected: 25 English rows, sampled before translation
- Use: genuine/deceptive contrast and lexical or implicit fake-review candidates
- Constraint: label 1 denotes computer-generated/deceptive text. It maps only to `fake_review` candidate and never implies `paid_review` or `rating_manipulation`.

### E-Review Business Supplement

- Source: project-owned Step 21.2.2A definitions
- Selected: 55 native Chinese cases
- Use: paid review, rating manipulation, review suppression, multi-risk, noisy expression, and after-sales/manipulation boundaries not covered by public labels
- Label status: `expert_designed`, candidate only; never human gold

## Skipped Sources

Amazon Reviews 2023 remains `SKIPPED_LICENSE_UNCLEAR` for committed review bodies. No text from that source enters either demo set.

## Reproduction

Run the downloader and builder from `ai-service`:

```powershell
.\.venv\Scripts\python.exe scripts\download_step2122a_sources.py
.\.venv\Scripts\python.exe scripts\build_step2122a_demo_dataset.py
```

Downloads use a fixed GitHub archive, pinned Hugging Face revision, and Figshare file ID with official byte-size and MD5 checks. Sampling uses the fixed seed `step21.2.2a-demo-v1-fixed-seed-2122`.
