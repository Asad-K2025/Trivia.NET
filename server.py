import json
import socket
import sys
import time
import threading
from pathlib import Path
import questions

players = []
players_threading_lock = threading.Lock()  # prevents players form accessing variables simultaneously in leaderboard


def main():
    config = load_config()
    port = config["port"]
    max_players = config["players"]

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # allows immediate server reuse (os has a wait time)
        try:
            sock.bind(("0.0.0.0", port))
        except Exception:
            sys.stderr.write(f"server.py: Binding to port {port} was unsuccessful\n")
            sys.exit(1)

        sock.listen()
        all_players_connected = False  # Flag checks when all players connected

        while True:
            connection, address = sock.accept()
            join_flag = threading.Event()  # Informs when client handling is complete in thread
            threading.Thread(target=handle_add_client, args=(connection, join_flag), daemon=True).start()

            if not join_flag.wait(timeout=3):
                continue  # Client didn't connect quick enough for some reason, skip them

            with players_threading_lock:  # Ensures threads enter block one at a time
                if len(players) >= max_players:  # Enough players joined
                    all_players_connected = True

            if all_players_connected:
                time.sleep(0.3)  # wait a bit before re-checking if clients disconnected
                with players_threading_lock:
                    for player in players:
                        try:
                            player["connection"].send(b"")  # Check if player is currently connected
                        except Exception:
                            players.remove(player)
                    if len(players) >= max_players:  # Recheck if enough players connected, then continue
                        break
                    else:  # Else wait for more players
                        all_players_connected = False

        print("All players connected. Ready to start the game!")
        main_game_handler(config)


def load_config():
    # Handle config file and errors
    if "--config" not in sys.argv:
        sys.stderr.write("server.py: Configuration not provided\n")
        sys.exit(1)

    config_index = sys.argv.index("--config") + 1  # config file's index passed through system arguments
    if config_index >= len(sys.argv):
        sys.stderr.write("server.py: Configuration not provided\n")
        sys.exit(1)

    config_file_path = Path(sys.argv[config_index])
    if not config_file_path.exists():
        sys.stderr.write(f"server.py: File {config_file_path} does not exist\n")
        sys.exit(1)

    with config_file_path.open("r", encoding="utf-8") as file:
        return json.load(file)  # load file into json


def handle_add_client(connection, joined_flag):
    # Function gets hi messages from client and adds to players list
    try:
        while True:
            data = connection.recv(1024)
            if not data:
                break
            message = json.loads(data.decode().strip())
            if message.get("message_type") == "HI":
                username = message.get("username")
                with players_threading_lock:
                    players.append({"connection": connection, "username": username, "score": 0})
                joined_flag.set()  # Flag ensures main gives thread enough time for adding player
                break
    except Exception:
        pass


def send_json(connection, message):
    try:
        encoded = json.dumps(message).encode("utf-8") + b"\n"
        connection.sendall(encoded)
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass


def send_json_all_players(message):
    for player in players:
        send_json(player["connection"], message)


def main_game_handler(config):
    ready_info = config["ready_info"].format(**config)
    send_json_all_players({"message_type": "READY", "info": ready_info})

    time.sleep(config["question_interval_seconds"])

    question_types = config["question_types"]
    question_formats = config["question_formats"]
    question_word = config["question_word"]
    time_limit = config["question_seconds"]

    # Each question handled in loop
    for i, question_type in enumerate(question_types):
        short_question = generate_short_question(question_type)
        trivia_question = f"{question_word} {i + 1} ({question_type}):\n{question_formats[question_type].format(short_question)}"

        question_message = {
            "message_type": "QUESTION",
            "question_type": question_type,
            "trivia_question": trivia_question,
            "short_question": short_question,
            "time_limit": time_limit
        }

        send_json_all_players(question_message)

        player_responses = collect_player_responses(short_question, config, time_limit)

        time.sleep(time_limit / 100)  # wait a tiny bit of time more for receiving responses
        send_results(player_responses, short_question, question_type, config)
        time.sleep(time_limit / 100)  # let all results send before sending leaderboard

        if i < len(question_types) - 1:  # Don't send leaderboard on final question
            send_leaderboard(config)
            time.sleep(time_limit / 5)  # allows time for leaderboard calculatons and sending

    send_finished(config)


def generate_short_question(question_type):
    # Calls questions.py for relevant question generation
    if question_type == "Mathematics":
        return questions.generate_mathematics_question()
    elif question_type == "Roman Numerals":
        return questions.generate_roman_numerals_question()
    elif question_type == "Usable IP Addresses of a Subnet":
        return questions.generate_usable_addresses_question()
    elif question_type == "Network and Broadcast Address of a Subnet":
        return questions.generate_network_broadcast_question()
    else:
        return


