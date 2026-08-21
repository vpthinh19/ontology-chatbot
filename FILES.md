# Từng tệp trong dự án dùng để làm gì

*Dựng tự động ngày 21/08/2026 từ chú thích đầu mỗi tệp và phép dò tham chiếu chéo.*

Tệp này dành cho người vận hành dự án, không phải tài liệu học thuật. Mô tả lấy nguyên từ dòng chú thích đầu tiên của chính tệp đó, nên nếu một mô tả sai thì sửa chú thích trong tệp rồi dựng lại.

Cột **ai dùng** ghi tệp nào nhắc tới nó. Trống nghĩa là không tệp nào nhắc — với mã thường thì đó là ứng viên xoá, còn với tệp kiểm thử thì là bình thường.


## Mã của hệ thống — `src/` (45 tệp)

Thư mục này là toàn bộ chương trình. Phần `runtime` chạy khi chatbot trả lời người dùng; phần `research` chỉ chạy lúc huấn luyện và đo đạc; phần `cli` là các lệnh gõ tay.

| tệp | dùng để làm gì | cỡ | ai dùng |
|---|---|---|---|
| `ontchatbot/__init__.py` | NTU ontology chatbot: Vietnamese text to direct SPARQL. | 591 B | bench-aoti.py, bench-onnx.py |
| `ontchatbot/catalogue.py` | Typed contract for supported SPARQL query families. | 10 KB | claude-review.md, manual-edit-report.md |
| `ontchatbot/cli/__init__.py` | — | 3 B | bench-aoti.py, bench-onnx.py |
| `ontchatbot/cli/benchmark.py` | Validate or score predictions on the canonical SPARQL test set. | 3 KB | README.md, bench-aoti.py |
| `ontchatbot/cli/benchmark_model.py` | Chấm LLM và seq2seq trên cùng bộ benchmark. | 17 KB | CODEX-RENAME-CHECK.md, claude-review.md |
| `ontchatbot/cli/chat.py` | Trò chuyện với trợ lý học vụ ở dòng lệnh. | 4 KB | README.md, bench-bf16.py |
| `ontchatbot/cli/check_conditions.py` | Kiểm dataset theo bốn điều kiện chất lượng. | 9 KB | pyproject.toml |
| `ontchatbot/cli/convert_model.py` | Convert a trained checkpoint for deployment. | 128 B | bench-bf16.py, pyproject.toml |
| `ontchatbot/cli/internal_eval.py` | Chấm model trên bộ câu hỏi thực tế, tách biệt với benchmark chính. | 3 KB | pyproject.toml, benchmark_model.py |
| `ontchatbot/cli/prepare_tokenizer.py` | Prepare the reproducible ViT5 tokenizer. | 131 B | pyproject.toml, train-server.sh |
| `ontchatbot/cli/report.py` | Generate public dataset and ontology reports. | 131 B | README.md, bench-aoti.py |
| `ontchatbot/cli/report_page.py` | Dựng một trang báo cáo: hình dạng ontology, phân bố dataset, kết quả model. | 13 KB | migration-report.md, pyproject.toml |
| `ontchatbot/cli/serve.py` | Run the chatbot HTTP service. | 3 KB | claude-review.md, documentation-report.md |
| `ontchatbot/cli/train.py` | Fine-tune a supported model for direct SPARQL generation. | 142 B | README.md, README.md |
| `ontchatbot/cli/train_llm_lora.py` | Run the causal-LLM QLoRA training path. | 133 B | pyproject.toml |
| `ontchatbot/cli/try_model.py` | Gõ câu hỏi, xem truy vấn do model sinh và kết quả từ đồ thị. | 4 KB | pyproject.toml |
| `ontchatbot/cli/validate_data.py` | Validate a SPARQL dataset against the canonical ontology. | 2 KB | manual-edit-report.md, migration-report.md |
| `ontchatbot/research/__init__.py` | Dataset, training and evaluation workflows. | 50 B | bench-aoti.py, bench-onnx.py |
| `ontchatbot/research/answer_scope.py` | Classify ontology individuals by their role in model-facing answers. | 4 KB | catalogue_validation.py, inventory.py |
| `ontchatbot/research/benchmark.py` | Test-set contract for direct-SPARQL generation. | 9 KB | README.md, bench-aoti.py |
| `ontchatbot/research/catalogue_validation.py` | Validate catalogue coverage against the canonical answer inventory. | 6 KB | validate_data.py, consistency.py |
| `ontchatbot/research/consistency.py` | Read-only consistency checks for canonical data and derived artifacts. | 6 KB | validate_data.py, reporting.py |
| `ontchatbot/research/coverage.py` | Machine-checkable coverage requirements for the official dataset. | 14 KB | manual-edit-report.md, prompt-report.md |
| `ontchatbot/research/dataset.py` | Loading and executable validation for the canonical dataset. | 13 KB | README.md, bench-bf16.py |
| `ontchatbot/research/evaluation.py` | Structural primary metrics and execution diagnostics for generated SPARQL. | 23 KB | bench-gpu.py, bench-quantization.py |
| `ontchatbot/research/inventory.py` | Build the machine-readable inventory of answerable ontology paths. | 9 KB | ONTOLOGY.md, validate_data.py |
| `ontchatbot/research/llm_lora_training.py` | QLoRA fine-tuning for a causal LLM that emits canonical SPARQL. | 34 KB | CODEX-RENAME-CHECK.md, benchmark_model.py |
| `ontchatbot/research/mentions.py` | Một sinh viên nhắc tới thực thể này bằng những cách nào? | 12 KB | coverage.py, reporting.py |
| `ontchatbot/research/query_features.py` | Derive overlapping research features from canonical SPARQL targets. | 3 KB | charts.py, evaluation.py |
| `ontchatbot/research/reporting.py` | Create concise, public reports for the canonical dataset and ontology. | 36 KB | report.py, consistency.py |
| `ontchatbot/research/training.py` | Fine-tune a supported encoder-decoder model to generate direct SPARQL. | 33 KB | README.md, charts.py |
| `ontchatbot/runtime/__init__.py` | Production question-answering pipeline. | 46 B | bench-aoti.py, bench-onnx.py |
| `ontchatbot/runtime/agent.py` | Trợ lý học vụ: một mô hình ngôn ngữ lớn gọi công cụ tra cứu ontology. | 15 KB | bench-quantization.py, documentation-report.md |
| `ontchatbot/runtime/api.py` | Giao diện HTTP: một trợ lý hội thoại, trả lời theo lối chảy dần. | 9 KB | screenshots.py, operations-report.md |
| `ontchatbot/runtime/llm.py` | Sinh truy vấn bằng LLM có nhắc ví dụ hoặc đã tinh chỉnh. | 8 KB | CODEX-RENAME-CHECK.md, readme-plan.md |
| `ontchatbot/runtime/model.py` | Minimal CTranslate2 inference pipeline for direct SPARQL generation. | 4 KB | README.md, bench-aoti.py |
| `ontchatbot/runtime/pipeline.py` | End-to-end question answering over the ontology. | 6 KB | measure_tool.py, run.py |
| `ontchatbot/runtime/render.py` | Render SPARQL rows as a compact, explicit contract for the LLM agent. | 4 KB | run.py, __init__.py |
| `ontchatbot/runtime/sparql.py` | Execute model-generated, read-only SPARQL on the canonical ontology. | 7 KB | bench-bf16.py, bench-fp32.py |
| `ontchatbot/runtime/text.py` | Chuẩn hóa source có kiểm soát trước tokenizer. | 4 KB | bench-aoti.py, bench-bf16.py |
| `ontchatbot/settings.py` | Đường dẫn và namespace dùng chung. | 2 KB | migration-report.md, benchmark.py |
| `ontchatbot/tools/__init__.py` | Reproducible preparation and migration utilities. | 56 B | bench-aoti.py, bench-onnx.py |
| `ontchatbot/tools/conversion.py` | Convert a saved Transformers checkpoint to a CTranslate2 artifact. | 4 KB | convert_model.py, test_answers.py |
| `ontchatbot/tools/prepare_tokenizer.py` | CLI for the deterministic ViT5 sentinel-token repair. | 1 KB | pyproject.toml, prepare_tokenizer.py |
| `ontchatbot/tools/tokenizer.py` | Reproducible tokenizer contract for the supported seq2seq models. | 11 KB | bench-aoti.py, bench-onnx.py |

