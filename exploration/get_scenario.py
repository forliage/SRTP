import os
import json
from ant_api.utils import (
    get_default_config,
    ask_chatgpt
)

task_dir = r"D:\data\[explicit_app]task_DAG_batch1"
task_files = [f for f in os.listdir(task_dir) if f.endswith('.json')]

# Define system prompt for task scenario classification
system_prompt = """You are a task scenario classifier. Your job is to analyze task intents and classify them into appropriate scenarios.
Common scenarios include but are not limited to:
- Video Conferencing (e.g., scheduling/joining meetings, sharing screens)
- Code Development (e.g., writing/debugging/reviewing code)
- News Query (e.g., searching/reading/summarizing news)
- Document Creation (e.g., writing reports, creating presentations)
- Data Analysis (e.g., processing data, creating visualizations)
- Email Management (e.g., composing/reading emails)

Please output your classification in the following JSON format:
{
    "scenario": "Video Conferencing"
}

Here's an example:
Input: "schedule a team meeting for next week"
Output: {
    "scenario": "Video Conferencing"
}"""

def process_task_file(task_file):
    task_path = os.path.join(task_dir, task_file)
    with open(task_path, 'r', encoding='utf-8') as f:
        task_data = json.load(f)
        task_intent = task_data.get('task_intent')

    prompt_message = [
        {
            "role": "system", 
            "content": system_prompt
        },
        {
            "role": "user", 
            "content": [
                {"type": "text", "text": f"Please classify the following task intent into an appropriate scenario category.\nTask Intent: {task_intent}"}
            ]
        }
    ]

    param = get_default_config(model="gpt-4o")
    param["queryConditions"]["model"] = "gpt-4o"
    param["queryConditions"]["temperature"] = "0.7"
    param["queryConditions"]["messages"] = prompt_message
    
    while True:
        try:
            response = ask_chatgpt(param)
            if response[0] == "`":
                response = response[7:-4]
            scenario_data = json.loads(response)
            return scenario_data["scenario"]
        except json.JSONDecodeError:
            print(f"Error parsing response for {task_file}: {response}")
        except Exception as e:
            print(f"Error processing {task_file}: {str(e)}")

scenarios = set()

# Process files sequentially
for task_file in task_files:
    try:
        scenario = process_task_file(task_file)
        if scenario:
            scenarios.add(scenario)
            print(f"\nProcessed {task_file}")
            print("Current unique scenarios:")
            print(list(scenarios))
    except Exception as e:
        print(f"Task {task_file} generated an exception: {str(e)}")

# Output final unique scenarios as a list
print("\nFinal unique scenarios found:")
print(list(scenarios))
