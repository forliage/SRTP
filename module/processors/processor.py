# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


import json
import os
import time
import requests
from logging import Logger
from typing import Dict, List, Optional, Tuple
import subprocess

import utils
from agent.agent import AppAgent, HostAgent
from agent.basic import MemoryItem
from config.config import Config
from module import interactor
from module.processors.basic import BaseProcessor
from module.state import Status
from ant_api.utils import (
    get_default_config,
    ask_chatgpt
)

configs = Config.get_instance().config_data
BACKEND = configs["CONTROL_BACKEND"]

class HostAgentProcessor(BaseProcessor):
    """
    The processor for the host agent at a single step.
    """

    def __init__(
        self,
        round_num: int,
        log_path: str,
        request: str,
        application: str,
        host_agent: HostAgent,
        round_step: int,
        session_step: int,
        prev_status: str,
        app_window=None,
        required_resources: str=""
    ) -> None:
        """
        Initialize the host agent processor.
        :param round_num: The total number of rounds in the session.
        :param log_path: The log path.
        :param request: The user request.
        :param request_logger: The logger for the request string.
        :param logger: The logger for the response and error.
        :param host_agent: The host agent to process the session.
        :param round_step: The number of steps in the round.
        :param session_step: The global step of the session.
        :param prev_status: The previous status of the session.
        :param app_window: The application window.
        """

        super().__init__(
            round_num=round_num,
            log_path=log_path,
            request=request,
            application=application,
            round_step=round_step,
            session_step=session_step,
            prev_status=prev_status,
            app_window=app_window,
            required_resources=required_resources
        )

        self.host_agent = host_agent

        self._desktop_screen_url = None
        self._desktop_windows_dict = None
        self._desktop_windows_info = None
        self.app_to_open = None

    def print_step_info(self) -> None:
        """
        Print the step information.
        """
        utils.print_with_color(
            "Round {round_num}, Step {step}: Selecting an application.".format(
                round_num=self.round_num + 1, step=self.round_step + 1
            ),
            "magenta",
        )

    def capture_screenshot(self) -> None:
        """
        Capture the screenshot.
        """
        pass

    def get_control_info(self) -> None:
        """
        Get the control information.
        """

        # Get all available windows on the desktop, into a dictionary with format {index: application object}.
        self._desktop_windows_dict = self.control_inspector.get_desktop_app_dict(
            remove_empty=True
        )

        # Get the textual information of all windows.
        self._desktop_windows_info = self.control_inspector.get_desktop_app_info(
            self._desktop_windows_dict
        )

    def get_prompt_message(self) -> None:
        """
        Get the prompt message.
        """

        # Get the request and action history of the host agent.
        request_history = self.host_agent.get_request_history_memory().to_json()
        action_history = self.host_agent.get_global_action_memory().to_json()

        # Get the previous plan from the memory. If the memory is empty, set the plan to an empty string.
        agent_memory = self.host_agent.memory
        if agent_memory.length > 0:
            plan = agent_memory.get_latest_item().to_dict()["Plan"]
        else:
            plan = []

        # Construct the prompt message for the host agent.
        self._prompt_message = self.host_agent.message_constructor(
            [self._desktop_screen_url],
            request_history,
            action_history,
            self._desktop_windows_info,
            plan,
            self.request,
        )

        # Log the prompt message. Only save them in debug mode.
        log = json.dumps(
            {
                "step": self.round_step,
                "prompt": self._prompt_message,
                "control_items": self._desktop_windows_info,
                "filted_control_items": self._desktop_windows_info,
                "status": "",
            }
        )
        self.request_logger.debug(log)

    def get_and_parse_response(self) -> None:
        pass
        # """
        # Get the response from the LLM.
        # """

        # # Try to get the response from the LLM. If an error occurs, catch the exception and log the error.
        # try:
        #     self._response, self._cost = self.host_agent.get_response(
        #         self._prompt_message, "HOSTAGENT", use_backup_engine=True
        #     )
        # except Exception:
        #     self.llm_error_handler()

    def parse_response(self) -> None:
        """
        Parse the response.
        """

        # Try to parse the response. If an error occurs, catch the exception and log the error.
        try:
            # self._response_json = self.host_agent.response_to_dict(self._response)
            self._response_json = {
                "Status": "CONTINUE",
                "Plan": [],
                "ControlText": CONTROL_NAME
            }

        except Exception:
            self.general_error_handler()

        self.control_label = self._response_json.get("ControlLabel", "")
        self._control_text = self._response_json.get("ControlText", "")
        self._plan = self._response_json.get("Plan", "")
        self._status = self._response_json.get("Status", "")
        self.app_to_open = self._response_json.get("AppsToOpen", None)

        self.host_agent.print_response(self._response_json)

        if (
            Status.FINISH in self._status.upper()
            or self._control_text == ""
            and self.app_to_open is None
        ):
            self._status = Status.FINISH

    def execute_action(self) -> None:
        pass

    def update_memory(self) -> None:
        """
        Update the memory of the Agent.
        """

        # Create a memory item for the host agent at the current step.
        host_agent_step_memory = MemoryItem()

        # Log additional information for the host agent.
        additional_memory = {
            "Step": self.session_step,
            "RoundStep": self.get_process_step(),
            "AgentStep": self.host_agent.get_step(),
            "Round": self.round_num,
            "ControlLabel": self._control_text,
            "Action": "set_focus()",
            "ActionType": "UIControl",
            "Request": self.request,
            "Agent": "HostAgent",
            "AgentName": self.host_agent.name,
            "Application": self.app_root,
            "Cost": self._cost,
            "Results": "",
        }

        host_agent_step_memory.set_values_from_dict(self._response_json)
        host_agent_step_memory.set_values_from_dict(additional_memory)
        self.host_agent.add_memory(host_agent_step_memory)

        # Log the memory item.
        self.log(host_agent_step_memory.to_dict())

        # Only memorize the keys in the HISTORY_KEYS list to feed into the prompt message in the future steps.
        memorized_action = {
            key: host_agent_step_memory.to_dict().get(key)
            for key in configs["HISTORY_KEYS"]
        }
        self.host_agent.add_global_action_memory(memorized_action)

    def update_status(self) -> None:
        """
        Update the status of the session.
        """
        self.host_agent.update_step()
        self.host_agent.update_status(self._status)

        # Wait for the application to be ready after an action is taken before proceeding to the next step.
        if self._status != Status.FINISH:
            time.sleep(configs["SLEEP_TIME"])
    
    def should_create_subagent(self) -> bool:
        """
        Check if the app agent should be created.
        :return: The boolean value indicating if the app agent should be created.
        """

        # Only create the app agent when the previous status is APP_SELECTION and the processor is HostAgentProcessor.
        if (
            isinstance(self, HostAgentProcessor)
            and self.prev_status == Status.APP_SELECTION
        ):
            return True
        else:
            return False

    def create_sub_agent(self) -> AppAgent:
        """
        Create the app agent.
        :return: The app agent.
        """

        # Create the app agent.
        app_agent = self.host_agent.create_subagent(
            "app",
            "AppAgent/{root}/{process}".format(
                root=self.app_root, process=self._control_text
            ),
            self._control_text,
            self.app_root,
            configs["APP_AGENT"]["VISUAL_MODE"],
            configs["APPAGENT_PROMPT"],
            configs["APPAGENT_EXAMPLE_PROMPT"],
            configs["API_PROMPT"],
        )

        # Create the COM receiver for the app agent.
        if configs.get("USE_APIS", False):
            app_agent.Puppeteer.receiver_manager.create_com_receiver(
                self.app_root, self._control_text
            )

        # Provision the context for the app agent, including the all retrievers.
        self.app_agent_context_provision(app_agent)

        return app_agent

    def app_agent_context_provision(self, app_agent: AppAgent) -> None:
        """
        Provision the context for the app agent.
        :param app_agent: The app agent to provision the context.
        """

