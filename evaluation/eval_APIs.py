from rapidfuzz import fuzz
import json
import os
import easyocr
import requests
from config.config import Config

configs = Config.get_instance().config_data

def get_trajectory_path():
    trajectory_id = configs['TRAJECTORY_ID']
    log_root = configs["LOG_ROOT"]
    trajectory_path = f"{log_root}{trajectory_id}/"
    return trajectory_path

def parse_actions():
    trajectory_path = get_trajectory_path()
    actions = []
    # Traverse all files ending in 'response.json' in the trajectory path.
    for filename in os.listdir(trajectory_path):
        if filename.endswith("response.json"):
            file_path = os.path.join(trajectory_path, filename)
            with open(file_path, 'r') as f:
                data = json.load(f)
            actions.append({"ControlText": data['response']['ControlText'], "Function": data['response']['Function'], "Args": data['response']['Args']})
            # print(data['response']['ControlText'])  # File Explorer
            # print(data['response']['Function'])  # click_input
            # print(data['response']['Args'])  # {'button': 'left', 'double': False}
    return actions

def fuzzy_match(str1, str2, threshold=60):
    similarity = fuzz.ratio(str1, str2)
    if similarity >= threshold:
        return True
    return False

def fuzzy_in(str1, str2, threshold=60):
    len_str1 = len(str1)
    for i in range(len(str2) - len_str1 + 1):
        substring = str2[i:i + len_str1]
        similarity = fuzz.ratio(str1, substring)
        if similarity >= threshold:
            return True
    return False

def check_mouse_clicks(text: str) -> bool:
    """Checks if the mouse has clicked on the specified text.
    Parameters
    ---------
    text: str
        The text associated with the click.
    Returns
    ---------
    bool
        True if the mouse has clicked on the specified text, False otherwise.
    Examples
    ---------
    >>> # Evaluate if the agent has successfully set the picture 'envelope.png' as background
    >>> from collections import namedtuple
    >>> EvalResult = namedtuple('EvalResult', ['success', 'message'])
    >>> def evaluate_agent_task_completion() -> EvalResult:
    >>>     if not check_mouse_clicks(text='envelope.png'):
    >>>         return EvalResult(False, "Subtask execution failed because did not click on 'envelope.png'.")
    >>>     if not check_mouse_clicks(text='set as background'):
    >>>         return EvalResult(False, "Subtask execution failed because did not click on 'set as background'.")
    >>>     return EvalResult(True, "Subtask completed successfully")
    """
    actions = parse_actions()
    for action in actions:
        if (action['Function'] == "click_input" and
            fuzzy_match(text.upper(), action['ControlText'].upper())):
            return True
    return False

def check_keyboard_types(text: str) -> bool:
    """Checks if the keyboard has typed the specified text.
    Parameters
    ---------
    text: str
        The text to be typed.
    Returns
    ---------
    bool
        True if the keyboard has typed the specified text, False otherwise.
    Examples
    ---------
    >>> # Evaluate if the agent has successfully typed 'Hello, World!'
    >>> from collections import namedtuple
    >>> EvalResult = namedtuple('EvalResult', ['success', 'message'])
    >>> def evaluate_agent_task_completion() -> EvalResult:
    >>>     if not check_keyboard_types(text='Hello, World!'):
    >>>         return EvalResult(False, "Subtask execution failed because text 'Hello, World!' was not typed.")
    >>>     return EvalResult(True, "Subtask completed successfully")
    """
    actions = parse_actions()
    for action in actions:
        if (action['Function'] == "keyboard_input" and
            fuzzy_match(text.upper(), action['Args']['keys'].upper())):
            return True
    return False

