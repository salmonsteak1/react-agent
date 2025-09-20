"""Padlet API tools used by chat agents.

Provides a typed `update_padlet` tool that performs the HTTP update by calling
the Rails API, using a JWT supplied per run via `config.configurable.padlet_token`.
"""

from enum import Enum
from typing import Any
import os
import pprint

import aiohttp
from langchain_core.tools import tool
from langgraph.runtime import get_runtime
from pydantic import BaseModel, Field


class WallUpdateFailedError(Exception):
    """Raised when the wall update fails or returns an invalid response."""


class PadletFormat(str, Enum):
    WALL = "wall"
    STREAM = "stream"
    TIMELINE = "timeline"
    GRID = "grid"
    CANVAS = "canvas"
    MAP = "map"


class ReactionType(str, Enum):
    NONE = "none"
    LIKE = "like"
    VOTE = "vote"
    STAR = "star"
    GRADE = "grade"
    EMOJI = "emoji"


class WishColor(str, Enum):
    RED = "red"
    ORANGE = "orange"
    GREEN = "green"
    BLUE = "blue"
    PURPLE = "purple"
    WHITE = "white"


class AttachmentType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    LINK = "link"


class WallUpdateSectionData(BaseModel):
    section_id: str = Field(description="The id of the section")
    section_title: str = Field(description="The title of the section")


class WallUpdateCustomFieldValueData(BaseModel):
    field_name: str = Field(description="The name of the custom field")
    field_value: str = Field(description="The value of the custom field")


class WallUpdateLocationData(BaseModel):
    latitude: float = Field(
        description="The latitude of the location. If format is 'map' then all posts must have this, otherwise don't include it."
    )
    longitude: float = Field(
        description="The longitude of the location. If format is 'map' then all posts must have this, otherwise don't include it."
    )
    location_name: str = Field(description="The name of this specific location")


class WallUpdatePostData(BaseModel):
    post_id: str = Field(description="The id of the post")
    section_id: str | None = Field(None, description="The id of the section")
    subject: str | None = Field(description="The title of the post")
    body: str | None = Field(None, description="The content of the post")
    custom_field_values: list[WallUpdateCustomFieldValueData] | None = Field(
        description="The values of custom fields for the post. Only include if custom fields are present."
    )
    color: WishColor | None = Field(None, description="The color of the post")
    attachment_search: str | None = Field(
        None,
        description="Used to search google for an attachment. The media type of the result is determined by attachment_type.",
    )
    attachment_type: AttachmentType | None = Field(
        None,
        description="This determines the type of media that we search google for using attachment_search.",
    )
    location_data: WallUpdateLocationData | None = Field(
        None,
        description="If format is 'map' this must be included, otherwise don't include it. The location data of the specific physical location of the post.",
    )


class WallUpdateCustomFieldData(BaseModel):
    field_name: str = Field(description="The name of the custom field")


class WallUpdateSettingsData(BaseModel):
    format: PadletFormat | None = Field(None, description="The format of the padlet")
    sections_enabled: bool | None = Field(
        None, description="Whether sections are visible"
    )
    comments_enabled: bool | None = Field(
        None, description="Whether comments on posts are enabled"
    )
    reactions: ReactionType | None = Field(
        None,
        description="The reactions on posts. 'none' means reactions are disabled. Default to 'like'.",
    )
    add_custom_fields: list[WallUpdateCustomFieldData] | None = Field(
        None,
        description="Add custom fields that show up as named sub-sections in the body of each post. Only add custom fields if they serve a clear purpose.",
    )


class WallUpdateData(BaseModel):
    padlet_title: str | None = Field(None, description="The title of the padlet")
    padlet_description: str | None = Field(
        None, description="The description of the padlet"
    )
    wallpaper_description: str | None = Field(
        None,
        description="A description of the ideal wallpaper/background image for the padlet. Used to search for and update the wallpaper.",
    )
    sections: list[WallUpdateSectionData] | None = Field(
        None, description="The sections that contain posts"
    )
    section_order: list[str] | None = Field(
        None,
        description="A list of section ids in the order they should appear on the padlet",
    )
    posts: list[WallUpdatePostData] | None = Field(
        None, description="The posts that may belong to sections"
    )
    post_order: list[str] | None = Field(
        None,
        description="A list of post ids in the order they should appear on the padlet",
    )
    settings: WallUpdateSettingsData | None = Field(
        None, description="The settings for the padlet"
    )


class UpdatePadletArgs(BaseModel):
    wall_id: int = Field(description="The id of the wall to update.")
    wall_data: WallUpdateData = Field(
        description="The data to update the wall with, include only parameters relevant to the requested changes."
    )


