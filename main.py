"""
main.py — Entry point for the Desktop Pet app
-----------------------------------------------
This file does three things:
  1. Creates the Qt application (required by PySide6)
  2. Creates and shows the pet window
  3. Starts the event loop (keeps the app running)

Run this file to launch the pet:
    python main.py
"""

import sys
from PySide6.QtWidgets import QApplication

# Local import — we'll build this file next
from pet_window import PetWindow


def main():
    # QApplication manages the app lifecycle.
    # sys.argv passes command-line args to Qt (usually just the script name).
    app = QApplication(sys.argv)

    # Tell Qt not to quit when the last *regular* window closes,
    # since our pet window is frameless/tool-type and Qt may not
    # count it the same way on all platforms.
    app.setQuitOnLastWindowClosed(False)

    # Create the pet window (transparent, frameless, always-on-top)
    window = PetWindow()
    window.show()

    # Start the event loop — this blocks until the app exits.
    # sys.exit() passes the exit code back to the OS cleanly.
    sys.exit(app.exec())


# Standard Python guard: only run main() when this file is executed directly,
# not when it's imported by another module.
if __name__ == "__main__":
    main()
