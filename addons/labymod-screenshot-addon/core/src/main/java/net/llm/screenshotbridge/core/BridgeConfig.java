package net.llm.screenshotbridge.core;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

public record BridgeConfig(String host, int port) {
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    public static BridgeConfig load() {
        Path configPath = resolveConfigPath();

        if (Files.exists(configPath)) {
            try {
                String json = Files.readString(configPath);
                BridgeConfig config = GSON.fromJson(json, BridgeConfig.class);
                if (config != null && config.host() != null && config.port() > 0) {
                    return config;
                }
            } catch (IOException ignored) {
            }
        }

        BridgeConfig defaults = new BridgeConfig("127.0.0.1", 47823);
        try {
            Files.createDirectories(configPath.getParent());
            Files.writeString(configPath, GSON.toJson(defaults));
        } catch (IOException ignored) {
        }
        return defaults;
    }

    private static Path resolveConfigPath() {
        String gameDir = System.getProperty("user.dir");
        if (gameDir != null && !gameDir.isBlank()) {
            return Path.of(gameDir, "config", "screenshot-bridge.json");
        }

        String appData = System.getenv("APPDATA");
        if (appData != null && !appData.isBlank()) {
            return Path.of(appData, ".minecraft", "config", "screenshot-bridge.json");
        }

        return Path.of("config", "screenshot-bridge.json");
    }
}
