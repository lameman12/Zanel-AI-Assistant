import os
import sys


def resource_path(name):
    frozen_base = getattr(sys, "_MEIPASS", None)

    if frozen_base:
        return os.path.join(frozen_base, name)

    package_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.dirname(package_dir)
    root_dir = os.path.dirname(app_dir)

    for folder in (app_dir, root_dir, package_dir):
        candidate = os.path.join(folder, name)

        if os.path.exists(candidate):
            return candidate

    return os.path.join(root_dir, name)