## Phép kiểm tự động — `tests/` (38 tệp)

Mỗi tệp canh một nhóm ràng buộc. Chúng **không được import ở đâu** — công cụ kiểm thử tự tìm theo tên bắt đầu bằng `test_`. Vì vậy đừng xoá tệp nào ở đây chỉ vì thấy không ai gọi tới.

| tệp | dùng để làm gì | cỡ | ai dùng |
|---|---|---|---|
| `__init__.py` | — | 3 B | bench-aoti.py, bench-onnx.py |
| `ontology/conftest.py` | — | 338 B | — |
| `ontology/test_answers.py` | Đồ thị đã lắp phải trả lời được từng miền, qua đúng đường mà runtime dùng. | 10 KB | test_dataset_content.py |
| `ontology/test_drafting_rules.py` | Quy tắc biên soạn tầng nghiệp vụ. | 11 KB | test_source_fidelity.py |
| `ontology/test_schema.py` | Lược đồ của đồ thị đã lắp phải tự mô tả đầy đủ. | 7 KB | — |
| `ontology/test_source_fidelity.py` | Tầng văn bản phải chép đúng nguyên văn công văn. | 17 KB | — |
| `research/test_benchmark.py` | — | 5 KB | — |
| `research/test_catalogue.py` | — | 7 KB | test_inference.py |
| `research/test_catalogue_validation.py` | — | 16 KB | — |
| `research/test_compose.py` | Ba trục ghép thành câu hỏi: cách gọi × khung ý định × phong cách. | 8 KB | — |
| `research/test_consistency.py` | — | 8 KB | — |
| `research/test_coverage.py` | — | 10 KB | — |
| `research/test_dataset.py` | — | 8 KB | — |
| `research/test_dataset_content.py` | Nội dung bản phát hành: chạy được, phủ đủ, và không tự mâu thuẫn. | 19 KB | — |
| `research/test_dataset_quality.py` | Mỗi luật ở đây tương ứng MỘT lỗi có thật đã tìm ra khi soát dataset. | 35 KB | — |
| `research/test_documentation_status.py` | — | 10 KB | documentation-report.md, editing-report.md |
| `research/test_evaluation.py` | — | 13 KB | EVALUATION.md, test_training_config.py |
| `research/test_inventory.py` | — | 4 KB | — |
| `research/test_llm_lora_training.py` | — | 7 KB | CODEX-RENAME-CHECK.md |
| `research/test_mentions.py` | Cách gọi tên thực thể phải rõ nghĩa, đủ tự nhiên, và không bịa. | 9 KB | — |
| `research/test_query_features.py` | — | 3 KB | — |
| `research/test_reporting.py` | — | 7 KB | — |
| `research/test_scoring_prompt.py` | Chấm model đã tinh chỉnh phải hỏi bằng ĐÚNG khuôn đã dạy nó. | 4 KB | CODEX-RENAME-CHECK.md |
| `research/test_training.py` | — | 4 KB | test_reporting.py |
| `research/test_training_config.py` | Ghim cấu hình huấn luyện vào đúng những giá trị đã đo. | 5 KB | — |
| `runtime/test_agent.py` | Canh hợp đồng giữa trợ lý và công cụ tra cứu. | 9 KB | — |
| `runtime/test_catalogue_guard.py` | — | 3 KB | test_inference.py |
| `runtime/test_inference.py` | — | 6 KB | — |
| `runtime/test_llm.py` | Gom lô lúc chấm phải cho ra ĐÚNG kết quả của việc hỏi từng câu. | 3 KB | CODEX-RENAME-CHECK.md, test_benchmark.py |
| `runtime/test_model_text.py` | Source normalization chỉ bung whitelist, vẫn giữ ngôn ngữ nói. | 4 KB | — |
| `runtime/test_query_engine.py` | — | 7 KB | — |
| `runtime/test_render.py` | — | 4 KB | — |
| `runtime/test_serve.py` | Tầng HTTP: chuyển lượt nói vào trợ lý và đẩy sự kiện ra ngay khi có. | 9 KB | test_serve_cli.py |
| `runtime/test_serve_cli.py` | — | 3 KB | — |
| `runtime/test_version.py` | — | 1 KB | — |
| `support/__init__.py` | — | 0 B | bench-aoti.py, bench-onnx.py |
| `support/frames.py` | Ghép ba trục thành một câu hỏi: cách gọi tên × khung ý định × phong cách. | 15 KB | manual-review.md, README.md |
| `tools/test_model_tokenizers.py` | — | 4 KB | — |

