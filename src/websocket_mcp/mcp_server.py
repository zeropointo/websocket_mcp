import asyncio
import json
import anyio
import websockets
from contextlib import asynccontextmanager

JSON_RPC_VERSION = "2.0"

# Standard JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

def create_error_response(id, code, message, data=None):
    return {
        "jsonrpc": JSON_RPC_VERSION,
        "id": id,
        "error": {
            "code": code,
            "message": message,
            "data": data,
        }
    }

def create_response(id, result):
    return {
        "jsonrpc": JSON_RPC_VERSION,
        "id": id,
        "result": result,
    }

class MCPServer:
    def __init__(self, name, version, capabilities=None):
        self.name = name
        self.version = version
        self.capabilities = capabilities or {}
        self.request_handlers = {}      # method -> async callable
        self.notification_handlers = {} # method -> async callable
        self.send = None                # Set once the transport is connected
        self.shutdown_event = asyncio.Event()

    def register_request_handler(self, method, handler):
        self.request_handlers[method] = handler

    def register_notification_handler(self, method, handler):
        self.notification_handlers[method] = handler

    async def send_message(self, message):
        if self.send:
            await self.send(message)

    async def receive(self, message):
        """
        Process an incoming JSON-RPC message.
        
        Recognizes built-in methods:
         • "initialize": Returns server identity and capabilities.
         • "shutdown": Returns a response and triggers shutdown.
        
        For other requests, it dispatches to a registered handler.
        For notifications (without "id") it calls any registered handler.
        """
        if not isinstance(message, dict):
            return
        if message.get("jsonrpc") != JSON_RPC_VERSION:
            # Optionally reply with an error for unsupported JSON-RPC version.
            return

        # If "method" is present, it's a request or notification.
        if "method" in message:
            method = message["method"]
            req_id = message.get("id")
            params = message.get("params", {})

            # Built-in initialization
            if method == "initialize":
                result = {
                    "serverName": self.name,
                    "serverVersion": self.version,
                    "capabilities": self.capabilities,
                }
                response = create_response(req_id, result)
                await self.send_message(response)
                return

            # Built-in shutdown: reply and signal termination.
            if method == "shutdown":
                response = create_response(req_id, {"message": "Server shutting down"})
                await self.send_message(response)
                self.shutdown_event.set()
                return

            # Process user-defined request handlers.
            if req_id is not None:
                handler = self.request_handlers.get(method)
                if handler:
                    try:
                        result = await handler(params)
                        response = create_response(req_id, result)
                        await self.send_message(response)
                    except Exception as e:
                        error_response = create_error_response(req_id, INTERNAL_ERROR, str(e))
                        await self.send_message(error_response)
                else:
                    error_response = create_error_response(req_id, METHOD_NOT_FOUND, f"Method '{method}' not found")
                    await self.send_message(error_response)
            else:
                # This is a notification (no "id")
                handler = self.notification_handlers.get(method)
                if handler:
                    try:
                        await handler(params)
                    except Exception:
                        pass  # Optionally log error.
                else:
                    # No handler registered; ignore.
                    pass
        # Responses (with "result" or "error") are not expected on the server side.

    async def wait_closed(self):
        await self.shutdown_event.wait()

@asynccontextmanager
async def websocket_transport_server(websocket):
    """
    Wrap an accepted WebSocket connection in a transport context.
    
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
                        # Optionally send a parse error response.
                        continue
                    await queue.put(message)
            except Exception:
                pass  # Connection closed or error.

        tg.start_soon(receive_loop)

        async def send_message(message):
            payload = json.dumps(message)
            await websocket.send(payload)

        try:
            yield send_message, queue
        finally:
            tg.cancel_scope.cancel()
            await websocket.close()

async def websocket_server_handler(websocket):
    """
    Wraps an accepted WebSocket connection in an MCP server.
    The 'path' parameter has been removed as it's no longer used in newer websockets versions.
    """
    server = MCPServer("example-server", "1.0.0", capabilities={"streaming": True})
    
    # Handler for "list_resources" requests.
    async def list_resources_handler(params):
        return [{"uri": "example://resource", "name": "Example Resource"}]
    server.register_request_handler("list_resources", list_resources_handler)
    
    # Handler for "stream_data" requests: sends multiple notifications simulating streaming.
    async def stream_data_handler(params):
        stream_id = params.get("stream_id", "default")
        for i in range(5):
            chunk_message = {
                "jsonrpc": JSON_RPC_VERSION,
                "method": "stream_data_chunk",
                "params": {"stream_id": stream_id, "chunk": f"Data chunk {i+1}"}
            }
            await server.send_message(chunk_message)
            await asyncio.sleep(1)
        complete_message = {
            "jsonrpc": JSON_RPC_VERSION,
            "method": "stream_complete",
            "params": {"stream_id": stream_id, "message": "Stream complete"}
        }
        await server.send_message(complete_message)
        return {"status": "streaming started"}
    server.register_request_handler("stream_data", stream_data_handler)

    # Handler for "initialized" notifications from the client.
    async def initialized_notification_handler(params):
        print("Client completed initialization:", params)
    server.register_notification_handler("initialized", initialized_notification_handler)

    async with websocket_transport_server(websocket) as (send_func, message_queue):
        server.send = send_func
        # Loop processing incoming messages until a shutdown is requested.
        while not server.shutdown_event.is_set():
            try:
                message = await asyncio.wait_for(message_queue.get(), timeout=1)
                await server.receive(message)
            except asyncio.TimeoutError:
                continue

async def start_mcp_server():
    async with websockets.serve(websocket_server_handler, "", 8765):  # Bind to all interfaces
        print("MCP WebSocket Server running on ws://0.0.0.0:8765")
        # Wait indefinitely until shutdown.
        await asyncio.Future()

def main():
    asyncio.run(start_mcp_server())

if __name__ == "__main__":
    main()