class AppAgentProcessor(BaseProcessor):
    """
    The processor for the app agent at a single step.
    """

    def __init__(
        self,
        round_num: int,
        log_path: str,
        request: str,
        application: str,
        app_agent: AppAgent,
        round_step: int,
        session_step: int,
        process_name: str,
        app_window: str,
        control_reannotate: Optional[list],
        prev_status: str,
        required_resources: str
    ) -> None:
        """
        Initialize the app agent processor.
        :param round_num: The total number of rounds in the session.
        :param log_path: The log path.
        :param request: The user request.
        :param request_logger: The logger for the request string.
        :param logger: The logger for the response and error.
        :param app_agent: The app agent to process the current step.
        :param round_step: The number of steps in the round.
        :param session_step: The global step of the session.
        :param process_name: The process name.
        :param app_window: The application window.
        :param control_reannotate: The list of controls to reannotate.
        :param prev_status: The previous status of the session.
        """

        super().__init__(
            round_num=round_num,
            log_path=log_path,
            request=request,
            application=application,
            round_step=round_step,
            session_step=session_step,
            prev_status=prev_status,
            app_window=app_window,
            required_resources=required_resources
        )

        self.app_agent = app_agent
        self.process_name = process_name

        self._annotation_dict = None
        self._control_info = None
        self._operation = None
        self._args = None
        self._image_url = []
        self.prev_plan = []
        self._control_reannotate = control_reannotate
        self.filtered_annotation_dict = None

        def send_python_code_to_server(python_code):
            command = f"python -c \"{python_code}\""
            payload = {
                "shell": True,  
                "command": command
            }
            while True:
                try:
                    self.IP = self._get_vm_ip()
                    response = requests.post(f"http://{self.IP}:5000/execute", json=payload)
                    if response.status_code == 200:
                        break
                    else:
                        print("status code != 200")
                        print(response.text)
                        time.sleep(5)
                except Exception as e:
                    print("exception when execute code...")
                    print(e)
                    time.sleep(5)

        self.taskbar_apps = ["File Explorer", "Settings", "Microsoft Store", "Microsoft To Do", "Mail", "Calendar", "People", "Maps", "Sticky Notes", "Media Player", "Photos", "Snipping Tool", "Record Screen - FREE", "Paint", "Microsoft Clipchamp", "Adobe Photoshop Express", "Power Automate", "Calculator", "Recipe Keeper"]
        
        if self.round_step == 0:
            # Initialize the first state.
            if application not in self.taskbar_apps:
                send_python_code_to_server("import pyautogui; screen_width, screen_height = pyautogui.size(); center_x = screen_width // 2; center_y = screen_height // 2; pyautogui.moveTo(center_x, center_y); pyautogui.click()")
            # Initialize required resources.
            if self.required_resources == "text_in_clipboard":
                send_python_code_to_server("import pyperclip; pyperclip.copy('''it's a nice day today''')")
            elif self.required_resources == "code_in_clipboard":
                send_python_code_to_server("import pyperclip; pyperclip.copy('''print('15/7=', 15/7)''')")
            elif self.required_resources == "img_in_clipboard":
                send_python_code_to_server(r"from PIL import Image; import win32clipboard; import io; image = Image.open(r'C:\Users\user\Desktop\image\feast.jpg'); output = io.BytesIO(); image.save(output, 'BMP'); data = output.getvalue()[14:]; output.close(); win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard(); win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data); win32clipboard.CloseClipboard()")
            elif self.required_resources == "file_in_clipboard":
                send_python_code_to_server(r"import win32clipboard, win32con, struct, sys, os; absolute_paths = [os.path.abspath(r'C:\Users\user\Desktop\music\corporate inspiring.mp3')]; DROPFILES_STRUCT_SIZE = 20; pFiles = DROPFILES_STRUCT_SIZE; dropfiles = struct.pack('<IiiI', pFiles, 0, 0, 1); file_list = '\0'.join(absolute_paths) + '\0\0'; file_list_utf16 = file_list.encode('utf-16le'); data = dropfiles + file_list_utf16; win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard(); win32clipboard.SetClipboardData(win32con.CF_HDROP, data); win32clipboard.CloseClipboard()")

    def _execute_command(self, command: List[str]) -> None:
        def _is_contained_in(a, b):
            for v in set(a):
                if a.count(v) > b.count(v):
                    return False
            return True

        # Specially handled for the `vmrun` command in Windows
        if _is_contained_in(["vmrun", "-T", "ws", "start"], command):
            p = subprocess.Popen(command)
            p.wait()
        else:
            result = subprocess.run(command, stdout=subprocess.PIPE, timeout=60, text=True, encoding="utf-8")
            
            return result.stdout
        
    # Get VM IP address.    
    def _get_vm_ip(self):    
        max_retries = 20
        for _ in range(max_retries):
            try:
                output = self._execute_command(["vmrun", "-T", "ws", "-vp", "gdcB/2O3/p2bB4H9V1+n", "getGuestIPAddress", configs["VM_PATH"], "-wait"]).strip()
                return output
            except Exception as e:
                print(e)
                time.sleep(5)
        raise Exception("Failed to get VM IP address!")
    
    def print_step_info(self) -> None:
        """
        Print the step information.
        """
        utils.print_with_color(
            "Step {step}:".format(
                step=self.round_step,
            ),
            "magenta",
        )

    def capture_screenshot(self) -> None:
        """
        Capture the screenshot.
        """

        # Define the paths for the screenshots saved.
        screenshot_save_path = self.log_path + f"action_step{self.session_step}.png"
        annotated_screenshot_save_path = self.log_path + f"action_step{self.session_step}_annotated.png"
        concat_screenshot_save_path = self.log_path + f"action_step{self.session_step}_concat.png"
        while True:
            try:
                self.IP = self._get_vm_ip()
                response = requests.get("http://"+self.IP+":5000/get_observation")
                if response.status_code == 200:
                    break
                else:
                    print("status code != 200")
                    print(response.text)
                    time.sleep(5)
            except Exception as e:
                print("exception when get_observation...")
                print(e)
                time.sleep(5)
        while True:
            try:
                self.IP = self._get_vm_ip()
                response = requests.get("http://"+self.IP+":5000/raw_screenshot")
                if response.status_code == 200:
                    with open(screenshot_save_path, 'wb') as f:
                        f.write(response.content)
                    break
                else:
                    print("status code != 200")
                    print(response.text)
                    time.sleep(5)
            except Exception as e:
                print("exception when get_raw_screenshot...")
                print(e)
                time.sleep(5)
        while True:
            try:
                time.sleep(5)
                self.IP = self._get_vm_ip()
                response = requests.get("http://"+self.IP+":5000/annotated_screenshot")
                if response.status_code == 200:
                    with open(annotated_screenshot_save_path, 'wb') as f:
                        f.write(response.content)
                    break
                else:
                    print("status code != 200")
                    print(response.text)
                    time.sleep(5)
            except Exception as e:
                print("exception when get_annotated_screenshot...")
                print(e)
                time.sleep(5)
        while True:
            try:
                self.IP = self._get_vm_ip()
                response = requests.get("http://"+self.IP+":5000/concat_screenshot")
                if response.status_code == 200:
                    with open(concat_screenshot_save_path, 'wb') as f:
                        f.write(response.content)
                    break
                else:
                    print("status code != 200")
                    print(response.text)
                    time.sleep(5)
            except Exception as e:
                print("exception when get_concat_screenshot...")
                print(e)
                time.sleep(5)

        # If the configuration is set to include the last screenshot with selected controls tagged, save the last screenshot.
        if configs["INCLUDE_LAST_SCREENSHOT"]:
            last_control_screenshot_save_path = (
                self.log_path
                + f"action_step{self.session_step-1}_selected_controls.png"
            )
            if os.path.exists(last_control_screenshot_save_path):
                self._image_url += [
                    self.photographer.encode_image_from_path(
                        last_control_screenshot_save_path
                    )
                ]

        # Whether to concatenate the screenshots of clean screenshot and annotated screenshot into one image.
        if configs["CONCAT_SCREENSHOT"]:
            self._image_url += [
                self.photographer.encode_image_from_path(concat_screenshot_save_path)
            ]
        else:
            screenshot_url = self.photographer.encode_image_from_path(
                screenshot_save_path
            )
            screenshot_annotated_url = self.photographer.encode_image_from_path(
                annotated_screenshot_save_path
            )
            self._image_url += [screenshot_url, screenshot_annotated_url]

    def get_control_info(self) -> None:
        """
        Get the control information.
        """

        # Get the control information for the control items and the filtered control items, in a format of list of dictionaries.
        controls_info_save_path = self.log_path + f"action_step{self.session_step}_controls_info.json"
        while True:
            try:
                self.IP = self._get_vm_ip()
                response = requests.get("http://"+self.IP+":5000/controls_info")
                if response.status_code == 200:
                    if len(response.json()) == 0:
                        self.send_python_code_to_server("import pyautogui; screen_width, screen_height = pyautogui.size(); center_x = screen_width // 2; center_y = screen_height // 2; pyautogui.moveTo(center_x, center_y); pyautogui.click()")
                        assert False
                    with open(controls_info_save_path, 'w') as f:
                        json.dump(response.json(), f)
                    break                
                else:
                    print("status code != 200")
                    print(response.text)
                    time.sleep(5)
            except Exception as e:
                print("exception when get_controls_info...")
                print(e)
                time.sleep(5)
        # Load the JSON file sent by the server.
        with open(controls_info_save_path, 'r') as f:
            controls = json.load(f)
            self._control_info = []
            for control in controls:
                dic = {}
                dic['label'] = control['id']
                dic['control_text'] = control['title']
                dic['control_type'] = control['control_type']
                self._control_info.append(dic)
        
        # The filtering operation is handled by the server.
        with open(controls_info_save_path, 'r') as f:
            controls = json.load(f)
            self.filtered_control_info = []
            for control in controls:
                dic = {}
                dic['label'] = control['id']
                dic['control_text'] = control['title']
                dic['control_type'] = control['control_type']
                dic['parent_control_text'] = control['parent_title']
                dic['parent_control_type'] = control['parent_control_type']
                self.filtered_control_info.append(dic)
                if self.round_step == 0 and control['title'] == self.application and control['control_type'] == "Button":
                    self.label = control['id']
                elif self.application not in self.taskbar_apps and self.round_step == 0 and control['title'] == self.application and control['control_type'] == "ListItem":
                    self.label = control['id']
                    
    def get_prompt_message(self) -> None:
        """
        Get the prompt message for the AppAgent.
        """

        # Get the action history and request history of the host agent and feed them into the prompt message.
        host_agent = self.app_agent.get_host()
        action_memory = host_agent.get_global_action_memory()
        action_history = [item.to_dict() for item in action_memory._content if item is not None]
        request_history = host_agent.get_request_history_memory().to_json()

        # Construct the prompt message for the AppAgent.
        self._prompt_message = self.app_agent.message_constructor(
            self._image_url,
            request_history,
            action_history,
            self.filtered_control_info,
            self.prev_plan,
            self.request,
            configs["INCLUDE_LAST_SCREENSHOT"],
            configs["CONCAT_SCREENSHOT"],
            self.round_step
        )
        # Save the prompt message.
        prompt = json.dumps(
            {
                "step": self.session_step,
                "prompt": self._prompt_message,
            }
        )
        prompt_path = self.log_path + f"action_step{self.session_step}_prompt.json"
        with open(prompt_path, 'w') as f:
            f.write(prompt)

    def get_and_parse_response(self) -> None:
        """
        Get and parse the response.
        """
        if self.round_step == 0:
            if self.application in self.taskbar_apps:
                self._response_json = {
                    "Status": "CONTINUE", 
                    "Observation": "There are many application icons on the taskbar, and I need to select the correct application to complete the task.", 
                    "Thought": "To fulfill '{request}', I need to first click the '{application}' button to open the corresponding application.".format(request=self.request, application=self.application), 
                    "ControlLabel": "{label}".format(label=self.label), 
                    "ControlText": "{application}".format(application=self.application), 
                    "Function": "click_input", 
                    "Args": {"button": "left", "double": False}, 
                }
            else:
                self._response_json = {
                    "Status": "CONTINUE", 
                    "Observation": "There are many application icons on the desktop, and I need to select the correct application to complete the task.", 
                    "Thought": "To fulfill '{request}', I need to first double click the '{application}' desktop icon to open the corresponding application.".format(request=self.request, application=self.application), 
                    "ControlLabel": "{label}".format(label=self.label), 
                    "ControlText": "{application}".format(application=self.application), 
                    "Function": "click_input", 
                    "Args": {"button": "left", "double": True}, 
                }
        else:
            while True:
                try:
                    try:
                        # # Original calling of LLM API. 
                        # self._response, self._cost = self.app_agent.get_response(
                        #     self._prompt_message, "APPAGENT", use_backup_engine=False
                        # )

                        # Ant API
                        param = get_default_config(model="gpt-4o")
                        param["queryConditions"]["model"] = "gpt-4o"
                        param["queryConditions"]["temperature"] = "0.0"
                        param["queryConditions"]["messages"] = self._prompt_message
                        self._response = ask_chatgpt(param)
                        self._cost = 0.0
                        # self._response = input("The response of LLM：")
                    except Exception as e:
                        print("LLM encountered an error while generating a response...")
                        raise e
                    try:
                        self._response_json = self.app_agent.response_to_dict(self._response)
                        assert self._response_json != None
                        assert self._response_json.get("Function", "") in ["click_input", "keyboard_input", "wheel_mouse_input", ""]
                        assert self._response_json.get("Status", "") in ["CONTINUE", "FINISH"]
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
                "step": self.session_step,
                "response": self._response_json,
            }
        )
        response_path = self.log_path + f"action_step{self.session_step}_response.json"
        with open(response_path, 'w') as f:
            f.write(response)
        self._control_label = self._response_json.get("ControlLabel", "")
        self._control_text = self._response_json.get("ControlText", "")
        self._operation = self._response_json.get("Function", "")
        self._args = utils.revise_line_breaks(self._response_json.get("Args", ""))
        self._plan = self._response_json.get("Plan", "")
        self._status = self._response_json.get("Status", "")
        # Compose the function call and the arguments string.
        self._action = self.app_agent.Puppeteer.get_command_string(
            self._operation, self._args
        )
        self.app_agent.print_response(self._response_json)

    def execute_action(self) -> None:
        """
        Execute the action.
        """
        while True:
            try:
                self.IP = self._get_vm_ip()
                payload = json.dumps({"control_label": self._control_label, "operation": self._operation, "args": self._args})
                headers = {
                    'Content-Type': 'application/json'
                }
                response = requests.post("http://"+self.IP+":5000/execute_action", headers=headers, data=payload, timeout=90)
                if response.status_code == 200:
                    break
                else:
                    print("status code != 200")
                    print(response.text)
                    requests.get("http://"+self.IP+":5000/get_observation")
                    time.sleep(5)
            except Exception as e:
                print(e)
                print("exception when execute_action...")
                time.sleep(5)
        # The process of opening the application may take some time.
        if self.round_step == 0:
            time.sleep(configs['FIRST_STEP_WAIT_TIME'])
            # if self.application == "Microsoft To Do":
            #     time.sleep(60)
        self.capture_control_screenshot()

    def capture_control_screenshot(self) -> None:
        """
        Capture the screenshot of the selected control.
        :param control_selected: The selected control item.
        """
        control_screenshot_save_path = (
            self.log_path + f"action_step{self.session_step}_selected_controls.png"
        )
        while True:
            self.IP = self._get_vm_ip()
            response = requests.get("http://"+self.IP+":5000/action_screenshot")
            if response.status_code == 200:
                with open(control_screenshot_save_path, 'wb') as f:
                    f.write(response.content)
                break
            print("fail to get action screenshot...")
            time.sleep(5)

    def handle_screenshot_status(self) -> None:
        """
        Handle the screenshot status when the annotation is overlapped and the agent is unable to select the control items.
        """

        if self._status.upper() == Status.SCREENSHOT:
            utils.print_with_color(
                "Annotation is overlapped and the agent is unable to select the control items. New annotated screenshot is taken.",
                "magenta",
            )
            self._control_reannotate = self.app_agent.Puppeteer.execute_command(
                "annotation", self._args, self._annotation_dict
            )
            if self._control_reannotate is None or len(self._control_reannotate) == 0:
                self._status = Status.CONTINUE
        else:
            self._control_reannotate = None

    def update_memory(self) -> None:
        """
        Update the memory of the Agent.
        """
        # Create a memory item for the app agent
        app_agent_step_memory = MemoryItem()

        app_root = self.application
        host_agent = self.app_agent.get_host()

        # Log additional information for the app agent.
        additional_memory = {
            "Step": self.session_step,
            "Action": self._action,
            "Request": self.request,
        }
        app_agent_step_memory.set_values_from_dict(self._response_json)
        app_agent_step_memory.set_values_from_dict(additional_memory)

        self.app_agent.add_memory(app_agent_step_memory)

        # Only memorize the keys in the HISTORY_KEYS list to feed into the prompt message in the future steps.
        memorized_action = {
            key: app_agent_step_memory.to_dict().get(key)
            for key in configs["HISTORY_KEYS"]
        }
        host_agent.add_global_action_memory(memorized_action)

    def update_status(self) -> None:
        """
        Update the status of the session.
        """

        self.app_agent.update_step()
        self.app_agent.update_status(self._status)

        if self._status != Status.FINISH:
            time.sleep(configs["SLEEP_TIME"])

    def _safe_guard_judgement(self, action: str, control_text: str) -> bool:
        """
        Safe guard for the session.
        action: The action to be taken.
        control_text: The text of the control item.
        return: The boolean value indicating whether to proceed or not.
        """

        # Ask the user whether to proceed with the action when the status is PENDING.
        decision = interactor.sensitive_step_asker(action, control_text)
        if not decision:
            utils.print_with_color("The user decide to stop the task.", "magenta")
            self._status = Status.FINISH
            return False

        # Handle the PENDING_AND_FINISH case
        elif len(self._plan) > 0 and Status.FINISH in self._plan[0]:
            self._status = Status.FINISH
        return True


    def get_prev_plan(self) -> str:
        """
        Retrieves the previous plan from the agent's memory.
        :return: The previous plan, or an empty string if the agent's memory is empty.
        """
        agent_memory = self.app_agent.memory

        if agent_memory.length > 0:
            prev_plan = agent_memory.get_latest_item().to_dict()["Plan"]
        else:
            prev_plan = []

        return prev_plan

