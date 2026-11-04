"""Outbound mail — `AM-273` m1/m3 (AB-150, 2026-11-02).

Two transports, chosen by the environment, and by default NEITHER: no mail at all.

  LEGALMIND_MAIL_SINK_DIR   each message written as an .eml file there (local, tests)
  LEGALMIND_MAIL_RELAY      host[:port] of the ONE LeapSwitch-controlled SMTP relay (m1)

The sink wins when both are set, so a development box never reaches a relay by accident.
What a message may carry is the caller's rule (m3: a fixed sentence and a link); this
module only delivers it.
"""
from __future__ import annotations

import os
import smtplib
import uuid
from email.message import EmailMessage
from pathlib import Path
from typing import Protocol


class MailTransport(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class FileSinkTransport:
    def __init__(self, directory: str):
        self.directory = Path(directory)

    def send(self, message: EmailMessage) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / f"{uuid.uuid4().hex}.eml").write_bytes(message.as_bytes())


class RelayTransport:
    """The relay m1 allow-lists. Opened only when LEGALMIND_MAIL_RELAY names it."""

    def __init__(self, relay: str):
        host, _, port = relay.partition(":")
        self.host, self.port = host, int(port or 25)

    def send(self, message: EmailMessage) -> None:
        with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
            smtp.send_message(message)


def transport() -> MailTransport | None:
    if sink := os.environ.get("LEGALMIND_MAIL_SINK_DIR"):
        return FileSinkTransport(sink)
    if relay := os.environ.get("LEGALMIND_MAIL_RELAY"):
        return RelayTransport(relay)
    return None


def sender() -> str:
    return os.environ.get("LEGALMIND_MAIL_FROM", "legalmind@localhost")
