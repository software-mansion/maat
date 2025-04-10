import platform
import subprocess


def send_notification(title: str, message: str) -> None:
    """
    Send a system notification.

    Args:
        title: The title of the notification.
        message: The body text of the notification.

    Note:
        This function only supports macOS and Linux. It will silently do nothing on other platforms.
    """

    match platform.system():
        case "Darwin":
            # Use AppleScript to send a notification.
            apple_script = f'display notification "{message}" with title "{title}"'
            subprocess.run(["osascript", "-e", apple_script], check=False)
        case "Linux":
            # Use notify-send on Linux.
            cmd = ["notify-send", title, message]
            subprocess.run(cmd, check=False)
        case _:
            # Silently do nothing on other platforms
            pass
