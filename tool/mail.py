#!/usr/bin/env python3
"""Compatibility path for the shared mail command, which now lives in the plugin
(plugins/exfu-agent-messaging/scripts/mail.py). Codex's skills and older notes call this path."""
import os
import sys

target = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugins", "exfu-agent-messaging",
                      "scripts", "mail.py")
os.execv(sys.executable, [sys.executable, target, *sys.argv[1:]])
