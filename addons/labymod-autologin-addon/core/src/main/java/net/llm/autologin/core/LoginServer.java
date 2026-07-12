package net.llm.autologin.core;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.function.Function;
import java.util.function.IntConsumer;

public class LoginServer {
    private static final int PORT_FALLBACK_RANGE = 10;

    private final LoginConfig config;
    private final Function<String, String> requestHandler;
    private final IntConsumer onBound;
    private final Thread acceptThread;
    private volatile ServerSocket serverSocket;
    private volatile int boundPort = -1;

    public LoginServer(
        LoginConfig config,
        Function<String, String> requestHandler,
        IntConsumer onBound
    ) {
        this.config = config;
        this.requestHandler = requestHandler;
        this.onBound = onBound;
        this.acceptThread = new Thread(this::acceptLoop, "autologin-server");
        this.acceptThread.setDaemon(true);
    }

    public int boundPort() {
        return this.boundPort;
    }

    public void start() {
        acceptThread.start();
    }

    public void stop() {
        try {
            if (serverSocket != null && !serverSocket.isClosed()) {
                serverSocket.close();
            }
        } catch (IOException ignored) {
        }
        acceptThread.interrupt();
    }

    private void acceptLoop() {
        String host = this.config.host();
        int basePort = this.config.port();

        for (int port = basePort; port < basePort + PORT_FALLBACK_RANGE; port++) {
            try {
                this.serverSocket = new ServerSocket(
                    port,
                    8,
                    InetAddress.getByName(host)
                );
                this.boundPort = port;
                if (this.onBound != null) {
                    this.onBound.accept(port);
                }
                break;
            } catch (IOException ignored) {
            }
        }

        if (this.serverSocket == null || this.boundPort < 0) {
            return;
        }

        while (!Thread.currentThread().isInterrupted()) {
            try (Socket socket = this.serverSocket.accept()) {
                socket.setSoTimeout(30_000);
                handleClient(socket);
            } catch (IOException ignored) {
            }
        }
    }

    private void handleClient(Socket socket) throws IOException {
        BufferedReader reader = new BufferedReader(
            new InputStreamReader(socket.getInputStream(), StandardCharsets.UTF_8)
        );
        BufferedWriter writer = new BufferedWriter(
            new OutputStreamWriter(socket.getOutputStream(), StandardCharsets.UTF_8)
        );

        String requestLine = reader.readLine();
        if (requestLine == null || requestLine.isBlank()) {
            writer.write("{\"ok\":false,\"error\":\"empty_request\"}");
            writer.write('\n');
            writer.flush();
            return;
        }

        String response = requestHandler.apply(requestLine);
        writer.write(response);
        writer.write('\n');
        writer.flush();
    }
}
