import threading
import websockets
import asyncio
import socket

from controller.web import init_app
from drone.tello import tello, tello_connect_if_not
from drone.state import connected_clients

command = ''
is_flying = False


def get_connected_clients() -> set:
    return connected_clients


def flythread():
    global command

    print("[fly] Connecting to tello...")

    tello_connect_if_not()

    tello.takeoff()
    tello.move_forward(100)

    try:
        print('[fly] Waiting command')
        while True:
            if command == '':
                continue

            print('Command: ', command)
            if command == 'stop':
                print('stopping...')
                tello.send_command_with_return('stop')
                break  # exit loop after stop command

    except Exception as e:
        print(f"[fly] Exception in flythread: {e}")
    finally:
        tello.land()
        pass


async def handler(websocket: websockets.WebSocketServerProtocol, path):
    global command
    connected_clients.add(websocket)
    print("[main] New connection: ", websocket.id)
    try:
        while True:
            print('[main]', connected_clients)
            data = await websocket.recv()
            reply = f"Data received: {data}"
            print(reply)
            command = data
            await websocket.send(reply)

    except websockets.ConnectionClosed as e:
        print(f"Connection closed: {e}")
    except Exception as e:
        print(e)
    finally:
        connected_clients.remove(websocket)


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.254.254.254', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


async def main():
    server = await websockets.serve(handler, host="0.0.0.0", port=8765)

    print("Server started at:")
    local_ip = get_local_ip()
    print(f"Server started at {local_ip}:8765 and is accessible from local network devices")
    for sock in server.sockets:
        host, port = sock.getsockname()[:2]
        print(f"Host: {host}, Port: {port}")
    await server.wait_closed()


if __name__ == '__main__':
    fly_thread = threading.Thread(target=flythread, daemon=True)

    web_thread = threading.Thread(target=init_app, daemon=True)

    web_thread.start()

    asyncio.run(main())