# Remove keys with null values from a dictionary
def remove_none_values(obj):
    if isinstance(obj, dict):
        return {k: remove_none_values(v) for k, v in obj.items() if v is not None}
    elif isinstance(obj, list):
        return [remove_none_values(item) for item in obj]
    else:
        return obj


def _get_padlet_token_from_runtime() -> str | None:
    """Resolve Padlet JWT from the current run's config/context.

    Checks, in order:
      - runtime.config.configurable["padlet_token"] (dict or attr style)
      - runtime.context["padlet_token"] (dict or attr style)
    """
    runtime = get_runtime()

    # Try config.configurable.padlet_token
    try:
        config_obj = getattr(runtime, "config", None)
        configurable = None
        if isinstance(config_obj, dict):
            configurable = config_obj.get("configurable")
        else:
            configurable = getattr(config_obj, "configurable", None)

        if isinstance(configurable, dict):
            token = configurable.get("padlet_token")
        else:
            token = getattr(configurable, "padlet_token", None)
        if token:
            return str(token)
    except Exception:
        pass

    # Try context.padlet_token
    try:
        ctx = getattr(runtime, "context", None)
        if isinstance(ctx, dict):
            token = ctx.get("padlet_token")
        else:
            token = getattr(ctx, "padlet_token", None)
        if token:
            return str(token)
    except Exception:
        pass

    return None


@tool(args_schema=UpdatePadletArgs)
async def update_padlet(wall_id: int, wall_data: WallUpdateData):
    """Update the padlet's title, description, wallpaper, sections, posts and settings.

    Note when using this tool:
      - **Parameters**: Include only parameters relevant to the requested changes.
      - **New Objects**: Prepend "id" with "new_" for new posts or sections.
      - **Existing Objects**: Include the "id" to update existing posts and sections. To create a post in a section, include the "section_id".
      - **location_data**: The "location_data" object must be included when creating posts for padlets when the format is "map".

    Args:
        wall_id (int): The id of the wall to update.
        wall_data (WallUpdateData): The data to update the wall with, include only parameters relevant to the requested changes. Structure:

    Returns:
        dict: A dictionary indicating success.

    """
    # Prefer a per-run JWT provided by the caller via run config: config.configurable.padlet_token
    token = _get_padlet_token_from_runtime()
    if not token:
        # Fallback for local/dev: allow env token if provided
        env_token = os.getenv("PADLET_AI_TOKEN")
        if env_token:
            token = env_token
        else:
            # In development, emit a helpful hint without leaking values
            if os.getenv("ENVIRONMENT") == "development":
                pprint.pprint({
                    "padlet_token_error": "Missing token",
                    "expected_location": "config.configurable.padlet_token or context.padlet_token",
                })
            raise WallUpdateFailedError(
                "Missing Padlet JWT token. Pass it via config.configurable.padlet_token"
            )

    await send_update_wall_request(token=token, wall_id=wall_id, wall_data=wall_data)
    return {"success": True, "wall_id": wall_id}


# Use data from the tool update_padlet to actually send update request to rails.
async def send_update_wall_request(token: str, wall_id: int, wall_data: Any):
    """Send the wall update to Rails, raising on non-200/invalid responses."""
    cleaned_wall_data = remove_none_values(wall_data)
    if os.getenv("ENVIRONMENT", "production") == "development":
        pprint.pprint({"sending_update_wall_request": cleaned_wall_data})

    async with aiohttp.ClientSession() as session:
        base_url = os.getenv("RAILS_INTERNAL_URL")
        if not base_url:
            raise WallUpdateFailedError("RAILS_INTERNAL_URL is not set in the environment")
        base_url = base_url.rstrip("/") + "/"
        async with session.post(
            f"{base_url}api/1/walls/{wall_id}/ai-chat",
            json={"tool_uses": cleaned_wall_data},
            headers={"Authorization": f"Bearer {token}"},
        ) as response:
            if response.status == 200:
                try:
                    response_json = await response.json()
                    # If the update failed, rails will return a success key set to False
                    if (
                        not response_json.get("data", {})
                        .get("attributes", {})
                        .get("success", True)
                    ):
                        raise WallUpdateFailedError("Wall update failed")
                except aiohttp.ContentTypeError:
                    raise WallUpdateFailedError(f"Response not json: {response.status}")
                except aiohttp.ClientError as e:
                    raise WallUpdateFailedError(f"Wall update failed: {str(e)}")
            else:
                raise WallUpdateFailedError(
                    f"Wall update failed with status {response.status}"
                )
