package net.llm.autologin.core;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

public record LoginConfig(String host, int port) {
    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    public static LoginConfig load() {
        Path configPath = resolveConfigPath();
        if (!Files.exists(configPath)) {
            Path legacyPath = resolveLegacyConfigPath();
            if (Files.exists(legacyPath)) {
                configPath = legacyPath;
            }
        }

        if (Files.exists(configPath)) {
            try {
                String json = Files.readString(configPath);
                LoginConfig config = GSON.fromJson(json, LoginConfig.class);
                if (config != null && config.host() != null && config.port() > 0) {
                    return config;
                }
            } catch (IOException ignored) {
            }
        }

        LoginConfig defaults = new LoginConfig("127.0.0.1", 47923);
        try {
            Files.createDirectories(configPath.getParent());
            Files.writeString(configPath, GSON.toJson(defaults));
        } catch (IOException ignored) {
        }
        return defaults;
    }

    public static Path resolveConfigDir() {
        return MinecraftDirs.resolveAutologinConfigDir();
    }

    public static Path resolveAccountsPath() {
        return resolveConfigDir().resolve("accounts.json");
    }

    private static Path resolveConfigPath() {
        return resolveConfigDir().resolve("autologin.json");
    }

    private static Path resolveLegacyConfigPath() {
        Path gameDir = MinecraftDirs.resolveGameDir();
        Path direct = gameDir.resolve("config").resolve("autologin.json");
        if (Files.exists(direct)) {
            return direct;
        }

        String appData = System.getenv("APPDATA");
        if (appData != null && !appData.isBlank()) {
            return Path.of(appData, ".minecraft", "config", "autologin.json");
        }

        return Path.of("config", "autologin.json");
    }
}
