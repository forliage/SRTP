# input: 1. directory_path = "D:\\data\\DAG_with_succ_topo_batch1"
#        2. subtasks_file = "D:\\data\\all_task.json"
# output: 1. consistent_dir = "D:\\data\\consistent_task_DAG_batch1"
#         2. inconsistent_dir = "D:\\data\\inconsistent_task_DAG_batch1"
# ----------------------------------------------------------------------------------------

# 从具有成功轨迹的DAG中进行一致校验
from ant_api.utils import (
    get_default_config,
    ask_chatgpt
)
import json
import os
from typing import Dict, List, Tuple
import networkx as nx
from concurrent.futures import ThreadPoolExecutor, as_completed
import shutil
from tqdm import tqdm

def load_subtasks(subtasks_file: str) -> Dict[str, Dict]:
    """Load subtask information from JSON file and index by ID."""
    with open(subtasks_file, 'r', encoding='utf-8') as f:
        subtasks = json.load(f)
    return {task["id"]: task for task in subtasks}

SYSTEM_PROMPT = """You are a task analysis expert. Your job is to analyze a task instruction and its subtasks to determine the dependencies between subtasks to form a directed acyclic graph (DAG).

Given:
1. A main task instruction that describes what needs to be accomplished
2. A set of subtasks that can be used to complete the main task

Follow these steps:
1. Understand the main task instruction and what it's trying to achieve
2. For each subtask, analyze:
   - What inputs it requires
   - What outputs it produces
   - How it contributes to the main task

3. Determine the dependencies between subtasks based on:
   - Data flow: when one subtask's output is another's input
   - Logical sequence: when tasks must happen in a specific order
   - Resource constraints: when tasks compete for the same resources

Output your analysis in this JSON format:
{
    "nodes": [
        "subtask_id_1",
        "subtask_id_2",
        ...
    ],
    "edges": {
        "subtask_id_1": [list of subtask IDs that directly depend on this subtask],
        "subtask_id_2": [list of subtask IDs that directly depend on this subtask],
        ...
    }
}

Ensure your analysis:
- Captures all necessary dependencies between subtasks
- Maintains correct dependency relationships
- Forms a valid DAG (no cycles)
- Uses the provided subtask IDs exactly as given
- Creates a sequence that fulfills the main task instruction
"""

def create_prompt(task_instruction: str, subtasks: Dict[str, Dict]) -> List[Dict]:
    # Format subtask information for the LLM
    subtask_descriptions = []
    for task_id, task_info in subtasks.items():
        desc = f"Subtask ID: {task_id}\n"
        desc += f"Instruction: {task_info['instruction_template']}"
        subtask_descriptions.append(desc)
    
    subtask_text = "\n\n".join(subtask_descriptions)
    
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": """Given this task instruction:
"Take an Excel file, translate its content to French, and save it as a Word document."

And these subtasks:

Subtask ID: task1
Instruction: Open '{xlsx_path}', select all data, and copy it.

Subtask ID: task2
Instruction: Translate the text in clipboard to '{target_language}'.

Subtask ID: task3
Instruction: Open '{docx_path}', paste the text from clipboard, and save it.

Please determine the dependencies between these subtasks to accomplish the main task."""},
        {"role": "assistant", "content": """{
    "nodes": [
        "task1",
        "task2",
        "task3"
    ],
    "edges": {
        "task1": ["task2"],
        "task2": ["task3"],
        "task3": []
    }
}"""},
        {"role": "user", "content": f"""Given this task instruction:
{task_instruction}

And these subtasks:

{subtask_text}