def check_file_exists(file_path: str) -> bool:
    """Checks if the specified file exists.
    Parameters
    ---------
    file_path: str
        The path to the file to be checked.
    Returns
    ---------
    bool
        True if the file exists, False otherwise.
    Examples
    ---------
    >>> # Evaluate if the agent has successfully renamed 'cat.jpg' to 'cute cat.jpg'
    >>> from collections import namedtuple
    >>> EvalResult = namedtuple('EvalResult', ['success', 'message'])
    >>> def evaluate_agent_task_completion() -> EvalResult:
    >>>     # Check if original file no longer exists
    >>>     if check_file_exists(file_path='C:/Users/user/Desktop/images/cat.jpg'):
    >>>         return EvalResult(False, "Subtask execution failed because original file 'cat.jpg' still exists.")
    >>>     # Check if new file exists
    >>>     if not check_file_exists(file_path='C:/Users/user/Desktop/images/cute cat.jpg'):
    >>>         return EvalResult(False, "Subtask execution failed because renamed file 'cute cat.jpg' was not found.")
    >>>     # All checks passed, task completed
    >>>     return EvalResult(True, "Subtask completed successfully")
    """
    IP = configs['VM_IP']
    command = f"IF EXIST \"{file_path}\" (echo True) ELSE (echo False)"
    payload = {
        "shell": True,  
        "command": command
    }
    response = requests.post(f"http://{IP}:5000/execute", json=payload)
    response = response.json()
    assert response['status'] == 'success'
    return eval(response["output"])

def check_text_exists_via_ocr(text: str) -> bool:
    """Checks if the specified text is present in the last screenshot using OCR (Optical Character Recognition).
    Parameters
    ---------
    text: str
        The text to be checked.
    Returns
    ---------
    bool
        True if the text is present in the last screenshot, False otherwise.
    Examples
    ---------
    >>> # Evaluate if the agent has successfully set the clock to '9:00 AM'
    >>> from collections import namedtuple
    >>> EvalResult = namedtuple('EvalResult', ['success', 'message'])
    >>> def evaluate_agent_task_completion() -> EvalResult:
    >>>     # Check if the time exists in the window
    >>>     if not check_text_exists_via_ocr(text='9:00 AM'):
    >>>         return EvalResult(False, "Subtask execution failed because time '9:00 AM' was not found.")
    >>>     # All checks passed, task completed
    >>>     return EvalResult(True, "Subtask completed successfully")
    """
    actions = parse_actions()
    step_num = len(actions)
    trajectory_path = get_trajectory_path()
    last_screenshot_path = os.path.join(trajectory_path, f"action_step{step_num-1}.png")
    reader = easyocr.Reader(['en'])
    ocr_result = reader.readtext(last_screenshot_path, detail=0)
    ocr_result = ' '.join(ocr_result)
    return fuzzy_in(text.upper(), ocr_result.upper())

def check_text_exists_via_control(text: str) -> bool:
    """Checks if the specified text is present in the last screenshot through control information.
    Parameters
    ---------
    text: str
        The text to be checked.
    Returns
    ---------
    bool
        True if the text is present in the last screenshot, False otherwise.
    Examples
    ---------
    >>> # Evaluate if the agent has successfully input the code 'print("Hello World!")'
    >>> from collections import namedtuple
    >>> EvalResult = namedtuple('EvalResult', ['success', 'message'])
    >>> def evaluate_agent_task_completion() -> EvalResult:
    >>>     # Check if the code exists in the window
    >>>     if not check_text_exists_via_control(text='print("Hello World!")'):
    >>>         return EvalResult(False, "Subtask execution failed because code 'print(\"Hello World!\")' was not found.")
    >>>     # All checks passed, task completed
    >>>     return EvalResult(True, "Subtask completed successfully")
    """
    actions = parse_actions()
    step_num = len(actions)
    trajectory_path = get_trajectory_path()
    last_control_path = os.path.join(trajectory_path, f"action_step{step_num-1}_controls_info.json")
    with open(last_control_path, 'r') as f:
        control_info = json.load(f)
    control_titles = [control['title'] for control in control_info]
    control_titles = ' '.join(control_titles)
    return fuzzy_in(text.upper(), control_titles.upper())

