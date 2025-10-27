import json
import sys
import socket
import threading
from pathlib import Path
import queue
import signal
import requests

connected = threading.Event()
should_exit = threading.Event()
result_message_received = threading.Event()

question_queue = queue.Queue()


def main():
    config = load_config()
    sock = None
    users_command = ""

    while True:
        try:
            if not connected.is_set():
                users_command = input()
        except KeyboardInterrupt:
            break

        if users_command.startswith("CONNECT"):
            try:
                _, address = users_command.split()
                host, port = address.split(":")
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((host, int(port)))
                users_command = ""  # reset to avoid a connect loop
                send_json(sock, {"message_type": "HI", "username": config["username"]})
                connected.set()
                threading.Thread(target=receive_loop, args=(sock, config), daemon=True).start()
            except Exception:
                print("Connection failed")
        elif users_command == "DISCONNECT":
            if sock is not None:
                send_json(sock, {"message_type": "BYE"})
                sock.close()
            sock = None
            connected.clear()
        elif users_command == "EXIT" or should_exit.is_set():
            try:
                send_json(sock, {"message_type": "BYE"})
                sock.close()
            except:
                pass
            sys.exit(0)
        else:
            try:  # used if client answered a question
                client_mode = config["client_mode"]
                message = question_queue.get(timeout=0.1)
                if message["message_type"] == "QUESTION":
                    if client_mode == "ai":
                        answer = ask_ollama(config["ollama_config"], message["short_question"], message["time_limit"])
                    else:
                        answer = input_handler_with_timeouts(message["time_limit"])
                    if answer is not None:
                        if answer == "EXIT":
                            send_json(sock, {"message_type": "BYE"})
                            sock.close()
                            sys.exit(0)
                        elif answer == "DISCONNECT":
                            send_json(sock, {"message_type": "BYE"})
                            sock.close()
                            connected.clear()
                        else:
                            send_json(sock, {"message_type": "ANSWER", "answer": answer})
            except queue.Empty:
                pass


def load_config():
    # Handle errors when loading config file
    if "--config" not in sys.argv:
        sys.stderr.write("client.py: Configuration not provided\n")
        sys.exit(1)

    config_index = sys.argv.index("--config") + 1
    if config_index >= len(sys.argv):
        sys.stderr.write("client.py: Configuration not provided\n")
        sys.exit(1)

    config_path = Path(sys.argv[config_index])
    if not config_path.exists():
        sys.stderr.write(f"client.py: File {config_path} does not exist\n")
        sys.exit(1)

    with config_path.open("r", encoding="utf-8") as file:
        config_file = json.load(file)

    if config_file.get("client_mode") == "ai" and not config_file.get("ollama_config"):
        sys.stderr.write("client.py: Missing values for Ollama configuration\n")
        sys.exit(1)

    return config_file


def input_handler_with_timeouts(time_limit):
    def timeout_handler(signum, frame):
        raise TimeoutError

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, time_limit)

    try:
        user_input = input()
        signal.setitimer(signal.ITIMER_REAL, 0)  # Cancel timeout
        return user_input
    except TimeoutError:
        return None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def send_json(sock, message):
    sock.sendall(json.dumps(message).encode("utf-8") + b"\n")


def receive_loop(sock, config):
    while True:
        if not connected.is_set():  # exit on disconnecting with client
            break

        try:
            data = sock.recv(4096)
            if not data:
                break
            for line in data.decode("utf-8").splitlines():
                message = json.loads(line)

                # Handle other messages in thread
                handle_message(sock, message, config)
        except Exception:
            break