Please determine the dependencies between these subtasks to accomplish the main task."""}
    ]

def call_llm(messages: List[Dict]) -> Dict:
    param = get_default_config(model="gpt-4o")
    param["queryConditions"]["model"] = "gpt-4o"
    param["queryConditions"]["temperature"] = "0.0"
    param["queryConditions"]["messages"] = messages

    while True:
        try:
            response = ask_chatgpt(param)
            if response[0] == "`":
                response = response[7:-3]
            response = json.loads(response)
            break
        except Exception as e:
            if "mosn" not in str(e):
                # print(response)
                print(subtasks)
                print(f"Error during LLM call: {str(e)}")
    return response

def compare_graphs(original_dag: Dict, generated_dag: Dict) -> Tuple[bool, str]:
    # Convert both DAGs to networkx graphs for comparison
    G1 = nx.DiGraph()
    G2 = nx.DiGraph()
    
    # Add nodes and edges from original DAG
    for node in original_dag["nodes"]:
        G1.add_node(node)
    for node, edges in original_dag["edges"].items():
        for target in edges:
            G1.add_edge(node, target)
    
    # Add nodes and edges from generated DAG
    for node in generated_dag["nodes"]:
        G2.add_node(node)
    for node, edges in generated_dag["edges"].items():
        for target in edges:
            G2.add_edge(node, target)
    
    # Compare graph structures
    is_isomorphic = nx.is_isomorphic(G1, G2)
    
    # Generate detailed message
    if is_isomorphic:
        message = "DAG structures are consistent - same number of nodes and identical dependency patterns"
    else:
        g1_nodes, g2_nodes = len(G1.nodes), len(G2.nodes)
        g1_edges, g2_edges = len(G1.edges), len(G2.edges)
        message = f"DAG structures differ - Original: {g1_nodes} nodes, {g1_edges} edges; Generated: {g2_nodes} nodes, {g2_edges} edges"
    
    return is_isomorphic, message

def verify_single_dag(args: Tuple[str, str, str, str]) -> Tuple[str, Dict]:
    """Verify a single DAG file and return results.
    
    Args:
        args: Tuple of (file_path, subtasks_file, consistent_dir, inconsistent_dir)
    
    Returns:
        Tuple of (filename, result_dict)
    """
    file_path, subtasks_file, consistent_dir, inconsistent_dir = args
    filename = os.path.basename(file_path)
    
    try:
        # Load subtasks information
        subtasks = load_subtasks(subtasks_file)
        
        # Read the task JSON file
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract original DAG and task instruction
        original_dag = data["dag"]
        is_consistent = True
        message = ""
        
        if original_dag == {} or original_dag["nodes"] == [] or original_dag["edges"] == {}:
            is_consistent = False
            message = "DAG is empty"
        else:
            task_instruction = data["task_instruction"]
            
            # Get relevant subtasks for this task
            task_subtasks = {node_id: subtasks[node_id] for node_id in original_dag["nodes"]}
            
            # Generate new DAG using LLM
            messages = create_prompt(task_instruction, task_subtasks)
            generated_dag = call_llm(messages)
            
            # Check if generated DAG is empty
            if generated_dag == {} or generated_dag["nodes"] == [] or generated_dag["edges"] == {}:
                is_consistent = False
                message = "Generated DAG is empty"
            else:
                # Compare the DAGs
                is_consistent, message = compare_graphs(original_dag, generated_dag)
        
        # Copy file to appropriate output directory
        if is_consistent:
            os.makedirs(consistent_dir, exist_ok=True)
            output_path = os.path.join(consistent_dir, filename)
            shutil.copy2(file_path, output_path)
        else:
            os.makedirs(inconsistent_dir, exist_ok=True)
            output_path = os.path.join(inconsistent_dir, filename)
            shutil.copy2(file_path, output_path)
        
        return filename, {
            "is_consistent": is_consistent,
            "message": message
        }
    except Exception as e:
        # For exceptions, still copy to inconsistent directory
        os.makedirs(inconsistent_dir, exist_ok=True)
        output_path = os.path.join(inconsistent_dir, filename)
        shutil.copy2(file_path, output_path)
        
        return filename, {
            "is_consistent": False,
            "message": f"Error during verification: {str(e)}"
        }

def verify_batch(directory_path: str, subtasks_file: str, consistent_dir: str = None, inconsistent_dir: str = None, max_workers: int = 32) -> Dict:
    """Verify multiple DAG files in parallel.
    
    Args:
        directory_path: Path to directory containing DAG files
        subtasks_file: Path to subtasks JSON file
        consistent_dir: Directory to save consistent DAGs
        inconsistent_dir: Directory to save inconsistent DAGs
        max_workers: Maximum number of parallel threads
    
    Returns:
        Dictionary of verification results
    """
    results = {}
    
    # Get list of already processed files
    processed_files = set()
    if consistent_dir and os.path.exists(consistent_dir):
        processed_files.update(f for f in os.listdir(consistent_dir) if f.endswith('.json'))
    if inconsistent_dir and os.path.exists(inconsistent_dir):
        processed_files.update(f for f in os.listdir(inconsistent_dir) if f.endswith('.json'))
    
    # Prepare list of files to process
    files_to_process = []
    skipped_files = []
    for filename in os.listdir(directory_path):
        if not (filename.endswith('.json') and filename[:-5].isdigit()):
            continue
            
        if filename in processed_files:
            skipped_files.append(filename)
            results[filename] = {
                "is_consistent": True,
                "message": "Skipped - Already processed"
            }
            continue
            
        file_path = os.path.join(directory_path, filename)
        files_to_process.append((file_path, subtasks_file, consistent_dir, inconsistent_dir))
    
    # if skipped_files:
    #     print(f"\nSkipping {len(skipped_files)} already processed files:")
    #     for filename in skipped_files:
    #         print(f"  • {filename}")
    
    if not files_to_process:
        print("\nNo new files to process.")
        return results
    
    # Process files in parallel with progress bar
    print(f"\nProcessing {len(files_to_process)} new files...")
    for i in files_to_process:
        print(i[0])
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(verify_single_dag, args) for args in files_to_process]
        
        with tqdm(total=len(files_to_process), desc="Verifying DAGs") as pbar:
            for future in as_completed(futures):
                filename, result = future.result()
                results[filename] = result
                pbar.update(1)
    
    return results

if __name__ == "__main__":
    directory_path = "D:\\data\\[explicit_app]DAG_with_both_topo_batch1"
    subtasks_file = "D:\\data\\all_task.json"
    consistent_dir = "D:\\data\\[explicit_app]consistent_task_DAG_batch1"
    inconsistent_dir = "D:\\data\\[explicit_app]inconsistent_task_DAG_batch1"
    
    # Create output directories if they don't exist
    os.makedirs(consistent_dir, exist_ok=True)
    os.makedirs(inconsistent_dir, exist_ok=True)
    
    results = verify_batch(directory_path, subtasks_file, consistent_dir, inconsistent_dir, max_workers=8)
    
    # Print results summary
    print("\nVerification Results:")
    total_count = len(results)
    skipped_count = sum(1 for result in results.values() if result["message"] == "Skipped - Already processed")
    processed_count = total_count - skipped_count
    consistent_count = sum(1 for result in results.values() if result["is_consistent"])
    
    if processed_count > 0:
        print(f"\nProcessed {processed_count} new files:")
        print(f"• {consistent_count - skipped_count}/{processed_count} new DAGs are semantically consistent")
    
    print(f"\nOverall Summary:")
    print(f"• Total files: {total_count}")
    print(f"• Already processed: {skipped_count}")
    print(f"• Newly processed: {processed_count}")
    print(f"• Total consistent: {consistent_count}")
    print(f"\nConsistent DAGs have been saved to: {consistent_dir}")
    print(f"Inconsistent DAGs have been saved to: {inconsistent_dir}")
    
    # # Print detailed results
    # print("\nDetailed Results:")
    # for filename, result in sorted(results.items()):
    #     status = "✓" if result["is_consistent"] else "✗"
    #     print(f"{status} {filename}: {result['message']}")