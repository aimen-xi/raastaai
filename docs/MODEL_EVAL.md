# Phase 2: Model prep & evaluation (2026-11-09)

## What was done
1. **Downloaded** four public pretrained checkpoints. SHA-256 hashes are in `api/models/models.json`.
2. **Scanned** every `.pt` pickle *statically* with `picklescan` and `tools/inspect_pickle.py` before loading it.
   - The only flagged global is `builtins.getattr(Detect, 'forward')`, Ultralytics' standard segmentation-head reference.
   - Nothing else is suspicious.
3. **Exported** all four to ONNX (opset 17, 640×640) with `tools/export_models.py`. This was conversion only; **no training**.
4. **Wrote our own runtime**, `api/app/vision.py`, using `onnxruntime` + numpy. There is no torch at runtime.
   - **Parity:** identical max-confidence to Ultralytics' own ONNX predictor on the same input (mean / max difference = 0.0000).
   - **Bug found and fixed:** phone photos carry an EXIF rotation tag, and we were feeding them to the models sideways. `open_upright()` now applies the EXIF orientation *before* inference. The EXIF data is then stripped before storage.
   - **Preprocessing change:** downscaling uses antialiased `INTER_AREA`. Plain linear resize of 12 MP phone photos lowered pothole recall from 0.69 to 0.38 at a 0.25 threshold.
5. **Built a licence-tracked evaluation set**, `eval/set1`, 56 images.
   - The full manifest is `manifest.csv`. Manual relabels after visual review are in `labels_override.csv`.

| Label | n | Source (licence) |
|---|---|---|
| pothole | 23 | 13 from Arpitraj01/Pothole_classification test set (MIT), plus 10 frames from the model author's demo video (MIT; may be close to the training domain) |
| garbage | 17 | Shynuaa/Street-garbage test set (MIT), plus Akhila-9849 overflowing bins (CC-BY-4.0) |
| litter_single | 4 | Street-garbage images with one item. The label files were empty; relabelled by hand. |
| neg_road | 4 | Clean roads ("none" class), Arpitraj01 (MIT) |
| neg_person | 2 | Ultralytics sample images (AGPL-3.0) |
| neg_blank | 6 | Generated: grey, white, black, gradient, lens-cap noise, blurred wall |

Animal negatives could not be fetched: the HF datasets-server returned 503 errors, and Wikimedia is blocked from this sandbox. **To-do:** add about 5 staged animal photos before the demo.

## Garbage model bake-off

Rule: "≥ 2 items at ≥ 0.40, or mask area ≥ 3%"; precision and recall for garbage vs everything else.

| Model | Best precision / recall | Latency (i5-1235U, 2 threads) |
|---|---|---|
| **turhancan YOLOv8m-seg** (Glass/Metal/Paper/Plastic/Waste) | **P 0.75 / R 0.75** (items ≥ 2); P 0.75 / R 0.56 (area ≥ 5%) | 1.2 s |
| kendrickfff YOLOv8l-det (12 material classes) | P 0.57 / R 0.25 at best | 1.8 s |

**Decision:** we use **turhancan**. kendrickfff is dropped: it's worse on street scenes, slower, and 175 MB.

## End-to-end decision results (`api/app/decide.py`, `tools/eval_decisions.py`)

| True label | issue: pothole | issue: garbage | uncertain: pothole | uncertain: garbage | not_issue |
|---|---|---|---|---|---|
| garbage (17) | 0 | **14** | 1 | 1 | 1 |
| pothole (23) | **8** | 0 | 8 | 2 | 5 |
| litter_single (4) | 0 | 1 | 2 | 1 | 0 |
| neg_blank (6) | 0 | 0 | 0 | 0 | **6** |
| neg_person (2) | 0 | 0 | 0 | 0 | **2** |
| neg_road (4) | 0 | 0 | 0 | 1 | 3 |

- **Irrelevant photos confidently suggested as an issue: 0 / 12.** This covers the judges' check on people, animals and blank images. Animals still need real test photos.
- **Garbage:** the right category was suggested for 15 / 17 photos; 14 of those were confident.
- **Potholes:** the right category was suggested for 16 / 23. Only 8 of those were confident. On the demo-video road frames the result is 8 / 10.
  - This is the weak spot. The independent pothole photos are top-down shots of rural, unpaved roads, which the model wasn't trained on.
  - The mitigation is the product design: uncertain results ask the user, and a manual category is always possible.

## Calibrated rules (single source: `api/app/decide.py`)

| Rule | Value | Why |
|---|---|---|
| Blank image | grayscale std-dev < 8 | All 6 blanks have std-dev < 1; real photos are > 27 |
| Person or animal is the subject | COCO conf ≥ 0.40 and box ≥ 15% of the image, **or** ≥ 3 people covering ≥ 25% together | The litter model fires on clothing, so the gate runs first. It also keeps photos of real people out of storage. |
| Pothole: issue | max conf ≥ **0.50** | |
| Pothole: uncertain | max conf 0.25–0.50 | |
| Garbage: issue | max conf ≥ **0.50** and (≥ **2** items at ≥ 0.40 **or** mask area ≥ **3%**) | "Accumulation", not a single wrapper |
| Garbage: uncertain | max conf ≥ 0.40 | |
| Models disagree | pothole ≥ 0.50 **and** a litter item ≥ 0.45 → *uncertain* | Dark leaf litter scored 0.75 as a "pothole" |
| Garbage vs pothole | Strong garbage wins unless pothole conf is higher | Debris piles also trigger the pothole model |

## Runtime footprint for deployment
- **Models:** pothole 13 MB + turhancan 109 MB + COCO 13 MB, about 135 MB of ONNX. The Phase 3 option is to convert turhancan to fp16, roughly halving it.
- **Latency:** about 1.6 s per photo on this laptop. Expect about 2–3 s on a free Hugging Face 2-vCPU Space. The 15 s client timeout leaves plenty of headroom.

## Honest limitations (for the pitch)
- The evaluation set is small: 56 images. The numbers show the decision logic works as designed; they are not a benchmark.
- Pothole recall on out-of-domain photos is modest. Demo with dataset-style urban pothole photos.
- Garbage detection finds litter *items*. Very large dump sites photographed from far away may come back as "uncertain".
