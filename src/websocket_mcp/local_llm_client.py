import asyncio
import websockets
from .mcp_client import MCPClient, websocket_transport_client

async def run_llm_client():
    uri = "ws://localhost:8766"  # The server running local_llm_server.py
    client = MCPClient("llm-client", "1.0.0", capabilities={"llm": True})
    
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

            # Optionally, send a shutdown request to gracefully end the session.
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

def main():
    asyncio.run(run_llm_client())

if __name__ == "__main__":
    main()
