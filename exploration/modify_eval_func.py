import os
import json
import concurrent.futures
from ant_api.utils import (
    get_default_config,
    ask_chatgpt
)

eval_funcs_dir = r"D:\data\eval_functions"

system_prompt = """You are a helpful assistant that modifies Python evaluation functions to include progress percentage. 
Your task is to add a progress percentage to each return statement, indicating how much of the task has been completed up to that point.
Only modify the return statements - do not change any other code. The progress percentage should be added as a third element in the EvalResult tuple.
The progress percentage should be expressed as a simple division expression, where the numerator represents the number of return statements encountered before this point, and the denominator represents the total number of return False statements in the code."""

example_func = """from collections import namedtuple

EvalResult = namedtuple('EvalResult', ['success', 'message'])

def evaluate_agent_task_completion(artist_name: str) -> EvalResult:
    # Check if the artist name was typed in the search field
    if not check_keyboard_types(text=artist_name):
        return EvalResult(False, f"Subtask execution failed because the artist name '{artist_name}' was not typed in the search field.")
    
    # Check if the artist was found and clicked
    if not check_mouse_clicks(text=artist_name):
        return EvalResult(False, f"Subtask execution failed because the artist '{artist_name}' was not clicked.")
    
    # Check if the share link was copied
    if not clipboard_contains_text():
        return EvalResult(False, "Subtask execution failed because the share link was not copied to the clipboard.")
    
    # All checks passed, subtask is considered complete
    return EvalResult(True, "Subtask completed successfully")"""

example_response = """from collections import namedtuple

EvalResult = namedtuple('EvalResult', ['success', 'message', 'progress'])

def evaluate_agent_task_completion(artist_name: str) -> EvalResult:
    # Check if the artist name was typed in the search field
    if not check_keyboard_types(text=artist_name):
        return EvalResult(False, f"Subtask execution failed because the artist name '{artist_name}' was not typed in the search field.", 0/3)
    
    # Check if the artist was found and clicked
    if not check_mouse_clicks(text=artist_name):
        return EvalResult(False, f"Subtask execution failed because the artist '{artist_name}' was not clicked.", 1/3)
    
    # Check if the share link was copied
    if not clipboard_contains_text():
        return EvalResult(False, "Subtask execution failed because the share link was not copied to the clipboard.", 2/3)
    
    # All checks passed, subtask is considered complete
    return EvalResult(True, "Subtask completed successfully", 3/3)"""

def process_file(txt_path):
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            eval_func = f.read()
            
            prompt_message = [
                {
                    "role": "system", 
                    "content": system_prompt
                },
                {
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": "Here is an example evaluation function:"},
                        {"type": "text", "text": example_func}
                    ]
                },
                {
                    "role": "assistant",
                    "content": example_response
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Please modify this evaluation function:"},
                        {"type": "text", "text": eval_func}
                    ]
                }
            ]

            param = get_default_config(model="gpt-4o")
            param["queryConditions"]["model"] = "gpt-4o"
            param["queryConditions"]["temperature"] = "0.0"
            param["queryConditions"]["messages"] = prompt_message
            
            while True:
                try:
                    modified_func = ask_chatgpt(param)
                    if modified_func[0] == "`":
                        modified_func = modified_func[9:-4]
                    break
                except Exception as e:
                    print(f"Error processing {txt_path}: {str(e)}")
            
            # Save the modified function back to file
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(modified_func)
                
    except Exception as e:
        print(f"Error processing {txt_path}: {str(e)}")

# Walk through all txt files in eval_functions directory and process them in parallel
txt_files = []
for root, dirs, files in os.walk(eval_funcs_dir):
    for file in files:
        if file.endswith('.txt') and len(file) == len("00e7d84b-41f5-868e-1f07-48589820205b.txt"):
            txt_path = os.path.join(root, file)
            txt_files.append(txt_path)

# Use ThreadPoolExecutor to process files in parallel
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
    executor.map(process_file, txt_files)