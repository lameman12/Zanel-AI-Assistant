import sounddevice as sd


def list_input_devices():
    names = []

    try:
        devices = sd.query_devices()
        apis = sd.query_hostapis()
    except Exception:
        return names

    target_api = None

    for index, api in enumerate(apis):
        try:
            if "wasapi" in str(api.get("name", "")).lower():
                target_api = index
                break
        except Exception:
            continue

    if target_api is None:
        try:
            target_api = sd.query_devices(kind="input").get("hostapi")
        except Exception:
            target_api = None

    for restrict in (True, False):
        for device in devices:
            try:
                if int(device.get("max_input_channels", 0)) <= 0:
                    continue

                if (
                    restrict
                    and target_api is not None
                    and device.get("hostapi") != target_api
                ):
                    continue

                name = str(device.get("name", "")).strip()

                if name and name not in names:
                    names.append(name)
            except Exception:
                continue

        if names:
            break

    return names