def collect_player_responses(_, _2, time_limit):
    answers = {}
    deadline = time.time() + time_limit + 0.5  # provides slightly more than time limit in case response still arriving

    while time.time() < deadline:
        with players_threading_lock:  # lock prevents threads racing to change variables
            for player in players:
                connection = player["connection"]
                connection.settimeout(0.1)
                try:
                    data = connection.recv(1024)
                    if not data:
                        continue
                    message = json.loads(data.decode().strip())
                    if message.get("message_type") == "ANSWER":
                        answers[player["username"]] = message["answer"]
                except socket.timeout:
                    continue
                except Exception:
                    continue

        if len(answers) == len(players):  # enough repsonses received
            break

    return answers


def evaluate_answer(question_type, short_question, player_response):
    # Auto modes question solving logic
    if question_type == "Mathematics":
        try:
            question_tokens = short_question.split()
            total = int(question_tokens[0])  # fist number in equation
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
        try:
            ip, prefix = short_question.split("/")
            prefix = int(prefix)

            total = 2 ** (32 - prefix)

            usable_ip_address = total - 2 if prefix < 31 else total  # handles special cases

            correct = str(usable_ip_address)
        except:
            correct = ""

    elif question_type == "Network and Broadcast Address of a Subnet":
        correct = solve_network_broadcast(short_question)  # complex logic handled by helper function

    else:
        correct = ""

    return correct, player_response == correct


def solve_network_broadcast(short_question):
    # helper for evaluate answer for some complex logic
    try:
        ip_str, prefix = short_question.split("/")
        prefix = int(prefix)

        # Convert IP to integer
        ip_parts = list(map(int, ip_str.split(".")))
        ip_int = (ip_parts[0] << 24) | (ip_parts[1] << 16) | (ip_parts[2] << 8) | ip_parts[3]

        # Create subnet mask
        mask = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF

        # Calculate network and broadcast
        network_int = ip_int & mask
        broadcast_int = ip_int | (~mask & 0xFFFFFFFF)

        def int_to_ip(number):
            # Convert back to dotted format in helper
            return f"{(number >> 24) & 0xFF}.{(number >> 16) & 0xFF}.{(number >> 8) & 0xFF}.{number & 0xFF}"

        return f"{int_to_ip(network_int)} and {int_to_ip(broadcast_int)}"
    except:
        return ""


def send_results(player_responses, short_question, question_type, config):
    # sends results of users responses to questiosn
    for player in players:
        username = player["username"]
        connection = player["connection"]
        player_response = player_responses.get(username)
        if player_response is None:  # player didn't answer so don't send a message
            continue

        correct_answer, is_correct = evaluate_answer(question_type, short_question, player_response)

        if is_correct:
            player["score"] += 1
            feedback = config["correct_answer"].format(answer=player_response)
        else:
            feedback = config["incorrect_answer"].format(answer=player_response, correct_answer=correct_answer)

        send_json(connection, {
            "message_type": "RESULT",
            "correct": is_correct,
            "feedback": feedback
        })


def send_leaderboard(config):
    sorted_players = sorted(players, key=lambda p: (-p["score"], p["username"]))  # sort by score and lexographically
    state_lines = []

    rank = 1
    prev_score = None  # used to check what each players rank is in tie situation
    same_score_count = 0  # used for ranking players if multiple people have same rank

    for i, player in enumerate(sorted_players):
        score = player["score"]
        noun = config["points_noun_singular"] if score == 1 else config["points_noun_plural"]

        # if new score different, increase same_score_count for a new tie group (if existing)
        if prev_score is not None and score != prev_score:
            rank += same_score_count
            same_score_count = 0

        # next player score same, therefore must be tie
        same_score_count += 1
        prev_score = score

        state_lines.append(f"{rank}. {player['username']}: {score} {noun}")

    send_json_all_players({
        "message_type": "LEADERBOARD",
        "state": "\n".join(state_lines)
    })


def send_finished(config):
    with players_threading_lock:
        sorted_players = sorted(players, key=lambda p: (-p["score"], p["username"]))  # sort lexographcially and by rank
        top_score = sorted_players[0]["score"]
        winners = [p["username"] for p in sorted_players if p["score"] == top_score]

        if len(winners) == 1:
            heading = config["one_winner"].format(winners[0])
        else:
            heading = config["multiple_winners"].format(", ".join(winners))

        state_lines = []
        rank = 1
        prev_score = None
        same_score_count = 0

        for i, player in enumerate(sorted_players):
            score = player["score"]
            noun = config["points_noun_singular"] if score == 1 else config["points_noun_plural"]

            # follows same logic as leaderboard
            if prev_score is not None and score != prev_score:
                rank += same_score_count
                same_score_count = 0

            same_score_count += 1
            prev_score = score

            state_lines.append(f"{rank}. {player['username']}: {score} {noun}")

        final = f"{config['final_standings_heading']}\n" + "\n".join(state_lines) + f"\n{heading}"

        send_json_all_players({
            "message_type": "FINISHED",
            "final_standings": final
        })

        for player in players:
            player["connection"].close()

        players.clear()


if __name__ == "__main__":
    main()
