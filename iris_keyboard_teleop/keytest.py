import sys
import termios
import tty
import select


def get_key(timeout):
    # wait up to `timeout` seconds for something to be typed
    ready, _, _ = select.select([sys.stdin], [], [], timeout)
    if ready:
        key = sys.stdin.read(1)
        if key == '\x1b':          # start of an arrow key sequence
            key += sys.stdin.read(2)
        return key
    return None                    # nothing was pressed


old_settings = termios.tcgetattr(sys.stdin)
tty.setcbreak(sys.stdin.fileno())  # deliver keys instantly, no Enter needed
try:
    while True:
        print(repr(get_key(0.1)))
except KeyboardInterrupt:
    pass
finally:
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)