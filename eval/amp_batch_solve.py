import asyncio
import json
import os
from pathlib import Path
import threading

from amp_sdk import AmpOptions, execute

# Thread-safe file writing
file_lock = threading.Lock()


async def solve_task(
    question: str, difficulty: str, task_idx: int, total: int, semaphore: asyncio.Semaphore
) -> dict:
    """Solve a single task using Amp SDK."""
    async with semaphore:
        print(f"[{task_idx}/{total}] Starting: {question[:60]}...")
        
        messages = []
        solution = None
        
        try:
            async for message in execute(
                question,
                AmpOptions(
                    cwd=os.getcwd(),
                    visibility="workspace",
                    dangerously_allow_all=True,
                ),
            ):
                messages.append(message.model_dump())
                
                # Extract the final text response as solution
                if message.type == "assistant":
                    content = message.message.get("content", [])
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            solution = item.get("text")
                elif message.type == "result":
                    if message.result:
                        solution = message.result
            
            print(f"[{task_idx}/{total}] ✓ Done: {question[:60]}...")
            return {
                "question": question,
                "difficulty": difficulty,
                "solution": solution,
                "messages": messages,
            }
        except Exception as e:
            print(f"[{task_idx}/{total}] ✗ Error: {e}")
            return {
                "question": question,
                "difficulty": difficulty,
                "solution": None,
                "messages": messages,
                "error": str(e),
            }


def write_result(output_path: Path, result: dict):
    """Thread-safe write to output file."""
    with file_lock:
        with open(output_path, "a") as f:
            f.write(json.dumps(result) + "\n")


async def main():
    # Load tasks
    tasks_path = Path(__file__).parent / "generated_tasks_with_difficulty.json"
    with open(tasks_path) as f:
        tasks = json.load(f)
    
    # Output file - clear it first
    output_path = Path(__file__).parent / "solved_tasks.jsonl"
    output_path.write_text("")
    
    # Semaphore to limit concurrency
    max_concurrent = 20
    semaphore = asyncio.Semaphore(max_concurrent)
    
    total = len(tasks)
    print(f"Processing {total} tasks with {max_concurrent} concurrent agents...")
    
    async def process_and_save(question: str, difficulty: str, idx: int):
        result = await solve_task(question, difficulty, idx, total, semaphore)
        write_result(output_path, result)
        return result
    
    # Create all tasks
    coroutines = [
        process_and_save(question, difficulty, i + 1)
        for i, (question, difficulty) in enumerate(tasks.items())
    ]
    
    # Run all concurrently (semaphore limits actual parallelism)
    results = await asyncio.gather(*coroutines, return_exceptions=True)
    
    successful = sum(1 for r in results if isinstance(r, dict) and "error" not in r)
    print(f"\nCompleted: {successful}/{total} successful")
    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
