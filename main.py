import threading
import time

from Ammeters.Circutor_Ammeter import CircutorAmmeter
from Ammeters.Entes_Ammeter import EntesAmmeter
from Ammeters.Greenlee_Ammeter import GreenleeAmmeter
from Ammeters.client import request_current_from_ammeter

# Instantiated once at module level so the client can reuse each ammeter's own
# get_current_command instead of duplicating the command string by hand.
greenlee = GreenleeAmmeter(5000)
entes = EntesAmmeter(5001)
circutor = CircutorAmmeter(5002)


def run_greenlee_emulator():
    greenlee.start_server()

def run_entes_emulator():
    entes.start_server()

def run_circutor_emulator():
    circutor.start_server()

if __name__ == "__main__":
    # Start each ammeter in a separate thread
    threading.Thread(target=run_greenlee_emulator, daemon=True).start()
    threading.Thread(target=run_entes_emulator, daemon=True).start()
    threading.Thread(target=run_circutor_emulator, daemon=True).start()

    # Wait for the servers to start, if you have problem restarting the servers between runs try increasing sleep time.
    time.sleep(5)

    # Using each ammeter's own get_current_command keeps the client and server
    # commands in sync, even if a command string changes in the future.
    for ammeter in (greenlee, entes, circutor):
        current = request_current_from_ammeter(ammeter.port, ammeter.get_current_command)
        print(f"Received current measurement from port {ammeter.port}: {current} A")

