import asyncio
import json
import anyio
import websockets

# Import the MCP server implementation.
from .mcp_server import MCPServer, websocket_transport_server, JSON_RPC_VERSION

# Import the ollama package.
import ollama

# --- LLM Request Handler using Ollama ---

async def ask_llm_handler(params):
    """
    Handles the "ask_llm" request.
    
    Expects a JSON-RPC request with parameters:
      - "prompt": the prompt to send to the local LLM.
      - "model": (optional) the name of the LLM to use.
      
    Returns:
      A dict with the LLM answer.
    """
    prompt = params.get("prompt")
    if not prompt:
        raise ValueError("Missing 'prompt' parameter")
    model = params.get("model", "deepseek-r1:7b")  # use a default model if none provided

    # Call the ollama package to run the prompt.
    try:
        response = ollama.generate(model=model, prompt=prompt)
        return {"answer": response['response']}
    except Exception as e:
        raise Exception(f"Ollama LLM error: {str(e)}")

# --- WebSocket Server Handler ---

async def websocket_llm_server_handler(websocket):
    """
    Wraps an accepted WebSocket connection in an MCP server that exposes
    a local LLM via the ollama package.
    The 'path' parameter has been removed as it's no longer used in newer websockets versions.
    """
    # Create an MCP server instance with LLM capability.
    server = MCPServer("local-llm-server", "1.0.0", capabilities={"llm": True})
    
    # Register the ask_llm request handler.
    server.register_request_handler("ask_llm", ask_llm_handler)
    
    # (Optional) You may register other handlers (e.g., list_resources) as needed.
    
    async with websocket_transport_server(websocket) as (send_func, message_queue):
        server.send = send_func
        # Process incoming messages until a shutdown is triggered.
        while not server.shutdown_event.is_set():
            try:
                message = await asyncio.wait_for(message_queue.get(), timeout=1)
                await server.receive(message)
            except asyncio.TimeoutError:
                continue

# --- Server Startup ---

async def start_local_llm_server():
    # Here we use port 8766 so it doesn't conflict with your other MCP servers.
    async with websockets.serve(websocket_llm_server_handler, "localhost", 8766):
        print("Local LLM MCP Server running on ws://localhost:8766")
        await asyncio.Future()  # Run indefinitely

def main():
    asyncio.run(start_local_llm_server())

if __name__ == "__main__":
    main()
