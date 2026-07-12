package net.llm.autologin.core;

import java.nio.file.Files;
import java.nio.file.Path;

public final class MinecraftDirs {

    private MinecraftDirs() {
    }

    public static Path resolveGameDir() {
        String custom = System.getenv("MINECRAFT_DIR");
        if (custom != null && !custom.isBlank()) {
            return Path.of(custom);
        }

        Path fromUserDir = fromUserDir();
        if (fromUserDir != null) {
            return fromUserDir;
        }

        String appData = System.getenv("APPDATA");
        if (appData != null && !appData.isBlank()) {
            return Path.of(appData, ".minecraft");
        }

        return Path.of(".");
    }

    public static Path resolveAutologinConfigDir() {
        return resolveGameDir().resolve("config").resolve("autologin");
    }

    private static Path fromUserDir() {
        String userDir = System.getProperty("user.dir");
        if (userDir == null || userDir.isBlank()) {
            return null;
        }

        Path dir = Path.of(userDir);
        if (looksLikeGameDir(dir)) {
            return dir;
        }

        Path parent = dir.getParent();
        if (parent != null && looksLikeGameDir(parent)) {
            return parent;
        }

        return dir;
    }

    private static boolean looksLikeGameDir(Path dir) {
        return Files.isDirectory(dir.resolve("logs"))
            || Files.isDirectory(dir.resolve("config"))
            || Files.isDirectory(dir.resolve("labymod-neo"));
    }
}
