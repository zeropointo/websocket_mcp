# WebSocket MCP

This project implements a websockets-based Model Context Protocol (MCP) server and client. It also includes a complete local llm chat bot demo. The goal of this project is to create a better MCP implementation that overcomes the limitations of the default stdio and sse transport layers.

## Modules

- **MCP Server**: Provides a robust and flexible server implementation for the Model Context Protocol, facilitating communication between clients and the local LLM. It supports WebSocket transport for efficient message exchange and can be extended to handle various types of requests and notifications.
- **MCP Client**: A generic client for interacting with MCP servers, supporting features like resource listing and data streaming.

## Demo
- **Local LLM Server**: Hosts the LLM and handles requests for generating responses based on provided prompts. It also lists available models using the `ollama` package.
- **LLM Client**: Connects to the server to send prompts and receive responses. It can be configured to connect to a remote server IP.

## Usage

The server and clients can be configured and run using command-line arguments, with default settings for local operation. The project is designed to be flexible and extendable, supporting various LLM models and configurations.

## Example (Server):

```zsh
$ uv run local-llm-server
Local LLM MCP Server running on ws://0.0.0.0:8766
Request: 'What are the steps to building a model rocket?', with model 'llama3.1:8b'
Response: 'Building a model rocket! Here's a step-by-step guide to help you construct a fun and safe model rocket:

**Step 1: Choose Your Kit (Optional)**
If you're new to model rockets, consider buying an kit that includes all the necessary components. This will ensure that you have everything you need to build your rocket.

**Step 2: Gather Materials**

* Balsa wood or plastic nose cone
* Body tube (available in various sizes and materials)'

[...continued...]
```

## Example (Client):

```zsh
$ uv run local-llm-client --server-ip 192.168.1.123
Initialization response from server: {'serverName': 'local-llm-server', 'serverVersion': '1.0.0', 'capabilities': {'llm': True}}
Available Resources:
 - Local LLM Service (URI: local://ask_llm, Capabilities: ['llm', 'ask_llm'])
   Models:
     - llava:13b
     - deepseek-r1:8b
     - deepseek-r1:14b
     - deepseek-r1:7b
     - deepseek-r1:32b
     - llama3.1:8b
     - deepseek-r1:latest
Enter your prompt for the LLM: What are the steps to building a model rocket?
Enter the model to use (leave blank for default): llama3.1:8b
LLM Response: {'answer': 'Building a model rocket! Here's a step-by-step guide to help you construct a fun and safe model rocket:

**Step 1: Choose Your Kit (Optional)**
If you're new to model rockets, consider buying an kit that includes all the necessary components. This will ensure that you have everything you need to build your rocket.

**Step 2: Gather Materials**

* Balsa wood or plastic nose cone
* Body tube (available in various sizes and materials)''}

[...continued...]

Shutdown response: {'message': 'Server shutting down'}
```
