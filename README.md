# Trivia.NET

**Trivia.NET** is a real-time trivia game inspired by platforms like Kahoot built in Python using networking concepts such as sockets. It features a **client and server architecture**, supports **multiple concurrent players**, and uniquely allows players to answer questions **manually, automatically via code, or using a locally hosted LLM (Ollama)**.

This project demonstrates advanced skills in **network programming**, **asynchronous I/O**, **protocol design**, and **AI integration**.

---

## Features

### Trivia Gameplay
- Timed, competitive trivia rounds
- Live score tracking and leaderboards
- Deterministic question order based on server configuration
- Automatic winner detection including tie handling

### Networking
- TCP protocol used for communication between clients and server
- Custom JSON messages sent for communication with server
- Supports multiple simultaneous clients
- Graceful handling of disconnects and partial failures

### Client Modes
Trivia.NET supports **three answering modes**:

| Mode   | Description                                                  |
|--------|--------------------------------------------------------------|
| `you`  | Manual answering via standard input                          |
| `auto` | Fully automatic code based solver (100% accuracy)            |
| `ai`   | Uses a locally hosted LLM via **Ollama** to generate answers |

### Ollama AI Integration
- Uses Ollama’s `/api/chat` endpoint
- Configurable model, host, and port
- Prompt-engineered for fast, concise answers
- The lightweight alternative [Ollama.py](ollama.py) can be used instead

### Question Types
- Mathematical questions
- Roman numeral conversion
- Subnet usable IP address calculation
- Network and broadcast address determination

---

## Running the Project

### Requirements
- Python
- Ollama (only required for AI mode)
- `requests` module installed

   ```bash
   pip install requests
   ```
### Server Setup

1. Create a server configuration file (a sample [server_config.json](server_config.json) file has been provided in this repository)

2. Start the Server
    ```bash
    python server.py --config <path to server config file>
    ```
   
### Client Setup
1. Create configuration for all clients (3 sample files have been provided. Both [auto_player_config.json](auto_player_config.json) 
and [manual_player_config.json](manual_player_config.json) can be run directly according to step 3. [ai_player_config.json](ai_player_config.json)
requires additional steps, see **step 2** for more)


2. For **AI Mode (Ollama)** setup, the client configuration file requires an additional `ollama_config` parameter.
The [ai_player_config.json](ai_player_config.json) file contains a working example. Additionally, Ollama must be running 
for the AI mode to function and not produce errors. AI setup is shown below.

    
3. Start the Client
    ```bash
    python client.py --config <path to client config file>
    ```
   
4. Connect to the Server

    ```bash
    CONNECT <HOSTNAME>:<PORT>
    ```
   For example, using the sample file [server_config.json](server_config.json), the command will be `CONNECT localhost:8888`
   
### Client AI Mode Setup

#### Alternative Lightweight Setup

The alternative lightweight [ollama.py](ollama.py) can emulate Ollama without requiring additional setup.
It has been setup to port 8000 and can be changed on the last line of the file to the desired port. The sample 
[ai_player_config.json](ai_player_config.json) has already been configured to run with the alternative setup.

The only drawback is this method does not have a random precessing time like a real LLM, however this can also
be emulated by adding a `time.sleep()` command inside [ollama.py](ollama.py).

#### Ollama Setup

Install Ollama: https://ollama.com

Pull a model:

```bash
ollama pull <model name>
```

Start Ollama:

```bash
ollama serve
```

The client will automatically send trivia questions to the LLM and forward the raw response to the server.

---

## Testing Instructions

The test cases for this project can be called using:

```bash
python tests/run_all_tests.py
```

```client.py``` and ```server.py``` have been tested extensively to ensure that they pass the custom testcases. However, the testcase will not automatically work ```test_ask_ollama_returns_message```, and requires the command:

 ```bash
 python ollama.py
 ``` 
 to be running on port 8000 (which is set by default in the file) before the Ollama testcase works. This is to imitate Ollama running locally in a more lightweight manner, as running multiple testcases together in networking can potentially cause timeouts.
 
https://github.com/Nicclassy/trivia.net.testing contains an additional 30 testcases which were used for marking this assignment (including 4 hidden cases at the time). Please note that these are have been developed by staff and are not associated with the author of this repository.