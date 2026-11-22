import threading

from zanelmodules.app import ZanelApp


if __name__ == "__main__":
    app = ZanelApp()

    if app.check_updates_start:
        app.root.after(
            500,
            lambda: threading.Thread(
                target=app.check_for_updates,
                daemon=True,
            ).start(),
        )

    app.run()
