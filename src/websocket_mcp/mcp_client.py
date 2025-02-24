import argparse
import asyncio
import json
import anyio
import websockets
from contextlib import asynccontextmanager

JSON_RPC_VERSION = "2.0"

def create_request(method, params, id):
    return {
        "jsonrpc": JSON_RPC_VERSION,
        "id": id,
        "method": method,
        "params": params,
    }

def create_notification(method, params):
    return {
        "jsonrpc": JSON_RPC_VERSION,
        "method": method,
        "params": params,
    }

class MCPClient:
    def __init__(self, name, version, capabilities=None):
        self.name = name
        self.version = version
        self.capabilities = capabilities or {}
        self.send = None  # Set once the transport is connected
        self.pending = {}  # Map request id to asyncio.Future
        self.next_id = 1

    async def connect(self, send_func):
        self.send = send_func
        # --- Initialization Handshake ---
        init_id = self.next_id
        self.next_id += 1
        init_request = create_request("initialize", {
            "clientName": self.name,
            "clientVersion": self.version,
            "capabilities": self.capabilities
        }, init_id)
        await self.send(init_request)
        fut = asyncio.get_event_loop().create_future()
        self.pending[init_id] = fut
        init_response = await fut
        print("Initialization response from server:", init_response)
        # Send an "initialized" notification.
        init_notification = create_notification("initialized", {"status": "ok"})
        await self.send(init_notification)

    async def request(self, method, params):
        req_id = self.next_id
        self.next_id += 1
        req_msg = create_request(method, params, req_id)
        fut = asyncio.get_event_loop().create_future()
        self.pending[req_id] = fut
        await self.send(req_msg)
        return await fut

    async def notify(self, method, params):
        note_msg = create_notification(method, params)
        await self.send(note_msg)

    async def receive(self, message):
        """
        Process an incoming JSON-RPC message.
        
        Distinguishes between responses (with an "id") and notifications.
        """
        if not isinstance(message, dict):
            return
        if message.get("jsonrpc") != JSON_RPC_VERSION:
            return
        if "id" in message:
            # This is a response to a previous request.
            req_id = message["id"]
            if req_id in self.pending:
                fut = self.pending.pop(req_id)
                if "result" in message:
                    fut.set_result(message["result"])
                elif "error" in message:
                    fut.set_exception(Exception(message["error"]))
        elif "method" in message:
            # Process server notifications.
            method = message["method"]
            params = message.get("params", {})
            if method == "stream_data_chunk":
                print(f"Stream chunk received: {params}")
            elif method == "stream_complete":
                print(f"Stream complete: {params}")
            # Additional notifications can be handled here.

@asynccontextmanager
async def websocket_transport_client(websocket):
    """
    Wrap a WebSocket connection into a transport context.
    
    Yields:
      send_func: Function to send JSON-RPC messages.
      queue: An asyncio.Queue of received messages.
    """
    async with anyio.create_task_group() as tg:
        queue = asyncio.Queue()

        async def receive_loop():
            try:
                while True:
                    message_text = await websocket.recv()
                    try:
                        message = json.loads(message_text)
                    except json.JSONDecodeError:
                        continue
                    await queue.put(message)
            except Exception:
                pass

        tg.start_soon(receive_loop)

        async def send_message(message):
            payload = json.dumps(message)
            await websocket.send(payload)

        try:
            yield send_message, queue
        finally:
            tg.cancel_scope.cancel()
            await websocket.close()

async def websocket_client(uri):
    async with websockets.connect(uri) as websocket:
        client = MCPClient("example-client", "1.0.0", capabilities={"streaming": True})
        async with websocket_transport_client(websocket) as (send_func, message_queue):
            client.send = send_func

            # Background task to process incoming messages.
            async def process_messages():
                while True:
                    message = await message_queue.get()
                    await client.receive(message)
            task = asyncio.create_task(process_messages())

            # --- Initialization Handshake ---
            await client.connect(send_func)

            # Make a request for listing resources.
            try:
                resources = await client.request("list_resources", {})
                print("List resources response:", resources)
            except Exception as e:
                print("Error in list_resources request:", e)

            # Make a request to start streaming data.
            try:
                stream_resp = await client.request("stream_data", {"stream_id": "abc123"})
                print("Stream data request response:", stream_resp)
            except Exception as e:
                print("Error in stream_data request:", e)

            # Allow time for stream notifications to arrive.
            await asyncio.sleep(7)

            # Initiate graceful shutdown.
            try:
                shutdown_resp = await client.request("shutdown", {})
                print("Shutdown response:", shutdown_resp)
            except Exception as e:
                print("Error during shutdown:", e)

            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

async def start_mcp_client(server_ip):
    uri = f"ws://{server_ip}:8765"
    print("Connecting to MCP server at", uri)
    await websocket_client(uri)

def main():
    parser = argparse.ArgumentParser(description="Run the MCP client.")
    parser.add_argument('--server-ip', default='127.0.0.1', help='IP address of the server to connect to')
    args = parser.parse_args()

    asyncio.run(start_mcp_client(args.server_ip))

if __name__ == "__main__":
    main()
