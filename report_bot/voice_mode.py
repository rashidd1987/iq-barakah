"""Paid Onyx is selected only by an explicit leading invocation."""
import re


def select_voice_task(task):
    match = re.match(r'^\s*(?:оникс|onyx)(?=$|[\s,:.!—-])[\s,:.!—-]*', task, re.I)
    return (task[match.end():].strip(), True) if match else (task.strip(), False)


def uses_onyx(source):
    return source.startswith('voice:onyx:')
