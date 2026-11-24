"""Jarvas selects paid Onyx; the name Onyx selects free local speech."""
import re


def select_voice_task(task):
    match = re.match(r'^\s*(джарвас|jarvas|оникс|onyx)(?=$|[\s,:.!—-])[\s,:.!—-]*', task, re.I)
    if not match:
        return task.strip(), False
    return task[match.end():].strip(), match.group(1).casefold() in {'джарвас', 'jarvas'}


def uses_onyx(source):
    return source.startswith('voice:onyx:')
