package net.llm.autologin.v1_20_1;

import java.util.Locale;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import net.labymod.api.models.Implements;
import net.llm.autologin.api.LoginBridge;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientPacketListener;
import net.minecraft.client.multiplayer.ServerData;
import net.minecraft.network.Connection;

@Implements(LoginBridge.class)
public class VersionedLoginBridge implements LoginBridge {

    private static final long ACTION_TIMEOUT_SECONDS = 5;

    @Override
    public String getLocalNickname() {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft == null || minecraft.player == null) {
            return null;
        }
        return minecraft.player.getGameProfile().getName();
    }

    @Override
    public boolean isInWorld() {
        Minecraft minecraft = Minecraft.getInstance();
        return minecraft != null && minecraft.player != null && minecraft.level != null;
    }

    @Override
    public String getServerAddress() {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft == null) {
            return "";
        }

        StringBuilder address = new StringBuilder();
        ServerData current = minecraft.getCurrentServer();
        if (current != null) {
            if (current.ip != null && !current.ip.isBlank()) {
                address.append(current.ip);
            }
            if (current.name != null && !current.name.isBlank()) {
                if (address.length() > 0) {
                    address.append(' ');
                }
                address.append(current.name);
            }
        }

        ClientPacketListener listener = minecraft.getConnection();
        if (listener != null) {
            Connection connection = listener.getConnection();
            if (connection != null && connection.getRemoteAddress() != null) {
                if (address.length() > 0) {
                    address.append(' ');
                }
                address.append(connection.getRemoteAddress().toString());
            }
        }

        return address.toString();
    }

    @Override
    public void sendChat(String message) throws Exception {
        runOnClientThread(() -> {
            Minecraft minecraft = Minecraft.getInstance();
            if (minecraft.player == null || minecraft.player.connection == null) {
                throw new IllegalStateException("not_in_world");
            }
            if (message.startsWith("/")) {
                minecraft.player.connection.sendCommand(message.substring(1));
            } else {
                minecraft.player.connection.sendChat(message);
            }
        });
    }

    private void runOnClientThread(ThrowingRunnable action) throws Exception {
        runOnClientThread(() -> {
            action.run();
            return null;
        });
    }

    private <T> T runOnClientThread(ThrowingSupplier<T> action) throws Exception {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft == null) {
            throw new IllegalStateException("minecraft_unavailable");
        }

        if (minecraft.isSameThread()) {
            return action.get();
        }

        CompletableFuture<T> future = new CompletableFuture<>();
        minecraft.execute(() -> {
            try {
                future.complete(action.get());
            } catch (Exception e) {
                future.completeExceptionally(e);
            }
        });

        try {
            return future.get(ACTION_TIMEOUT_SECONDS, TimeUnit.SECONDS);
        } catch (TimeoutException e) {
            throw new IllegalStateException("client_action_timeout");
        }
    }

    @FunctionalInterface
    private interface ThrowingSupplier<T> {
        T get() throws Exception;
    }

    @FunctionalInterface
    private interface ThrowingRunnable {
        void run() throws Exception;
    }
}