def handle_message(sock, message, config):
    global connected
    message_type = message.get("message_type")

    if message_type == "READY":
        print(message["info"])

    elif message_type == "QUESTION":
        print(message["trivia_question"])
        mode = config["client_mode"]
        short_question = message["short_question"]

        if mode == "you":
            question_queue.put(message)
            answer = None
        elif mode == "auto":
            question_queue.put(message)
            answer = evaluate_answer(message["question_type"], short_question)
        elif mode == "ai":
            question_queue.put(message)
            answer = None
        else:
            answer = ""

        if answer is not None:  # make sure user didn't time out
            send_json(sock, {"message_type": "ANSWER", "answer": answer})

    elif message_type == "RESULT":
        result_message_received.set()
        print(message["feedback"])
        result_message_received.clear()  # clear for next question in case quiz does not exit

    elif message_type == "LEADERBOARD":
        print(message["state"])

    elif message_type == "FINISHED":
        print(message["final_standings"])
        connected.clear()


def ask_ollama(ollama_config, short_question, time_limit):
    def timeout_handler(signum, frame):
        raise TimeoutError

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, time_limit)

    try:
        host = ollama_config["ollama_host"]
        port = ollama_config["ollama_port"]
        model = ollama_config["ollama_model"]

        url = f"http://{host}:{port}/api/chat"
        headers = {"Content-Type": "application/json"}

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": f'Evaluate {short_question}. No extra output'}
            ],
            "stream": False
        }

        response = requests.post(url, headers=headers, json=payload, timeout=time_limit)
        signal.setitimer(signal.ITIMER_REAL, 0)  # Cancel timeout
        response.raise_for_status()  # raise error if request failed
        data = response.json()
        return data["message"]["content"]
    except:
        return None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def evaluate_answer(question_type, short_question):
    if question_type == "Mathematics":
        try:
            question_tokens = short_question.split()
            total = int(question_tokens[0])
            i = 1
            while i < len(question_tokens):
                operation = question_tokens[i]
                number = int(question_tokens[i + 1])
                if operation == "+":
                    total += number
                elif operation == "-":
                    total -= number
                else:
                    return "", False
                i += 2
            correct = str(total)
        except:
            return "", False

    elif question_type == "Roman Numerals":
        try:
            values = {
                'I': 1, 'V': 5, 'X': 10, 'L': 50,
                'C': 100, 'D': 500, 'M': 1000
            }
            total = 0
            prev = 0
            for char in reversed(short_question):
                value = values.get(char, 0)
                if value < prev:
                    total -= value
                else:
                    total += value
                    prev = value
            correct = str(total)
        except:
            correct = ""

    elif question_type == "Usable IP Addresses of a Subnet":
        correct = solve_usable_addresses(short_question)

    elif question_type == "Network and Broadcast Address of a Subnet":
        correct = solve_network_broadcast(short_question)

    else:
        correct = ""

    return correct


def solve_usable_addresses(short_q: str) -> str:
    try:
        ip, prefix = short_q.split("/")
        prefix = int(prefix)
        if prefix < 0 or prefix > 32:
            return ""
        total = 2 ** (32 - prefix)
        usable = total - 2 if prefix < 31 else total
        return str(usable)
    except:
        return ""


def solve_network_broadcast(short_q: str) -> str:
    try:
        ip_str, prefix = short_q.split("/")
        prefix = int(prefix)
        if prefix < 0 or prefix > 32:
            return ""

        # Convert IP to integer
        ip_parts = list(map(int, ip_str.split(".")))
        ip_int = (ip_parts[0] << 24) | (ip_parts[1] << 16) | (ip_parts[2] << 8) | ip_parts[3]

        # Create subnet mask
        mask = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF

        # Calculate network and broadcast
        net_int = ip_int & mask
        broadcast_int = ip_int | (~mask & 0xFFFFFFFF)

        # Convert back to dotted format
        def int_to_ip(n):
            return f"{(n >> 24) & 0xFF}.{(n >> 16) & 0xFF}.{(n >> 8) & 0xFF}.{n & 0xFF}"

        return f"{int_to_ip(net_int)} and {int_to_ip(broadcast_int)}"
    except:
        return ""


if __name__ == "__main__":
    main()
