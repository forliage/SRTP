import json
import os
import time

import yaml
from config.config import Config
from ant_api.utils import (
    get_default_config,
    ask_chatgpt
)
from utils import encode_image_from_path
from utils import revise_line_breaks
from utils import get_command_string
from utils import print_response


configs = Config.get_instance().config_data

class Agent:
    def __init__(
        self, 
        observation_space: list[str] = ["Screen_A11Y"], 
        action_space: str = "pyautogui",
        uuid: str = "",
        step: int = 0,
        related_app: str = "",
    ) -> None:
        self.observation_space = observation_space
        self.action_space = action_space
        self.uuid = uuid
        self.step = step
        self.action_history = []
        self.log_path = f"{configs['LOG_ROOT']}/{uuid}/"
        # 仅探索时有用，将以后的subtask传进去，避免重复
        self.existing_subtasks = []
        self.related_app = related_app # Not needed during inference
        self.taskbar_apps = ["File Explorer", "Settings", "Microsoft Store", "Microsoft To Do", "Mail", "Calendar", "People", "Maps", "Sticky Notes", "Media Player", "Photos", "Snipping Tool", "Record Screen - FREE", "Paint", "Microsoft Clipchamp", "Adobe Photoshop Express", "Power Automate", "Calculator", "Recipe Keeper"]

    def get_prompt_message(self, observation: dict) -> list[dict]:
        """
        Get the prompt message for the agent by loading prompt templates, API documentation, and examples.
        
        Returns:
            list[dict]: A list of dictionaries containing the system and user prompts with:
                - API documentation for available actions
                - Example interactions and responses
                - Formatted templates for consistent prompting
        """
        if self.observation_space == ["Screen_A11Y"]:
            path = configs["PROMPT_PATH"]
            if os.path.exists(path):
                prompt = yaml.safe_load(open(path, "r", encoding="utf-8"))
            else:
                raise FileNotFoundError(f"Prompt template not found at {path}")
            
            # Load API template and construct API list
            api_prompt_template = yaml.safe_load(open(configs["API_PATH"], "r", encoding="utf-8"))
            api_list = [
                "- The action types for UI elements are: {actions}.".format(
                    actions=list(api_prompt_template.keys())
                )
            ]
            
            for key in api_prompt_template.keys():
                api = api_prompt_template[key]
                api_text = "{summary}\n{usage}".format(
                    summary=api["summary"], usage=api["usage"]
                )
                api_list.append(api_text)

            # Load example template and construct example list
            example_prompt_template = yaml.safe_load(open(configs["EXAMPLE_PATH"], "r", encoding="utf-8"))
            template = """
            [User Request]:
                {request}
            [Response]:
                {response}"""
            
            example_list = []
            for key in example_prompt_template.keys():
                if key.startswith("example"):
                    example = template.format(
                        request=example_prompt_template[key].get("Request"),
                        response=json.dumps(
                            example_prompt_template[key].get("Response")
                        ),
                    )
                    example_list.append(example)
            example_list += [json.dumps(example)]

            # Construct system and user content
            system_content = prompt['system'].format(
                apis=api_list,
                examples=example_list,
            )
            
            user_content = []
            if self.observation_space == ["Screen_A11Y"]:
                if configs["INCLUDE_LAST_SCREENSHOT"] and self.step > 0:
                    user_content.append({"type": "text", "text": "Screenshot for the last step, the red box annotated the control selected in the previous step:"})
                    user_content.append({"type": "image_url", "image_url": {"url": encode_image_from_path(observation["screen"]["annotated_screenshot"])}})
                if configs["CONCAT_SCREENSHOT"]:
                    user_content.append({"type": "text", "text": "Current Screenshot(left) and Annotated Screenshot(right):"})
                    user_content.append({"type": "image_url", "image_url": {"url": encode_image_from_path(observation["screen"]["concat_screenshot"])}})
                else:
                    user_content.append({"type": "text", "text": "Current Screenshots:"})
                    user_content.append({"type": "image_url", "image_url": {"url": encode_image_from_path(observation["screen"]["raw_screenshot"])}})
                    user_content.append({"type": "text", "text": "Annotated Screenshot:"})
                    user_content.append({"type": "image_url", "image_url": {"url": encode_image_from_path(observation["screen"]["annotated_screenshot"])}})
            subtasks_path = os.path.join(configs["LOG_ROOT"], f"{self.related_app}_subtasks.json")
            if not os.path.exists(subtasks_path):
                with open(subtasks_path, 'w', encoding='utf-8') as f:
                    json.dump([], f, ensure_ascii=False)
            with open(subtasks_path, 'r', encoding='utf-8') as f:
                dic = json.load(f)
            existing_subtasks = dic
            if os.path.exists(os.path.join(configs["DOCUMENT_PATH"], f"{self.related_app}.md")):
                document = open(os.path.join(configs["DOCUMENT_PATH"], f"{self.related_app}.md"), 'r', encoding='utf-8').read()
            else:
                document = ""
            user_content.append(
                {
                    "type": "text",
                    "text": prompt['user'].format(
                        control_item=observation['a11y'],
                        action_history=self.action_history,
                        related_app=self.related_app,
                        document=document,
                        existing_subtasks=existing_subtasks,
                    ),
                }
            )

            prompt_message = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ]
            prompt = json.dumps(
                {
                    "step": self.step,
                    "prompt": prompt_message,
                }
            )
            prompt_path = self.log_path + f"action_step{self.step}_prompt.json"
            with open(prompt_path, 'w') as f:
                f.write(prompt)

            # 把第一步的label提取出来，为了get_response时第一步选app时使用
            for control in observation['a11y']:
                if self.step == 0 and control['control_text'] == self.related_app and control['control_type'] == "Button":
                    self.label = control['label']
                elif self.related_app not in self.taskbar_apps and self.step == 0 and control['control_text'] == self.related_app and control['control_type'] == "ListItem":
                    self.label = control['label']
            return prompt_message

    def get_response(self, prompt_message: list[dict]) -> None:
        # 对于第一步选择app的特殊处理
        if self.step == 0:
            if self.related_app in self.taskbar_apps:
                response_json = {
                    "Status": "CONTINUE", 
                    "Observation": "There are many application icons on the taskbar, and I need to select the correct application to complete the task.", 
                    "Thought": "To design subtasks, I need to first click the '{application}' button to open the corresponding application and explore the environment.".format(application=self.related_app), 
                    "ControlLabel": "{label}".format(label=self.label), 
                    "ControlText": "{application}".format(application=self.related_app), 
                    "Function": "click_input", 
                    "Args": {"button": "left", "double": False}, 
                    "GeneratedSubtask": {}
                }
            else:
                response_json = {
                    "Status": "CONTINUE", 
                    "Observation": "There are many application icons on the desktop, and I need to select the correct application to complete the task.", 
                    "Thought": "To design subtasks, I need to first double click the '{application}' desktop icon to open the corresponding application and explore the environment.".format(application=self.related_app), 
                    "ControlLabel": "{label}".format(label=self.label), 
                    "ControlText": "{application}".format(application=self.related_app), 
                    "Function": "click_input", 
                    "Args": {"button": "left", "double": True}, 
                    "GeneratedSubtask": {}
                }
        else:
            for i in range(configs["RETRY_TIMES"]):
                try:
                    try:

                        # Ant API
                        param = get_default_config(model="gpt-4o")
                        param["queryConditions"]["model"] = "gpt-4o"
                        param["queryConditions"]["temperature"] = "0.6"
                        param["queryConditions"]["messages"] = prompt_message
                        response = ask_chatgpt(param)
                    except Exception as e:
                        print("LLM encountered an error while generating a response...")
                        raise e
                    try:
                        if response[0] == '`':
                            response = response[7:-3]
                        response_json = json.loads(response)
                        assert response_json != None
                        assert response_json.get("Function", "") in ["click_input", "keyboard_input", "wheel_mouse_input", ""]
                        assert response_json.get("Status", "") in ["CONTINUE", "FINISH"]
                    except Exception as e:
                        print("LLM encountered an error while parsing a response...")
                        raise e
                except Exception as e:
                    print(e)
                    print("Retrying...")
                    time.sleep(5)
                else:
                    break

        # Save the response message.
        response = json.dumps({
                "step": self.step,
                "response": response_json,
            }
        )
        response_path = self.log_path + f"action_step{self.step}_response.json"
        with open(response_path, 'w') as f:
            f.write(response)
        control_label = response_json.get("ControlLabel", "")
        control_text = response_json.get("ControlText", "")
        operation = response_json.get("Function", "")
        args = revise_line_breaks(response_json.get("Args", ""))
        status = response_json.get("Status", "")
        generated_subtask = response_json.get("GeneratedSubtask", {})
        if generated_subtask != {}:
            subtasks_path = os.path.join(configs["LOG_ROOT"], f"{self.related_app}_subtasks.json")
            with open(subtasks_path, 'r', encoding='utf-8') as f:
                existing_subtasks = json.load(f)
            
            # Calculate similarity with existing subtasks
            should_add = True
            for existing in existing_subtasks:                    
                # Calculate multiple similarity metrics
                # 1. Word overlap similarity
                existing_words = set(existing["instruction_template"].lower().split())
                new_words = set(generated_subtask["instruction_template"].lower().split())
                common_words = existing_words.intersection(new_words)
                jaccard_sim = len(common_words) / len(existing_words.union(new_words))
                
                # 2. Length ratio similarity
                len_ratio = min(len(existing_words), len(new_words)) / max(len(existing_words), len(new_words))
                
                # 3. Sequential word matching
                existing_seq = existing["instruction_template"].lower().split()
                new_seq = generated_subtask["instruction_template"].lower().split()
                seq_matches = sum(1 for i in range(min(len(existing_seq), len(new_seq))) 
                                if existing_seq[i] == new_seq[i])
                seq_sim = seq_matches / min(len(existing_seq), len(new_seq))
                
                # Combined similarity score with weights
                similarity = (0.5 * jaccard_sim + 0.3 * len_ratio + 0.2 * seq_sim)
                
                # More strict threshold and additional conditions
                if (similarity > 0.6 or  # Lower threshold but multiple metrics
                    jaccard_sim > 0.7 or # High word overlap
                    seq_sim > 0.8):      # High sequential match
                    should_add = False
                    break
            
            if should_add:
                generated_subtask["path"] = self.log_path
                generated_subtask["related_app"] = self.related_app
                generated_subtask["id"] = self.uuid
                existing_subtasks.append(generated_subtask)
                with open(subtasks_path, 'w', encoding='utf-8') as f:
                    json.dump(existing_subtasks, f, ensure_ascii=False)
        # Compose the function call and the arguments string.
        action = {
            "control_label": control_label,
            "operation": operation,
            "args": args,
        }
        print_response(response_json)
        self.action_history.append({"control_text": control_text, "action": get_command_string(operation, args)})

        return action, status

    def get_action(self, observation: dict) -> dict:
        prompt_message = self.get_prompt_message(observation)
        action, status = self.get_response(prompt_message)

        return action, status