def check_text_exists(text: str) -> bool:
    """Checks if the specified text is included in the last screenshot.
    Parameters
    ---------
    text: str
        The text to be checked.
    Returns
    ---------
    bool
        True if the text is present in the last screenshot, False otherwise.
    Examples
    ---------
    >>> # Evaluate if the agent has successfully created a new folder named 'Project Files'
    >>> from collections import namedtuple
    >>> EvalResult = namedtuple('EvalResult', ['success', 'message'])
    >>> def evaluate_agent_task_completion() -> EvalResult:
    >>>     # Check if the folder name exists in the window
    >>>     if not check_text_exists(text='Project Files'):
    >>>         return EvalResult(False, "Subtask execution failed because folder 'Project Files' was not found.")
    >>>     # All checks passed, task completed
    >>>     return EvalResult(True, "Subtask completed successfully")
    """
    return check_text_exists_via_ocr(text) or check_text_exists_via_control(text)

def clipboard_contains_text() -> bool:
    """Checks if the clipboard contains text.
    Returns
    ---------
    bool
        True if the clipboard contains text, False otherwise.
    Examples
    ---------
    >>> # Evaluate if the agent has successfully opened the note and copied all the text
    >>> from collections import namedtuple
    >>> EvalResult = namedtuple('EvalResult', ['success', 'message'])
    >>> def evaluate_agent_task_completion() -> EvalResult:
    >>>     # Check if there is text in clipboard
    >>>     if not clipboard_contains_text():
    >>>         return EvalResult(False, "Subtask execution failed because no text was found in clipboard.")
    >>>     # All checks passed, task completed
    >>>     return EvalResult(True, "Subtask completed successfully")
    """
    IP = configs['VM_IP']
    command = 'python -c "import win32clipboard; win32clipboard.OpenClipboard(); result = win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT) or win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_TEXT); win32clipboard.CloseClipboard(); print(result,end=\'\')"'
    payload = {
        "shell": True,
        "command": command
    }
    response = requests.post(f"http://{IP}:5000/execute", json=payload)
    response = response.json()
    assert response['status'] == 'success'
    return eval(response["output"])

def clipboard_contains_image() -> bool:
    """Checks if the clipboard contains an image.
    Returns
    ---------
    bool
        True if the clipboard contains an image, False otherwise.
    Examples
    ---------
    >>> # Evaluate if the agent has successfully copied the picture
    >>> from collections import namedtuple
    >>> EvalResult = namedtuple('EvalResult', ['success', 'message'])
    >>> def evaluate_agent_task_completion() -> EvalResult:
    >>>     # Check if there is an image in clipboard
    >>>     if not clipboard_contains_image():
    >>>         return EvalResult(False, "Subtask execution failed because no image was found in clipboard.")
    >>>     # All checks passed, task completed
    >>>     return EvalResult(True, "Subtask completed successfully")
    """
    IP = configs['VM_IP']
    command = 'python -c "import win32clipboard; win32clipboard.OpenClipboard(); result = win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_DIB); win32clipboard.CloseClipboard(); print(result,end=\'\')"'
    payload = {
        "shell": True,
        "command": command
    }
    response = requests.post(f"http://{IP}:5000/execute", json=payload)
    response = response.json()
    assert response['status'] == 'success'
    return eval(response["output"])

def clipboard_contains_file() -> bool:
    """Checks if the clipboard contains file paths.
    Returns
    ---------
    bool
        True if the clipboard contains file paths, False otherwise.
    Examples
    ---------
    >>> # Evaluate if the agent has successfully copied the file
    >>> from collections import namedtuple
    >>> EvalResult = namedtuple('EvalResult', ['success', 'message'])
    >>> def evaluate_agent_task_completion() -> EvalResult:
    >>>     # Check if there is a file in clipboard
    >>>     if not clipboard_contains_file():
    >>>         return EvalResult(False, "Subtask execution failed because no file was found in clipboard.")
    >>>     # All checks passed, task completed
    >>>     return EvalResult(True, "Subtask completed successfully")
    """
    IP = configs['VM_IP']
    command = 'python -c "import win32clipboard; win32clipboard.OpenClipboard(); result = win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_HDROP); win32clipboard.CloseClipboard(); print(result,end=\'\')"'
    payload = {
        "shell": True,
        "command": command
    }
    response = requests.post(f"http://{IP}:5000/execute", json=payload)
    response = response.json()
    assert response['status'] == 'success'
    return eval(response["output"])

