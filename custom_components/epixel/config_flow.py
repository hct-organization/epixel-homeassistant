"""Pairing flow and page builder.

PAIRING DIRECTION: the device generates the PIN and shows it on its screen; the
user types it here. The other direction (Home Assistant shows the code, user
types it on the device) would mean typing on a 320 px touch keyboard. This
direction also removes any need for a listening port on the device.

PAGE BUILDER: built entirely from Home Assistant's own form UI -- no custom
frontend. The user lays out pages on a machine with a keyboard and a mouse;
the device only draws them.
"""

from __future__ import annotations

import asyncio
import logging
import secrets

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_DEVICE_NAME,
    CONF_PAGES,
    CONF_TOKEN,
    DOMAIN,
    MAX_BOXES_PER_PAGE,
    MAX_PAGES,
    NAME_MAX,
    PAIR_MAX_ATTEMPTS,
    SUPPORTED_DOMAINS,
)

_LOGGER = logging.getLogger(__name__)

CONF_PIN = "pin"
CONF_TITLE = "title"
CONF_ENTITIES = "entities"
CONF_INDEX = "index"

# The device polls every 2 seconds. A user may well type the code before the
# device has polled even once, so wait up to 8 seconds before giving up.
_WAIT_TICKS = 16
_WAIT_STEP_S = 0.5


def _page_schema(defaults: dict | None = None) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_TITLE, default=(defaults or {}).get(CONF_TITLE, "")): str,
            vol.Required(
                CONF_ENTITIES, default=(defaults or {}).get(CONF_ENTITIES, [])
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=list(SUPPORTED_DOMAINS), multiple=True
                )
            ),
        }
    )


def _validate_page(user_input: dict) -> tuple[dict | None, str | None]:
    entities = list(user_input.get(CONF_ENTITIES) or [])
    if not entities:
        return None, "no_entities"
    if len(entities) > MAX_BOXES_PER_PAGE:
        return None, "too_many_entities"
    title = str(user_input.get(CONF_TITLE, "")).strip()[:NAME_MAX]
    return {"title": title, "entities": entities}, None


class EpixelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Connects a display to Home Assistant."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        from . import ensure_data  # late import: avoids a circular dependency

        data = ensure_data(self.hass)
        errors: dict[str, str] = {}

        if user_input is not None:
            if data["attempts"] >= PAIR_MAX_ATTEMPTS:
                return self.async_abort(reason="too_many_attempts")

            pin = str(user_input[CONF_PIN]).strip()
            found = None
            for _ in range(_WAIT_TICKS):
                found = _find_pending(data, pin)
                if found is not None:
                    break
                await asyncio.sleep(_WAIT_STEP_S)

            if found is None:
                data["attempts"] += 1
                errors["base"] = "no_device"
            else:
                _session, record = found
                token = secrets.token_hex(24)
                record["token"] = token          # the device collects it on its next poll
                data["attempts"] = 0

                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=record["name"],
                    data={CONF_TOKEN: token, CONF_DEVICE_NAME: record["name"]},
                    options={CONF_PAGES: []},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_PIN): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> config_entries.OptionsFlow:
        return EpixelOptionsFlow()


def _find_pending(data: dict, pin: str) -> tuple[str, dict] | None:
    for session, record in data["pending"].items():
        if record["pin"] == pin and not record["token"]:
            return session, record
    return None


class EpixelOptionsFlow(config_entries.OptionsFlow):
    """Page builder: add / edit / remove / save."""

    def __init__(self) -> None:
        self._pages: list[dict] | None = None
        self._edit_index: int | None = None

    def _load(self) -> list[dict]:
        if self._pages is None:
            self._pages = [
                dict(page) for page in (self.config_entry.options or {}).get(CONF_PAGES, [])
            ]
        return self._pages

    async def async_step_init(self, user_input: dict | None = None):
        pages = self._load()
        options = ["add_page"]
        if pages:
            options += ["edit_page", "remove_page"]
        options.append("save")
        return self.async_show_menu(step_id="init", menu_options=options)

    # -------------------------------------------------------------- add

    async def async_step_add_page(self, user_input: dict | None = None):
        pages = self._load()
        errors: dict[str, str] = {}

        if len(pages) >= MAX_PAGES:
            return self.async_abort(reason="too_many_pages")

        if user_input is not None:
            page, error = _validate_page(user_input)
            if error:
                errors["base"] = error
            else:
                pages.append(page)
                return await self.async_step_init()

        return self.async_show_form(
            step_id="add_page", data_schema=_page_schema(), errors=errors
        )

    # ------------------------------------------------------------- edit

    async def async_step_edit_page(self, user_input: dict | None = None):
        pages = self._load()
        if user_input is not None:
            self._edit_index = int(user_input[CONF_INDEX])
            return await self.async_step_edit_form()
        return self.async_show_form(
            step_id="edit_page", data_schema=self._index_schema(pages)
        )

    async def async_step_edit_form(self, user_input: dict | None = None):
        pages = self._load()
        index = self._edit_index or 0
        errors: dict[str, str] = {}

        if user_input is not None:
            page, error = _validate_page(user_input)
            if error:
                errors["base"] = error
            else:
                pages[index] = page
                self._edit_index = None
                return await self.async_step_init()

        current = pages[index]
        return self.async_show_form(
            step_id="edit_form",
            data_schema=_page_schema(
                {
                    CONF_TITLE: current.get("title", ""),
                    CONF_ENTITIES: current.get("entities", []),
                }
            ),
            errors=errors,
        )

    # ----------------------------------------------------------- remove

    async def async_step_remove_page(self, user_input: dict | None = None):
        pages = self._load()
        if user_input is not None:
            pages.pop(int(user_input[CONF_INDEX]))
            return await self.async_step_init()
        return self.async_show_form(
            step_id="remove_page", data_schema=self._index_schema(pages)
        )

    # ------------------------------------------------------------- save

    async def async_step_save(self, user_input: dict | None = None):
        return self.async_create_entry(title="", data={CONF_PAGES: self._load()})

    # ---------------------------------------------------------- helpers

    def _index_schema(self, pages: list[dict]) -> vol.Schema:
        choices = [
            selector.SelectOptionDict(
                value=str(index),
                label=f"{index + 1}. {page.get('title') or '(untitled)'} "
                f"({len(page.get('entities', []))} boxes)",
            )
            for index, page in enumerate(pages)
        ]
        return vol.Schema(
            {
                vol.Required(CONF_INDEX): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=choices)
                )
            }
        )
