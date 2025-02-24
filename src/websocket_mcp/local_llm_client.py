import argparse
import asyncio
import websockets
from .mcp_client import MCPClient, websocket_transport_client

async def run_llm_client(server_ip):
    uri = f"ws://{server_ip}:8766"  # The server running local_llm_server.py
    client = MCPClient("llm-client", "1.0.0", capabilities={"llm": True})
    
    try:
        async with websockets.connect(uri) as websocket:
            async with websocket_transport_client(websocket) as (send_func, message_queue):
                # Set the client's send function.
                client.send = send_func

                # Start a background task to process incoming MCP messages.
                async def process_messages():
                    while True:
                        message = await message_queue.get()
                        await client.receive(message)
                task = asyncio.create_task(process_messages())

                # --- Initialization Handshake ---
                await client.connect(send_func)

                # Retrieve and display available resources.
                try:
                    resources = await client.request("list_resources", {})
                    print("Available Resources:")
                    for resource in resources:
                        name = resource.get("name", "Unnamed")
                        uri_val = resource.get("uri", "No URI")
                        capabilities = resource.get("capabilities", [])
                        models = resource.get("models", [])
                        print(f" - {name} (URI: {uri_val}, Capabilities: {capabilities})")
                        print("   Models:")
                        for model in models:
                            print(f"     - {model}")
                except Exception as e:
                    print("Error fetching resources:", e)

                # Prompt the user for input.
                prompt_text = input("Enter your prompt for the LLM: ").strip()
                model = input("Enter the model to use (leave blank for default): ").strip() or None

                # Build parameters for the ask_llm request.
                params = {"prompt": prompt_text}
                if model:
                    params["model"] = model

                # Send the ask_llm request and wait for the response.
                try:
                    response = await client.request("ask_llm", params)
                    print("LLM Response:", response)
                except Exception as e:
                    print("Error in ask_llm request:", e)

                # Initiate graceful shutdown.
                try:
                    shutdown_resp = await client.request("shutdown", {})
                    print("Shutdown response:", shutdown_resp)
                except Exception as e:
                    print("Error during shutdown:", e)

                # Cancel the background message processing task.
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
    except (OSError, websockets.exceptions.InvalidURI, websockets.exceptions.InvalidHandshake) as e:
        print(f"Failed to connect to the server at {uri}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Run the LLM client.")
    parser.add_argument('--server-ip', default='127.0.0.1', help='IP address of the server to connect to')
    args = parser.parse_args()

    asyncio.run(run_llm_client(args.server_ip))

if __name__ == "__main__":
    main()