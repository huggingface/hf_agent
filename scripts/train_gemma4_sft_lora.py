from __future__ import annotations

import argparse
import json
from pathlib import Path

from datasets import Dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTConfig, SFTTrainer

from teacher_distill.prompts import format_student_answer, format_student_message
from teacher_distill.schemas import VerifiedTrajectory


def load_records(path: Path) -> list[VerifiedTrajectory]:
    records: list[VerifiedTrajectory] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(VerifiedTrajectory.model_validate_json(line))
    return records


def build_dataset(path: Path, tokenizer) -> Dataset:
    rows = []
    for verified in load_records(path):
        messages = [format_student_message(verified), format_student_answer(verified)]
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False,
            enable_thinking=True,
        )
        rows.append({"text": text, "task_id": verified.task.task_id})
    return Dataset.from_list(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--model", default="google/gemma-4-12B-it")
    parser.add_argument("--max_seq_length", type=int, default=8192)
    parser.add_argument("--num_train_epochs", type=float, default=1.0)
    parser.add_argument("--learning_rate", type=float, default=2e-5)
    parser.add_argument("--per_device_train_batch_size", type=int, default=1)
    parser.add_argument("--gradient_accumulation_steps", type=int, default=16)
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    train_dataset = build_dataset(args.dataset, tokenizer)
    print(json.dumps({"train_rows": len(train_dataset)}, indent=2))

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype="bfloat16",
        device_map=None,
        trust_remote_code=True,
    )
    model.gradient_checkpointing_enable()

    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        task_type="CAUSAL_LM",
    )
    train_args = SFTConfig(
        output_dir=str(args.output_dir),
        dataset_text_field="text",
        max_seq_length=args.max_seq_length,
        num_train_epochs=args.num_train_epochs,
        learning_rate=args.learning_rate,
        per_device_train_batch_size=args.per_device_train_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        bf16=True,
        gradient_checkpointing=True,
        logging_steps=10,
        save_steps=100,
        save_total_limit=3,
        report_to="none",
    )
    trainer = SFTTrainer(
        model=model,
        args=train_args,
        train_dataset=train_dataset,
        peft_config=peft_config,
    )
    trainer.train()
    trainer.save_model(str(args.output_dir))


if __name__ == "__main__":
    main()
