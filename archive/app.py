from http.server import HTTPServer, SimpleHTTPRequestHandler


def create_server(host: str = "127.0.0.1", port: int = 8080) -> HTTPServer:
    """Create the local web server without starting it."""
    return HTTPServer((host, port), SimpleHTTPRequestHandler)


def run_server() -> None:
    server = create_server()
    print("Running at http://localhost:8080")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    run_server()
