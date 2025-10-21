import json
import sys
import socket
import threading
from pathlib import Path


def main():
    config = load_config()

    while True:
        try:
            users_command = input()
        except KeyboardInterrupt:
            break

        if users_command.startswith("CONNECT"):
            try:
                _, address = users_command.split()
                host, port = address.split(":")
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((host, int(port)))
                send_json(sock, {"message_type": "HI", "username": config["username"]})
                threading.Thread(target=receive_loop, args=(sock, config), daemon=True).start()
            except Exception:
                print("Connection failed")
        elif users_command == "DISCONNECT":
            send_json(sock, {"message_type": "BYE"})
            sock.close()
        elif users_command == "EXIT":
            try:
                send_json(sock, {"message_type": "BYE"})
                sock.close()
            except:
                pass
            sys.exit(0)


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


def send_json(sock, message):
    sock.sendall(json.dumps(message).encode("utf-8") + b"\n")


def receive_loop(sock, config):
    while True:
        try:
            data = sock.recv(4096)
            if not data:
                break
            for line in data.decode("utf-8").splitlines():
                message = json.loads(line)
                handle_message(sock, message, config)
        except Exception:
            break


def handle_message(sock, message, config):
    message_type = message.get("message_type")

    if message_type == "READY":
        print(message["info"])

    elif message_type == "QUESTION":
        print(message["trivia_question"])
        mode = config["client_mode"]
        short_question = message["short_question"]
        time_limit = message["time_limit"]

        if mode == "you":
            try:
                answer = input()
            except KeyboardInterrupt:
                answer = ""
        elif mode == "auto":
            answer = evaluate_answer(message["question_type"], short_question)
        elif mode == "ai":
            """
            from ollama import ask_ollama
            answer = ask_ollama(config["ollama_config"], short_question)"""
            answer = "test_ollama"
        else:
            answer = ""

        send_json(sock, {"message_type": "ANSWER", "answer": answer})

    elif message_type == "RESULT":
        print(message["feedback"])

    elif message_type == "LEADERBOARD":
        print(message["state"])

    elif message_type == "FINISHED":
        print(message["final_standings"])


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
