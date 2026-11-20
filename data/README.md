# Data provenance

These are unchanged upstream JSON files from the official
[`tatsu-lab/alpaca_eval` dataset](https://huggingface.co/datasets/tatsu-lab/alpaca_eval/tree/main),
downloaded on 20 November 2026 for the noncommercial K06 course study.
The dataset page identifies its license as **CC BY-NC 4.0**. Attribution and
license terms remain with the original creators; this repository does not
claim ownership of the annotations.

| Local file | Official source | SHA-256 |
| --- | --- | --- |
| `raw/alpaca_farm_human_crossannotations.json` | [Human cross-annotations](https://huggingface.co/datasets/tatsu-lab/alpaca_eval/resolve/main/alpaca_farm_human_crossannotations.json) | `e75b70d6176cf50f8d9898065541445050e164ebce3704e6d7becf99e39ed704` |
| `raw/alpaca_eval_annotations_alpaca_eval_gpt4.json` | [Published GPT-4 annotations](https://huggingface.co/datasets/tatsu-lab/alpaca_eval/resolve/main/alpaca_eval_annotations_alpaca_eval_gpt4.json) | `e73710ff283d5b8f42fe176db791c8a4f4c6eea9641ccbc6117667110848538c` |

The human file is the analysis source. The GPT-4 file is retained to reproduce
the pair-overlap audit that ruled out a direct judge comparison. It is not used
to claim GPT-4 accuracy on these human-labeled pairs. The generated results
are in [`../results/`](../results/).
