import unittest
import subprocess
import sys
import io
import os
import time
import socket
import json
import tempfile
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Paths to files
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if __file__ else os.getcwd()
CLIENT_PY = os.path.join(ROOT, 'client.py')
SERVER_PY = os.path.join(ROOT, 'server.py')
OLLAMA_PY = os.path.join(ROOT, 'ollama.py')

# import the ask_ollama function directly from client.py, safe because main runs only when client py is directly run
sys.path.insert(0, ROOT)
from client import ask_ollama
from server import evaluate_answer
from client import input_handler_with_timeouts


class TestClientWithOllama(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start ollama.py
        cls.ollama_proc = subprocess.Popen([sys.executable, OLLAMA_PY], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.2)  # give server time to set up

    @classmethod
    def tearDownClass(cls):
        cls.ollama_proc.terminate()
        cls.ollama_proc.wait(timeout=2)

    def test_ask_ollama_returns_message(self):
        config = {"ollama_host": "127.0.0.1", "ollama_port": 8000, "ollama_model": "llama3.2"}
        res = ask_ollama(config, "dummy question", time_limit=2)  # result, best to not rename due to some inbuilt result
        self.assertIsNotNone(res)
        self.assertIn("Hello!", res)


class SlowHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # disable console logging

    def slow_request(self):
        # simulate long running interaction
        length = int(self.headers.get('Content-Length', 0))
        _ = self.rfile.read(length)
        time.sleep(3)
        resp = {"model": "mock", "message": {"role": "assistant", "content": "slow response"}, "done": True}
        body = json.dumps(resp).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(body)


class TestClientTimeoutBehavior(unittest.TestCase):
    def setUp(self):
        # Start small HTTP server in backgrond thread that sleeps before responding
        self.server = HTTPServer(('127.0.0.1', 8001), SlowHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.1)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)

    def test_ask_ollama_times_out(self):
        config = {"ollama_host": "127.0.0.1", "ollama_port": 8001, "ollama_model": "mock"}
        # time_limit shorter than server sleep, should return None
        res = ask_ollama(config, "slow request", time_limit=1)
        self.assertIsNone(res)