def get_clipboard_text() -> str:
    """Retrieves text from the clipboard.
    Returns
    ---------
    str
        The text from the clipboard.
    Examples
    ---------
    >>> # Evaluate if the agent has successfully copied the image url
    >>> from collections import namedtuple
    >>> EvalResult = namedtuple('EvalResult', ['success', 'message'])
    >>> def evaluate_agent_task_completion() -> EvalResult:
    >>>     # Check if there is text in clipboard
    >>>     if not clipboard_contains_text():
    >>>         return EvalResult(False, "Subtask execution failed because no text was found in clipboard.")
    >>>     # Get the text from clipboard
    >>>     clipboard_text = get_clipboard_text()
    >>>     if not clipboard_text:
    >>>         return EvalResult(False, "Subtask execution failed because could not get text from clipboard.")
    >>>     # Check if text is a URL
    >>>     if not clipboard_text.startswith(('http://', 'https://')):
    >>>         return EvalResult(False, "Subtask execution failed because clipboard text is not a valid URL.")
    >>>     # All checks passed, task completed
    >>>     return EvalResult(True, "Subtask completed successfully")
    """
    IP = configs['VM_IP']
    command = 'python -c "import pyperclip; print(pyperclip.paste(), end=\'\')"'
    payload = {
        "shell": True,
        "command": command
    }
    response = requests.post(f"http://{IP}:5000/execute", json=payload)
    response = response.json()
    assert response['status'] == 'success'
    return response["output"]

def get_clipboard_file_name() -> str:
    """Retrieves file name from the clipboard.
    Returns
    ---------
    str
        The file name from the clipboard.
    Examples
    ---------
    >>> # Evaluate if the agent has successfully copied the '{file_path}'
    >>> import os
    >>> from collections import namedtuple
    >>> EvalResult = namedtuple('EvalResult', ['success', 'message'])
    >>> def evaluate_agent_task_completion(file_path: str) -> EvalResult:
    >>>     # Extract the file name
    >>>     file_path = file_path.rstrip('/\\')
    >>>     file_name = os.path.basename(file_path)
    >>>     # Check if there is a file in clipboard
    >>>     if not clipboard_contains_file():
    >>>         return EvalResult(False, "Subtask execution failed because no file was found in clipboard.")
    >>>     # Get the file name from clipboard
    >>>     file_name_in_clipboard = get_clipboard_file_name()
    >>>     if not file_name_in_clipboard:
    >>>         return EvalResult(False, "Subtask execution failed because could not get file name from clipboard.")
    >>>     # If file path is provided, check if file name matches
    >>>     expected_name = os.path.basename(file_path)
    >>>     if expected_name != file_name_in_clipboard:
    >>>         return EvalResult(False, f"Subtask execution failed because clipboard file name '{file_name_in_clipboard}' does not match expected '{expected_name}'.")
    >>>     # All checks passed, task completed
    >>>     return EvalResult(True, "Subtask completed successfully")
    """
    IP = configs['VM_IP']
    command = 'python -c "import win32clipboard; import os; win32clipboard.OpenClipboard(); file_names = win32clipboard.GetClipboardData(win32clipboard.CF_HDROP); print(os.path.basename(file_names[0]), end=\'\'); win32clipboard.CloseClipboard()"'
    payload = {
        "shell": True,
        "command": command
    }
    response = requests.post(f"http://{IP}:5000/execute", json=payload)
    response = response.json()
    assert response['status'] == 'success'
    return response["output"]
