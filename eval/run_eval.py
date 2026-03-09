#!/usr/bin/env python3
"""
Evaluation script for Prisme — Anomaly Insights.

Runs each question in dataset.json through the LLM and checks:
1. Response type matches expected type
2. Generated SQL matches expected regex pattern
3. Generated SQL executes without error

Usage:
    python eval/run_eval.py                    # Run with default model (Qwen)
    python eval/run_eval.py --model qwen3.5:9b
    python eval/run_eval.py --model mistral-small-latest
    python eval/run_eval.py --all-models       # Run all models
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import init_database, validate_sql
from src.llm import generate_response, MODEL_REGISTRY


def load_dataset() -> list[dict]:
    path = Path(__file__).parent / "dataset.json"
    return json.loads(path.read_text(encoding="utf-8"))


def evaluate_question(question: dict, model_id: str, db_conn) -> dict:
    """Evaluate a single question and return results."""
    result = {
        "id": question["id"],
        "question": question["question"],
        "model": model_id,
        "success": False,
        "type_match": False,
        "sql_match": False,
        "sql_valid": False,
        "generated_sql": None,
        "response_type": None,
        "error": None,
        "latency_ms": 0,
    }

    messages = [{"role": "user", "content": question["question"]}]

    t0 = time.time()
    try:
        response = generate_response(messages, model_id=model_id)
        result["latency_ms"] = int((time.time() - t0) * 1000)
    except Exception as e:
        result["error"] = str(e)
        result["latency_ms"] = int((time.time() - t0) * 1000)
        return result

    result["response_type"] = response.get("type")
    result["generated_sql"] = response.get("sql")

    # Check type match
    result["type_match"] = response.get("type") == question["expected_type"]

    # Check SQL pattern match
    if response.get("sql") and question.get("expected_sql_pattern"):
        result["sql_match"] = bool(
            re.search(question["expected_sql_pattern"], response["sql"], re.IGNORECASE)
        )

    # Check SQL validity
    if response.get("sql"):
        try:
            validate_sql(response["sql"])
            db_conn.execute(f"EXPLAIN QUERY PLAN {response['sql']}")
            result["sql_valid"] = True
        except Exception as e:
            result["error"] = f"SQL invalid: {e}"

    # Overall success
    result["success"] = result["type_match"] and result["sql_match"] and result["sql_valid"]

    return result


def run_evaluation(model_id: str, dataset: list[dict], db_conn) -> list[dict]:
    """Run evaluation for a single model."""
    results = []
    for i, question in enumerate(dataset):
        print(f"  [{i+1}/{len(dataset)}] {question['question'][:50]}...", end=" ", flush=True)
        result = evaluate_question(question, model_id, db_conn)
        status = "OK" if result["success"] else "FAIL"
        print(f"{status} ({result['latency_ms']}ms)")
        results.append(result)
    return results


def print_summary(results: list[dict], model_id: str):
    """Print evaluation summary."""
    total = len(results)
    success = sum(1 for r in results if r["success"])
    type_match = sum(1 for r in results if r["type_match"])
    sql_match = sum(1 for r in results if r["sql_match"])
    sql_valid = sum(1 for r in results if r["sql_valid"])
    avg_latency = sum(r["latency_ms"] for r in results) / total if total > 0 else 0

    print(f"\n{'=' * 60}")
    print(f"Model: {model_id}")
    print(f"{'=' * 60}")
    print(f"  Total questions:   {total}")
    print(f"  Overall success:   {success}/{total} ({100*success/total:.0f}%)")
    print(f"  Type match:        {type_match}/{total} ({100*type_match/total:.0f}%)")
    print(f"  SQL pattern match: {sql_match}/{total} ({100*sql_match/total:.0f}%)")
    print(f"  SQL valid:         {sql_valid}/{total} ({100*sql_valid/total:.0f}%)")
    print(f"  Avg latency:       {avg_latency:.0f}ms")

    # Show failures
    failures = [r for r in results if not r["success"]]
    if failures:
        print(f"\n  Failures:")
        for f in failures:
            print(f"    #{f['id']}: {f['question'][:50]}...")
            if not f["type_match"]:
                print(f"      Type: expected={f.get('expected_type', '?')}, got={f['response_type']}")
            if not f["sql_match"]:
                print(f"      SQL pattern not matched")
            if f["error"]:
                print(f"      Error: {f['error']}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate Prisme")
    parser.add_argument("--model", type=str, default=None, help="Model ID to evaluate")
    parser.add_argument("--all-models", action="store_true", help="Evaluate all models")
    parser.add_argument("--output", type=str, default=None, help="Output JSON file path")
    args = parser.parse_args()

    print("Loading database...")
    db_conn = init_database()
    dataset = load_dataset()
    print(f"Loaded {len(dataset)} evaluation questions.\n")

    models = list(MODEL_REGISTRY.keys()) if args.all_models else [args.model or "qwen3.5:9b"]
    all_results = {}

    for model_id in models:
        print(f"\nEvaluating model: {model_id}")
        print("-" * 40)
        results = run_evaluation(model_id, dataset, db_conn)
        print_summary(results, model_id)
        all_results[model_id] = results

    # Save results
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(__file__).parent / "results.json"

    output_path.write_text(json.dumps(all_results, indent=2, default=str), encoding="utf-8")
    print(f"\nResults saved to {output_path}")

    db_conn.close()


if __name__ == "__main__":
    main()