## Dữ liệu của dự án — `resources/` (27 tệp)

Chia hai loại: **dữ liệu gốc do người sửa tay** (ontology, ba tập dữ liệu, câu hỏi soạn tay) và **báo cáo dẫn xuất** (sinh lại được từ dữ liệu gốc).

| tệp | dùng để làm gì | cỡ | ai dùng |
|---|---|---|---|
| `cases/user_queries.json` | 3 mục · note, expectations, label_basis | 6 KB | settings.py |
| `dataset/coverage.json` | 4 mục · priority_domains, numeric_cases, rejection_classes, required_registers | 371 B | README.md, consistency.py |
| `dataset/manifest.json` | 8 mục · schema, files, catalogue, coverage, totals | 3 KB | export-onnx.py, CODEX-RENAME-CHECK.md |
| `dataset/test.jsonl` | 390 dòng · trường: id, query_id, register, input, target | 221 KB | bench-bf16.py, bench-fp32.py |
| `dataset/train.jsonl` | 5,518 dòng · trường: id, query_id, register, input, target | 3119 KB | manual-edit-report.md, README.md |
| `dataset/val.jsonl` | 400 dòng · trường: id, query_id, register, input, target | 224 KB | claude-review.md, manual-edit-report.md |
| `end-to-end/conclusions.json` | 5 mục · ghi_chu, nhom_2_sai, nhom_2_dung_nhung_nhan_tap_cham_qua_chat, nhom_3_ghi_chu, nhom_1_ba_cau_khong_tra_cuu | 2 KB | — |
| `end-to-end/inspect_one.py` | Hỏi lại đúng một câu và in cả dữ liệu công cụ trả về, để đối chiếu tay. | 1 KB | CODEX-RENAME-CHECK.md |
| `end-to-end/measure_tool.py` | Đo thời gian bên trong công cụ, dùng chính từ khoá trợ lý đã gửi lúc chạy thật. | 2 KB | — |
| `end-to-end/question_set.py` | Dựng bộ câu hỏi cho phép đo đầu-cuối, lấy từ chính tập chấm. | 3 KB | CODEX-RENAME-CHECK.md |
| `end-to-end/questions.json` | 3 mục · trong_pham_vi, ngoai_pham_vi, do_thi_khong_co | 18 KB | manual-edit-report.md, manual-review.md |
| `end-to-end/results-rescored.json` | danh sách 85 phần tử | 115 KB | score_recheck.py |
| `end-to-end/results.json` | danh sách 85 phần tử | 113 KB | charts_end_to_end.py, measure_tool.py |
| `end-to-end/run.py` | Đo trợ lý đầu-cuối: hỏi bằng câu người dùng thật, chấm bằng dữ liệu công cụ trả về. | 7 KB | README.md, README.md |
| `end-to-end/score.py` | Tổng hợp phép đo đầu-cuối thành các con số đưa vào README. | 3 KB | README.md, bench-quantization.py |
| `end-to-end/score_recheck.py` | Chấm lại: nguồn hợp lệ gồm cả danh sách chủ đề trong khuôn nhắc hệ thống. | 1 KB | CODEX-RENAME-CHECK.md |
| `ontology/answer_inventory.json` | 3 mục · schema_version, ontology_namespace, entries | 1242 KB | ONTOLOGY.md, reporting.py |
| `ontology/catalogue.jsonl` | 50 dòng · trường: query_id, domain, target_template, slots, coverage, tier | 56 KB | manual-review.md, README.md |
| `provenance/frames.jsonl` | 49 dòng · trường: query_id, frames, short_frames | 22 KB | manual-review.md, README.md |
| `provenance/rejection_checklist.json` | 8 mục · adjacent-domain, ambiguous, greeting-social, hard-negative, incomplete-request | 20 KB | settings.py |
| `provenance/rejection_provenance.json` | 884 mục · question-005274, question-005275, question-005276, question-005277, question-005278 | 132 KB | settings.py |
| `provenance/rejections.jsonl` | 8 dòng · trường: class, templates | 5 KB | README.md, settings.py |
| `provenance/written-questions.jsonl` | 3,130 dòng · trường: anchor, query_id, register, input | 507 KB | manual-edit-report.md, manual-review.md |
| `reports/audit-bon-dieu-kien.json` | 5 mục · tong_dong, dk1, dk2, dk3, dk4 | 896 KB | check_conditions.py |
| `reports/dataset.json` | 7 mục · dataset, in_domain_contract, coverage, training_readiness, ontology | 119 KB | README.md, README.md |
| `reports/procedure-dataset.json` | 5 mục · scope, procedure_target_count, procedure_family_count, splits, contracts | 2 KB | README.md, consistency.py |
| `reports/provenance.json` | 7 mục · schema_version, baseline_release, provenance_basis, baseline_inputs, current_inputs | 1 KB | README.md, consistency.py |