class TestServerIntegration(unittest.TestCase):
    def setUp(self):
        # create a small temporary config so the game runs fast
        config = {
            "port": 8890,
            "players": 2,
            "question_types": ["Mathematics"],
            "question_formats": {"Mathematics": "Evaluate {}"},
            "question_seconds": 2,
            "question_interval_seconds": 0.5,
            "ready_info": "Game starts in {question_interval_seconds} seconds!",
            "question_word": "Question",
            "correct_answer": "{answer} is correct!",
            "incorrect_answer": "The correct answer is {correct_answer}, but your answer {answer} is incorrect :(",
            "points_noun_singular": "point",
            "points_noun_plural": "points",
            "final_standings_heading": "Final standings:",
            "one_winner": "The winner is: {}",
            "multiple_winners": "The winners are: {}"
        }
        self.config_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        json.dump(config, self.config_file)
        self.config_file.close()

        # start server.py with this config
        self.server_process = subprocess.Popen([sys.executable, SERVER_PY, '--config', self.config_file.name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.2)

    def tearDown(self):
        try:
            self.server_process.terminate()
            self.server_process.wait(timeout=2)
        except Exception:
            pass
        try:
            os.unlink(self.config_file.name)
        except Exception:
            pass

    def test_two_clients_connect_and_receive_question(self):
        # Connect two raw sockets to the server and send HI messages
        sock_1 = socket.create_connection(('127.0.0.1', 8890), timeout=2)
        sock_2 = socket.create_connection(('127.0.0.1', 8890), timeout=2)

        send_json(sock_1, {"message_type": "HI", "username": "Tester1"})
        send_json(sock_2, {"message_type": "HI", "username": "Tester2"})

        # Read READY and QUESTION messages in sockets
        ready1 = receive_json_line(sock_1, timeout=3)
        ready2 = receive_json_line(sock_2, timeout=3)
        self.assertIsNotNone(ready1)
        self.assertEqual(ready1.get('message_type'), 'READY')
        self.assertIsNotNone(ready2)
        self.assertEqual(ready2.get('message_type'), 'READY')

        question1 = receive_json_line(sock_1, timeout=5)
        question2 = receive_json_line(sock_2, timeout=5)
        self.assertIsNotNone(question1)
        self.assertEqual(question1.get('message_type'), 'QUESTION')
        self.assertIsNotNone(question2)
        self.assertEqual(question2.get('message_type'), 'QUESTION')

        # evaluate correct answer using the server's evlaute_answer function
        short_question = question1.get('short_question')
        correct_answer, is_correct = evaluate_answer(question1.get('question_type'), short_question, None)

        # Send answer for both clients
        send_json(sock_1, {"message_type": "ANSWER", "answer": correct_answer})
        send_json(sock_2, {"message_type": "ANSWER", "answer": correct_answer})

        # Both should receive RESULT messages
        result_1 = receive_json_line(sock_1, timeout=3)
        result_2 = receive_json_line(sock_2, timeout=3)
        self.assertIsNotNone(result_1)
        self.assertEqual(result_1.get('message_type'), 'RESULT')
        self.assertIsNotNone(result_2)
        self.assertEqual(result_2.get('message_type'), 'RESULT')

        # Should receive FINISHED message from server
        finished1 = receive_json_line(sock_1, timeout=3)
        finished2 = receive_json_line(sock_2, timeout=3)
        self.assertIsNotNone(finished1)
        self.assertEqual(finished1.get('message_type'), 'FINISHED')
        self.assertIsNotNone(finished2)
        self.assertEqual(finished2.get('message_type'), 'FINISHED')

        sock_1.close()
        sock_2.close()


class TestClientEdgeCases(unittest.TestCase):
    def setUp(self):
        config = {
            "port": 8891,
            "players": 2,
            "question_types": ["Mathematics"],
            "question_formats": {"Mathematics": "Evaluate {}"},
            "question_seconds": 2,
            "question_interval_seconds": 0.5,
            "ready_info": "Game starts soon!",
            "question_word": "Question",
            "correct_answer": "{answer} is correct!",
            "incorrect_answer": "Incorrect",
            "points_noun_singular": "point",
            "points_noun_plural": "points",
            "final_standings_heading": "Final standings:",
            "one_winner": "Winner: {}",
            "multiple_winners": "Winners: {}"
        }
        self.config_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        json.dump(config, self.config_file)
        self.config_file.close()
        self.server_process = subprocess.Popen(
            [sys.executable, SERVER_PY, "--config", self.config_file.name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(0.3)

    def tearDown(self):
        try:
            self.server_process.terminate()
            self.server_process.wait(timeout=2)
        except Exception:
            pass
        try:
            os.unlink(self.config_file.name)
        except Exception:
            pass

    def test_client_disconnects_early(self):
        # Client connects then disconnects before sending HI
        s = socket.create_connection(("127.0.0.1", 8891), timeout=2)
        s.close()

        time.sleep(0.5)

        # Server should still be alive and nto crash
        self.assertIsNone(self.server_process.poll(), "Server crashed on disconnect")


class TestClientInputSequences(unittest.TestCase):

    def test_client_empty_input(self):
        res = input_handler_with_timeouts(0.5)
        self.assertIsNone(res)

    def test_client_valid_then_empty_input(self):
        old_stdin = sys.stdin
        try:
            # first call correct
            sys.stdin = io.StringIO("yes\n")
            result1 = input_handler_with_timeouts(1)
            self.assertEqual(result1.strip(), "yes")

            # second call no input
            sys.stdin = io.StringIO("")
            try:
                result2 = input_handler_with_timeouts(0.5)
            except EOFError:
                result2 = None  # treat EOF as “no input”
            self.assertIsNone(result2)
        finally:
            sys.stdin = old_stdin


# -- Helper functions for interacting with server.py --

def receive_json_line(sock, timeout=2.0):
    # receives single json line from socket
    sock.settimeout(timeout)
    buffer = b''
    try:
        while True:
            data = sock.recv(4096)
            if not data:
                break
            buffer += data
            if b"\n" in buffer:
                line, rest = buffer.split(b"\n", 1)
                return json.loads(line.decode('utf-8'))
    except socket.timeout:
        return None
    except Exception:
        return None


def send_json(sock, obj):
    sock.sendall(json.dumps(obj).encode('utf-8') + b"\n")


if __name__ == '__main__':
    result = unittest.main(verbosity=2, exit=False)
    print("\n--- TEST SUMMARY ---")
    if result.result.wasSuccessful():
        print("All tests passed successfully.")
    else:
        print("Some tests failed.")

