# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import base64
import mimetypes
import os
from abc import ABC, abstractmethod
from io import BytesIO
from typing import Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont, ImageGrab

from config.config import Config

configs = Config.get_instance().config_data

class PhotographerFacade:
    @staticmethod
    def encode_image_from_path(image_path: str, mime_type: Optional[str] = None) -> str:
        """
        Encode an image file to base64 string.
        :param image_path: The path of the image file.
        :param mime_type: The mime type of the image.
        :return: The base64 string.
        """

        file_name = os.path.basename(image_path)
        mime_type = (
            mime_type if mime_type is not None else mimetypes.guess_type(file_name)[0]
        )
        with open(image_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode("ascii")

        if mime_type is None or not mime_type.startswith("image/"):
            print(
                "Warning: mime_type is not specified or not an image mime type. Defaulting to png."
            )
            mime_type = "image/png"

        image_url = f"data:{mime_type};base64," + encoded_image
        return image_url