## Kết quả chạy, không nằm trong git — `artifacts/` (37 tệp)

Adapter đã huấn luyện, model đã chuyển đổi để phục vụ, kịch bản đo tốc độ và bộ dựng hình cho README.

| tệp | dùng để làm gì | cỡ | ai dùng |
|---|---|---|---|
| `benchmarks/bench-aoti.py` | Build và đo AOTInductor cho encoder của đúng benchmark bench-torch.py. | 19 KB | CODEX-RENAME-CHECK.md |
| `benchmarks/bench-bf16.py` | Gộp adapter và chuyển đổi ngay ở bfloat16, rồi suy luận cũng bằng bfloat16. | 4 KB | — |
| `benchmarks/bench-fp32.py` | So float32 trên GPU với float32 trên CPU, cùng một model, cùng 120 câu. | 3 KB | — |
| `benchmarks/bench-gpu.py` | Đo CTranslate2 theo từng câu trên cùng một mẫu test tất định. | 7 KB | — |
| `benchmarks/bench-onnx.py` | Greedy benchmark T5Gemma2 thuần tokenizers + NumPy + ONNX Runtime. | 11 KB | CODEX-RENAME-CHECK.md |
| `benchmarks/bench-quantization.py` | Đo mọi kiểu tính toán của CTranslate2 trên một card, và trả lời câu hỏi | 8 KB | — |
| `benchmarks/bench-torch.py` | Đo PyTorch/torch.compile trên đúng 120 câu của phép đo CT2. | 23 KB | bench-aoti.py, CODEX-RENAME-CHECK.md |
| `benchmarks/export-onnx.py` | Xuất T5Gemma2 đã gộp sang ba đồ thị ONNX bằng tracer cũ của torch.onnx. | 10 KB | — |
| `benchmarks/onnx-manifest.json` | 9 mục · format, opset, exporter, model, num_layers | 476 B | CODEX-RENAME-CHECK.md |
| `benchmarks/results-aoti.json` | 6 mục · status, protocol, environment, runtime_without_transformers, error | 5 KB | bench-aoti.py, CODEX-RENAME-CHECK.md |
| `benchmarks/results-bf16.json` | 3 mục · cases, median_ns, p95_ns | 842 KB | bench-bf16.py |
| `benchmarks/results-fp32.json` | 2 mục · gpu-float32, cpu-float32 | 122 KB | bench-fp32.py, bench-torch.py |
| `benchmarks/results-gpu.json` | 2 mục · protocol, configs | 2529 KB | bench-aoti.py, bench-bf16.py |
| `benchmarks/results-onnx.json` | 5 mục · protocol, environment, disk_usage, runtime_imports, configs | 167 KB | bench-onnx.py, CODEX-RENAME-CHECK.md |
| `benchmarks/results-quantization.json` | 4 mục · model, records, scorer, runs | 5 KB | bench-quantization.py |
| `benchmarks/results-torch.json` | 4 mục · protocol, environment, disk_usage, configs | 254 KB | bench-aoti.py, bench-onnx.py |
| `figures/charts.py` | Dựng toàn bộ biểu đồ kết quả cho README. | 10 KB | README.md, CODEX-RENAME-CHECK.md |
| `figures/charts_end_to_end.py` | Biểu đồ kết quả đo trợ lý đầu-cuối, sau khi soát lại từng con số. | 4 KB | README.md, CODEX-RENAME-CHECK.md |
| `figures/crop.py` | Cắt bỏ khoảng nền trống giữa câu trả lời và thanh nhập liệu. | 2 KB | — |
| `figures/screenshots.py` | Chụp ảnh giao diện từ lượt trò chuyện thật với máy chủ đang chạy. | 1 KB | — |
| `figures/style.py` | Kiểu vẽ dùng chung cho mọi biểu đồ trong README. | 2 KB | charts.py, charts_end_to_end.py |
| `training-results/bartpho/benchmark-test.json` | 14 mục · metric_policy, primary_metrics, coverage_accounting, overall, in_domain | 3368 KB | style.py, claude-review.md |
| `training-results/bartpho/benchmark-val.json` | 14 mục · metric_policy, primary_metrics, coverage_accounting, overall, in_domain | 3235 KB | claude-review.md, reporting.py |
| `training-results/bartpho/training-metrics.json` | 15 mục · metric_policy, primary_metrics, coverage_accounting, overall, in_domain | 3280 KB | claude-review.md, reporting.py |
| `training-results/mbart/benchmark-test.json` | 14 mục · metric_policy, primary_metrics, coverage_accounting, overall, in_domain | 3274 KB | style.py, claude-review.md |
| `training-results/mbart/benchmark-val.json` | 14 mục · metric_policy, primary_metrics, coverage_accounting, overall, in_domain | 3182 KB | claude-review.md, reporting.py |
| `training-results/mbart/training-metrics.json` | 15 mục · metric_policy, primary_metrics, coverage_accounting, overall, in_domain | 3220 KB | claude-review.md, reporting.py |
| `training-results/report/dataset.json` | 7 mục · dataset, in_domain_contract, coverage, training_readiness, ontology | 119 KB | README.md, README.md |
| `training-results/report/models.json` | 2 mục · protocol, models | 117 KB | README.md, style.py |
| `training-results/report/procedure-dataset.json` | 5 mục · scope, procedure_target_count, procedure_family_count, splits, contracts | 2 KB | README.md, consistency.py |
| `training-results/report/provenance.json` | 7 mục · schema_version, baseline_release, provenance_basis, baseline_inputs, current_inputs | 799 B | README.md, consistency.py |
| `training-results/t5gemma2/benchmark-test.json` | 14 mục · metric_policy, primary_metrics, coverage_accounting, overall, in_domain | 3116 KB | style.py, claude-review.md |
| `training-results/t5gemma2/benchmark-val.json` | 14 mục · metric_policy, primary_metrics, coverage_accounting, overall, in_domain | 3119 KB | claude-review.md, reporting.py |
| `training-results/t5gemma2/training-metrics.json` | 15 mục · metric_policy, primary_metrics, coverage_accounting, overall, in_domain | 3150 KB | claude-review.md, reporting.py |
| `training-results/vit5/benchmark-test.json` | 14 mục · metric_policy, primary_metrics, coverage_accounting, overall, in_domain | 2977 KB | style.py, claude-review.md |
| `training-results/vit5/benchmark-val.json` | 14 mục · metric_policy, primary_metrics, coverage_accounting, overall, in_domain | 3009 KB | claude-review.md, reporting.py |
| `training-results/vit5/training-metrics.json` | 15 mục · metric_policy, primary_metrics, coverage_accounting, overall, in_domain | 3033 KB | claude-review.md, reporting.py |
